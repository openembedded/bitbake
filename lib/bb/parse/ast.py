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

import bb, re, string

__word__ = re.compile(r"\S+")
__parsed_methods__ = bb.methodpool.get_parsed_dict()

class StatementGroup:
    def __init__(self):
        self.statements = []

    def append(self, statement):
        self.statements.append(statement)

    def eval(self, data):
        """
        Apply each statement on the data... in order
        """
        map(lambda x: x.eval(data), self.statements)

    def __getitem__(self, item):
        return self.statements.__getitem__(item)

class IncludeNode:
    def __init__(self, what_file, fn, lineno, force):
        self.what_file = what_file
        self.from_fn = fn
        self.from_lineno = lineno
        self.force = force

    def eval(self, data):
        """
        Include the file and evaluate the statements
        """
        s = bb.data.expand(self.what_file, data)
        bb.msg.debug(3, bb.msg.domain.Parsing, "CONF %s:%d: including %s" % (self.from_fn, self.from_lineno, s))

        # TODO: Cache those includes...
        statements = StatementGroup()
        if self.force:
            bb.parse.ConfHandler.include(statements, self.from_fn, s, data, "include required")
        else:
            bb.parse.ConfHandler.include(statements, self.from_fn, s, data, False)
        #statements.eval(data)

class ExportNode:
    def __init__(self, var):
        self.var = var

    def eval(self, data):
        bb.data.setVarFlag(self.var, "export", 1, data)

class DataNode:
    """
    Various data related updates. For the sake of sanity
    we have one class doing all this. This means that all
    this need to be re-evaluated... we might be able to do
    that faster with multiple classes.
    """
    def __init__(self, groupd):
        self.groupd = groupd

    def getFunc(self, key, data):
        if 'flag' in self.groupd and self.groupd['flag'] != None:
            return bb.data.getVarFlag(key, self.groupd['flag'], data)
        else:
            return bb.data.getVar(key, data)

    def eval(self, data):
        groupd = self.groupd
        key = groupd["var"]
        if "exp" in groupd and groupd["exp"] != None:
            bb.data.setVarFlag(key, "export", 1, data)
        if "ques" in groupd and groupd["ques"] != None:
            val = self.getFunc(key, data)
            if val == None:
                val = groupd["value"]
        elif "colon" in groupd and groupd["colon"] != None:
            e = data.createCopy()
            bb.data.update_data(e)
            val = bb.data.expand(groupd["value"], e)
        elif "append" in groupd and groupd["append"] != None:
            val = "%s %s" % ((self.getFunc(key, data) or ""), groupd["value"])
        elif "prepend" in groupd and groupd["prepend"] != None:
            val = "%s %s" % (groupd["value"], (self.getFunc(key, data) or ""))
        elif "postdot" in groupd and groupd["postdot"] != None:
            val = "%s%s" % ((self.getFunc(key, data) or ""), groupd["value"])
        elif "predot" in groupd and groupd["predot"] != None:
            val = "%s%s" % (groupd["value"], (self.getFunc(key, data) or ""))
        else:
            val = groupd["value"]
        if 'flag' in groupd and groupd['flag'] != None:
            bb.msg.debug(3, bb.msg.domain.Parsing, "setVarFlag(%s, %s, %s, data)" % (key, groupd['flag'], val))
            bb.data.setVarFlag(key, groupd['flag'], val, data)
        else:
            bb.data.setVar(key, val, data)

class MethodNode:
    def __init__(self, func_name, body, lineno, fn):
        self.func_name = func_name
        self.body = body
        self.fn = fn
        self.lineno = lineno

    def eval(self, data):
        if self.func_name == "__anonymous":
            funcname = ("__anon_%s_%s" % (self.lineno, self.fn.translate(string.maketrans('/.+-', '____'))))
            if not funcname in bb.methodpool._parsed_fns:
                text = "def %s(d):\n" % (funcname) + '\n'.join(self.body)
                bb.methodpool.insert_method(funcname, text, self.fn)
            anonfuncs = bb.data.getVar('__BBANONFUNCS', data) or []
            anonfuncs.append(funcname)
            bb.data.setVar('__BBANONFUNCS', anonfuncs, data)
        else:
            bb.data.setVarFlag(self.func_name, "func", 1, data)
            bb.data.setVar(self.func_name, '\n'.join(self.body), data)

class PythonMethodNode:
    def __init__(self, root, body, fn):
        self.root = root
        self.body = body
        self.fn = fn

    def eval(self, data):
        # Note we will add root to parsedmethods after having parse
        # 'this' file. This means we will not parse methods from
        # bb classes twice
        if not self.root  in __parsed_methods__:
            text = '\n'.join(self.body)
            bb.methodpool.insert_method(self.root, text, self.fn)

class MethodFlagsNode:
    def __init__(self, key, m):
        self.key = key
        self.m = m

    def eval(self, data):
        if bb.data.getVar(self.key, data):
            # clean up old version of this piece of metadata, as its
            # flags could cause problems
            bb.data.setVarFlag(self.key, 'python', None, data)
            bb.data.setVarFlag(self.key, 'fakeroot', None, data)
        if self.m.group("py") is not None:
            bb.data.setVarFlag(self.key, "python", "1", data)
        else:
            bb.data.delVarFlag(self.key, "python", data)
        if self.m.group("fr") is not None:
            bb.data.setVarFlag(self.key, "fakeroot", "1", data)
        else:
            bb.data.delVarFlag(self.key, "fakeroot", data)

