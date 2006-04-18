# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
#
# Copyright (C)       2006 Holger Hans Peter Freyther
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#   Neither the name Holger Hans Peter Freyther nor the names of its
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.


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
    comp = better_compile(code, "<bb>", fn )
    better_exec(comp, __builtins__, code, fn)

    # hack hack hack XXX
    return

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
