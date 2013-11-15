# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Tests for Copy-on-Write (cow.py)
#
# Copyright 2006 Holger Freyther <freyther@handhelds.org>
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
import os
from bb.COW import COWDictBase, COWSetBase
from nose.tools import raises


class TestCOWDictBase(unittest.TestCase):

    """
    Test case for the COW module from mithro
    """

    def test_cow(self):
        # Test base COW functionality
        c = COWDictBase()
        c['123'] = 1027
        c['other'] = 4711
        d = {'abc': 10, 'bcd': 20}
        c['d'] = d

        self.assertEquals(c.count(), 1)  # Level: 1
        self.assertEquals(len(c), 3)  # c has 3 keys in Level #1

        c_2 = c.copy()

        self.assertEquals(c_2.count(), 2)  # c_2 Level: 2 (copy of c)
        self.assertEquals(len(c_2), 0)  # c_2 has 0 keys in Level #2
        self.assertEquals(1027, c['123'])
        self.assertEquals(4711, c['other'])
        self.assertEquals(d, c['d'])
        self.assertEquals(1027, c_2['123'])
        self.assertEquals(4711, c_2['other'])

        # The two dictionary objects must be identical at this point:
        # We must use getattr() instead of c_2['d']
        self.assertEquals(id(d), id(getattr(c_2, 'd__mutable__')))

        # c_2['d'] will result in calling __getmutable__ and since 'd__mutable__'
        # is not an attribute of c_2 (but only of c), and since readonly=False,
        # it will do a d.copy() aka a 'shallow copy' of the dictionary 'd'
        # So the copy on write behaviour actually happens here:
        self.assertEquals(d, c_2['d'])

        # At this point, the two dictionary objects must be different:
        # We must use getattr() instead of c_2['d']
        self.assertNotEquals(id(d), id(getattr(c_2, 'd__mutable__')))

        # At this point c_2 has 1 key in Level #2
        self.assertEquals(c_2.count(), 2)
        self.assertEquals(len(c_2), 1)

        # Change the immutable values for the same keys as in c
        c_2['123'] = 1028
        c_2['other'] = 4712

        # Since we only changed c_2, verify again that that c is unchanged
        self.assertEquals(1027, c['123'])
        self.assertEquals(4711, c['other'])
        # However, c_2 values must have changed
        self.assertEquals(1028, c_2['123'])
        self.assertEquals(4712, c_2['other'])

        # Change the mutable values for the same keys as in c
        c_2['d']['abc'] = 20

        # Since we only changed c_2, verify again that that c is unchanged
        self.assertEquals(d, c['d'])
        # However, c_2 is changed
        self.assertEquals({'abc': 20, 'bcd': 20}, c_2['d'])

        # At this point c_2 has 3 keys in Level #2
        self.assertEquals(c_2.count(), 2)
        self.assertEquals(len(c_2), 3)

    def test_iter_readonly(self):
        c = COWDictBase()
        c['123'] = 1027
        c['other'] = 4711
        d = {'abc': 10, 'bcd': 20}
        c['d'] = d
        expected_keys = ('123', 'other', 'd')
        expected_values = (1027, 4711, d)
        expected_items = (('123', 1027), ('other', 4711), ('d', d))

        i = 0
        for x in c.iterkeys(readonly=True):
            i += 1
            self.assertTrue(x in expected_keys)
        self.assertTrue(i == 3)

        i = 0
        for x in c.itervalues(readonly=True):
            i += 1
            self.assertTrue(x in expected_values)
        self.assertTrue(i == 3)

        i = 0
        for x in c.iteritems(readonly=True):
            i += 1
            self.assertTrue(x in expected_items)
        self.assertTrue(i == 3)

        c_2 = c.copy()

        self.assertEquals(id(d), id(getattr(c_2, 'd__mutable__')))

        i = 0
        for x in c_2.iterkeys(readonly=True):
            i += 1
            self.assertTrue(x in expected_keys)
        self.assertTrue(i == 3)

        # Check that the mutable dict 'd' has not been shallow copied
        self.assertEquals(id(d), id(getattr(c_2, 'd__mutable__')))

        i = 0
        for x in c_2.itervalues(readonly=True):
            i += 1
            self.assertTrue(x in expected_values)
        self.assertTrue(i == 3)

        i = 0
        for x in c.iteritems(readonly=True):
            i += 1
            self.assertTrue(x in expected_items)
        self.assertTrue(i == 3)

    def test_default_ro_iter(self):
        c = COWDictBase()
        c['123'] = 1027
        c['other'] = 4711
        d = {'abc': 10, 'bcd': 20}
        c['d'] = d
        expected_keys = ('123', 'other', 'd')

        c_2 = c.copy()

        self.assertEquals(id(d), id(getattr(c_2, 'd__mutable__')))

        i = 0
        for x in c:
            i += 1
            self.assertTrue(x in expected_keys)
        self.assertTrue(i == 3)

        # Check that the mutable dict 'd' has not been shallow copied
        self.assertEquals(id(d), id(getattr(c_2, 'd__mutable__')))

    def test_nonro_iteritems(self):
        c = COWDictBase()
        c['123'] = 1027
        c['other'] = 4711
        d = {'abc': 10, 'bcd': 20}
        c['d'] = d
        expected_keys = ('123', 'other', 'd')

        c_2 = c.copy()

        self.assertEquals(id(d), id(getattr(c_2, 'd__mutable__')))

        i = 0
        for k, v in c_2.iteritems():
            i += 1
            self.assertTrue(k in expected_keys)
        self.assertTrue(i == 3)

        # Check that the mutable dict 'd' _has been_ shallow copied
        self.assertNotEquals(id(d), id(getattr(c_2, 'd__mutable__')))

    def test_cow_get_set(self):
        a = COWDictBase()
        self.assertEquals(False, a.has_key('a'))

        a['a'] = 'a'
        a['b'] = 'b'
        self.assertEquals(True, a.has_key('a'))
        self.assertEquals(True, a.has_key('b'))
        self.assertEquals('a', a['a'])
        self.assertEquals('b', a['b'])

    def test_cow_copy_of_copy(self):
        # Test the copy of copies

        # create two COW dict 'instances'
        b = COWDictBase()
        c = COWDictBase()

        # assign some keys to one instance, some keys to another
        b['a'] = 10
        b['c'] = 20
        c['a'] = 30

        # test separation of the two instances
        self.assertEquals(False, c.has_key('c'))
        self.assertEquals(30, c['a'])
        self.assertEquals(10, b['a'])

        # test copy
        b_2 = b.copy()
        c_2 = c.copy()

        self.assertEquals(False, c_2.has_key('c'))
        self.assertEquals(10, b_2['a'])

        b_2['d'] = 40
        self.assertEquals(False, c_2.has_key('d'))
        self.assertEquals(True, b_2.has_key('d'))
        self.assertEquals(40, b_2['d'])
        self.assertEquals(False, b.has_key('d'))
        self.assertEquals(False, c.has_key('d'))

        c_2['d'] = 30
        self.assertEquals(True, c_2.has_key('d'))
        self.assertEquals(True, b_2.has_key('d'))
        self.assertEquals(30, c_2['d'])
        self.assertEquals(40, b_2['d'])
        self.assertEquals(False, b.has_key('d'))
        self.assertEquals(False, c.has_key('d'))

        # test copy of the copy
        c_3 = c_2.copy()
        b_3 = b_2.copy()
        b_3_2 = b_2.copy()

        c_3['e'] = 4711
        self.assertEquals(4711, c_3['e'])
        self.assertEquals(False, c_2.has_key('e'))
        self.assertEquals(False, b_3.has_key('e'))
        self.assertEquals(False, b_3_2.has_key('e'))
        self.assertEquals(False, b_2.has_key('e'))

        b_3['e'] = 'viel'
        self.assertEquals('viel', b_3['e'])
        self.assertEquals(4711, c_3['e'])
        self.assertEquals(False, c_2.has_key('e'))
        self.assertEquals(True, b_3.has_key('e'))
        self.assertEquals(False, b_3_2.has_key('e'))
        self.assertEquals(False, b_2.has_key('e'))

    def test_contains_ro(self):
        c = COWDictBase()
        c['xyz'] = 1
        d = {'abc': 10, 'bcd': 20}
        c['d'] = d
        self.assertTrue('xyz' in c)
        c_2 = c.copy()
        self.assertTrue('d' in c)
        self.assertTrue('d' in c_2)
        # Check that the mutable dict 'd' has not been shallow copied
        self.assertEquals(id(d), id(getattr(c_2, 'd__mutable__')))

    @raises(KeyError)
    def test_raise_keyerror(self):
        c = COWDictBase()
        c['123'] = 1027
        c['other'] = 4711
        a = c['gfgd']

    def test_revertitem(self):
        c = COWDictBase()
        c['xyz'] = 1
        d = {'abc': 10, 'bcd': 20}
        c['d'] = d
        c_2 = c.copy()
        c_2['xyz'] = 2
        self.assertTrue(c_2['xyz'], 2)
        c_2.__revertitem__('xyz')
        self.assertTrue(c_2['xyz'], 1)

        c_2['d']['abc'] = 20
        self.assertTrue(c_2['d']['abc'], 20)
        c_2.__revertitem__('d')
        self.assertTrue(c_2['d']['abc'], 10)

    def test_cowset(self):
        c = COWDictBase()
        c['set'] = COWSetBase()
        c['set'].add("o1")
        c['set'].add("o1")
        self.assertTrue(len(c['set']), 1)
        c['set'].add("o2")
        self.assertTrue(len(c['set']), 2)
        c['set'].remove("o1")
        self.assertTrue(len(c['set']), 1)
        self.assertTrue('o2' in c['set'])

    def test_cow_copy_anything(self):
        class Anything:
            var = 0
            pass
        a = Anything()
        c = COWDictBase()
        c['any'] = a
        self.assertEquals(id(a), id(getattr(c, 'any__mutable__')))
        c_2 = c.copy()
        self.assertEquals(id(a), id(getattr(c_2, 'any__mutable__')))
        c_2['any'].var = 1
        self.assertNotEquals(id(a), id(getattr(c_2, 'any__mutable__')))
