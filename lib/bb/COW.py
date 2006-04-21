# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
This is a copy on write dictionary which abuses classes to be nice and fast.

Please Note: Be careful when using mutable types (ie Dict and Lists). The copy on write stuff only kicks in on Assignment.
"""

from inspect import getmro

class COWMeta(type):
    def __str__(cls):
        return "<COW Level: %i Current Keys: %i>" % (cls.__count__, len(cls.__dict__))
    __repr__ = __str__

    def cow(cls):
        class C(cls):
            __count__ = cls.__count__ + 1
        return C

    def __setitem__(cls, key, value):
        setattr(cls, key, value)
    def __getitem__(cls, key):
        return getattr(cls, key)
    def haskey(cls, key):
        return hasattr(cls, key)

    def iter(cls, type):
        for key in dir(cls):
            if key.startswith("__"):
                continue

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

class COWBase(object):
    __metaclass__ = COWMeta
    __count__ = 0

if __name__ == "__main__":
    a = COWBase
    print a
    a['a'] = 'a'
    
    b = a.copy()
    print b
    b['b'] = 'b'

    for x in b.iteritems():
        print x
    print

    b['a'] = 'c'

    for x in b.iteritems():
        print x
    print

