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
separators = ".-"

import re, fcntl, os, types

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
        r.append(s[0])
        s = s[1:]
    return r

def vercmp_part(a, b):
    va = explode_version(a)
    vb = explode_version(b)
    sa = False
    sb = False
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

        if type(ca) is types.StringType:
            sa = ca in separators
        if type(cb) is types.StringType:
            sb = cb in separators
        if sa and not sb:
            return -1
        if not sa and sb:
            return 1

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
            #j = []
        if not flag:
            r.append(i)
        #else:
        #    j.append(i)
        if flag and i.endswith(')'):
            flag = False
            # Ignore version
            #r[-1] += ' ' + ' '.join(j)
    return r

def explode_dep_versions(s):
    """
    Take an RDEPENDS style string of format:
    "DEPEND1 (optional version) DEPEND2 (optional version) ..."
    and return a dictonary of dependencies and versions.
    """
    r = {}
    l = s.split()
    lastdep = None
    lastver = ""
    inversion = False
    for i in l:
        if i[0] == '(':
            inversion = True
            lastver = i[1:] or ""
            #j = []
        elif inversion and i.endswith(')'):
            inversion = False
            lastver = lastver + " " + (i[:-1] or "")
            r[lastdep] = lastver
        elif not inversion:
            r[i] = None
            lastdep = i
            lastver = ""
        elif inversion:
            lastver = lastver + " " + i

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
        bb.msg.error(bb.msg.domain.Util, "Error in compiling python function in: ", realfile)
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
        bb.msg.error(bb.msg.domain.Util, "Error in executing python function in: %s" % realfile)
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

def lockfile(name):
    """
    Use the file fn as a lock file, return when the lock has been acquired.
    Returns a variable to pass to unlockfile().
    """
    path = os.path.dirname(name)
    if not os.path.isdir(path):
        import bb, sys
        bb.msg.error(bb.msg.domain.Util, "Error, lockfile path does not exist!: %s" % path)
        sys.exit(1)

    while True:
        # If we leave the lockfiles lying around there is no problem
        # but we should clean up after ourselves. This gives potential
        # for races though. To work around this, when we acquire the lock 
        # we check the file we locked was still the lock file on disk. 
        # by comparing inode numbers. If they don't match or the lockfile 
        # no longer exists, we start again.

        # This implementation is unfair since the last person to request the 
        # lock is the most likely to win it.

        try:
            lf = open(name, "a+")
            fcntl.flock(lf.fileno(), fcntl.LOCK_EX)
            statinfo = os.fstat(lf.fileno())
            if os.path.exists(lf.name):
               statinfo2 = os.stat(lf.name)
               if statinfo.st_ino == statinfo2.st_ino:
                   return lf
            # File no longer exists or changed, retry
            lf.close
        except Exception, e:
            continue

def unlockfile(lf):
    """
    Unlock a file locked using lockfile()				
    """
    os.unlink(lf.name)
    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    lf.close

def md5_file(filename):
    """
    Return the hex string representation of the MD5 checksum of filename.
    """
    try:
        import hashlib
        m = hashlib.md5()
    except ImportError:
        import md5
        m = md5.new()
    
    for line in open(filename):
        m.update(line)
    return m.hexdigest()

def sha256_file(filename):
    """
    Return the hex string representation of the 256-bit SHA checksum of
    filename.  On Python 2.4 this will return None, so callers will need to
    handle that by either skipping SHA checks, or running a standalone sha256sum
    binary.
    """
    try:
        import hashlib
    except ImportError:
        return None

    s = hashlib.sha256()
    for line in open(filename):
        s.update(line)
    return s.hexdigest()

def preserved_envvars_list():
    return [
        'BBPATH',
        'BB_PRESERVE_ENV',
        'BB_ENV_WHITELIST',
        'BB_ENV_EXTRAWHITE',
        'COLORTERM',
        'DBUS_SESSION_BUS_ADDRESS',
        'DESKTOP_SESSION',
        'DESKTOP_STARTUP_ID',
        'DISPLAY',
        'GNOME_KEYRING_PID',
        'GNOME_KEYRING_SOCKET',
        'GPG_AGENT_INFO',
        'GTK_RC_FILES',
        'HOME',
        'LANG',
        'LOGNAME',
        'PATH',
        'PWD',
        'SESSION_MANAGER',
        'SHELL',
        'SSH_AUTH_SOCK',
        'TERM',
        'USER',
        'USERNAME',
        '_',
        'XAUTHORITY',
        'XDG_DATA_DIRS',
        'XDG_SESSION_COOKIE',
    ]

