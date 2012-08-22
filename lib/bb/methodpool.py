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

# A dict of function names we have seen
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
            error("The function %s defined in %s was already declared in %s. BitBake has a global python function namespace so shared functions should be declared in a common include file rather than being duplicated, or if the functions are different, please use different function names." % (name, modulename, _parsed_fns[name]))
        else:
            _parsed_fns[name] = modulename

# A dict of modules the parser has finished with
_parsed_methods = {}

def parsed_module(modulename):
    """
    Has module been parsed?
    """
    return modulename in _parsed_methods

def set_parsed_module(modulename):
    """
    Set module as parsed
    """
    _parsed_methods[modulename] = True