def handleInclude(statements, m, fn, lineno, data, force):
    # AST handling
    statements.append(IncludeNode(m.group(1), fn, lineno, force))
    statements[-1].eval(data)

def handleExport(statements, m, data):
    # AST handling
    statements.append(ExportNode(m.group(1)))
    statements[-1].eval(data)

def handleData(statements, groupd, data):
    # AST handling
    statements.append(DataNode(groupd))
    statements[-1].eval(data)

def handleMethod(statements, func_name, lineno, fn, body, d):
    # AST handling
    statements.append(MethodNode(func_name, body, lineno, fn))
    statements[-1].eval(d)

def handlePythonMethod(statements, root, body, fn):
    # AST handling
    statements.append(PythonMethodNode(root, body, fn))
    statements[-1].eval(None)

def handleMethodFlags(statements, key, m, d):
    statements.append(MethodFlagsNode(key, m))
    statements[-1].eval(d)

def handleExportFuncs(statements, m, classes, d):
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
            if bb.data.getVar(var, d) and not bb.data.getVarFlag(var, 'export_func', d):
                continue

            if bb.data.getVar(var, d):
                bb.data.setVarFlag(var, 'python', None, d)
                bb.data.setVarFlag(var, 'func', None, d)

            for flag in [ "func", "python" ]:
                if bb.data.getVarFlag(calledvar, flag, d):
                    bb.data.setVarFlag(var, flag, bb.data.getVarFlag(calledvar, flag, d), d)
            for flag in [ "dirs" ]:
                if bb.data.getVarFlag(var, flag, d):
                    bb.data.setVarFlag(calledvar, flag, bb.data.getVarFlag(var, flag, d), d)

            if bb.data.getVarFlag(calledvar, "python", d):
                bb.data.setVar(var, "\tbb.build.exec_func('" + calledvar + "', d)\n", d)
            else:
                bb.data.setVar(var, "\t" + calledvar + "\n", d)
            bb.data.setVarFlag(var, 'export_func', '1', d)

def handleAddTask(statements, m, d):
    func = m.group("func")
    before = m.group("before")
    after = m.group("after")
    if func is None:
        return
    if func[:3] != "do_":
        var = "do_" + func

    bb.data.setVarFlag(var, "task", 1, d)

    bbtasks = bb.data.getVar('__BBTASKS', d) or []
    if not var in bbtasks:
        bbtasks.append(var)
    bb.data.setVar('__BBTASKS', bbtasks, d)

    existing = bb.data.getVarFlag(var, "deps", d) or []
    if after is not None:
        # set up deps for function
        for entry in after.split():
            if entry not in existing:
                existing.append(entry)
    bb.data.setVarFlag(var, "deps", existing, d)
    if before is not None:
        # set up things that depend on this func
        for entry in before.split():
            existing = bb.data.getVarFlag(entry, "deps", d) or []
            if var not in existing:
                bb.data.setVarFlag(entry, "deps", [var] + existing, d)

def handleBBHandlers(statements, m, d):
    fns = m.group(1)
    hs = __word__.findall(fns)
    bbhands = bb.data.getVar('__BBHANDLERS', d) or []
    for h in hs:
        bbhands.append(h)
        bb.data.setVarFlag(h, "handler", 1, d)
    bb.data.setVar('__BBHANDLERS', bbhands, d)

def handleInherit(statements, m, d):
    files = m.group(1)
    n = __word__.findall(files)
    bb.parse.BBHandler.inherit(statements, n, d)

def finalise(fn, d):
    bb.data.expandKeys(d)
    bb.data.update_data(d)
    anonqueue = bb.data.getVar("__anonqueue", d, 1) or []
    body = [x['content'] for x in anonqueue]
    flag = { 'python' : 1, 'func' : 1 }
    bb.data.setVar("__anonfunc", "\n".join(body), d)
    bb.data.setVarFlags("__anonfunc", flag, d)
    from bb import build
    try:
        t = bb.data.getVar('T', d)
        bb.data.setVar('T', '${TMPDIR}/anonfunc/', d)
        anonfuncs = bb.data.getVar('__BBANONFUNCS', d) or []
        code = ""
        for f in anonfuncs:
            code = code + "    %s(d)\n" % f
        bb.data.setVar("__anonfunc", code, d)        
        build.exec_func("__anonfunc", d)
        bb.data.delVar('T', d)
        if t:
            bb.data.setVar('T', t, d)
    except Exception, e:
        bb.msg.debug(1, bb.msg.domain.Parsing, "Exception when executing anonymous function: %s" % e)
        raise
    bb.data.delVar("__anonqueue", d)
    bb.data.delVar("__anonfunc", d)
    bb.data.update_data(d)

    all_handlers = {} 
    for var in bb.data.getVar('__BBHANDLERS', d) or []:
        # try to add the handler
        handler = bb.data.getVar(var,d)
        bb.event.register(var, handler)

    tasklist = bb.data.getVar('__BBTASKS', d) or []
    bb.build.add_tasks(tasklist, d)

    bb.event.fire(bb.event.RecipeParsed(fn), d)