def filter_environment(good_vars):
    """
    Create a pristine environment for bitbake. This will remove variables that
    are not known and may influence the build in a negative way.
    """

    import bb

    removed_vars = []
    for key in os.environ.keys():
        if key in good_vars:
            continue
        
        removed_vars.append(key)
        os.unsetenv(key)
        del os.environ[key]

    if len(removed_vars):
        bb.debug(1, "Removed the following variables from the environment:", ",".join(removed_vars))

    return removed_vars

def clean_environment():
    """
    Clean up any spurious environment variables. This will remove any
    variables the user hasn't chose to preserve.
    """
    if 'BB_PRESERVE_ENV' not in os.environ:
        if 'BB_ENV_WHITELIST' in os.environ:
            good_vars = os.environ['BB_ENV_WHITELIST'].split()
        else:
            good_vars = preserved_envvars_list()
        if 'BB_ENV_EXTRAWHITE' in os.environ:
            good_vars.extend(os.environ['BB_ENV_EXTRAWHITE'].split())
        filter_environment(good_vars)

def empty_environment():
    """
    Remove all variables from the environment.
    """
    for s in os.environ.keys():
        os.unsetenv(s)
        del os.environ[s]

def build_environment(d):
    """
    Build an environment from all exported variables.
    """
    import bb
    for var in bb.data.keys(d):
        export = bb.data.getVarFlag(var, "export", d)
        if export:
            os.environ[var] = bb.data.getVar(var, d, True) or ""

def prunedir(topdir):
    # Delete everything reachable from the directory named in 'topdir'.
    # CAUTION:  This is dangerous!
    for root, dirs, files in os.walk(topdir, topdown=False):
        for name in files:
            os.remove(os.path.join(root, name))
        for name in dirs:
            if os.path.islink(os.path.join(root, name)):
                os.remove(os.path.join(root, name))
            else:
                os.rmdir(os.path.join(root, name))
    os.rmdir(topdir)

#
# Could also use return re.compile("(%s)" % "|".join(map(re.escape, suffixes))).sub(lambda mo: "", var)
# but thats possibly insane and suffixes is probably going to be small
#
def prune_suffix(var, suffixes, d):
    # See if var ends with any of the suffixes listed and 
    # remove it if found
    for suffix in suffixes:
        if var.endswith(suffix):
            return var.replace(suffix, "")
    return var

def mkdirhier(dir):
    """Create a directory like 'mkdir -p', but does not complain if
    directory already exists like os.makedirs
    """

    debug(3, "mkdirhier(%s)" % dir)
    try:
        os.makedirs(dir)
        debug(2, "created " + dir)
    except OSError, e:
        if e.errno != 17: raise e

import stat

def movefile(src,dest,newmtime=None,sstat=None):
    """Moves a file from src to dest, preserving all permissions and
    attributes; mtime will be preserved even when moving across
    filesystems.  Returns true on success and false on failure. Move is
    atomic.
    """

    #print "movefile("+src+","+dest+","+str(newmtime)+","+str(sstat)+")"
    try:
        if not sstat:
            sstat=os.lstat(src)
    except Exception, e:
        print "movefile: Stating source file failed...", e
        return None

    destexists=1
    try:
        dstat=os.lstat(dest)
    except:
        dstat=os.lstat(os.path.dirname(dest))
        destexists=0

    if destexists:
        if stat.S_ISLNK(dstat[stat.ST_MODE]):
            try:
                os.unlink(dest)
                destexists=0
            except Exception, e:
                pass

    if stat.S_ISLNK(sstat[stat.ST_MODE]):
        try:
            target=os.readlink(src)
            if destexists and not stat.S_ISDIR(dstat[stat.ST_MODE]):
                os.unlink(dest)
            os.symlink(target,dest)
            #os.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
            os.unlink(src)
            return os.lstat(dest)
        except Exception, e:
            print "movefile: failed to properly create symlink:", dest, "->", target, e
            return None

    renamefailed=1
    if sstat[stat.ST_DEV]==dstat[stat.ST_DEV]:
        try:
            ret=os.rename(src,dest)
            renamefailed=0
        except Exception, e:
            import errno
            if e[0]!=errno.EXDEV:
                # Some random error.
                print "movefile: Failed to move", src, "to", dest, e
                return None
            # Invalid cross-device-link 'bind' mounted or actually Cross-Device

    if renamefailed:
        didcopy=0
        if stat.S_ISREG(sstat[stat.ST_MODE]):
            try: # For safety copy then move it over.
                shutil.copyfile(src,dest+"#new")
                os.rename(dest+"#new",dest)
                didcopy=1
            except Exception, e:
                print 'movefile: copy', src, '->', dest, 'failed.', e
                return None
        else:
            #we don't yet handle special, so we need to fall back to /bin/mv
            a=getstatusoutput("/bin/mv -f "+"'"+src+"' '"+dest+"'")
            if a[0]!=0:
                print "movefile: Failed to move special file:" + src + "' to '" + dest + "'", a
                return None # failure
        try:
            if didcopy:
                missingos.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
                os.chmod(dest, stat.S_IMODE(sstat[stat.ST_MODE])) # Sticky is reset on chown
                os.unlink(src)
        except Exception, e:
            print "movefile: Failed to chown/chmod/unlink", dest, e
            return None

    if newmtime:
        os.utime(dest,(newmtime,newmtime))
    else:
        os.utime(dest, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))
        newmtime=sstat[stat.ST_MTIME]
    return newmtime

