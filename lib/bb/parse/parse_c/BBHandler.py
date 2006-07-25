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

import os, sys

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
    if not bb.data.getVar('TOPDIR', data):
        bb.data.setVar('TOPDIR', os.getcwd(), data)
    if not bb.data.getVar('BBPATH', data):
        bb.data.setVar('BBPATH', os.path.join(sys.prefix, 'share', 'bitbake'), data)

def handle_inherit(d):
    """
    Handle inheriting of classes. This will load all default classes.
    It could be faster, it could detect infinite loops but this is todo
    Also this delayed loading of bb.parse could impose a penalty
    """
    from bb.parse import handle

    files = (data.getVar('INHERIT', d, True) or "").split()
    if not "base" in i:
        files[0:0] = ["base"]

    __inherit_cache = data.getVar('__inherit_cache', d) or []
    for f in files:
        file = data.expand(f, d)
        if file[0] != "/" and file[-8:] != ".bbclass":
            file = os.path.join('classes', '%s.bbclass' % file)

        if not file in __inherit_cache:
            debug(2, "BB %s:%d: inheriting %s" % (fn, lineno, file))
            __inherit_cache.append( file )

            try:
                handle(file, d, True)
            except IOError:
                print "Failed to inherit %s" % file
    data.setVar('__inherit_cache', __inherit_cache, d)


def handle(fn, d, include):
    from bb import data, parse

    (root, ext) = os.path.splitext(os.path.basename(fn))
    base_name = "%s%s" % (root,ext)

    # initialize with some data
    init(fn,d)

    # check if we include or are the beginning
    oldfile = None
    if include:
        oldfile = d.getVar('FILE', False)
        is_conf = False
    elif ext == ".conf":
        is_conf = True
        data.inheritFromOS(d)

    # find the file
    if not os.path.isabs(fn):
        abs_fn = bb.which(d.getVar('BBPATH', True), fn)
    else:
        abs_fn = fn

    # check if the file exists
    if not os.path.exists(abs_fn):
        raise IOError("file '%(fn)s' not found" % locals() )

    # now we know the file is around mark it as dep
    if include:
        parse.mark_dependency(d, abs_fn)

    # manipulate the bbpath
    if ext != ".bbclass" and ext != ".conf":
        old_bb_path = data.getVar('BBPATH', d)
        data.setVar('BBPATH', os.path.dirname(abs_fn) + (":%s" %old_bb_path) , d)

    # handle INHERITS and base inherit
    if ext != ".bbclass" and ext != ".conf":
        data.setVar('FILE', fn, d)
        handle_interit(d)

    # now parse this file - by defering it to C++
    parsefile(abs_fn, d, is_conf)

    # Finish it up
    if include == 0:
        data.expandKeys(d)
        data.update_data(d)
        #### !!! XXX Finish it up by executing the anonfunc


    # restore the original FILE
    if oldfile:
        d.setVar('FILE', oldfile)

    # restore bbpath
    if ext != ".bbclass" and ext != ".conf":
        data.setVar('BBPATH', old_bb_path, d )


    return d


# Needed for BitBake files...
__pkgsplit_cache__={}
def vars_from_file(mypkg, d):
    if not mypkg:
        return (None, None, None)
    if mypkg in __pkgsplit_cache__:
        return __pkgsplit_cache__[mypkg]

    myfile = os.path.splitext(os.path.basename(mypkg))
    parts = myfile[0].split('_')
    __pkgsplit_cache__[mypkg] = parts
    exp = 3 - len(parts)
    tmplist = []
    while exp != 0:
        exp -= 1
        tmplist.append(None)
    parts.extend(tmplist)
    return parts




# Inform bitbake that we are a parser
# We need to define all three
from bb.parse import handlers
handlers.append( {'supports' : supports, 'handle': handle, 'init' : init})
del handlers
