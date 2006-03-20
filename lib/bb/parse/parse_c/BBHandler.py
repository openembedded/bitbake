# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2006 Holger Hans Peter Freyther
#
# Permission is hereby granted, free of charge, to any person obtaining a copy
# of this software and associated documentation files (the "Software"), to deal
# in the Software without restriction, including without limitation the rights
# to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
# copies of the Software, and to permit persons to whom the Software is
# furnished to do so, subject to the following conditions:
#
# The above copyright notice and this permission notice shall be included in all
# copies or substantial portions of the Software.
#
# THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
# IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
# FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
# SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
# DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
# OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
# THE USE OR OTHER DEALINGS IN THE SOFTWARE.
#

from bb import data
from bb.parse import ParseError

#
# This is the Python Part of the Native Parser Implementation.
# We will only parse .bbclass, .inc and .bb files but no
# configuration files.
# supports, init and handle are the public methods used by
# parser module
#
# The rest of the methods are internal implementation details.



#
# internal
#


#
# public
#
def supports(fn, data):
    return fn[-3:] == ".bb" or fn[-8:] == ".bbclass" or fn[-4:] == ".inc"

def init(fn, data):
    print "Init"

def handle(fn, data, include):
    print ""
    print "fn: %s" % fn
    print "data: %s" % data
    print "include: %s" % include

    pass

# Inform bitbake that we are a parser
# We need to define all three
from bb.parse import handlers
handlers.append( {'supports' : supports, 'handle': handle, 'init' : init})
del handlers
