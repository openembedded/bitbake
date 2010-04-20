# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Data' implementations

Functions for interacting with the data structure used by the
BitBake build tools.

The expandData and update_data are the most expensive
operations. At night the cookie monster came by and
suggested 'give me cookies on setting the variables and
things will work out'. Taking this suggestion into account
applying the skills from the not yet passed 'Entwurf und
Analyse von Algorithmen' lecture and the cookie
monster seems to be right. We will track setVar more carefully
to have faster update_data and expandKeys operations.

This is a treade-off between speed and memory again but
the speed is more critical here.
"""

# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2005        Holger Hans Peter Freyther
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
#
#Based on functions from the base bb module, Copyright 2003 Holger Schurig

import sys, os, re
if sys.argv[0][-5:] == "pydoc":
    path = os.path.dirname(os.path.dirname(sys.argv[1]))
else:
    path = os.path.dirname(os.path.dirname(sys.argv[0]))
sys.path.insert(0, path)
from itertools import groupby

from bb import data_smart
import bb

_dict_type = data_smart.DataSmart

def init():
    """Return a new object representing the Bitbake data"""
    return _dict_type()

def init_db(parent = None):
    """Return a new object representing the Bitbake data,
    optionally based on an existing object"""
    if parent:
        return parent.createCopy()
    else:
        return _dict_type()

def createCopy(source):
    """Link the source set to the destination
    If one does not find the value in the destination set,
    search will go on to the source set to get the value.
    Value from source are copy-on-write. i.e. any try to
    modify one of them will end up putting the modified value
    in the destination set.
    """
    return source.createCopy()

def initVar(var, d):
    """Non-destructive var init for data structure"""
    d.initVar(var)


def setVar(var, value, d):
    """Set a variable to a given value"""
    d.setVar(var, value)


def getVar(var, d, exp = 0):
    """Gets the value of a variable"""
    return d.getVar(var, exp)


def renameVar(key, newkey, d):
    """Renames a variable from key to newkey"""
    d.renameVar(key, newkey)

def delVar(var, d):
    """Removes a variable from the data set"""
    d.delVar(var)

def setVarFlag(var, flag, flagvalue, d):
    """Set a flag for a given variable to a given value"""
    d.setVarFlag(var, flag, flagvalue)

def getVarFlag(var, flag, d):
    """Gets given flag from given var"""
    return d.getVarFlag(var, flag)

def delVarFlag(var, flag, d):
    """Removes a given flag from the variable's flags"""
    d.delVarFlag(var, flag)

def setVarFlags(var, flags, d):
    """Set the flags for a given variable

    Note:
        setVarFlags will not clear previous
        flags. Think of this method as
        addVarFlags
    """
    d.setVarFlags(var, flags)

def getVarFlags(var, d):
    """Gets a variable's flags"""
    return d.getVarFlags(var)

def delVarFlags(var, d):
    """Removes a variable's flags"""
    d.delVarFlags(var)

def keys(d):
    """Return a list of keys in d"""
    return d.keys()


__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")

def expand(s, d, varname = None):
    """Variable expansion using the data store"""
    return d.expand(s, varname)

def expandKeys(alterdata, readdata = None):
    if readdata == None:
        readdata = alterdata

    todolist = {}
    for key in keys(alterdata):
        if not '${' in key:
            continue

        ekey = expand(key, readdata)
        if key == ekey:
            continue
        todolist[key] = ekey

    # These two for loops are split for performance to maximise the
    # usefulness of the expand cache

    for key in todolist:
        ekey = todolist[key]
        renameVar(key, ekey, alterdata)

def inheritFromOS(d):
    """Inherit variables from the environment."""
    for s in os.environ.keys():
        try:
            setVar(s, os.environ[s], d)
            setVarFlag(s, "export", True, d)
        except TypeError:
            pass

def emit_var(var, o=sys.__stdout__, d = init(), all=False):
    """Emit a variable to be sourced by a shell."""
    if getVarFlag(var, "python", d):
        return 0

    export = getVarFlag(var, "export", d)
    unexport = getVarFlag(var, "unexport", d)
    func = getVarFlag(var, "func", d)
    if not all and not export and not unexport and not func:
        return 0

    try:
        if all:
            oval = getVar(var, d, 0)
        val = getVar(var, d, 1)
    except (KeyboardInterrupt, bb.build.FuncFailed):
        raise
    except Exception, exc:
        o.write('# expansion of %s threw %s: %s\n' % (var, exc.__class__.__name__, str(exc)))
        return 0

    if all:
        o.write('# %s=%s\n' % (var, oval))

    if (var.find("-") != -1 or var.find(".") != -1 or var.find('{') != -1 or var.find('}') != -1 or var.find('+') != -1) and not all:
        return 0

    varExpanded = expand(var, d)

    if unexport:
        o.write('unset %s\n' % varExpanded)
        return 1

    if not val:
        return 0

    val = str(val)

    if func:
        # NOTE: should probably check for unbalanced {} within the var
        o.write("%s() {\n%s\n}\n" % (varExpanded, val))
        return 1

    if export:
        o.write('export ')

    # if we're going to output this within doublequotes,
    # to a shell, we need to escape the quotes in the var
    alter = re.sub('"', '\\"', val.strip())
    o.write('%s="%s"\n' % (varExpanded, alter))
    return 1

def emit_env(o=sys.__stdout__, d = init(), all=False):
    """Emits all items in the data store in a format such that it can be sourced by a shell."""

    isfunc = lambda key: bool(d.getVarFlag(key, "func"))
    keys = sorted((key for key in d.keys() if not key.startswith("__")), key=isfunc)
    grouped = groupby(keys, isfunc)
    for isfunc, keys in grouped:
        for key in keys:
            emit_var(key, o, d, all and not isfunc) and o.write('\n')

def update_data(d):
    """Performs final steps upon the datastore, including application of overrides"""
    d.finalize()

def inherits_class(klass, d):
    val = getVar('__inherit_cache', d) or []
    if os.path.join('classes', '%s.bbclass' % klass) in val:
        return True
    return False
