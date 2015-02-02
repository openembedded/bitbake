# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Tests for the Data Store (data.py/data_smart.py)
#
# Copyright (C) 2010 Chris Larson
# Copyright (C) 2012 Richard Purdie
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
#

import unittest
import bb
import bb.data
import bb.parse

class DataExpansions(unittest.TestCase):
    def setUp(self):
        self.d = bb.data.init()
        self.d["foo"] = "value_of_foo"
        self.d["bar"] = "value_of_bar"
        self.d["value_of_foo"] = "value_of_'value_of_foo'"

    def test_one_var(self):
        val = self.d.expand("${foo}")
        self.assertEqual(str(val), "value_of_foo")

    def test_indirect_one_var(self):
        val = self.d.expand("${${foo}}")
        self.assertEqual(str(val), "value_of_'value_of_foo'")

    def test_indirect_and_another(self):
        val = self.d.expand("${${foo}} ${bar}")
        self.assertEqual(str(val), "value_of_'value_of_foo' value_of_bar")

    def test_python_snippet(self):
        val = self.d.expand("${@5*12}")
        self.assertEqual(str(val), "60")

    def test_expand_in_python_snippet(self):
        val = self.d.expand("${@'boo ' + '${foo}'}")
        self.assertEqual(str(val), "boo value_of_foo")

    def test_python_snippet_getvar(self):
        val = self.d.expand("${@d.getVar('foo', True) + ' ${bar}'}")
        self.assertEqual(str(val), "value_of_foo value_of_bar")

    def test_python_snippet_syntax_error(self):
        self.d.setVar("FOO", "${@foo = 5}")
        self.assertRaises(bb.data_smart.ExpansionError, self.d.getVar, "FOO", True)

    def test_python_snippet_runtime_error(self):
        self.d.setVar("FOO", "${@int('test')}")
        self.assertRaises(bb.data_smart.ExpansionError, self.d.getVar, "FOO", True)

    def test_python_snippet_error_path(self):
        self.d.setVar("FOO", "foo value ${BAR}")
        self.d.setVar("BAR", "bar value ${@int('test')}")
        self.assertRaises(bb.data_smart.ExpansionError, self.d.getVar, "FOO", True)

    def test_value_containing_value(self):
        val = self.d.expand("${@d.getVar('foo', True) + ' ${bar}'}")
        self.assertEqual(str(val), "value_of_foo value_of_bar")

    def test_reference_undefined_var(self):
        val = self.d.expand("${undefinedvar} meh")
        self.assertEqual(str(val), "${undefinedvar} meh")

    def test_double_reference(self):
        self.d.setVar("BAR", "bar value")
        self.d.setVar("FOO", "${BAR} foo ${BAR}")
        val = self.d.getVar("FOO", True)
        self.assertEqual(str(val), "bar value foo bar value")

    def test_direct_recursion(self):
        self.d.setVar("FOO", "${FOO}")
        self.assertRaises(bb.data_smart.ExpansionError, self.d.getVar, "FOO", True)

    def test_indirect_recursion(self):
        self.d.setVar("FOO", "${BAR}")
        self.d.setVar("BAR", "${BAZ}")
        self.d.setVar("BAZ", "${FOO}")
        self.assertRaises(bb.data_smart.ExpansionError, self.d.getVar, "FOO", True)

    def test_recursion_exception(self):
        self.d.setVar("FOO", "${BAR}")
        self.d.setVar("BAR", "${${@'FOO'}}")
        self.assertRaises(bb.data_smart.ExpansionError, self.d.getVar, "FOO", True)

    def test_incomplete_varexp_single_quotes(self):
        self.d.setVar("FOO", "sed -i -e 's:IP{:I${:g' $pc")
        val = self.d.getVar("FOO", True)
        self.assertEqual(str(val), "sed -i -e 's:IP{:I${:g' $pc")

    def test_nonstring(self):
        self.d.setVar("TEST", 5)
        val = self.d.getVar("TEST", True)
        self.assertEqual(str(val), "5")

    def test_rename(self):
        self.d.renameVar("foo", "newfoo")
        self.assertEqual(self.d.getVar("newfoo"), "value_of_foo")
        self.assertEqual(self.d.getVar("foo"), None)

    def test_deletion(self):
        self.d.delVar("foo")
        self.assertEqual(self.d.getVar("foo"), None)

    def test_keys(self):
        keys = self.d.keys()
        self.assertEqual(keys, ['value_of_foo', 'foo', 'bar'])

