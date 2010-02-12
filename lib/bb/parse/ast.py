# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
 AbstractSyntaxTree classes for the Bitbake language
"""

# Copyright (C) 2003, 2004 Chris Larson
# Copyright (C) 2003, 2004 Phil Blundell
# Copyright (C) 2009 Holger Hans Peter Freyther
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE. See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import bb, re

__word__ = re.compile(r"\S+")
__parsed_methods__ = methodpool.get_parsed_dict()

def handleInclude(m, fn, lineno, data, force):
    s = bb.data.expand(m.group(1), data)
    bb.msg.debug(3, bb.msg.domain.Parsing, "CONF %s:%d: including %s" % (fn, lineno, s))
    if force:
        include(fn, s, data, "include required")
    else:
        include(fn, s, data, False)

def handleExport(m, data):
    bb.data.setVarFlag(m.group(1), "export", 1, data)

def handleData(groupd, data):
    key = groupd["var"]
    if "exp" in groupd and groupd["exp"] != None:
        bb.data.setVarFlag(key, "export", 1, data)
    if "ques" in groupd and groupd["ques"] != None:
        val = getFunc(groupd, key, data)
        if val == None:
            val = groupd["value"]
    elif "colon" in groupd and groupd["colon"] != None:
        e = data.createCopy()
        bb.data.update_data(e)
        val = bb.data.expand(groupd["value"], e)
    elif "append" in groupd and groupd["append"] != None:
        val = "%s %s" % ((getFunc(groupd, key, data) or ""), groupd["value"])
    elif "prepend" in groupd and groupd["prepend"] != None:
        val = "%s %s" % (groupd["value"], (getFunc(groupd, key, data) or ""))
    elif "postdot" in groupd and groupd["postdot"] != None:
        val = "%s%s" % ((getFunc(groupd, key, data) or ""), groupd["value"])
    elif "predot" in groupd and groupd["predot"] != None:
        val = "%s%s" % (groupd["value"], (getFunc(groupd, key, data) or ""))
    else:
        val = groupd["value"]
    if 'flag' in groupd and groupd['flag'] != None:
        bb.msg.debug(3, bb.msg.domain.Parsing, "setVarFlag(%s, %s, %s, data)" % (key, groupd['flag'], val))
        bb.data.setVarFlag(key, groupd['flag'], val, data)
    else:
        bb.data.setVar(key, val, data)

def getFunc(groupd, key, data):
    if 'flag' in groupd and groupd['flag'] != None:
        return bb.data.getVarFlag(key, groupd['flag'], data)
    else:
        return bb.data.getVar(key, data)

def handleMethod(func_name, lineno, fn, body, d):
    if func_name == "__anonymous":
        funcname = ("__anon_%s_%s" % (lineno, fn.translate(string.maketrans('/.+-', '____'))))
        if not funcname in methodpool._parsed_fns:
            text = "def %s(d):\n" % (funcname) + '\n'.join(body)
            methodpool.insert_method(funcname, text, fn)
        anonfuncs = data.getVar('__BBANONFUNCS', d) or []
        anonfuncs.append(funcname)
        data.setVar('__BBANONFUNCS', anonfuncs, d)
    else:
        data.setVarFlag(func_name, "func", 1, d)
        data.setVar(func_name, '\n'.join(body), d)



def handlePythonMethod(root, body, fn):
    # Note we will add root to parsedmethods after having parse
    # 'this' file. This means we will not parse methods from
    # bb classes twice
    if not root in __parsed_methods__:
        text = '\n'.join(body)
        methodpool.insert_method(root, text, fn)

def handleMethodFlags(key, m, d):
    if data.getVar(key, d):
        # Clean up old version of this piece of metadata, as its
        # flags could cause problems
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

def handleExportFuncs(m, d):
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

def handleAddTask(m, d):
    func = m.group("func")
    before = m.group("before")
    after = m.group("after")
    if func is None:
        return
    if func[:3] != "do_":
        var = "do_" + func

    data.setVarFlag(var, "task", 1, d)

    bbtasks = data.getVar('__BBTASKS', d) or []
    if not var in bbtasks:
        bbtasks.append(var)
    data.setVar('__BBTASKS', bbtasks, d)

    existing = data.getVarFlag(var, "deps", d) or []
    if after is not None:
        # set up deps for function
        for entry in after.split():
            if entry not in existing:
                existing.append(entry)
    data.setVarFlag(var, "deps", existing, d)
    if before is not None:
        # set up things that depend on this func
        for entry in before.split():
            existing = data.getVarFlag(entry, "deps", d) or []
            if var not in existing:
                data.setVarFlag(entry, "deps", [var] + existing, d)

def handleBBHandlers(m, d):
    fns = m.group(1)
    hs = __word__.findall(fns)
    bbhands = data.getVar('__BBHANDLERS', d) or []
    for h in hs:
        bbhands.append(h)
        data.setVarFlag(h, "handler", 1, d)
    data.setVar('__BBHANDLERS', bbhands, d)

def handleInherit(m, d):
    files = m.group(1)
    n = __word__.findall(files)
    inherit(n, d)

