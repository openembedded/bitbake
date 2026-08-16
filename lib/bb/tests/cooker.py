#
# BitBake Tests for cooker.py
#
# Copyright BitBake Contributors
#
# SPDX-License-Identifier: GPL-2.0-only
#

import unittest
import contextlib
import os
import subprocess
import sys
import tempfile
import time
import bb, bb.cooker
import re
import logging


class _BitbakeSubprocessTestCase(unittest.TestCase):
    """Common helpers for tests that run bitbake/tinfoil in a subprocess.

    Shared because every such subprocess can start a memory-resident bitbake
    server (and, if BB_HASHSERVE=auto, a hashserv) rooted at TOPDIR, and both
    must release that directory before the caller's TemporaryDirectory can be
    safely removed.
    """

    def _run_subprocess(self, cmd, env, cwd):
        proc = subprocess.run(
            cmd,
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.STDOUT,
            universal_newlines=True,
            cwd=cwd,
        )
        if proc.returncode:
            self.fail('%s failed: %s' % (cmd, proc.stdout))
        return proc.stdout

    def _shutdown(self, builddir):
        """Wait for the bitbake server and hashserv to release builddir.

        Must run before the caller's TemporaryDirectory is removed, so it
        cannot be a tearDown().
        """
        deadline = time.monotonic() + 30
        while time.monotonic() < deadline:
            if not any(os.path.exists(os.path.join(builddir, p))
                       for p in ('hashserve.sock', 'bitbake.lock')):
                return
            time.sleep(0.5)

    @contextlib.contextmanager
    def _build_dir(self, prefix='tinfoiltest'):
        """TemporaryDirectory that also waits out _shutdown() before removal."""
        with tempfile.TemporaryDirectory(prefix=prefix) as builddir:
            try:
                yield builddir
            finally:
                self._shutdown(builddir)


class CookerTest(unittest.TestCase):
    def setUp(self):
        # At least one variable needs to be set
        self.d = bb.data.init()
        topdir = os.path.join(os.path.dirname(os.path.realpath(__file__)), "testdata/cooker")
        self.d.setVar('TOPDIR', topdir)

    def test_CookerCollectFiles_sublayers(self):
        '''Test that a sublayer of an existing layer does not trigger
           No bb files matched ...'''

        def append_collection(topdir, path, d):
            collection = path.split('/')[-1]
            pattern = "^" + topdir + "/" + path + "/"
            regex = re.compile(pattern)
            priority = 5

            d.setVar('BBFILE_COLLECTIONS', (d.getVar('BBFILE_COLLECTIONS') or "") + " " + collection)
            d.setVar('BBFILE_PATTERN_%s' % (collection), pattern)
            d.setVar('BBFILE_PRIORITY_%s' % (collection), priority)

            return (collection, pattern, regex, priority)

        topdir = self.d.getVar("TOPDIR")

        # Priorities: list of (collection, pattern, regex, priority)
        bbfile_config_priorities = []
        # Order is important for this test, shortest to longest is typical failure case
        bbfile_config_priorities.append( append_collection(topdir, 'first', self.d) )
        bbfile_config_priorities.append( append_collection(topdir, 'second', self.d) )
        bbfile_config_priorities.append( append_collection(topdir, 'second/third', self.d) )

        pkgfns = [ topdir + '/first/recipes/sample1_1.0.bb',
                   topdir + '/second/recipes/sample2_1.0.bb',
                   topdir + '/second/third/recipes/sample3_1.0.bb' ]

        class LogHandler(logging.Handler):
            def __init__(self):
                logging.Handler.__init__(self)
                self.logdata = []

            def emit(self, record):
                self.logdata.append(record.getMessage())

        # Move cooker to use my special logging
        logger = bb.cooker.logger
        log_handler = LogHandler()
        logger.addHandler(log_handler)
        collection = bb.cooker.CookerCollectFiles(bbfile_config_priorities)
        collection.collection_priorities(pkgfns, pkgfns, self.d)
        logger.removeHandler(log_handler)

        # Should be empty (no generated messages)
        expected = []

        self.assertEqual(log_handler.logdata, expected)
