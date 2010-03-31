# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
#
# Copyright (C)       2006 Holger Hans Peter Freyther
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


"""
    What is a method pool?

    BitBake has a global method scope where .bb, .inc and .bbclass
    files can install methods. These methods are parsed from strings.
    To avoid recompiling and executing these string we introduce
    a method pool to do this task.

    This pool will be used to compile and execute the functions. It
    will be smart enough to
"""

from bb.utils import better_compile, better_exec
from bb       import error

# A dict of modules we have handled
# it is the number of .bbclasses + x in size
_parsed_methods = { }
_parsed_fns     = { }

def insert_method(modulename, code, fn):
    """
    Add code of a module should be added. The methods
    will be simply added, no checking will be done
    """
    comp = better_compile(code, modulename, fn )
    better_exec(comp, None, code, fn)

    # now some instrumentation
    code = comp.co_names
    for name in code:
        if name in ['None', 'False']:
            continue
        elif name in _parsed_fns and not _parsed_fns[name] == modulename:
            error( "Error Method already seen: %s in' %s' now in '%s'" % (name, _parsed_fns[name], modulename))
        else:
            _parsed_fns[name] = modulename

def check_insert_method(modulename, code, fn):
    """
    Add the code if it wasnt added before. The module
    name will be used for that

    Variables:
        @modulename a short name e.g. base.bbclass
        @code The actual python code
        @fn   The filename from the outer file
    """
    if not modulename in _parsed_methods:
        return insert_method(modulename, code, fn)
    _parsed_methods[modulename] = 1

def parsed_module(modulename):
    """
    Inform me file xyz was parsed
    """
    return modulename in _parsed_methods


def get_parsed_dict():
    """
    shortcut
    """
    return _parsed_methods