class TestNestedExpansions(unittest.TestCase):
    def setUp(self):
        self.d = bb.data.init()
        self.d["foo"] = "foo"
        self.d["bar"] = "bar"
        self.d["value_of_foobar"] = "187"

    def test_refs(self):
        val = self.d.expand("${value_of_${foo}${bar}}")
        self.assertEqual(str(val), "187")

    #def test_python_refs(self):
    #    val = self.d.expand("${@${@3}**2 + ${@4}**2}")
    #    self.assertEqual(str(val), "25")

    def test_ref_in_python_ref(self):
        val = self.d.expand("${@'${foo}' + 'bar'}")
        self.assertEqual(str(val), "foobar")

    def test_python_ref_in_ref(self):
        val = self.d.expand("${${@'f'+'o'+'o'}}")
        self.assertEqual(str(val), "foo")

    def test_deep_nesting(self):
        depth = 100
        val = self.d.expand("${" * depth + "foo" + "}" * depth)
        self.assertEqual(str(val), "foo")

    #def test_deep_python_nesting(self):
    #    depth = 50
    #    val = self.d.expand("${@" * depth + "1" + "+1}" * depth)
    #    self.assertEqual(str(val), str(depth + 1))

    def test_mixed(self):
        val = self.d.expand("${value_of_${@('${foo}'+'bar')[0:3]}${${@'BAR'.lower()}}}")
        self.assertEqual(str(val), "187")

    def test_runtime(self):
        val = self.d.expand("${${@'value_of' + '_f'+'o'+'o'+'b'+'a'+'r'}}")
        self.assertEqual(str(val), "187")

class TestMemoize(unittest.TestCase):
    def test_memoized(self):
        d = bb.data.init()
        d.setVar("FOO", "bar")
        self.assertTrue(d.getVar("FOO") is d.getVar("FOO"))

    def test_not_memoized(self):
        d1 = bb.data.init()
        d2 = bb.data.init()
        d1.setVar("FOO", "bar")
        d2.setVar("FOO", "bar2")
        self.assertTrue(d1.getVar("FOO") is not d2.getVar("FOO"))

    def test_changed_after_memoized(self):
        d = bb.data.init()
        d.setVar("foo", "value of foo")
        self.assertEqual(str(d.getVar("foo")), "value of foo")
        d.setVar("foo", "second value of foo")
        self.assertEqual(str(d.getVar("foo")), "second value of foo")

    def test_same_value(self):
        d = bb.data.init()
        d.setVar("foo", "value of")
        d.setVar("bar", "value of")
        self.assertEqual(d.getVar("foo"),
                         d.getVar("bar"))

class TestConcat(unittest.TestCase):
    def setUp(self):
        self.d = bb.data.init()
        self.d.setVar("FOO", "foo")
        self.d.setVar("VAL", "val")
        self.d.setVar("BAR", "bar")

    def test_prepend(self):
        self.d.setVar("TEST", "${VAL}")
        self.d.prependVar("TEST", "${FOO}:")
        self.assertEqual(self.d.getVar("TEST", True), "foo:val")

    def test_append(self):
        self.d.setVar("TEST", "${VAL}")
        self.d.appendVar("TEST", ":${BAR}")
        self.assertEqual(self.d.getVar("TEST", True), "val:bar")

    def test_multiple_append(self):
        self.d.setVar("TEST", "${VAL}")
        self.d.prependVar("TEST", "${FOO}:")
        self.d.appendVar("TEST", ":val2")
        self.d.appendVar("TEST", ":${BAR}")
        self.assertEqual(self.d.getVar("TEST", True), "foo:val:val2:bar")