def copyfile(src,dest,newmtime=None,sstat=None):
    """
    Copies a file from src to dest, preserving all permissions and
    attributes; mtime will be preserved even when moving across
    filesystems.  Returns true on success and false on failure.
    """
    import os, stat, shutil

    #print "copyfile("+src+","+dest+","+str(newmtime)+","+str(sstat)+")"
    try:
        if not sstat:
            sstat=os.lstat(src)
    except Exception, e:
        print "copyfile: Stating source file failed...", e
        return False

    destexists=1
    try:
        dstat=os.lstat(dest)
    except:
        dstat=os.lstat(os.path.dirname(dest))
        destexists=0

    if destexists:
        if stat.S_ISLNK(dstat[stat.ST_MODE]):
            try:
                os.unlink(dest)
                destexists=0
            except Exception, e:
                pass

    if stat.S_ISLNK(sstat[stat.ST_MODE]):
        try:
            target=os.readlink(src)
            if destexists and not stat.S_ISDIR(dstat[stat.ST_MODE]):
                os.unlink(dest)
            os.symlink(target,dest)
            #os.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
            return os.lstat(dest)
        except Exception, e:
            print "copyfile: failed to properly create symlink:", dest, "->", target, e
            return False

    if stat.S_ISREG(sstat[stat.ST_MODE]):
            try: # For safety copy then move it over.
                shutil.copyfile(src,dest+"#new")
                os.rename(dest+"#new",dest)
            except Exception, e:
                print 'copyfile: copy', src, '->', dest, 'failed.', e
                return False
    else:
            #we don't yet handle special, so we need to fall back to /bin/mv
            a=getstatusoutput("/bin/cp -f "+"'"+src+"' '"+dest+"'")
            if a[0]!=0:
                print "copyfile: Failed to copy special file:" + src + "' to '" + dest + "'", a
                return False # failure
    try:
        os.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
        os.chmod(dest, stat.S_IMODE(sstat[stat.ST_MODE])) # Sticky is reset on chown
    except Exception, e:
        print "copyfile: Failed to chown/chmod/unlink", dest, e
        return False

    if newmtime:
        os.utime(dest,(newmtime,newmtime))
    else:
        os.utime(dest, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))
        newmtime=sstat[stat.ST_MTIME]
    return newmtime

def which(path, item, direction = 0):
    """
    Locate a file in a PATH
    """

    paths = (path or "").split(':')
    if direction != 0:
        paths.reverse()

    for p in (path or "").split(':'):
        next = os.path.join(p, item)
        if os.path.exists(next):
            return next

    return ""

whitespace = '\t\n\x0b\x0c\r '
lowercase = 'abcdefghijklmnopqrstuvwxyz'

