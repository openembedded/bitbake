#
# Copyright (C) 2026 Agilent Technologies, Inc.
#
# SPDX-License-Identifier: GPL-2.0-only
#

import os
import subprocess
import sys
import unittest


class FetchImportTests(unittest.TestCase):
    def run_python(self, code):
        env = os.environ.copy()
        libdir = os.path.realpath(os.path.join(os.path.dirname(__file__), "..", ".."))
        env["PYTHONPATH"] = os.pathsep.join(filter(None, (libdir, env.get("PYTHONPATH"))))
        result = subprocess.run(
            [sys.executable, "-c", code],
            env=env,
            stdout=subprocess.PIPE,
            stderr=subprocess.PIPE,
            text=True,
        )
        self.assertEqual(result.returncode, 0, result.stderr)

    def test_fetch_is_lazy(self):
        self.run_python("""
import sys
import bb

assert "bb.fetch" not in sys.modules
assert "bb.fetch2" not in sys.modules
""")

    def test_fetch_import(self):
        self.run_python("""
import sys
import bb.fetch
from bb.fetch import Fetch

assert sys.modules["bb.fetch"] is bb.fetch
assert Fetch is bb.fetch.Fetch
""")

    def test_fetch2_import_compatibility(self):
        self.run_python("""
import sys
import warnings

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    import bb.fetch2
    from bb.fetch2 import Fetch

assert len(caught) == 1
assert caught[0].category is DeprecationWarning
assert str(caught[0].message) == "bb.fetch2 is deprecated; use bb.fetch instead"
assert caught[0].filename == "<string>"

assert bb.fetch2 is bb.fetch
assert sys.modules["bb.fetch2"] is bb.fetch
assert Fetch is bb.fetch.Fetch
""")

    def test_fetch2_attribute_access(self):
        self.run_python("""
import sys
import warnings
import bb

assert "bb.fetch" not in sys.modules
assert "bb.fetch2" not in sys.modules

with warnings.catch_warnings(record=True) as caught:
    warnings.simplefilter("always")
    fetch2 = bb.fetch2

assert len(caught) == 1
assert caught[0].category is DeprecationWarning
assert str(caught[0].message) == "bb.fetch2 is deprecated; use bb.fetch instead"

assert fetch2 is bb.fetch
assert bb.fetch2 is bb.fetch
assert sys.modules["bb.fetch2"] is bb.fetch
""")