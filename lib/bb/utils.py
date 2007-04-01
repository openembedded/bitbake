# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake Utility Functions
"""

# Copyright (C) 2004 Michael Lauer
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

digits = "0123456789"
ascii_letters = "abcdefghijklmnopqrstuvwxyzABCDEFGHIJKLMNOPQRSTUVWXYZ"

import re

def explode_version(s):
    r = []
    alpha_regexp = re.compile('^([a-zA-Z]+)(.*)$')
    numeric_regexp = re.compile('^(\d+)(.*)$')
    while (s != ''):
        if s[0] in digits:
            m = numeric_regexp.match(s)
            r.append(int(m.group(1)))
            s = m.group(2)
            continue
        if s[0] in ascii_letters:
            m = alpha_regexp.match(s)
            r.append(m.group(1))
            s = m.group(2)
            continue
        s = s[1:]
    return r

def vercmp_part(a, b):
    va = explode_version(a)
    vb = explode_version(b)
    while True:
        if va == []:
            ca = None
        else:
            ca = va.pop(0)
        if vb == []:
            cb = None
        else:
            cb = vb.pop(0)
        if ca == None and cb == None:
            return 0
        if ca > cb:
            return 1
        if ca < cb:
            return -1

def vercmp(ta, tb):
    (ea, va, ra) = ta
    (eb, vb, rb) = tb

    r = int(ea)-int(eb)
    if (r == 0):
        r = vercmp_part(va, vb)
    if (r == 0):
        r = vercmp_part(ra, rb)
    return r

def explode_deps(s):
    """
    Take an RDEPENDS style string of format:
    "DEPEND1 (optional version) DEPEND2 (optional version) ..."
    and return a list of dependencies.
    Version information is ignored.
    """
    r = []
    l = s.split()
    flag = False
    for i in l:
        if i[0] == '(':
            flag = True
            j = []
        if flag:
            j.append(i)
        else:
            r.append(i)
        if flag and i.endswith(')'):
            flag = False
            # Ignore version
            #r[-1] += ' ' + ' '.join(j)
    return r



def _print_trace(body, line):
    """
    Print the Environment of a Text Body
    """
    import bb

    # print the environment of the method
    bb.msg.error(bb.msg.domain.Util, "Printing the environment of the function")
    min_line = max(1,line-4)
    max_line = min(line+4,len(body)-1)
    for i in range(min_line,max_line+1):
        bb.msg.error(bb.msg.domain.Util, "\t%.4d:%s" % (i, body[i-1]) )


def better_compile(text, file, realfile):
    """
    A better compile method. This method
    will print  the offending lines.
    """
    try:
        return compile(text, file, "exec")
    except Exception, e:
        import bb,sys

        # split the text into lines again
        body = text.split('\n')
        bb.msg.error(bb.msg.domain.Util, "Error in compiling: ", realfile)
        bb.msg.error(bb.msg.domain.Util, "The lines resulting into this error were:")
        bb.msg.error(bb.msg.domain.Util, "\t%d:%s:'%s'" % (e.lineno, e.__class__.__name__, body[e.lineno-1]))

        _print_trace(body, e.lineno)

        # exit now
        sys.exit(1)

def better_exec(code, context, text, realfile):
    """
    Similiar to better_compile, better_exec will
    print the lines that are responsible for the
    error.
    """
    import bb,sys
    try:
        exec code in context
    except:
        (t,value,tb) = sys.exc_info()

        if t in [bb.parse.SkipPackage, bb.build.FuncFailed]:
            raise

        # print the Header of the Error Message
        bb.msg.error(bb.msg.domain.Util, "Error in executing: ", realfile)
        bb.msg.error(bb.msg.domain.Util, "Exception:%s Message:%s" % (t,value) )

        # let us find the line number now
        while tb.tb_next:
            tb = tb.tb_next

        import traceback
        line = traceback.tb_lineno(tb)

        _print_trace( text.split('\n'), line )
        
        raise

def Enum(*names):
   """
   A simple class to give Enum support
   """

   assert names, "Empty enums are not supported"

   class EnumClass(object):
      __slots__ = names
      def __iter__(self):        return iter(constants)
      def __len__(self):         return len(constants)
      def __getitem__(self, i):  return constants[i]
      def __repr__(self):        return 'Enum' + str(names)
      def __str__(self):         return 'enum ' + str(constants)

   class EnumValue(object):
      __slots__ = ('__value')
      def __init__(self, value): self.__value = value
      Value = property(lambda self: self.__value)
      EnumType = property(lambda self: EnumType)
      def __hash__(self):        return hash(self.__value)
      def __cmp__(self, other):
         # C fans might want to remove the following assertion
         # to make all enums comparable by ordinal value {;))
         assert self.EnumType is other.EnumType, "Only values from the same enum are comparable"
         return cmp(self.__value, other.__value)
      def __invert__(self):      return constants[maximum - self.__value]
      def __nonzero__(self):     return bool(self.__value)
      def __repr__(self):        return str(names[self.__value])

   maximum = len(names) - 1
   constants = [None] * len(names)
   for i, each in enumerate(names):
      val = EnumValue(i)
      setattr(EnumClass, each, val)
      constants[i] = val
   constants = tuple(constants)
   EnumType = EnumClass()
   return EnumType