def tokenize(mystring):
    """Breaks a string like 'foo? (bar) oni? (blah (blah))' into (possibly embedded) lists:

    >>> tokenize("x")
    ['x']
    >>> tokenize("x y")
    ['x', 'y']
    >>> tokenize("(x y)")
    [['x', 'y']]
    >>> tokenize("(x y) b c")
    [['x', 'y'], 'b', 'c']
    >>> tokenize("foo? (bar) oni? (blah (blah))")
    ['foo?', ['bar'], 'oni?', ['blah', ['blah']]]
    >>> tokenize("sys-apps/linux-headers nls? (sys-devel/gettext)")
    ['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']]
    """

    newtokens = []
    curlist   = newtokens
    prevlists = []
    level     = 0
    accum     = ""
    for x in mystring:
        if x=="(":
            if accum:
                curlist.append(accum)
                accum=""
            prevlists.append(curlist)
            curlist=[]
            level=level+1
        elif x==")":
            if accum:
                curlist.append(accum)
                accum=""
            if level==0:
                print "!!! tokenizer: Unmatched left parenthesis in:\n'"+mystring+"'"
                return None
            newlist=curlist
            curlist=prevlists.pop()
            curlist.append(newlist)
            level=level-1
        elif x in whitespace:
            if accum:
                curlist.append(accum)
                accum=""
        else:
            accum=accum+x
    if accum:
        curlist.append(accum)
    if (level!=0):
        print "!!! tokenizer: Exiting with unterminated parenthesis in:\n'"+mystring+"'"
        return None
    return newtokens

def evaluate(tokens,mydefines,allon=0):
    """Removes tokens based on whether conditional definitions exist or not.
    Recognizes !

    >>> evaluate(['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']], {})
    ['sys-apps/linux-headers']

    Negate the flag:

    >>> evaluate(['sys-apps/linux-headers', '!nls?', ['sys-devel/gettext']], {})
    ['sys-apps/linux-headers', ['sys-devel/gettext']]

    Define 'nls':

    >>> evaluate(['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']], {"nls":1})
    ['sys-apps/linux-headers', ['sys-devel/gettext']]

    Turn allon on:

    >>> evaluate(['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']], {}, True)
    ['sys-apps/linux-headers', ['sys-devel/gettext']]
    """

    if tokens == None:
        return None
    mytokens = tokens + []        # this copies the list
    pos = 0
    while pos < len(mytokens):
        if type(mytokens[pos]) == types.ListType:
            evaluate(mytokens[pos], mydefines)
            if not len(mytokens[pos]):
                del mytokens[pos]
                continue
        elif mytokens[pos][-1] == "?":
            cur = mytokens[pos][:-1]
            del mytokens[pos]
            if allon:
                if cur[0] == "!":
                    del mytokens[pos]
            else:
                if cur[0] == "!":
                    if (cur[1:] in mydefines) and (pos < len(mytokens)):
                        del mytokens[pos]
                        continue
                elif (cur not in mydefines) and (pos < len(mytokens)):
                    del mytokens[pos]
                    continue
        pos = pos + 1
    return mytokens

def flatten(mytokens):
    """Converts nested arrays into a flat arrays:

    >>> flatten([1,[2,3]])
    [1, 2, 3]
    >>> flatten(['sys-apps/linux-headers', ['sys-devel/gettext']])
    ['sys-apps/linux-headers', 'sys-devel/gettext']
    """

    newlist=[]
    for x in mytokens:
        if type(x)==types.ListType:
            newlist.extend(flatten(x))
        else:
            newlist.append(x)
    return newlist

_package_weights_ = {"pre":-2,"p":0,"alpha":-4,"beta":-3,"rc":-1}    # dicts are unordered
_package_ends_    = ["pre", "p", "alpha", "beta", "rc", "cvs", "bk", "HEAD" ]            # so we need ordered list

def relparse(myver):
    """Parses the last elements of a version number into a triplet, that can
    later be compared:

    >>> relparse('1.2_pre3')
    [1.2, -2, 3.0]
    >>> relparse('1.2b')
    [1.2, 98, 0]
    >>> relparse('1.2')
    [1.2, 0, 0]
    """

    number   = 0
    p1       = 0
    p2       = 0
    mynewver = myver.split('_')
    if len(mynewver)==2:
        # an _package_weights_
        number = float(mynewver[0])
        match = 0
        for x in _package_ends_:
            elen = len(x)
            if mynewver[1][:elen] == x:
                match = 1
                p1 = _package_weights_[x]
                try:
                    p2 = float(mynewver[1][elen:])
                except:
                    p2 = 0
                break
        if not match:
            # normal number or number with letter at end
            divider = len(myver)-1
            if myver[divider:] not in "1234567890":
                # letter at end
                p1 = ord(myver[divider:])
                number = float(myver[0:divider])
            else:
                number = float(myver)
    else:
        # normal number or number with letter at end
        divider = len(myver)-1
        if myver[divider:] not in "1234567890":
            #letter at end
            p1     = ord(myver[divider:])
            number = float(myver[0:divider])
        else:
            number = float(myver)
    return [number,p1,p2]

