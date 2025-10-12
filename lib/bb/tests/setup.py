#
# Copyright BitBake Contributors
#
# SPDX-License-Identifier: GPL-2.0-only
#

from bb.tests.fetch import FetcherTest
import json

class BitbakeSetupTest(FetcherTest):
    def setUp(self):
        super(BitbakeSetupTest, self).setUp()

        self.registrypath = os.path.join(self.tempdir, "bitbake-setup-configurations")

        os.makedirs(self.registrypath)
        self.git_init(cwd=self.registrypath)
        self.git('commit --allow-empty -m "Initial commit"', cwd=self.registrypath)

        self.testrepopath = os.path.join(self.tempdir, "test-repo")
        os.makedirs(self.testrepopath)
        self.git_init(cwd=self.testrepopath)
        self.git('commit --allow-empty -m "Initial commit"', cwd=self.testrepopath)

        oeinitbuildenv = """BBPATH=$1
export BBPATH
PATH={}:$PATH
""".format(os.path.join(self.testrepopath, 'scripts'))
        self.add_file_to_testrepo('oe-init-build-env',oeinitbuildenv, script=True)

        oesetupbuild = """#!/usr/bin/env python3
import getopt
import sys
import os
import shutil
opts, args = getopt.getopt(sys.argv[2:], "c:b:", ["no-shell"])
for option, value in opts:
    if option == '-c':
        template = value
    if option == '-b':
        builddir = value
confdir = os.path.join(builddir, 'conf')
os.makedirs(confdir, exist_ok=True)
with open(os.path.join(confdir, 'conf-summary.txt'), 'w') as f:
    f.write(template)
shutil.copy(os.path.join(os.path.dirname(__file__), 'test-repo/test-file'), confdir)
with open(os.path.join(builddir, 'init-build-env'), 'w') as f:
    f.write("BBPATH={}\\nexport BBPATH\\nPATH={}:$PATH".format(builddir, os.path.join(os.path.dirname(__file__), 'test-repo/scripts')))
"""
        self.add_file_to_testrepo('scripts/oe-setup-build', oesetupbuild, script=True)

        installbuildtools = """#!/usr/bin/env python3
import getopt
import sys
import os

opts, args = getopt.getopt(sys.argv[1:], "d:", ["downloads-directory="])
for option, value in opts:
    if option == '-d':
        installdir = value

print("Buildtools installed into {}".format(installdir))
os.makedirs(installdir)
"""
        self.add_file_to_testrepo('scripts/install-buildtools', installbuildtools, script=True)

        bitbakeconfigbuild = """#!/usr/bin/env python3
import os
import sys
confdir = os.path.join(os.environ['BBPATH'], 'conf')
fragment = sys.argv[2]
with open(os.path.join(confdir, fragment), 'w') as f:
    f.write('')
"""
        self.add_file_to_testrepo('scripts/bitbake-config-build', bitbakeconfigbuild, script=True)

        sometargetexecutable_template = """#!/usr/bin/env python3
import os
print("This is {}")
print("BBPATH is {{}}".format(os.environ["BBPATH"]))
"""
        for e_name in ("some-target-executable-1", "some-target-executable-2"):
            sometargetexecutable = sometargetexecutable_template.format(e_name)
            self.add_file_to_testrepo('scripts/{}'.format(e_name), sometargetexecutable, script=True)

    def runbbsetup(self, cmd):
        bbsetup = os.path.abspath(os.path.dirname(__file__) +  "/../../../bin/bitbake-setup")
        return bb.process.run("{} --global-settings {} {}".format(bbsetup, os.path.join(self.tempdir, 'global-config'), cmd))

    def add_json_config_to_registry(self, name, rev, branch):
        config = """
{
    "sources": {
        "test-repo": {
            "git-remote": {
                "remotes": {
                    "origin": {
                        "uri": "file://%s"
                    }
                },
                "branch": "%s",
                "rev": "%s"
            },
            "path": "test-repo"
        }
    },
    "description": "Test configuration",
    "bitbake-setup": {
        "configurations": [
            {
                "name": "gadget",
                "description": "Gadget build configuration",
                "oe-template": "test-configuration-gadget",
                "oe-fragments": ["test-fragment-1"]
            },
            {
                "name": "gizmo",
                "description": "Gizmo build configuration",
                "oe-template": "test-configuration-gizmo",
                "oe-fragments": ["test-fragment-2"]
            },
            {
                "name": "gizmo-env-passthrough",
                "description": "Gizmo build configuration with environment-passthrough",
                "bb-layers": ["layerC","layerD/meta-layer"],
                "oe-fragments": ["test-fragment-1"],
                "bb-env-passthrough-additions": [
                    "BUILD_ID",
                    "BUILD_DATE",
                    "BUILD_SERVER"
                ]
            },
            {
                "name": "gizmo-no-fragment",
                "description": "Gizmo no-fragment template-only build configuration",
                "oe-template": "test-configuration-gizmo"
            },
            {
                "name": "gadget-notemplate",
                "description": "Gadget notemplate build configuration",
                "bb-layers": ["layerA","layerB/meta-layer"],
                "oe-fragments": ["test-fragment-1"]
            },
            {
                "name": "gizmo-notemplate",
                "description": "Gizmo notemplate build configuration",
                "bb-layers": ["layerC","layerD/meta-layer"],
                "oe-fragments": ["test-fragment-2"]
            },
            {
                "name": "gizmo-notemplate-with-thisdir",
                "description": "Gizmo notemplate build configuration using THISDIR",
                "bb-layers": ["layerC","layerD/meta-layer","{THISDIR}/layerE/meta-layer"],
                "oe-fragments": ["test-fragment-2"]
            }
        ]
    },
    "version": "1.0"
}
""" % (self.testrepopath, branch, rev)
        os.makedirs(os.path.join(self.registrypath, os.path.dirname(name)), exist_ok=True)
        with open(os.path.join(self.registrypath, name), 'w') as f:
            f.write(config)
        self.git('add {}'.format(name), cwd=self.registrypath)
        self.git('commit -m "Adding {}"'.format(name), cwd=self.registrypath)
        return json.loads(config)

    def add_file_to_testrepo(self, name, content, script=False):
        fullname = os.path.join(self.testrepopath, name)
        os.makedirs(os.path.join(self.testrepopath, os.path.dirname(name)), exist_ok=True)
        with open(fullname, 'w') as f:
            f.write(content)
        if script:
            import stat
            st = os.stat(fullname)
            os.chmod(fullname, st.st_mode | stat.S_IEXEC)
        self.git('add {}'.format(name), cwd=self.testrepopath)
        self.git('commit -m "Adding {}"'.format(name), cwd=self.testrepopath)

    def check_builddir_files(self, buildpath, test_file_content, json_config):
        with open(os.path.join(buildpath, 'layers', 'test-repo', 'test-file')) as f:
            self.assertEqual(f.read(), test_file_content)
        bitbake_config = json_config["bitbake-config"]
        bb_build_path = os.path.join(buildpath, 'build')
        bb_conf_path = os.path.join(bb_build_path, 'conf')
        self.assertTrue(os.path.exists(os.path.join(bb_build_path, 'init-build-env')))

        if "oe-template" in bitbake_config:
            with open(os.path.join(bb_conf_path, 'conf-summary.txt')) as f:
                self.assertEqual(f.read(), bitbake_config["oe-template"])
            with open(os.path.join(bb_conf_path, 'test-file')) as f:
                self.assertEqual(f.read(), test_file_content)
        else:
            with open(os.path.join(bb_conf_path, 'conf-summary.txt')) as f:
                self.assertIn(bitbake_config["description"], f.read())
            with open(os.path.join(bb_conf_path, 'bblayers.conf')) as f:
                bblayers = f.read()
                for l in bitbake_config["bb-layers"]:
                    if l.startswith('{THISDIR}/'):
                        thisdir_layer = os.path.join(
                            os.path.dirname(json_config["path"]),
                            l.removeprefix("{THISDIR}/"),
                        )
                        self.assertIn(thisdir_layer, bblayers)
                    else:
                        self.assertIn(os.path.join(buildpath, "layers", l), bblayers)

        if 'oe-fragment' in bitbake_config.keys():
            for f in bitbake_config["oe-fragments"]:
                self.assertTrue(os.path.exists(os.path.join(bb_conf_path, f)))

        if 'bb-environment-passthrough' in bitbake_config.keys():
            with open(os.path.join(bb_build_path, 'init-build-env'), 'r') as f:
                init_build_env = f.read()
            self.assertTrue('BB_ENV_PASSTHROUGH_ADDITIONS' in init_build_env)
            self.assertTrue('BUILD_ID' in init_build_env)
            self.assertTrue('BUILD_DATE' in init_build_env)
            self.assertTrue('BUILD_SERVER' in init_build_env)
            # a more throrough test could be to initialize a bitbake build-env, export FOO to the shell environment, set the env-passthrough on it and finally check against 'bitbake-getvar FOO'


    def test_setup(self):
        # unset BBPATH to ensure tests run in isolation from the existing bitbake environment
        import os
        if 'BBPATH' in os.environ:
            del os.environ['BBPATH']

        # check that no arguments works
        self.runbbsetup("")

        # check that --help works
        self.runbbsetup("--help")

        # set up global location for top-dir-prefix
        out = self.runbbsetup("settings set --global default top-dir-prefix {}".format(self.tempdir))
        settings_path = "{}/global-config".format(self.tempdir)
        self.assertIn(settings_path, out[0])
        self.assertIn("From section 'default' the setting 'top-dir-prefix' was changed to", out[0])
        self.assertIn("Settings written to".format(settings_path), out[0])
        out = self.runbbsetup("settings set --global default dl-dir {}".format(os.path.join(self.tempdir, 'downloads')))
        self.assertIn("From section 'default' the setting 'dl-dir' was changed to", out[0])
        self.assertIn("Settings written to".format(settings_path), out[0])

        # check that writing settings works and then adjust them to point to
        # test registry repo
        out = self.runbbsetup("settings set default registry 'git://{};protocol=file;branch=master;rev=master'".format(self.registrypath))
        settings_path = "{}/bitbake-builds/settings.conf".format(self.tempdir)
        self.assertIn(settings_path, out[0])
        self.assertIn("From section 'default' the setting 'registry' was changed to", out[0])
        self.assertIn("Settings written to".format(settings_path), out[0])

        # check that listing settings works
        out = self.runbbsetup("settings list")
        self.assertIn("default top-dir-prefix {}".format(self.tempdir), out[0])
        self.assertIn("default dl-dir {}".format(os.path.join(self.tempdir, 'downloads')), out[0])
        self.assertIn("default registry {}".format('git://{};protocol=file;branch=master;rev=master'.format(self.registrypath)), out[0])

        # check that 'list' produces correct output with no configs, one config and two configs
        out = self.runbbsetup("list")
        self.assertNotIn("test-config-1", out[0])
        self.assertNotIn("test-config-2", out[0])

        json_1 = self.add_json_config_to_registry('test-config-1.conf.json', 'master', 'master')
        out = self.runbbsetup("list")
        self.assertIn("test-config-1", out[0])
        self.assertNotIn("test-config-2", out[0])

        json_2 = self.add_json_config_to_registry('config-2/test-config-2.conf.json', 'master', 'master')
        out = self.runbbsetup("list --write-json={}".format(os.path.join(self.tempdir, "test-configs.json")))
        self.assertIn("test-config-1", out[0])
        self.assertIn("test-config-2", out[0])
        with open(os.path.join(self.tempdir, "test-configs.json")) as f:
            json_configs = json.load(f)
        self.assertIn("test-config-1", json_configs)
        self.assertIn("test-config-2", json_configs)

        # check that init/status/update work
        # (the latter two should do nothing and say that config hasn't changed)
        test_file_content = 'initial\n'
        self.add_file_to_testrepo('test-file', test_file_content)

        # test-config-1 is tested as a registry config, test-config-2 as a local file
        test_configurations = {'test-config-1': {'cmdline': 'test-config-1',
                                                 'buildconfigs':('gadget','gizmo',
                                                                 'gizmo-env-passthrough',
                                                                 'gizmo-no-fragment',
                                                                 'gadget-notemplate','gizmo-notemplate')},
                               'test-config-2': {'cmdline': os.path.join(self.registrypath,'config-2/test-config-2.conf.json'),
                                                 'buildconfigs': ('gadget','gizmo',
                                                                  'gizmo-env-passthrough',
                                                                  'gizmo-no-fragment',
                                                                  'gadget-notemplate','gizmo-notemplate',
                                                                  'gizmo-notemplate-with-thisdir')}
                               }
        for cf, v in test_configurations.items():
            for c in v['buildconfigs']:
                out = self.runbbsetup("init --non-interactive {} {}".format(v['cmdline'], c))
                buildpath = os.path.join(self.tempdir, 'bitbake-builds', '{}-{}'.format(cf, c))
                with open(os.path.join(buildpath, 'config', "config-upstream.json")) as f:
                    config_upstream = json.load(f)
                self.check_builddir_files(buildpath, test_file_content, config_upstream)
                os.environ['BBPATH'] = os.path.join(buildpath, 'build')
                out = self.runbbsetup("status")
                self.assertIn("Configuration in {} has not changed".format(buildpath), out[0])
                out = self.runbbsetup("update")
                self.assertIn("Configuration in {} has not changed".format(buildpath), out[0])

        # install buildtools
        out = self.runbbsetup("install-buildtools")
        self.assertIn("Buildtools installed into", out[0])
        self.assertTrue(os.path.exists(os.path.join(buildpath, 'buildtools')))

        # change a file in the test layer repo, make a new commit and
        # test that status/update correctly report the change and update the config
        prev_test_file_content = test_file_content
        test_file_content = 'modified\n'
        self.add_file_to_testrepo('test-file', test_file_content)
        for c in ('gadget', 'gizmo',
                  'gizmo-env-passthrough',
                  'gizmo-no-fragment',
                  'gadget-notemplate', 'gizmo-notemplate'):
            buildpath = os.path.join(self.tempdir, 'bitbake-builds', 'test-config-1-{}'.format(c))
            os.environ['BBPATH'] = os.path.join(buildpath, 'build')
            out = self.runbbsetup("status")
            self.assertIn("Layer repository file://{} checked out into {}/layers/test-repo updated revision master from".format(self.testrepopath, buildpath), out[0])
            out = self.runbbsetup("update")
            if c in ('gadget', 'gizmo'):
                self.assertIn("Existing bitbake configuration directory renamed to {}/build/conf-backup.".format(buildpath), out[0])
                self.assertIn('-{}+{}'.format(prev_test_file_content, test_file_content), out[0])
            with open(os.path.join(buildpath, 'config', "config-upstream.json")) as f:
                config_upstream = json.load(f)
            self.check_builddir_files(buildpath, test_file_content, config_upstream)

        # make a new branch in the test layer repo, change a file on that branch,
        # make a new commit, update the top level json config to refer to that branch,
        # and test that status/update correctly report the change and update the config
        prev_test_file_content = test_file_content
        test_file_content = 'modified-in-branch\n'
        branch = "another-branch"
        self.git('checkout -b {}'.format(branch), cwd=self.testrepopath)
        self.add_file_to_testrepo('test-file', test_file_content)
        json_1 = self.add_json_config_to_registry('test-config-1.conf.json', branch, branch)
        for c in ('gadget', 'gizmo',
                  'gizmo-env-passthrough',
                  'gizmo-no-fragment',
                  'gadget-notemplate', 'gizmo-notemplate'):
            buildpath = os.path.join(self.tempdir, 'bitbake-builds', 'test-config-1-{}'.format(c))
            os.environ['BBPATH'] = os.path.join(buildpath, 'build')
            out = self.runbbsetup("status")
            self.assertIn("Configuration in {} has changed:".format(buildpath), out[0])
            self.assertIn('-                    "rev": "master"\n+                    "rev": "another-branch"', out[0])
            out = self.runbbsetup("update")
            if c in ('gadget', 'gizmo'):
                self.assertIn("Existing bitbake configuration directory renamed to {}/build/conf-backup.".format(buildpath), out[0])
                self.assertIn('-{}+{}'.format(prev_test_file_content, test_file_content), out[0])
            with open(os.path.join(buildpath, 'config', "config-upstream.json")) as f:
                config_upstream = json.load(f)
            self.check_builddir_files(buildpath, test_file_content, config_upstream)
