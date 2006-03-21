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

# The Module we will use here
from bb import data, parse
from bb.parse import ParseError
import bb

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
def _init(fn, d):
    """
    Initialize the data implementation with values of
    the environment and data from the file.
    """
    pass

#
# public
#
def supports(fn, data):
    return fn[-3:] == ".bb" or fn[-8:] == ".bbclass" or fn[-4:] == ".inc"

def init(fn, data):
    if not bb.data.getVar('TOPDIR', data):
        bb.error('TOPDIR is not set')
    if not bb.data.getVar('BBPATH', data):
        bb.error('BBPATH is not set')


def handle(fn, d, include):
    print ""
    print "fn: %s" % fn
    print "data: %s" % data
    print "include: %s" % include

    # check if we include or are the beginning
    if include:
        oldfile = data.getVar('FILE', d)
    else:
        data.inheritFromOS(d)
        oldfile = None

    # find the file
    if not os.path.isabs(fn):
        bb.error("No Absolute FILE name")
        abs_fn = bb.which(data.getVar('BBPATH',d), fn)
    else:
        abs_fn = fn

    # check if the file exists
    if not os.path.exists(abs_fn):
        raise IOError("file '%(fn)' not found" % locals() )

    fn = file(abs_fn, 'r')

    # now we know the file is around mark it as dep
    if include:
        parse.mark_dependency(d, abs_fn)

    # now parse this file - by defering it to C++


    # restore the original FILE
    if oldfile:
        data.setVar('FILE', oldfile, data)

    return data

# Inform bitbake that we are a parser
# We need to define all three
from bb.parse import handlers
handlers.append( {'supports' : supports, 'handle': handle, 'init' : init})
del handlers