__ververify_cache__ = {}

def ververify(myorigval,silent=1):
    """Returns 1 if given a valid version string, els 0. Valid versions are in the format

    <v1>.<v2>...<vx>[a-z,_{_package_weights_}[vy]]

    >>> ververify('2.4.20')
    1
    >>> ververify('2.4..20')        # two dots
    0
    >>> ververify('2.x.20')            # 'x' is not numeric
    0
    >>> ververify('2.4.20a')
    1
    >>> ververify('2.4.20cvs')        # only one trailing letter
    0
    >>> ververify('1a')
    1
    >>> ververify('test_a')            # no version at all
    0
    >>> ververify('2.4.20_beta1')
    1
    >>> ververify('2.4.20_beta')
    1
    >>> ververify('2.4.20_wrongext')    # _wrongext is no valid trailer
    0
    """

    # Lookup the cache first
    try:
        return __ververify_cache__[myorigval]
    except KeyError:
        pass

    if len(myorigval) == 0:
        if not silent:
            error("package version is empty")
        __ververify_cache__[myorigval] = 0
        return 0
    myval = myorigval.split('.')
    if len(myval)==0:
        if not silent:
            error("package name has empty version string")
        __ververify_cache__[myorigval] = 0
        return 0
    # all but the last version must be a numeric
    for x in myval[:-1]:
        if not len(x):
            if not silent:
                error("package version has two points in a row")
            __ververify_cache__[myorigval] = 0
            return 0
        try:
            foo = int(x)
        except:
            if not silent:
                error("package version contains non-numeric '"+x+"'")
            __ververify_cache__[myorigval] = 0
            return 0
    if not len(myval[-1]):
            if not silent:
                error("package version has trailing dot")
            __ververify_cache__[myorigval] = 0
            return 0
    try:
        foo = int(myval[-1])
        __ververify_cache__[myorigval] = 1
        return 1
    except:
        pass

    # ok, our last component is not a plain number or blank, let's continue
    if myval[-1][-1] in lowercase:
        try:
            foo = int(myval[-1][:-1])
            return 1
            __ververify_cache__[myorigval] = 1
            # 1a, 2.0b, etc.
        except:
            pass
    # ok, maybe we have a 1_alpha or 1_beta2; let's see
    ep=string.split(myval[-1],"_")
    if len(ep)!= 2:
        if not silent:
            error("package version has more than one letter at then end")
        __ververify_cache__[myorigval] = 0
        return 0
    try:
        foo = string.atoi(ep[0])
    except:
        # this needs to be numeric, i.e. the "1" in "1_alpha"
        if not silent:
            error("package version must have numeric part before the '_'")
        __ververify_cache__[myorigval] = 0
        return 0

    for mye in _package_ends_:
        if ep[1][0:len(mye)] == mye:
            if len(mye) == len(ep[1]):
                # no trailing numeric is ok
                __ververify_cache__[myorigval] = 1
                return 1
            else:
                try:
                    foo = string.atoi(ep[1][len(mye):])
                    __ververify_cache__[myorigval] = 1
                    return 1
                except:
                    # if no _package_weights_ work, *then* we return 0
                    pass
    if not silent:
        error("package version extension after '_' is invalid")
    __ververify_cache__[myorigval] = 0
    return 0

def isjustname(mypkg):
    myparts = string.split(mypkg,'-')
    for x in myparts:
        if ververify(x):
            return 0
    return 1

_isspecific_cache_={}

def isspecific(mypkg):
    "now supports packages with no category"
    try:
        return __isspecific_cache__[mypkg]
    except:
        pass

    mysplit = string.split(mypkg,"/")
    if not isjustname(mysplit[-1]):
            __isspecific_cache__[mypkg] = 1
            return 1
    __isspecific_cache__[mypkg] = 0
    return 0

