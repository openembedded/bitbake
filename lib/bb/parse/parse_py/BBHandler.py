#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""class for handling .bb files

   Reads a .bb file and obtains its metadata

   Copyright (C) 2003, 2004  Chris Larson
   Copyright (C) 2003, 2004  Phil Blundell
   
   This program is free software; you can redistribute it and/or modify it under
   the terms of the GNU General Public License as published by the Free Software
   Foundation; either version 2 of the License, or (at your option) any later
   version.
   
   This program is distributed in the hope that it will be useful, but WITHOUT
   ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
   FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
   
   You should have received a copy of the GNU General Public License along with
   this program; if not, write to the Free Software Foundation, Inc., 59 Temple
   Place, Suite 330, Boston, MA 02111-1307 USA.""" 

import re, bb, os, sys, time
import bb.fetch, bb.build, bb.utils
from bb import debug, data, fetch, fatal, methodpool

from ConfHandler import include, localpath, obtain, init
from bb.parse import ParseError

__func_start_regexp__    = re.compile( r"(((?P<py>python)|(?P<fr>fakeroot))\s*)*(?P<func>[\w\.\-\+\{\}\$]+)?\s*\(\s*\)\s*{$" )
__inherit_regexp__       = re.compile( r"inherit\s+(.+)" )
__export_func_regexp__   = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )
__addtask_regexp__       = re.compile("addtask\s+(?P<func>\w+)\s*((before\s*(?P<before>((.*(?=after))|(.*))))|(after\s*(?P<after>((.*(?=before))|(.*)))))*")
__addhandler_regexp__    = re.compile( r"addhandler\s+(.+)" )
__def_regexp__           = re.compile( r"def\s+(\w+).*:" )
__python_func_regexp__   = re.compile( r"(\s+.*)|(^$)" )
__word__ = re.compile(r"\S+")

__infunc__ = ""
__inpython__ = False
__body__   = []
__bbpath_found__ = 0
__classname__ = ""
classes = [ None, ]

__parsed_methods__ = methodpool.get_parsed_dict()

def supports(fn, d):
    localfn = localpath(fn, d)
    return localfn[-3:] == ".bb" or localfn[-8:] == ".bbclass" or localfn[-4:] == ".inc"

def inherit(files, d):
    __inherit_cache = data.getVar('__inherit_cache', d) or ""
    fn = ""
    lineno = 0
    for f in files:
        file = data.expand(f, d)
        if file[0] != "/" and file[-8:] != ".bbclass":
            file = os.path.join('classes', '%s.bbclass' % file)

        if not file in __inherit_cache.split():
            debug(2, "BB %s:%d: inheriting %s" % (fn, lineno, file))
            __inherit_cache += " %s" % file
            include(fn, file, d)
    data.setVar('__inherit_cache', __inherit_cache, d)


def handle(fn, d, include = 0):
    global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __infunc__, __body__, __bbpath_found__, __residue__
    __body__ = []
    __bbpath_found__ = 0
    __infunc__ = ""
    __classname__ = ""
    __residue__ = []

    if include == 0:
        debug(2, "BB " + fn + ": handle(data)")
    else:
        debug(2, "BB " + fn + ": handle(data, include)")

    (root, ext) = os.path.splitext(os.path.basename(fn))
    base_name = "%s%s" % (root,ext)
    init(d)

    if ext == ".bbclass":
        __classname__ = root
        classes.append(__classname__)

    if include != 0:
        oldfile = data.getVar('FILE', d)
    else:
        oldfile = None

    fn = obtain(fn, d)
    bbpath = (data.getVar('BBPATH', d, 1) or '').split(':')
    if not os.path.isabs(fn):
        f = None
        for p in bbpath:
            p = data.expand(p, d)
            j = os.path.join(p, fn)
            if os.access(j, os.R_OK):
                abs_fn = j
                f = open(j, 'r')
                break
        if f is None:
            raise IOError("file not found")
    else:
        f = open(fn,'r')
        abs_fn = fn

    if ext != ".bbclass":
        bbpath.insert(0, os.path.dirname(abs_fn))
        data.setVar('BBPATH', ":".join(bbpath), d)

    if include:
        bb.parse.mark_dependency(d, abs_fn)

    if ext != ".bbclass":
        data.setVar('FILE', fn, d)
        i = (data.getVar("INHERIT", d, 1) or "").split()
        if not "base" in i and __classname__ != "base":
            i[0:0] = ["base"]
        inherit(i, d)

    lineno = 0
    while 1:
        lineno = lineno + 1
        s = f.readline()
        if not s: break
        s = s.rstrip()
        feeder(lineno, s, fn, base_name, d)
    if __inpython__:
        # add a blank line to close out any python definition
        feeder(lineno + 1, "", fn, base_name, d)
    if ext == ".bbclass":
        classes.remove(__classname__)
    else:
        if include == 0:
            data.expandKeys(d)
            data.update_data(d)
            anonqueue = data.getVar("__anonqueue", d, 1) or []
            for anon in anonqueue:
                data.setVar("__anonfunc", anon["content"], d)
                data.setVarFlags("__anonfunc", anon["flags"], d)
                from bb import build
                try:
                    t = data.getVar('T', d)
                    data.setVar('T', '${TMPDIR}/', d)
                    build.exec_func("__anonfunc", d)
                    data.delVar('T', d)
                    if t:
                        data.setVar('T', t, d)
                except Exception, e:
                    bb.debug(1, "executing anonymous function: %s" % e)
                    raise
            data.delVar("__anonqueue", d)
            data.delVar("__anonfunc", d)
            set_additional_vars(fn, d, include)
            data.update_data(d)

            all_handlers = {} 
            for var in data.keys(d):
                # try to add the handler
                # if we added it remember the choiche
                if data.getVarFlag(var, 'handler', d):
                    handler = data.getVar(var,d)
                    if bb.event.register(var,handler) == bb.event.Registered:
                        all_handlers[var] = handler

                    continue

                if not data.getVarFlag(var, 'task', d):
                    continue

                deps = data.getVarFlag(var, 'deps', d) or []
                postdeps = data.getVarFlag(var, 'postdeps', d) or []
                bb.build.add_task(var, deps, d)
                for p in postdeps:
                    pdeps = data.getVarFlag(p, 'deps', d) or []
                    pdeps.append(var)
                    data.setVarFlag(p, 'deps', pdeps, d)
                    bb.build.add_task(p, pdeps, d)

            # now add the handlers
            if not len(all_handlers) == 0:
                data.setVar('__all_handlers__', all_handlers, d)

        bbpath.pop(0)
    if oldfile:
        bb.data.setVar("FILE", oldfile, d)

    # we have parsed the bb class now
    if ext == ".bbclass" or ext == ".inc":
        __parsed_methods__[base_name] = 1

    return d

def feeder(lineno, s, fn, root, d):
    global __func_start_regexp__, __inherit_regexp__, __export_func_regexp__, __addtask_regexp__, __addhandler_regexp__, __def_regexp__, __python_func_regexp__, __inpython__,__infunc__, __body__, __bbpath_found__, classes, bb, __residue__
    if __infunc__:
        if s == '}':
            __body__.append('')
            data.setVar(__infunc__, '\n'.join(__body__), d)
            data.setVarFlag(__infunc__, "func", 1, d)
            if __infunc__ == "__anonymous":
                anonqueue = bb.data.getVar("__anonqueue", d) or []
                anonitem = {}
                anonitem["content"] = bb.data.getVar("__anonymous", d)
                anonitem["flags"] = bb.data.getVarFlags("__anonymous", d)
                anonqueue.append(anonitem)
                bb.data.setVar("__anonqueue", anonqueue, d)
                bb.data.delVarFlags("__anonymous", d)
                bb.data.delVar("__anonymous", d)
            __infunc__ = ""
            __body__ = []
        else:
            __body__.append(s)
        return

    if __inpython__:
        m = __python_func_regexp__.match(s)
        if m:
            __body__.append(s)
            return
        else:
            # Note we will add root to parsedmethods after having parse
            # 'this' file. This means we will not parse methods from
            # bb classes twice
            if not root  in __parsed_methods__:
                text = '\n'.join(__body__)
                methodpool.insert_method( root, text, fn )
                funcs = data.getVar('__functions__', d) or {}
                if not funcs.has_key( root ):
                    funcs[root] = text 
                else:
                    funcs[root] = "%s\n%s" % (funcs[root], text)

                data.setVar('__functions__', funcs, d)
            __body__ = []
            __inpython__ = False

#           fall through

    if s == '' or s[0] == '#': return          # skip comments and empty lines

    if s[-1] == '\\':
        __residue__.append(s[:-1])
        return

    s = "".join(__residue__) + s
    __residue__ = []

    m = __func_start_regexp__.match(s)
    if m:
        __infunc__ = m.group("func") or "__anonymous"
        key = __infunc__
        if data.getVar(key, d):
#           clean up old version of this piece of metadata, as its
#           flags could cause problems
            data.setVarFlag(key, 'python', None, d)
            data.setVarFlag(key, 'fakeroot', None, d)
        if m.group("py") is not None:
            data.setVarFlag(key, "python", "1", d)
        else:
            data.delVarFlag(key, "python", d)
        if m.group("fr") is not None:
            data.setVarFlag(key, "fakeroot", "1", d)
        else:
            data.delVarFlag(key, "fakeroot", d)
        return

    m = __def_regexp__.match(s)
    if m:
        __body__.append(s)
        __inpython__ = True
        return

    m = __export_func_regexp__.match(s)
    if m:
        fns = m.group(1)
        n = __word__.findall(fns)
        for f in n:
            allvars = []
            allvars.append(f)
            allvars.append(classes[-1] + "_" + f)

            vars = [[ allvars[0], allvars[1] ]]
            if len(classes) > 1 and classes[-2] is not None:
                allvars.append(classes[-2] + "_" + f)
                vars = []
                vars.append([allvars[2], allvars[1]])
                vars.append([allvars[0], allvars[2]])

            for (var, calledvar) in vars:
                if data.getVar(var, d) and not data.getVarFlag(var, 'export_func', d):
                    continue

                if data.getVar(var, d):
                    data.setVarFlag(var, 'python', None, d)
                    data.setVarFlag(var, 'func', None, d)

                for flag in [ "func", "python" ]:
                    if data.getVarFlag(calledvar, flag, d):
                        data.setVarFlag(var, flag, data.getVarFlag(calledvar, flag, d), d)
                for flag in [ "dirs" ]:
                    if data.getVarFlag(var, flag, d):
                        data.setVarFlag(calledvar, flag, data.getVarFlag(var, flag, d), d)

                if data.getVarFlag(calledvar, "python", d):
                    data.setVar(var, "\tbb.build.exec_func('" + calledvar + "', d)\n", d)
                else:
                    data.setVar(var, "\t" + calledvar + "\n", d)
                data.setVarFlag(var, 'export_func', '1', d)

        return

    m = __addtask_regexp__.match(s)
    if m:
        func = m.group("func")
        before = m.group("before")
        after = m.group("after")
        if func is None:
            return
        var = "do_" + func

        data.setVarFlag(var, "task", 1, d)

        if after is not None:
#           set up deps for function
            data.setVarFlag(var, "deps", after.split(), d)
        if before is not None:
#           set up things that depend on this func
            data.setVarFlag(var, "postdeps", before.split(), d)
        return

    m = __addhandler_regexp__.match(s)
    if m:
        fns = m.group(1)
        hs = __word__.findall(fns)
        for h in hs:
            data.setVarFlag(h, "handler", 1, d)
        return

    m = __inherit_regexp__.match(s)
    if m:

        files = m.group(1)
        n = __word__.findall(files)
        inherit(n, d)
        return

    from bb.parse import ConfHandler
    return ConfHandler.feeder(lineno, s, fn, d)

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

def set_additional_vars(file, d, include):
    """Deduce rest of variables, e.g. ${A} out of ${SRC_URI}"""

    debug(2,"BB %s: set_additional_vars" % file)

    src_uri = data.getVar('SRC_URI', d)
    if not src_uri:
        return
    src_uri = data.expand(src_uri, d)

    a = data.getVar('A', d)
    if a:
        a = data.expand(a, d).split()
    else:
        a = []

    from bb import fetch
    try:
        fetch.init(src_uri.split(), d)
    except fetch.NoMethodError:
        pass
    except bb.MalformedUrl,e:
        raise ParseError("Unable to generate local paths for SRC_URI due to malformed uri: %s" % e)

    a += fetch.localpaths(d)
    del fetch
    data.setVar('A', " ".join(a), d)


# Add us to the handlers list
from bb.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