class TestConcatOverride(unittest.TestCase):
    def setUp(self):
        self.d = bb.data.init()
        self.d.setVar("FOO", "foo")
        self.d.setVar("VAL", "val")
        self.d.setVar("BAR", "bar")

    def test_prepend(self):
        self.d.setVar("TEST", "${VAL}")
        self.d.setVar("TEST_prepend", "${FOO}:")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "foo:val")

    def test_append(self):
        self.d.setVar("TEST", "${VAL}")
        self.d.setVar("TEST_append", ":${BAR}")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "val:bar")

    def test_multiple_append(self):
        self.d.setVar("TEST", "${VAL}")
        self.d.setVar("TEST_prepend", "${FOO}:")
        self.d.setVar("TEST_append", ":val2")
        self.d.setVar("TEST_append", ":${BAR}")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "foo:val:val2:bar")

    def test_remove(self):
        self.d.setVar("TEST", "${VAL} ${BAR}")
        self.d.setVar("TEST_remove", "val")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "bar")

    def test_doubleref_remove(self):
        self.d.setVar("TEST", "${VAL} ${BAR}")
        self.d.setVar("TEST_remove", "val")
        self.d.setVar("TEST_TEST", "${TEST} ${TEST}")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST_TEST", True), "bar bar")

    def test_empty_remove(self):
        self.d.setVar("TEST", "")
        self.d.setVar("TEST_remove", "val")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "")

    def test_remove_expansion(self):
        self.d.setVar("BAR", "Z")
        self.d.setVar("TEST", "${BAR}/X Y")
        self.d.setVar("TEST_remove", "${BAR}/X")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "Y")

    def test_remove_expansion_items(self):
        self.d.setVar("TEST", "A B C D")
        self.d.setVar("BAR", "B D")
        self.d.setVar("TEST_remove", "${BAR}")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "A C")

class TestOverrides(unittest.TestCase):
    def setUp(self):
        self.d = bb.data.init()
        self.d.setVar("OVERRIDES", "foo:bar:local")
        self.d.setVar("TEST", "testvalue")

    def test_no_override(self):
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "testvalue")

    def test_one_override(self):
        self.d.setVar("TEST_bar", "testvalue2")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "testvalue2")

    def test_multiple_override(self):
        self.d.setVar("TEST_bar", "testvalue2")
        self.d.setVar("TEST_local", "testvalue3")
        self.d.setVar("TEST_foo", "testvalue4")
        bb.data.update_data(self.d)
        self.assertEqual(self.d.getVar("TEST", True), "testvalue3")


class TestFlags(unittest.TestCase):
    def setUp(self):
        self.d = bb.data.init()
        self.d.setVar("foo", "value of foo")
        self.d.setVarFlag("foo", "flag1", "value of flag1")
        self.d.setVarFlag("foo", "flag2", "value of flag2")

    def test_setflag(self):
        self.assertEqual(self.d.getVarFlag("foo", "flag1"), "value of flag1")
        self.assertEqual(self.d.getVarFlag("foo", "flag2"), "value of flag2")

    def test_delflag(self):
        self.d.delVarFlag("foo", "flag2")
        self.assertEqual(self.d.getVarFlag("foo", "flag1"), "value of flag1")
        self.assertEqual(self.d.getVarFlag("foo", "flag2"), None)


class Contains(unittest.TestCase):
    def setUp(self):
        self.d = bb.data.init()
        self.d.setVar("SOMEFLAG", "a b c")

    def test_contains(self):
        self.assertTrue(bb.utils.contains("SOMEFLAG", "a", True, False, self.d))
        self.assertTrue(bb.utils.contains("SOMEFLAG", "b", True, False, self.d))
        self.assertTrue(bb.utils.contains("SOMEFLAG", "c", True, False, self.d))

        self.assertTrue(bb.utils.contains("SOMEFLAG", "a b", True, False, self.d))
        self.assertTrue(bb.utils.contains("SOMEFLAG", "b c", True, False, self.d))
        self.assertTrue(bb.utils.contains("SOMEFLAG", "c a", True, False, self.d))

        self.assertTrue(bb.utils.contains("SOMEFLAG", "a b c", True, False, self.d))
        self.assertTrue(bb.utils.contains("SOMEFLAG", "c b a", True, False, self.d))

        self.assertFalse(bb.utils.contains("SOMEFLAG", "x", True, False, self.d))
        self.assertFalse(bb.utils.contains("SOMEFLAG", "a x", True, False, self.d))
        self.assertFalse(bb.utils.contains("SOMEFLAG", "x c b", True, False, self.d))
        self.assertFalse(bb.utils.contains("SOMEFLAG", "x c b a", True, False, self.d))

    def test_contains_any(self):
        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "a", True, False, self.d))
        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "b", True, False, self.d))
        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "c", True, False, self.d))

        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "a b", True, False, self.d))
        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "b c", True, False, self.d))
        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "c a", True, False, self.d))

        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "a x", True, False, self.d))
        self.assertTrue(bb.utils.contains_any("SOMEFLAG", "x c", True, False, self.d))

        self.assertFalse(bb.utils.contains_any("SOMEFLAG", "x", True, False, self.d))
        self.assertFalse(bb.utils.contains_any("SOMEFLAG", "x y z", True, False, self.d))