__pkgsplit_cache__={}

def pkgsplit(mypkg, silent=1):

    """This function can be used as a package verification function. If
    it is a valid name, pkgsplit will return a list containing:
    [pkgname, pkgversion(norev), pkgrev ].

    >>> pkgsplit('')
    >>> pkgsplit('x')
    >>> pkgsplit('x-')
    >>> pkgsplit('-1')
    >>> pkgsplit('glibc-1.2-8.9-r7')
    >>> pkgsplit('glibc-2.2.5-r7')
    ['glibc', '2.2.5', 'r7']
    >>> pkgsplit('foo-1.2-1')
    >>> pkgsplit('Mesa-3.0')
    ['Mesa', '3.0', 'r0']
    """

    try:
        return __pkgsplit_cache__[mypkg]
    except KeyError:
        pass

    myparts = string.split(mypkg,'-')
    if len(myparts) < 2:
        if not silent:
            error("package name without name or version part")
        __pkgsplit_cache__[mypkg] = None
        return None
    for x in myparts:
        if len(x) == 0:
            if not silent:
                error("package name with empty name or version part")
            __pkgsplit_cache__[mypkg] = None
            return None
    # verify rev
    revok = 0
    myrev = myparts[-1]
    ververify(myrev, silent)
    if len(myrev) and myrev[0] == "r":
        try:
            string.atoi(myrev[1:])
            revok = 1
        except:
            pass
    if revok:
        if ververify(myparts[-2]):
            if len(myparts) == 2:
                __pkgsplit_cache__[mypkg] = None
                return None
            else:
                for x in myparts[:-2]:
                    if ververify(x):
                        __pkgsplit_cache__[mypkg]=None
                        return None
                        # names can't have versiony looking parts
                myval=[string.join(myparts[:-2],"-"),myparts[-2],myparts[-1]]
                __pkgsplit_cache__[mypkg]=myval
                return myval
        else:
            __pkgsplit_cache__[mypkg] = None
            return None

    elif ververify(myparts[-1],silent):
        if len(myparts)==1:
            if not silent:
                print "!!! Name error in",mypkg+": missing name part."
            __pkgsplit_cache__[mypkg]=None
            return None
        else:
            for x in myparts[:-1]:
                if ververify(x):
                    if not silent: error("package name has multiple version parts")
                    __pkgsplit_cache__[mypkg] = None
                    return None
            myval = [string.join(myparts[:-1],"-"), myparts[-1],"r0"]
            __pkgsplit_cache__[mypkg] = myval
            return myval
    else:
        __pkgsplit_cache__[mypkg] = None
        return None

__catpkgsplit_cache__ = {}

def catpkgsplit(mydata,silent=1):
    """returns [cat, pkgname, version, rev ]

    >>> catpkgsplit('sys-libs/glibc-1.2-r7')
    ['sys-libs', 'glibc', '1.2', 'r7']
    >>> catpkgsplit('glibc-1.2-r7')
    [None, 'glibc', '1.2', 'r7']
    """

    try:
        return __catpkgsplit_cache__[mydata]
    except KeyError:
        pass

    cat = os.path.basename(os.path.dirname(mydata))
    mydata = os.path.join(cat, os.path.basename(mydata))
    if mydata[-3:] == '.bb':
        mydata = mydata[:-3]

    mysplit = mydata.split("/")
    p_split = None
    splitlen = len(mysplit)
    if splitlen == 1:
        retval = [None]
        p_split = pkgsplit(mydata,silent)
    else:
        retval = [mysplit[splitlen - 2]]
        p_split = pkgsplit(mysplit[splitlen - 1],silent)
    if not p_split:
        __catpkgsplit_cache__[mydata] = None
        return None
    retval.extend(p_split)
    __catpkgsplit_cache__[mydata] = retval
    return retval

def pkgcmp(pkg1,pkg2):
    """ Compares two packages, which should have been split via
    pkgsplit(). if the return value val is less than zero, then pkg2 is
    newer than pkg1, zero if equal and positive if older.

    >>> pkgcmp(['glibc', '2.2.5', 'r7'], ['glibc', '2.2.5', 'r7'])
    0
    >>> pkgcmp(['glibc', '2.2.5', 'r4'], ['glibc', '2.2.5', 'r7'])
    -1
    >>> pkgcmp(['glibc', '2.2.5', 'r7'], ['glibc', '2.2.5', 'r2'])
    1
    """

    mycmp = vercmp(pkg1[1],pkg2[1])
    if mycmp > 0:
        return 1
    if mycmp < 0:
        return -1
    r1=string.atoi(pkg1[2][1:])
    r2=string.atoi(pkg2[2][1:])
    if r1 > r2:
        return 1
    if r2 > r1:
        return -1
    return 0

