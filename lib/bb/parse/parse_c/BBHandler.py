# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""class for handling .bb files (using a C++ parser)

    Reads a .bb file and obtains its metadata (using a C++ parser)

    Copyright (C) 2006 Tim Robert Ansell
	Copyright (C) 2006 Holger Hans Peter Freyther
   
    This program is free software; you can redistribute it and/or modify it under
    the terms of the GNU General Public License as published by the Free Software
    Foundation; either version 2 of the License, or (at your option) any later
    version.

	Permission is hereby granted, free of charge, to any person obtaining a copy
	of this software and associated documentation files (the "Software"), to deal
	in the Software without restriction, including without limitation the rights
	to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
	copies of the Software, and to permit persons to whom the Software is
	furnished to do so, subject to the following conditions:

	The above copyright notice and this permission notice shall be included in all
	copies or substantial portions of the Software.

	THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
	IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
	FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
	SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
	DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
	OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
	THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

import os

# The Module we will use here
import bb

from bitbakec import parsefile

#
# This is the Python Part of the Native Parser Implementation.
# We will only parse .bbclass, .inc and .bb files but no
# configuration files.
# supports, init and handle are the public methods used by
# parser module
#
# The rest of the methods are internal implementation details.

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
    return fn[-3:] == ".bb" or fn[-8:] == ".bbclass" or fn[-4:] == ".inc" or fn[-5:] == ".conf"

def init(fn, data):
    if not data.getVar('TOPDIR'):
        bb.error('TOPDIR is not set')
    if not data.getVar('BBPATH'):
        bb.error('BBPATH is not set')


def handle(fn, d, include):
    print ""
    print "fn: %s" % fn
    print "data: %s" % d
    print dir(d)
    print d.getVar.__doc__
    print "include: %s" % include

    # check if we include or are the beginning
    if include:
        oldfile = d.getVar('FILE')
    else:
        #d.inheritFromOS()
        oldfile = None

    # find the file
    if not os.path.isabs(fn):
        bb.error("No Absolute FILE name")
        abs_fn = bb.which(d.getVar('BBPATH'), fn)
    else:
        abs_fn = fn

    # check if the file exists
    if not os.path.exists(abs_fn):
        raise IOError("file '%(fn)' not found" % locals() )

    # now we know the file is around mark it as dep
    if include:
        parse.mark_dependency(d, abs_fn)

    # now parse this file - by defering it to C++
    parsefile(fn, d)

    # restore the original FILE
    if oldfile:
        d.setVar('FILE', oldfile)

    return d

# Inform bitbake that we are a parser
# We need to define all three
from bb.parse import handlers
handlers.append( {'supports' : supports, 'handle': handle, 'init' : init})
del handlers
