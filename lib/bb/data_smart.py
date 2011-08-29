# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake Smart Dictionary Implementation

Functions for interacting with the data structure used by the
BitBake build tools.

"""

# Copyright (C) 2003, 2004  Chris Larson
# Copyright (C) 2004, 2005  Seb Frankengul
# Copyright (C) 2005, 2006  Holger Hans Peter Freyther
# Copyright (C) 2005        Uli Luckas
# Copyright (C) 2005        ROAD GmbH
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
# Based on functions from the base bb module, Copyright 2003 Holger Schurig

import copy, re
from collections import MutableMapping
import logging
import bb, bb.codeparser
from bb   import utils
from bb.COW  import COWDictBase

logger = logging.getLogger("BitBake.Data")

__setvar_keyword__ = ["_append", "_prepend"]
__setvar_regexp__ = re.compile('(?P<base>.*?)(?P<keyword>_append|_prepend)(_(?P<add>.*))?')
__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")


class VariableParse:
    def __init__(self, varname, d, val = None):
        self.varname = varname
        self.d = d
        self.value = val

        self.references = set()
        self.execs = set()

    def var_sub(self, match):
            key = match.group()[2:-1]
            if self.varname and key:
                if self.varname == key:
                    raise Exception("variable %s references itself!" % self.varname)
            var = self.d.getVar(key, 1)
            if var is not None:
                self.references.add(key)
                return var
            else:
                return match.group()

    def python_sub(self, match):
            code = match.group()[3:-1]
            codeobj = compile(code.strip(), self.varname or "<expansion>", "eval")

            parser = bb.codeparser.PythonParser()
            parser.parse_python(code)
            self.references |= parser.references
            self.execs |= parser.execs

            value = utils.better_eval(codeobj, DataContext(self.d))
            return str(value)


class DataContext(dict):
    def __init__(self, metadata, **kwargs):
        self.metadata = metadata
        dict.__init__(self, **kwargs)
        self['d'] = metadata

    def __missing__(self, key):
        value = self.metadata.getVar(key, True)
        if value is None or self.metadata.getVarFlag(key, 'func'):
            raise KeyError(key)
        else:
            return value

class ExpansionError(Exception):
    def __init__(self, varname, expression, exception):
        self.expression = expression
        self.variablename = varname
        self.exception = exception
        self.msg = "Failure expanding variable %s, expression was %s which triggered exception %s: %s" % (varname, expression, type(exception).__name__, exception)
        Exception.__init__(self, self.msg)
        self.args = (varname, expression, exception)
    def __str__(self):
        return self.msg

class DataSmart(MutableMapping):
    def __init__(self, special = COWDictBase.copy(), seen = COWDictBase.copy() ):
        self.dict = {}

        # cookie monster tribute
        self._special_values = special
        self._seen_overrides = seen

        self.expand_cache = {}

    def expandWithRefs(self, s, varname):

        if not isinstance(s, basestring): # sanity check
            return VariableParse(varname, self, s)

        if varname and varname in self.expand_cache:
            return self.expand_cache[varname]

        varparse = VariableParse(varname, self)

        while s.find('${') != -1:
            olds = s
            try:
                s = __expand_var_regexp__.sub(varparse.var_sub, s)
                s = __expand_python_regexp__.sub(varparse.python_sub, s)
                if s == olds:
                    break
            except ExpansionError:
                raise
            except Exception as exc:
                raise ExpansionError(varname, s, exc)

        varparse.value = s

        if varname:
            self.expand_cache[varname] = varparse

        return varparse

    def expand(self, s, varname):
        return self.expandWithRefs(s, varname).value


    def finalize(self):
        """Performs final steps upon the datastore, including application of overrides"""

        overrides = (self.getVar("OVERRIDES", True) or "").split(":") or []

        #
        # Well let us see what breaks here. We used to iterate
        # over each variable and apply the override and then
        # do the line expanding.
        # If we have bad luck - which we will have - the keys
        # where in some order that is so important for this
        # method which we don't have anymore.
        # Anyway we will fix that and write test cases this
        # time.

        #
        # First we apply all overrides
        # Then  we will handle _append and _prepend
        #

        for o in overrides:
            # calculate '_'+override
            l = len(o) + 1

            # see if one should even try
            if o not in self._seen_overrides:
                continue

            vars = self._seen_overrides[o].copy()
            for var in vars:
                name = var[:-l]
                try:
                    self.setVar(name, self.getVar(var, False))
                    self.delVar(var)
                except Exception:
                    logger.info("Untracked delVar")

        # now on to the appends and prepends
        for op in __setvar_keyword__:
            if op in self._special_values:
                appends = self._special_values[op] or []
                for append in appends:
                    keep = []
                    for (a, o) in self.getVarFlag(append, op) or []:
                        if o and not o in overrides:
                            keep.append((a ,o))
                            continue

                        if op == "_append":
                            sval = self.getVar(append, False) or ""
                            sval += a
                            self.setVar(append, sval)
                        elif op == "_prepend":
                            sval = a + (self.getVar(append, False) or "")
                            self.setVar(append, sval)

                    # We save overrides that may be applied at some later stage
                    if keep:
                        self.setVarFlag(append, op, keep)
                    else:
                        self.delVarFlag(append, op)

    def initVar(self, var):
        self.expand_cache = {}
        if not var in self.dict:
            self.dict[var] = {}

    def _findVar(self, var):
        dest = self.dict
        while dest:
            if var in dest:
                return dest[var]

            if "_data" not in dest:
                break
            dest = dest["_data"]

    def _makeShadowCopy(self, var):
        if var in self.dict:
            return

        local_var = self._findVar(var)

        if local_var:
            self.dict[var] = copy.copy(local_var)
        else:
            self.initVar(var)

    def setVar(self, var, value):
        self.expand_cache = {}
        match  = __setvar_regexp__.match(var)
        if match and match.group("keyword") in __setvar_keyword__:
            base = match.group('base')
            keyword = match.group("keyword")
            override = match.group('add')
            l = self.getVarFlag(base, keyword) or []
            l.append([value, override])
            self.setVarFlag(base, keyword, l)

            # todo make sure keyword is not __doc__ or __module__
            # pay the cookie monster
            try:
                self._special_values[keyword].add( base )
            except KeyError:
                self._special_values[keyword] = set()
                self._special_values[keyword].add( base )

            return

        if not var in self.dict:
            self._makeShadowCopy(var)

        # more cookies for the cookie monster
        if '_' in var:
            override = var[var.rfind('_')+1:]
            if len(override) > 0:
                if override not in self._seen_overrides:
                    self._seen_overrides[override] = set()
                self._seen_overrides[override].add( var )

        # setting var
        self.dict[var]["content"] = value

    def getVar(self, var, expand=False, noweakdefault=False):
        value = self.getVarFlag(var, "content", False, noweakdefault)

        # Call expand() separately to make use of the expand cache
        if expand and value:
            return self.expand(value, var)
        return value

    def renameVar(self, key, newkey):
        """
        Rename the variable key to newkey
        """
        val = self.getVar(key, 0)
        if val is not None:
            self.setVar(newkey, val)

        for i in ('_append', '_prepend'):
            src = self.getVarFlag(key, i)
            if src is None:
                continue

            dest = self.getVarFlag(newkey, i) or []
            dest.extend(src)
            self.setVarFlag(newkey, i, dest)

            if i in self._special_values and key in self._special_values[i]:
                self._special_values[i].remove(key)
                self._special_values[i].add(newkey)

        self.delVar(key)

    def delVar(self, var):
        self.expand_cache = {}
        self.dict[var] = {}
        if '_' in var:
            override = var[var.rfind('_')+1:]
            if override and override in self._seen_overrides and var in self._seen_overrides[override]:
                self._seen_overrides[override].remove(var)

    def setVarFlag(self, var, flag, flagvalue):
        if not var in self.dict:
            self._makeShadowCopy(var)
        self.dict[var][flag] = flagvalue

    def getVarFlag(self, var, flag, expand=False, noweakdefault=False):
        local_var = self._findVar(var)
        value = None
        if local_var:
            if flag in local_var:
                value = copy.copy(local_var[flag])
            elif flag == "content" and "defaultval" in local_var and not noweakdefault:
                value = copy.copy(local_var["defaultval"])
        if expand and value:
            value = self.expand(value, None)
        return value

    def delVarFlag(self, var, flag):
        local_var = self._findVar(var)
        if not local_var:
            return
        if not var in self.dict:
            self._makeShadowCopy(var)

        if var in self.dict and flag in self.dict[var]:
            del self.dict[var][flag]

    def setVarFlags(self, var, flags):
        if not var in self.dict:
            self._makeShadowCopy(var)

        for i in flags:
            if i == "content":
                continue
            self.dict[var][i] = flags[i]

    def getVarFlags(self, var):
        local_var = self._findVar(var)
        flags = {}

        if local_var:
            for i in local_var:
                if i == "content":
                    continue
                flags[i] = local_var[i]

        if len(flags) == 0:
            return None
        return flags


    def delVarFlags(self, var):
        if not var in self.dict:
            self._makeShadowCopy(var)

        if var in self.dict:
            content = None

            # try to save the content
            if "content" in self.dict[var]:
                content  = self.dict[var]["content"]
                self.dict[var]            = {}
                self.dict[var]["content"] = content
            else:
                del self.dict[var]


    def createCopy(self):
        """
        Create a copy of self by setting _data to self
        """
        # we really want this to be a DataSmart...
        data = DataSmart(seen=self._seen_overrides.copy(), special=self._special_values.copy())
        data.dict["_data"] = self.dict

        return data

    def expandVarref(self, variable, parents=False):
        """Find all references to variable in the data and expand it
           in place, optionally descending to parent datastores."""

        if parents:
            keys = iter(self)
        else:
            keys = self.localkeys()

        ref = '${%s}' % variable
        value = self.getVar(variable, False)
        for key in keys:
            referrervalue = self.getVar(key, False)
            if referrervalue and ref in referrervalue:
                self.setVar(key, referrervalue.replace(ref, value))

    def localkeys(self):
        for key in self.dict:
            if key != '_data':
                yield key

    def __iter__(self):
        def keylist(d):        
            klist = set()
            for key in d:
                if key == "_data":
                    continue
                if not d[key]:
                    continue
                klist.add(key)

            if "_data" in d:
                klist |= keylist(d["_data"])

            return klist

        for k in keylist(self.dict):
             yield k

    def __len__(self):
        return len(frozenset(self))

    def __getitem__(self, item):
        value = self.getVar(item, False)
        if value is None:
            raise KeyError(item)
        else:
            return value

    def __setitem__(self, var, value):
        self.setVar(var, value)

    def __delitem__(self, var):
        self.delVar(var)
