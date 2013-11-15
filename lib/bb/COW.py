# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# This is a copy on write dictionary and set which abuses classes to try and be nice and fast.
#
# Copyright (C) 2006 Tim Amsell
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
# Please Note:
# Be careful when using mutable types (ie Dict and Lists) - operations involving these are SLOW.
# Assign a file to __warn__ to get warnings about slow operations.
#

from __future__ import print_function
import copy
import types
ImmutableTypes = (
    types.NoneType,
    bool,
    complex,
    float,
    int,
    long,
    tuple,
    frozenset,
    basestring
)

MUTABLE = "__mutable__"

IGNORELIST = ['__module__', '__doc__',  # Python's default builtins
              '__count__',  # from class COWDictBase, COWSetBase
              '__hasmutable__',  # from COWDictMeta
              ]


class COWMeta(type):
    pass


class COWDictMeta(COWMeta):
    __warn__ = None
    __hasmutable__ = False
    __marker__ = tuple()

    def copy(cls):
        class COWDict(cls):
            __count__ = cls.__count__ + 1
        return COWDict

    __call__ = copy

    def count(cls):
        return cls.__count__

    def __setitem__(cls, key, value):
        if not isinstance(key, str):
            raise TypeError("%s: user key must be a string" % cls.__name__)
        if key.startswith('__'):
            # It does not make sense to let the user enter keys starting with
            # '__' since we risk to overwrite existing Python builtins or
            # even our own builtins
            raise TypeError("%s: user key is not allowed to start with '__'" %
                            cls.__name__)
        if not isinstance(value, ImmutableTypes):
            if not isinstance(value, COWMeta):
                cls.__hasmutable__ = True
            key += MUTABLE  # mutable keys will be suffixed by "__mutable__"
        setattr(cls, key, value)

    def __getmutable__(cls, key, readonly=False):
        # Add the __mutable__ suffix to the key
        nkey = key + MUTABLE
        try:
            return cls.__dict__[nkey]
        except KeyError:
            pass

        # Get nkey's value otherwise will raise AttributeError
        value = getattr(cls, nkey)
        if readonly:
            return value

        if cls.__warn__ and not isinstance(value, COWMeta):
            print("Warning: Doing a copy because %s is a mutable type." %
                  key, file=cls.__warn__)

        try:
            value = value.copy()
        except AttributeError as e:
            value = copy.copy(value)
        setattr(cls, nkey, value)
        return value

    __getmarker__ = []

    def __getreadonly__(cls, key, default=__getmarker__):
        """
        Get a value (even if mutable) which you promise not to change.
        """
        return cls.__getitem__(key, default, True)

    def __getitem__(cls, key, default=__getmarker__, readonly=False):
        """ This method is called when calling obj[key] """
        try:
            try:
                # Check if the key is present in the attribute list
                value = getattr(cls, key)
            except AttributeError:
                # Check if the key is mutable (with '__mutable__' suffix)
                value = cls.__getmutable__(key, readonly)

            # This is for values which have been deleted
            if value is cls.__marker__:
                raise AttributeError("key %s does not exist." % key)

            return value
        except AttributeError as e:
            if not default is cls.__getmarker__:
                return default

            raise KeyError(str(e))

    def __delitem__(cls, key):
        cls.__setitem__(key, cls.__marker__)

    def __revertitem__(cls, key):
        if not cls.__dict__.has_key(key):
            key += MUTABLE
        delattr(cls, key)

    def __contains__(cls, key):
        return cls.has_key(key)

    def has_key(cls, key):
        value = cls.__getreadonly__(key, cls.__marker__)
        if value is cls.__marker__:
            return False
        return True

    def iter(cls, type_str, readonly=False):
        for key in dir(cls):
            # We skip Python's builtins and the ones in IGNORELIST
            if key.startswith("__"):
                continue

            # Mutable keys have a __mutable__ suffix that we remove
            if key.endswith(MUTABLE):
                key = key[:-len(MUTABLE)]

            if type_str == "keys":
                yield key

            try:
                if readonly:
                    value = cls.__getreadonly__(key)
                else:
                    value = cls[key]
            except KeyError:
                continue

            if type_str == "values":
                yield value
            if type_str == "items":
                yield (key, value)
        raise StopIteration()

    def iterkeys(cls, readonly=False):
        return cls.iter("keys", readonly)

    # The default iterator is 'readonly'
    def __iter__(cls):
        return cls.iter("keys", readonly=True)

    def itervalues(cls, readonly=False):
        if cls.__warn__ and cls.__hasmutable__ and readonly is False:
            print(
                "Warning: If you arn't going to change any of the values call with True.", file=cls.__warn__)
        return cls.iter("values", readonly)

    def iteritems(cls, readonly=False):
        if cls.__warn__ and cls.__hasmutable__ and readonly is False:
            print(
                "Warning: If you arn't going to change any of the values call with True.", file=cls.__warn__)
        return cls.iter("items", readonly)

    def __str__(cls):
        """
        Returns a string representation of this object
        The number of keys is only showing keys in the current 'level'
        """
        return ("<%s Level: %i Number of keys: %i>" %
               (cls.__name__, cls.__count__, cls.__len__()))
    __repr__ = __str__

    def __len__(cls):
        """ Returns the number of 'keys' in the COWDict """
        # cls.__dict__ is the default module namespace as a dictionary
        # We skip keys found in IGNORELIST
        i = 0
        for x in cls.__dict__:
            if x in IGNORELIST:
                continue
            i += 1
        return i


class COWSetMeta(COWDictMeta):

    def copy(cls):
        class COWSet(cls):
            __count__ = cls.__count__ + 1
        return COWSet

    def add(cls, value):
        COWDictMeta.__setitem__(cls, repr(hash(value)), value)

    def remove(cls, value):
        COWDictMeta.__delitem__(cls, repr(hash(value)))

    def __contains__(cls, value):
        return COWDictMeta.has_key(cls, repr(hash(value)))

    def iterkeys(cls):
        raise TypeError("sets don't have keys")

    def iteritems(cls):
        raise TypeError("sets don't have 'items'")


# These are the actual classes you use!
class COWDictBase(object):
    __metaclass__ = COWDictMeta
    __count__ = 0


class COWSetBase(object):
    __metaclass__ = COWSetMeta
    __count__ = 0


if __name__ == "__main__":
    print("The unit tests in test_cow.py show how COWDict/SetBase are used")
