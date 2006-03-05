#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'Data' implementations

Functions for interacting with the data structure used by the
BitBake build tools.

Copyright (C) 2003, 2004  Chris Larson
Copyright (C) 2005        Holger Hans Peter Freyther

This program is free software; you can redistribute it and/or modify it under
the terms of the GNU General Public License as published by the Free Software
Foundation; either version 2 of the License, or (at your option) any later
version.

This program is distributed in the hope that it will be useful, but WITHOUT
ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.

You should have received a copy of the GNU General Public License along with
this program; if not, write to the Free Software Foundation, Inc., 59 Temple
Place, Suite 330, Boston, MA 02111-1307 USA. 

Based on functions from the base bb module, Copyright 2003 Holger Schurig
"""

import sys, os, re, time, types
if sys.argv[0][-5:] == "pydoc":
    path = os.path.dirname(os.path.dirname(sys.argv[1]))
else:
    path = os.path.dirname(os.path.dirname(sys.argv[0]))
sys.path.insert(0,path)

from bb import note, debug, data_smart

_dict_type = data_smart.DataSmart
_dict_p_type = data_smart.DataSmartPackage

class DataDictFull(dict):
    """
    This implements our Package Data Storage Interface.
    setDirty is a no op as all items are held in memory
    """
    def setDirty(self, bbfile, data):
        """
        No-Op we assume data was manipulated as some sort of
        reference
        """
        if not bbfile in self:
            raise Exception("File %s was not in dictionary before" % bbfile)

        self[bbfile] = data

class DataDictCache:
    """
    Databacked Dictionary implementation
    """
    def __init__(self, cache_dir, config):
        self.cache_dir = cache_dir
        self.files     = []
        self.dirty     = {}
        self.config    = config

    def has_key(self,key):
        return key in self.files

    def keys(self):
        return self.files

    def __setitem__(self, key, data):
        """
        Add the key to the list of known files and
        place the data in the cache?
        """
        if key in self.files:
            return

        self.files.append(key)

    def __getitem__(self, key):
        if not key in self.files:
            return None

        # if it was dirty we will
        if key in self.dirty:
            return self.dirty[key]

        # not cached yet
        return _dict_p_type(self.cache_dir, key,False,self.config)

    def setDirty(self, bbfile, data):
        """
        Only already added items can be declared dirty!!!
        """

        if not bbfile in self.files:
            raise Exception("File %s was not in dictionary before" % bbfile)

        self.dirty[bbfile] = data



def init():
    return _dict_type()

def init_db(cache,name,clean,parent = None):
    return _dict_p_type(cache,name,clean,parent)

def init_db_mtime(cache,cache_bbfile):
    return _dict_p_type.mtime(cache,cache_bbfile)

def pkgdata(use_cache, cache, config = None):
    """
    Return some sort of dictionary to lookup parsed dictionaires
    """
    if use_cache:
        return DataDictCache(cache, config)
    return DataDictFull()

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
    """Set a variable to a given value

    Example:
        >>> d = init()
        >>> setVar('TEST', 'testcontents', d)
        >>> print getVar('TEST', d)
        testcontents
    """
    d.setVar(var,value)


def getVar(var, d, exp = 0):
    """Gets the value of a variable

    Example:
        >>> d = init()
        >>> setVar('TEST', 'testcontents', d)
        >>> print getVar('TEST', d)
        testcontents
    """
    return d.getVar(var,exp)

def delVar(var, d):
    """Removes a variable from the data set

    Example:
        >>> d = init()
        >>> setVar('TEST', 'testcontents', d)
        >>> print getVar('TEST', d)
        testcontents
        >>> delVar('TEST', d)
        >>> print getVar('TEST', d)
        None
    """
    d.delVar(var)

def setVarFlag(var, flag, flagvalue, d):
    """Set a flag for a given variable to a given value

    Example:
        >>> d = init()
        >>> setVarFlag('TEST', 'python', 1, d)
        >>> print getVarFlag('TEST', 'python', d)
        1
    """
    d.setVarFlag(var,flag,flagvalue)

def getVarFlag(var, flag, d):
    """Gets given flag from given var

    Example:
        >>> d = init()
        >>> setVarFlag('TEST', 'python', 1, d)
        >>> print getVarFlag('TEST', 'python', d)
        1
    """
    return d.getVarFlag(var,flag)

def delVarFlag(var, flag, d):
    """Removes a given flag from the variable's flags

    Example:
        >>> d = init()
        >>> setVarFlag('TEST', 'testflag', 1, d)
        >>> print getVarFlag('TEST', 'testflag', d)
        1
        >>> delVarFlag('TEST', 'testflag', d)
        >>> print getVarFlag('TEST', 'testflag', d)
        None

    """
    d.delVarFlag(var,flag)

def setVarFlags(var, flags, d):
    """Set the flags for a given variable

    Note:
        setVarFlags will not clear previous
        flags. Think of this method as
        addVarFlags

    Example:
        >>> d = init()
        >>> myflags = {}
        >>> myflags['test'] = 'blah'
        >>> setVarFlags('TEST', myflags, d)
        >>> print getVarFlag('TEST', 'test', d)
        blah
    """
    d.setVarFlags(var,flags)

def getVarFlags(var, d):
    """Gets a variable's flags

    Example:
        >>> d = init()
        >>> setVarFlag('TEST', 'test', 'blah', d)
        >>> print getVarFlags('TEST', d)['test']
        blah
    """
    return d.getVarFlags(var)

def delVarFlags(var, d):
    """Removes a variable's flags

    Example:
        >>> data = init()
        >>> setVarFlag('TEST', 'testflag', 1, data)
        >>> print getVarFlag('TEST', 'testflag', data)
        1
        >>> delVarFlags('TEST', data)
        >>> print getVarFlags('TEST', data)
        None

    """
    d.delVarFlags(var)

def keys(d):
    """Return a list of keys in d

    Example:
        >>> d = init()
        >>> setVar('TEST',  1, d)
        >>> setVar('MOO' ,  2, d)
        >>> setVarFlag('TEST', 'test', 1, d)
        >>> keys(d)
        ['TEST', 'MOO']
    """
    return d.keys()

def getData(d):
    """Returns the data object used"""
    return d

def setData(newData, d):
    """Sets the data object to the supplied value"""
    d = newData

__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")

def expand(s, d, varname = None):
    """Variable expansion using the data store.

    Example:
        Standard expansion:
        >>> d = init()
        >>> setVar('A', 'sshd', d)
        >>> print expand('/usr/bin/${A}', d)
        /usr/bin/sshd

        Python expansion:
        >>> d = init()
        >>> print expand('result: ${@37 * 72}', d)
        result: 2664

        Shell expansion:
        >>> d = init()
        >>> print expand('${TARGET_MOO}', d)
        ${TARGET_MOO}
        >>> setVar('TARGET_MOO', 'yupp', d)
        >>> print expand('${TARGET_MOO}',d)
        yupp
        >>> setVar('SRC_URI', 'http://somebug.${TARGET_MOO}', d)
        >>> delVar('TARGET_MOO', d)
        >>> print expand('${SRC_URI}', d)
        http://somebug.${TARGET_MOO}
    """
    def var_sub(match):
        key = match.group()[2:-1]
        if varname and key:
            if varname == key:
                raise Exception("variable %s references itself!" % varname)
        var = getVar(key, d, 1)
        if var is not None:
            return var
        else:
            return match.group()

    def python_sub(match):
        import bb
        code = match.group()[3:-1]
        locals()['d'] = d
        s = eval(code)
        if type(s) == types.IntType: s = str(s)
        return s

    if type(s) is not types.StringType: # sanity check
        return s

    while s.find('$') != -1:
        olds = s
        try:
            s = __expand_var_regexp__.sub(var_sub, s)
            s = __expand_python_regexp__.sub(python_sub, s)
            if s == olds: break
            if type(s) is not types.StringType: # sanity check
                import bb
                bb.error('expansion of %s returned non-string %s' % (olds, s))
        except KeyboardInterrupt:
            raise
        except:
            note("%s:%s while evaluating:\n%s" % (sys.exc_info()[0], sys.exc_info()[1], s))
            raise
    return s

def expandKeys(alterdata, readdata = None):
    if readdata == None:
        readdata = alterdata

    for key in keys(alterdata):
        ekey = expand(key, readdata)
        if key == ekey:
            continue
        val = getVar(key, alterdata)
        if val is None:
            continue
#        import copy
#        setVarFlags(ekey, copy.copy(getVarFlags(key, readdata)), alterdata)
        setVar(ekey, val, alterdata)

        for i in ('_append', '_prepend', '_delete'):
            dest = getVarFlag(ekey, i, alterdata) or []
            src = getVarFlag(key, i, readdata) or []
            dest.extend(src)
            setVarFlag(ekey, i, dest, alterdata)

        delVar(key, alterdata)

def expandData(alterdata, readdata = None):
    """For each variable in alterdata, expand it, and update the var contents.
       Replacements use data from readdata.

    Example:
        >>> a=init()
        >>> b=init()
        >>> setVar("dlmsg", "dl_dir is ${DL_DIR}", a)
        >>> setVar("DL_DIR", "/path/to/whatever", b)
        >>> expandData(a, b)
        >>> print getVar("dlmsg", a)
        dl_dir is /path/to/whatever
       """
    if readdata == None:
        readdata = alterdata

    for key in keys(alterdata):
        val = getVar(key, alterdata)
        if type(val) is not types.StringType:
            continue
        expanded = expand(val, readdata)
#       print "key is %s, val is %s, expanded is %s" % (key, val, expanded)
        if val != expanded:
            setVar(key, expanded, alterdata)

import os

def inheritFromOS(d):
    """Inherit variables from the environment."""
#   fakeroot needs to be able to set these
    non_inherit_vars = [ "LD_LIBRARY_PATH", "LD_PRELOAD" ]
    for s in os.environ.keys():
        if not s in non_inherit_vars:
            try:
                setVar(s, os.environ[s], d)
                setVarFlag(s, 'matchesenv', '1', d)
            except TypeError:
                pass

import sys

def emit_var(var, o=sys.__stdout__, d = init(), all=False):
    """Emit a variable to be sourced by a shell."""
    if getVarFlag(var, "python", d):
        return 0

    try:
        if all:
            oval = getVar(var, d, 0)
        val = getVar(var, d, 1)
    except KeyboardInterrupt:
        raise
    except:
        excname = str(sys.exc_info()[0])
        if excname == "bb.build.FuncFailed":
            raise
        o.write('# expansion of %s threw %s\n' % (var, excname))
        return 0

    if all:
        o.write('# %s=%s\n' % (var, oval))

    if type(val) is not types.StringType:
        return 0

    if getVarFlag(var, 'matchesenv', d):
        return 0

    if (var.find("-") != -1 or var.find(".") != -1 or var.find('{') != -1 or var.find('}') != -1 or var.find('+') != -1) and not all:
        return 0

    val.rstrip()
    if not val:
        return 0

    if getVarFlag(var, "func", d):
#       NOTE: should probably check for unbalanced {} within the var
        o.write("%s() {\n%s\n}\n" % (var, val))
    else:
        if getVarFlag(var, "export", d):
            o.write('export ')
        else:
            if not all:
                return 0
#       if we're going to output this within doublequotes,
#       to a shell, we need to escape the quotes in the var
        alter = re.sub('"', '\\"', val.strip())
        o.write('%s="%s"\n' % (var, alter))
    return 1


def emit_env(o=sys.__stdout__, d = init(), all=False):
    """Emits all items in the data store in a format such that it can be sourced by a shell."""

    env = keys(d)

    for e in env:
        if getVarFlag(e, "func", d):
            continue
        emit_var(e, o, d, all) and o.write('\n')

    for e in env:
        if not getVarFlag(e, "func", d):
            continue
        emit_var(e, o, d) and o.write('\n')

def update_data(d):
    """Modifies the environment vars according to local overrides and commands.
    Examples:
        Appending to a variable:
        >>> d = init()
        >>> setVar('TEST', 'this is a', d)
        >>> setVar('TEST_append', ' test', d)
        >>> setVar('TEST_append', ' of the emergency broadcast system.', d)
        >>> update_data(d)
        >>> print getVar('TEST', d)
        this is a test of the emergency broadcast system.

        Prepending to a variable:
        >>> setVar('TEST', 'virtual/libc', d)
        >>> setVar('TEST_prepend', 'virtual/tmake ', d)
        >>> setVar('TEST_prepend', 'virtual/patcher ', d)
        >>> update_data(d)
        >>> print getVar('TEST', d)
        virtual/patcher virtual/tmake virtual/libc

        Overrides:
        >>> setVar('TEST_arm', 'target', d)
        >>> setVar('TEST_ramses', 'machine', d)
        >>> setVar('TEST_local', 'local', d)
        >>> setVar('OVERRIDES', 'arm', d)

        >>> setVar('TEST', 'original', d)
        >>> update_data(d)
        >>> print getVar('TEST', d)
        target

        >>> setVar('OVERRIDES', 'arm:ramses:local', d)
        >>> setVar('TEST', 'original', d)
        >>> update_data(d)
        >>> print getVar('TEST', d)
        local
    """

    debug(2, "update_data()")

#   can't do delete env[...] while iterating over the dictionary, so remember them
    dodel = []
    overrides = (getVar('OVERRIDES', d, 1) or "").split(':') or []

    def applyOverrides(var, d):
        if not overrides:
            debug(1, "OVERRIDES not defined, nothing to do")
            return
        val = getVar(var, d)
        for o in overrides:
            if var.endswith("_" + o):
                l = len(o)+1
                name = var[:-l]
                d[name] = d[var]

    for s in keys(d):
        applyOverrides(s, d)
        sval = getVar(s, d) or ""

#       Handle line appends:
        for (a, o) in getVarFlag(s, '_append', d) or []:
            # maybe the OVERRIDE was not yet added so keep the append
            if (o and o in overrides) or not o:
                delVarFlag(s, '_append', d)
            if o:
                if not o in overrides:
                    continue
            sval+=a
            setVar(s, sval, d)

#       Handle line prepends
        for (a, o) in getVarFlag(s, '_prepend', d) or []:
            # maybe the OVERRIDE was not yet added so keep the append
            if (o and o in overrides) or not o:
                delVarFlag(s, '_prepend', d)
            if o:
                if not o in overrides:
                    continue
            sval=a+sval
            setVar(s, sval, d)

#       Handle line deletions
        name = s + "_delete"
        nameval = getVar(name, d)
        if nameval:
            sval = getVar(s, d)
            if sval:
                new = ''
                pattern = nameval.replace('\n','').strip()
                for line in sval.split('\n'):
                    if line.find(pattern) == -1:
                        new = new + '\n' + line
                setVar(s, new, d)
                dodel.append(name)

#   delete all environment vars no longer needed
    for s in dodel:
        delVar(s, d)

def inherits_class(klass, d):
    val = getVar('__inherit_cache', d) or ""
    if os.path.join('classes', '%s.bbclass' % klass) in val.split():
        return True
    return False

def _test():
    """Start a doctest run on this module"""
    import doctest
    from bb import data
    doctest.testmod(data)

if __name__ == "__main__":
    _test()
