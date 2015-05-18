#!/usr/bin/python

# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2015 Alexandru Damian for Intel Corp.
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.


# This is the main test execution controller. It is designed to be run
# manually from the command line, or to be called from a different program
# that schedules test execution.
#
# Execute   runner.py -h   for help.



from __future__ import print_function
import optparse
import sys, os
import unittest, inspect, importlib
import logging, pprint, json

from shellutils import *

import config

# we also log to a file, in addition to console, because our output is important
__log_file_name =os.path.join(os.path.dirname(__file__),"log/tts_%d.log" % config.OWN_PID)
mkdirhier(os.path.dirname(__log_file_name))
__log_file = open(__log_file_name, "w")
__file_handler = logging.StreamHandler(__log_file)
__file_handler.setFormatter(logging.Formatter("%(asctime)s %(levelname)s: %(message)s"))

config.logger.addHandler(__file_handler)


# set up log directory
try:
    if not os.path.exists(config.LOGDIR):
        os.mkdir(config.LOGDIR)
    else:
        if not os.path.isdir(config.LOGDIR):
            raise Exception("Expected log dir '%s' is not actually a directory." % config.LOGDIR)
except OSError as e:
    raise e

# creates the under-test-branch as a separate directory
def set_up_test_branch(settings, branch_name):
    testdir = "%s/%s.%d" % (settings['workdir'], config.TEST_DIR_NAME,  config.OWN_PID)

    # creates the host dir
    if os.path.exists(testdir):
        raise Exception("Test dir '%s'is already there, aborting" % testdir)
    os.mkdir(testdir)

    # copies over the .git from the localclone
    run_shell_cmd("cp -a '%s'/.git '%s'" % (settings['localclone'], testdir))

    # add the remote if it doesn't exist
    crt_remotes = run_shell_cmd("git remote -v", cwd = testdir)
    remotes = [word for line in crt_remotes.split("\n") for word in line.split()]
    if not config.CONTRIB_REPO in remotes:
        remote_name = "tts_contrib"
        run_shell_cmd("git remote add %s %s" % (remote_name, config.CONTRIB_REPO), cwd = testdir)
    else:
        remote_name = remotes[remotes.index(config.CONTRIB_REPO) - 1]

    # do the fetch
    run_shell_cmd("git fetch %s -p" % remote_name, cwd=testdir)

    # do the checkout
    run_shell_cmd("git checkout origin/master && git branch -D %s; git checkout %s/%s -b %s && git reset --hard" % (branch_name,remote_name,branch_name,branch_name), cwd=testdir)

    return testdir


def __search_for_tests():
    # we find all classes that can run, and run them
    tests = []
    for dir_name, dirs_list, files_list in os.walk(os.path.dirname(os.path.abspath(__file__))):
        for f in [f[:-3] for f in files_list if f.endswith(".py") and not f.startswith("__init__")]:
            config.logger.debug("Inspecting module %s", f)
            current_module = importlib.import_module(f)
            crtclass_names = vars(current_module)
            for v in crtclass_names:
                t = crtclass_names[v]
                if isinstance(t, type(unittest.TestCase)) and issubclass(t, unittest.TestCase):
                    tests.append((f,v))
        break
    return tests


# boilerplate to self discover tests and run them
def execute_tests(dir_under_test, testname):

    if testname is not None and "." in testname:
        tests = []
        tests.append(tuple(testname.split(".", 2)))
    else:
        tests = __search_for_tests()

    # let's move to the directory under test
    crt_dir = os.getcwd()
    os.chdir(dir_under_test)

    # execute each module
    try:
        config.logger.debug("Discovered test clases: %s" % pprint.pformat(tests))
        suite = unittest.TestSuite()
        loader = unittest.TestLoader()
        result = unittest.TestResult()
        for m,t in tests:
            suite.addTest(loader.loadTestsFromName("%s.%s" % (m,t)))
        config.logger.info("Running %d test(s)", suite.countTestCases())
        suite.run(result)

        if len(result.errors) > 0:
            map(lambda x: config.logger.error("Exception on test: %s" % pprint.pformat(x)), result.errors)

        if len(result.failures) > 0:
            map(lambda x: config.logger.error("Failed test: %s:\n%s\n" % (pprint.pformat(x[0]), "\n".join(["--  %s" % x for x in eval(pprint.pformat(x[1])).split("\n")]))), result.failures)

        config.logger.info("Test results: %d ran, %d errors, %d failures"  % (result.testsRun, len(result.errors), len(result.failures)))

    except Exception as e:
        import traceback
        config.logger.error("Exception while running test. Tracedump: \n%s", traceback.format_exc(e))
    finally:
        os.chdir(crt_dir)
    return len(result.failures)

# verify that we had a branch-under-test name as parameter
def validate_args():
    from optparse import OptionParser
    parser = OptionParser(usage="usage: %prog [options] branch_under_test")

    parser.add_option("-t", "--test-dir", dest="testdir", default=None, help="Use specified directory to run tests, inhibits the checkout.")
    parser.add_option("-s", "--single", dest="singletest", default=None, help="Run only the specified test")

    (options, args) = parser.parse_args()
    if len(args) < 1:
        raise Exception("Please specify the branch to run on. Use option '-h' when in doubt.")
    return (options, args)




# load the configuration options
def read_settings():
    if not os.path.exists(config.SETTINGS_FILE) or not os.path.isfile(config.SETTINGS_FILE):
        raise Exception("Config file '%s' cannot be openend" % config.SETTINGS_FILE);
    return json.loads(open(config.SETTINGS_FILE, "r").read())


# cleanup !
def clean_up(testdir):
    # TODO: delete the test dir
    run_shell_cmd("rm -rf -- '%s'" % testdir)
    pass

if __name__ == "__main__":
    (options, args) = validate_args()

    settings = read_settings()
    need_cleanup = False

    testdir = None
    no_failures = 1
    try:
        if options.testdir is not None and os.path.exists(options.testdir):
            testdir = os.path.abspath(options.testdir)
            config.logger.info("No checkout, using %s" % testdir)
        else:
            need_cleanup = True
            testdir = set_up_test_branch(settings, args[0]) # we expect a branch name as first argument

        config.testdir = testdir    # we let tests know where to run
        no_failures = execute_tests(testdir, options.singletest)

    except ShellCmdException as e :
        import traceback
        config.logger.error("Error while setting up testing. Traceback: \n%s" % traceback.format_exc(e))
    finally:
        if need_cleanup and testdir is not None:
            clean_up(testdir)

    sys.exit(no_failures)
