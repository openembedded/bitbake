"""itertools appeared in Python 2.3 - this module mimicks it (partly)"""

from __future__ import generators

def cycle( sequence ):
    """Return a cyclic generator iterating over sequence"""
    while True:
        for element in sequence:
            yield element

