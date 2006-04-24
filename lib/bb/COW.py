# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
This is a copy on write dictionary which abuses classes to be nice and fast.

Please Note: Be careful when using mutable types (ie Dict and Lists). The copy on write stuff only kicks in on Assignment.
"""

from inspect import getmro

import copy
import types, sets
types.ImmutableTypes = tuple([ \
    types.BooleanType, \
    types.ComplexType, \
    types.FloatType, \
    types.IntType, \
    types.LongType, \
    types.NoneType, \
    types.TupleType, \
    sets.ImmutableSet] + \
    list(types.StringTypes))

MUTABLE = "_mutable__"
 
class COWDictMeta(type):
    def __str__(cls):
        return "<COWDict Level: %i Current Keys: %i>" % (cls.__count__, len(cls.__dict__))
    __repr__ = __str__

    def cow(cls):
        class C(cls):
            __count__ = cls.__count__ + 1
        return C

    def __setitem__(cls, key, value):
        if not isinstance(value, types.ImmutableTypes):
            key += MUTABLE
        setattr(cls, key, value)
    
    def __getmutable__(cls, key):
        """
        This gets called when you do a "o.b" and b doesn't exist on o.

        IE When the type is mutable.
        """
        nkey = key + MUTABLE
        # Do we already have a copy of this on us?
        if nkey in cls.__dict__:
            return cls.__dict__[nkey]

        r = getattr(cls, nkey)
        try:
            r = r.copy()
        except NameError, e:
            r = copy.copy(r)
        setattr(cls, nkey, r)
        return r

    def __getitem__(cls, key):
        try:
            try:
                return getattr(cls, key)
            except AttributeError:
                # Degrade to slow mode if type is not immutable, 
                # If the type is also a COW this will be cheap anyway
                return cls.__getmutable__(key)
        except AttributeError, e:
            raise KeyError(e)

    def has_key(cls, key):
        return (hasattr(cls, key) or hasattr(cls, key + MUTABLE))

    def iter(cls, type):
        for key in dir(cls):
            if key.startswith("__"):
                    continue

            if key.endswith(MUTABLE):
                key = key[:-len(MUTABLE)]

            if type == "keys":
                yield key
            if type == "values":
                yield cls[key]
            if type == "items":
                yield (key, cls[key])
        raise StopIteration()

    def iterkeys(cls):
        return cls.iter("keys")
    def itervalues(cls):
        return cls.iter("values")
    def iteritems(cls):
        return cls.iter("items")
    copy = cow

class COWSetMeta(COWDictMeta):
    def __str__(cls):
        return "<COWSet Level: %i Current Keys: %i>" % (cls.__count__, len(cls.__dict__))
    __repr__ = __str__

    def cow(cls):
        class C(cls):
            __count__ = cls.__count__ + 1
        return C

    def add(cls, key, value):
        cls.__setitem__(hash(key), value)

class COWDictBase(object):
    __metaclass__ = COWDictMeta
    __count__ = 0


if __name__ == "__main__":
    a = COWDictBase.copy()
    print a
    a['a'] = 'a'
    a['dict'] = {}

    print "ha"
    hasattr(a, "a")
    print "ha"
    
    b = a.copy()
    print b
    b['b'] = 'b'

    for x in a.iteritems():
        print x
    print "--"
    for x in b.iteritems():
        print x
    print

    b['dict']['a'] = 'b'
    b['a'] = 'c'

    for x in a.iteritems():
        print x
    print "--"
    for x in b.iteritems():
        print x
    print

    try:
        b['dict2']
    except KeyError, e:
        print "Okay!"