def dep_parenreduce(mysplit, mypos=0):
    """Accepts a list of strings, and converts '(' and ')' surrounded items to sub-lists:

    >>> dep_parenreduce([''])
    ['']
    >>> dep_parenreduce(['1', '2', '3'])
    ['1', '2', '3']
    >>> dep_parenreduce(['1', '(', '2', '3', ')', '4'])
    ['1', ['2', '3'], '4']
    """

    while mypos < len(mysplit):
        if mysplit[mypos] == "(":
            firstpos = mypos
            mypos = mypos + 1
            while mypos < len(mysplit):
                if mysplit[mypos] == ")":
                    mysplit[firstpos:mypos+1] = [mysplit[firstpos+1:mypos]]
                    mypos = firstpos
                    break
                elif mysplit[mypos] == "(":
                    # recurse
                    mysplit = dep_parenreduce(mysplit,mypos)
                mypos = mypos + 1
        mypos = mypos + 1
    return mysplit

def dep_opconvert(mysplit, myuse):
    "Does dependency operator conversion"

    mypos   = 0
    newsplit = []
    while mypos < len(mysplit):
        if type(mysplit[mypos]) == types.ListType:
            newsplit.append(dep_opconvert(mysplit[mypos],myuse))
            mypos += 1
        elif mysplit[mypos] == ")":
            # mismatched paren, error
            return None
        elif mysplit[mypos]=="||":
            if ((mypos+1)>=len(mysplit)) or (type(mysplit[mypos+1])!=types.ListType):
                # || must be followed by paren'd list
                return None
            try:
                mynew = dep_opconvert(mysplit[mypos+1],myuse)
            except Exception, e:
                error("unable to satisfy OR dependancy: " + string.join(mysplit," || "))
                raise e
            mynew[0:0] = ["||"]
            newsplit.append(mynew)
            mypos += 2
        elif mysplit[mypos][-1] == "?":
            # use clause, i.e "gnome? ( foo bar )"
            # this is a quick and dirty hack so that repoman can enable all USE vars:
            if (len(myuse) == 1) and (myuse[0] == "*"):
                # enable it even if it's ! (for repoman) but kill it if it's
                # an arch variable that isn't for this arch. XXX Sparc64?
                if (mysplit[mypos][:-1] not in settings.usemask) or \
                        (mysplit[mypos][:-1]==settings["ARCH"]):
                    enabled=1
                else:
                    enabled=0
            else:
                if mysplit[mypos][0] == "!":
                    myusevar = mysplit[mypos][1:-1]
                    enabled = not myusevar in myuse
                    #if myusevar in myuse:
                    #    enabled = 0
                    #else:
                    #    enabled = 1
                else:
                    myusevar=mysplit[mypos][:-1]
                    enabled = myusevar in myuse
                    #if myusevar in myuse:
                    #    enabled=1
                    #else:
                    #    enabled=0
            if (mypos +2 < len(mysplit)) and (mysplit[mypos+2] == ":"):
                # colon mode
                if enabled:
                    # choose the first option
                    if type(mysplit[mypos+1]) == types.ListType:
                        newsplit.append(dep_opconvert(mysplit[mypos+1],myuse))
                    else:
                        newsplit.append(mysplit[mypos+1])
                else:
                    # choose the alternate option
                    if type(mysplit[mypos+1]) == types.ListType:
                        newsplit.append(dep_opconvert(mysplit[mypos+3],myuse))
                    else:
                        newsplit.append(mysplit[mypos+3])
                mypos += 4
            else:
                # normal use mode
                if enabled:
                    if type(mysplit[mypos+1]) == types.ListType:
                        newsplit.append(dep_opconvert(mysplit[mypos+1],myuse))
                    else:
                        newsplit.append(mysplit[mypos+1])
                # otherwise, continue
                mypos += 2
        else:
            # normal item
            newsplit.append(mysplit[mypos])
            mypos += 1
    return newsplit

