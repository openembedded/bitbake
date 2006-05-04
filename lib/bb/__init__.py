#!/usr/bin/python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake Build System Python Library

Copyright (C) 2003  Holger Schurig
Copyright (C) 2003, 2004  Chris Larson

Based on Gentoo's portage.py.

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
"""

__version__ = "1.4.3"

__all__ = [

    "debug",
    "note",
    "error",
    "fatal",

    "mkdirhier",
    "movefile",

    "tokenize",
    "evaluate",
    "flatten",
    "relparse",
    "ververify",
    "isjustname",
    "isspecific",
    "pkgsplit",
    "catpkgsplit",
    "vercmp",
    "pkgcmp",
    "dep_parenreduce",
    "dep_opconvert",
    "digraph",

# fetch
    "decodeurl",
    "encodeurl",

# modules
    "parse",
    "data",
    "event",
    "build",
    "fetch",
    "manifest",
    "methodpool",
    "cache",
 ]

whitespace = '\t\n\x0b\x0c\r '
lowercase = 'abcdefghijklmnopqrstuvwxyz'

import sys, os, types, re, string

#projectdir = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
projectdir = os.getcwd()

debug_level = 0

if "BBDEBUG" in os.environ:
    level = int(os.environ["BBDEBUG"])
    if level:
        debug_level = level
    else:
        debug_level = 0

class VarExpandError(Exception):
    pass

class MalformedUrl(Exception):
    """Exception raised when encountering an invalid url"""


#######################################################################
#######################################################################
#
# SECTION: Debug
#
# PURPOSE: little functions to make yourself known
#
#######################################################################
#######################################################################

debug_prepend = ''


def debug(lvl, *args):
    if debug_level >= lvl:
        print debug_prepend + 'DEBUG:', ''.join(args)

def note(*args):
    print debug_prepend + 'NOTE:', ''.join(args)

def error(*args):
    print debug_prepend + 'ERROR:', ''.join(args)

def fatal(*args):
    print debug_prepend + 'ERROR:', ''.join(args)
    sys.exit(1)


#######################################################################
#######################################################################
#
# SECTION: File
#
# PURPOSE: Basic file and directory tree related functions
#
#######################################################################
#######################################################################

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


#######################################################################

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
        print "!!! Stating source file failed... movefile()"
        print "!!!",e
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
#            os.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
            os.unlink(src)
            return os.lstat(dest)
        except Exception, e:
            print "!!! failed to properly create symlink:"
            print "!!!",dest,"->",target
            print "!!!",e
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
                print "!!! Failed to move",src,"to",dest
                print "!!!",e
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
                print '!!! copy',src,'->',dest,'failed.'
                print "!!!",e
                return None
        else:
            #we don't yet handle special, so we need to fall back to /bin/mv
            a=getstatusoutput("/bin/mv -f "+"'"+src+"' '"+dest+"'")
            if a[0]!=0:
                print "!!! Failed to move special file:"
                print "!!! '"+src+"' to '"+dest+"'"
                print "!!!",a
                return None # failure
        try:
            if didcopy:
                missingos.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
                os.chmod(dest, stat.S_IMODE(sstat[stat.ST_MODE])) # Sticky is reset on chown
                os.unlink(src)
        except Exception, e:
            print "!!! Failed to chown/chmod/unlink in movefile()"
            print "!!!",dest
            print "!!!",e
            return None

    if newmtime:
        os.utime(dest,(newmtime,newmtime))
    else:
        os.utime(dest, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))
        newmtime=sstat[stat.ST_MTIME]
    return newmtime



#######################################################################
#######################################################################
#
# SECTION: Download
#
# PURPOSE: Download via HTTP, FTP, CVS, BITKEEPER, handling of MD5-signatures
#          and mirrors
#
#######################################################################
#######################################################################

def decodeurl(url):
    """Decodes an URL into the tokens (scheme, network location, path,
    user, password, parameters).

    >>> decodeurl("http://www.google.com/index.html")
    ('http', 'www.google.com', '/index.html', '', '', {})

    CVS url with username, host and cvsroot. The cvs module to check out is in the
    parameters:

    >>> decodeurl("cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg")
    ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', '', {'module': 'familiar/dist/ipkg'})

    Dito, but this time the username has a password part. And we also request a special tag
    to check out.

    >>> decodeurl("cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;module=familiar/dist/ipkg;tag=V0-99-81")
    ('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'})
    """

    m = re.compile('(?P<type>[^:]*)://((?P<user>.+)@)?(?P<location>[^;]+)(;(?P<parm>.*))?').match(url)
    if not m:
        raise MalformedUrl(url)

    type = m.group('type')
    location = m.group('location')
    if not location:
        raise MalformedUrl(url)
    user = m.group('user')
    parm = m.group('parm')
    m = re.compile('(?P<host>[^/;]+)(?P<path>/[^;]+)').match(location)
    if m:
        host = m.group('host')
        path = m.group('path')
    else:
        host = ""
        path = location
    if user:
        m = re.compile('(?P<user>[^:]+)(:?(?P<pswd>.*))').match(user)
        if m:
            user = m.group('user')
            pswd = m.group('pswd')
    else:
        user = ''
        pswd = ''

    p = {}
    if parm:
        for s in parm.split(';'):
            s1,s2 = s.split('=')
            p[s1] = s2

    return (type, host, path, user, pswd, p)

#######################################################################

def encodeurl(decoded):
    """Encodes a URL from tokens (scheme, network location, path,
    user, password, parameters).

    >>> encodeurl(['http', 'www.google.com', '/index.html', '', '', {}])
    'http://www.google.com/index.html'

    CVS with username, host and cvsroot. The cvs module to check out is in the
    parameters:

    >>> encodeurl(['cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', '', {'module': 'familiar/dist/ipkg'}])
    'cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg'

    Dito, but this time the username has a password part. And we also request a special tag
    to check out.

    >>> encodeurl(['cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'}])
    'cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;tag=V0-99-81;module=familiar/dist/ipkg'
    """

    (type, host, path, user, pswd, p) = decoded

    if not type or not path:
        fatal("invalid or missing parameters for url encoding")
    url = '%s://' % type
    if user:
        url += "%s" % user
        if pswd:
            url += ":%s" % pswd
        url += "@"
    if host:
        url += "%s" % host
    url += "%s" % path
    if p:
        for parm in p.keys():
            url += ";%s=%s" % (parm, p[parm])

    return url

#######################################################################

def which(path, item, direction = 0):
    """Useful function for locating a file in a PATH"""
    found = ""
    for p in (path or "").split(':'):
        if os.path.exists(os.path.join(p, item)):
            found = os.path.join(p, item)
            if direction == 0:
                break
    return found

#######################################################################




#######################################################################
#######################################################################
#
# SECTION: Dependency
#
# PURPOSE: Compare build & run dependencies
#
#######################################################################
#######################################################################

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


#######################################################################

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


#######################################################################

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


#######################################################################

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


#######################################################################

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


#######################################################################

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


#######################################################################

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


#######################################################################

__vercmp_cache__ = {}

def vercmp(val1,val2):
    """This takes two version strings and returns an integer to tell you whether
    the versions are the same, val1>val2 or val2>val1.

    >>> vercmp('1', '2')
    -1.0
    >>> vercmp('2', '1')
    1.0
    >>> vercmp('1', '1.0')
    0
    >>> vercmp('1', '1.1')
    -1.0
    >>> vercmp('1.1', '1_p2')
    1.0
    """

    # quick short-circuit
    if val1 == val2:
        return 0
    valkey = val1+" "+val2

    # cache lookup
    try:
        return __vercmp_cache__[valkey]
        try:
            return - __vercmp_cache__[val2+" "+val1]
        except KeyError:
            pass
    except KeyError:
        pass

    # consider 1_p2 vc 1.1
    # after expansion will become (1_p2,0) vc (1,1)
    # then 1_p2 is compared with 1 before 0 is compared with 1
    # to solve the bug we need to convert it to (1,0_p2)
    # by splitting _prepart part and adding it back _after_expansion

    val1_prepart = val2_prepart = ''
    if val1.count('_'):
        val1, val1_prepart = val1.split('_', 1)
    if val2.count('_'):
        val2, val2_prepart = val2.split('_', 1)

    # replace '-' by '.'
    # FIXME: Is it needed? can val1/2 contain '-'?

    val1 = string.split(val1,'-')
    if len(val1) == 2:
        val1[0] = val1[0] +"."+ val1[1]
    val2 = string.split(val2,'-')
    if len(val2) == 2:
        val2[0] = val2[0] +"."+ val2[1]

    val1 = string.split(val1[0],'.')
    val2 = string.split(val2[0],'.')

    # add back decimal point so that .03 does not become "3" !
    for x in range(1,len(val1)):
        if val1[x][0] == '0' :
            val1[x] = '.' + val1[x]
    for x in range(1,len(val2)):
        if val2[x][0] == '0' :
            val2[x] = '.' + val2[x]

    # extend varion numbers
    if len(val2) < len(val1):
        val2.extend(["0"]*(len(val1)-len(val2)))
    elif len(val1) < len(val2):
        val1.extend(["0"]*(len(val2)-len(val1)))

    # add back _prepart tails
    if val1_prepart:
        val1[-1] += '_' + val1_prepart
    if val2_prepart:
        val2[-1] += '_' + val2_prepart
    # The above code will extend version numbers out so they
    # have the same number of digits.
    for x in range(0,len(val1)):
        cmp1 = relparse(val1[x])
        cmp2 = relparse(val2[x])
        for y in range(0,3):
            myret = cmp1[y] - cmp2[y]
            if myret != 0:
                __vercmp_cache__[valkey] = myret
                return myret
    __vercmp_cache__[valkey] = 0
    return 0


#######################################################################

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


#######################################################################

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

class digraph:
    """beautiful directed graph object"""

    def __init__(self):
        self.dict={}
        #okeys = keys, in order they were added (to optimize firstzero() ordering)
        self.okeys=[]
        self.__callback_cache=[]

    def __str__(self):
        str = ""
        for key in self.okeys:
            str += "%s:\t%s\n" % (key, self.dict[key][1])
        return str

    def addnode(self,mykey,myparent):
        if not mykey in self.dict:
            self.okeys.append(mykey)
            if myparent==None:
                self.dict[mykey]=[0,[]]
            else:
                self.dict[mykey]=[0,[myparent]]
                self.dict[myparent][0]=self.dict[myparent][0]+1
            return
        if myparent and (not myparent in self.dict[mykey][1]):
            self.dict[mykey][1].append(myparent)
            self.dict[myparent][0]=self.dict[myparent][0]+1

    def delnode(self,mykey, ref = 1):
        """Delete a node

        If ref is 1, remove references to this node from other nodes.
        If ref is 2, remove nodes that reference this node."""
        if not mykey in self.dict:
            return
        for x in self.dict[mykey][1]:
            self.dict[x][0]=self.dict[x][0]-1
        del self.dict[mykey]
        while 1:
            try:
                self.okeys.remove(mykey)
            except ValueError:
                break
        if ref:
            __kill = []
            for k in self.okeys:
                if mykey in self.dict[k][1]:
                    if ref == 1 or ref == 2:
                        self.dict[k][1].remove(mykey)
                    if ref == 2:
                        __kill.append(k)
            for l in __kill:
                self.delnode(l, ref)

    def allnodes(self):
        "returns all nodes in the dictionary"
        return self.dict.keys()

    def firstzero(self):
        "returns first node with zero references, or NULL if no such node exists"
        for x in self.okeys:
            if self.dict[x][0]==0:
                return x
        return None

    def firstnonzero(self):
        "returns first node with nonzero references, or NULL if no such node exists"
        for x in self.okeys:
            if self.dict[x][0]!=0:
                return x
        return None


    def allzeros(self):
        "returns all nodes with zero references, or NULL if no such node exists"
        zerolist = []
        for x in self.dict.keys():
            if self.dict[x][0]==0:
                zerolist.append(x)
        return zerolist

    def hasallzeros(self):
        "returns 0/1, Are all nodes zeros? 1 : 0"
        zerolist = []
        for x in self.dict.keys():
            if self.dict[x][0]!=0:
                return 0
        return 1

    def empty(self):
        if len(self.dict)==0:
            return 1
        return 0

    def hasnode(self,mynode):
        return mynode in self.dict

    def getparents(self, item):
        if not self.hasnode(item):
            return []
        return self.dict[item][1]

    def getchildren(self, item):
        if not self.hasnode(item):
            return []
        children = [i for i in self.okeys if item in self.getparents(i)]
        return children

    def walkdown(self, item, callback, debug = None, usecache = False):
        if not self.hasnode(item):
            return 0

        if usecache:
            if self.__callback_cache.count(item):
                if debug:
                    print "hit cache for item: %s" % item
                return 1

        parents = self.getparents(item)
        children = self.getchildren(item)
        for p in parents:
            if p in children:
#                print "%s is both parent and child of %s" % (p, item)
                if usecache:
                    self.__callback_cache.append(p)
                ret = callback(self, p)
                if ret == 0:
                    return 0
                continue
            if item == p:
                print "eek, i'm my own parent!"
                return 0
            if debug:
                print "item: %s, p: %s" % (item, p)
            ret = self.walkdown(p, callback, debug, usecache)
            if ret == 0:
                return 0
        if usecache:
            self.__callback_cache.append(item)
        return callback(self, item)

    def walkup(self, item, callback):
        if not self.hasnode(item):
            return 0

        parents = self.getparents(item)
        children = self.getchildren(item)
        for c in children:
            if c in parents:
                ret = callback(self, item)
                if ret == 0:
                    return 0
                continue
            if item == c:
                print "eek, i'm my own child!"
                return 0
            ret = self.walkup(c, callback)
            if ret == 0:
                return 0
        return callback(self, item)

    def copy(self):
        mygraph=digraph()
        for x in self.dict.keys():
            mygraph.dict[x]=self.dict[x][:]
            mygraph.okeys=self.okeys[:]
        return mygraph

if __name__ == "__main__":
    import doctest, bb
    doctest.testmod(bb)
