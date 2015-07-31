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

import re, fcntl, os, string, stat, shutil, time
import sys
import errno
import logging
import bb
import bb.msg
import multiprocessing
import fcntl
import subprocess
import glob
import traceback
import errno
import signal
from commands import getstatusoutput
from contextlib import contextmanager

logger = logging.getLogger("BitBake.Util")

def clean_context():
    return {
        "os": os,
        "bb": bb,
        "time": time,
    }

def get_context():
    return _context
    

def set_context(ctx):
    _context = ctx

# Context used in better_exec, eval
_context = clean_context()

def explode_version(s):
    r = []
    alpha_regexp = re.compile('^([a-zA-Z]+)(.*)$')
    numeric_regexp = re.compile('^(\d+)(.*)$')
    while (s != ''):
        if s[0] in string.digits:
            m = numeric_regexp.match(s)
            r.append((0, int(m.group(1))))
            s = m.group(2)
            continue
        if s[0] in string.letters:
            m = alpha_regexp.match(s)
            r.append((1, m.group(1)))
            s = m.group(2)
            continue
        if s[0] == '~':
            r.append((-1, s[0]))
        else:
            r.append((2, s[0]))
        s = s[1:]
    return r

def split_version(s):
    """Split a version string into its constituent parts (PE, PV, PR)"""
    s = s.strip(" <>=")
    e = 0
    if s.count(':'):
        e = int(s.split(":")[0])
        s = s.split(":")[1]
    r = ""
    if s.count('-'):
        r = s.rsplit("-", 1)[1]
        s = s.rsplit("-", 1)[0]
    v = s
    return (e, v, r)

def vercmp_part(a, b):
    va = explode_version(a)
    vb = explode_version(b)
    while True:
        if va == []:
            (oa, ca) = (0, None)
        else:
            (oa, ca) = va.pop(0)
        if vb == []:
            (ob, cb) = (0, None)
        else:
            (ob, cb) = vb.pop(0)
        if (oa, ca) == (0, None) and (ob, cb) == (0, None):
            return 0
        if oa < ob:
            return -1
        elif oa > ob:
            return 1
        elif ca < cb:
            return -1
        elif ca > cb:
            return 1

def vercmp(ta, tb):
    (ea, va, ra) = ta
    (eb, vb, rb) = tb

    r = int(ea or 0) - int(eb or 0)
    if (r == 0):
        r = vercmp_part(va, vb)
    if (r == 0):
        r = vercmp_part(ra, rb)
    return r

def vercmp_string(a, b):
    ta = split_version(a)
    tb = split_version(b)
    return vercmp(ta, tb)

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

def explode_dep_versions2(s):
    """
    Take an RDEPENDS style string of format:
    "DEPEND1 (optional version) DEPEND2 (optional version) ..."
    and return a dictionary of dependencies and versions.
    """
    r = {}
    l = s.replace(",", "").split()
    lastdep = None
    lastcmp = ""
    lastver = ""
    incmp = False
    inversion = False
    for i in l:
        if i[0] == '(':
            incmp = True
            i = i[1:].strip()
            if not i:
                continue

        if incmp:
            incmp = False
            inversion = True
            # This list is based on behavior and supported comparisons from deb, opkg and rpm.
            #
            # Even though =<, <<, ==, !=, =>, and >> may not be supported, 
            # we list each possibly valid item. 
            # The build system is responsible for validation of what it supports.
            if i.startswith(('<=', '=<', '<<', '==', '!=', '>=', '=>', '>>')):
                lastcmp = i[0:2]
                i = i[2:]
            elif i.startswith(('<', '>', '=')):
                lastcmp = i[0:1]
                i = i[1:]
            else:
                # This is an unsupported case!
                lastcmp = (i or "")
                i = ""
            i.strip()
            if not i:
                continue

        if inversion:
            if i.endswith(')'):
                i = i[:-1] or ""
                inversion = False
                if lastver and i:
                    lastver += " "
            if i:
                lastver += i
                if lastdep not in r:
                    r[lastdep] = []
                r[lastdep].append(lastcmp + " " + lastver)
            continue

        #if not inversion:
        lastdep = i
        lastver = ""
        lastcmp = ""
        if not (i in r and r[i]):
            r[lastdep] = []

    return r

def explode_dep_versions(s):
    r = explode_dep_versions2(s)
    for d in r:
        if not r[d]:
            r[d] = None
            continue
        if len(r[d]) > 1:
            bb.warn("explode_dep_versions(): Item %s appeared in dependency string '%s' multiple times with different values.  explode_dep_versions cannot cope with this." % (d, s))
        r[d] = r[d][0]
    return r

def join_deps(deps, commasep=True):
    """
    Take the result from explode_dep_versions and generate a dependency string
    """
    result = []
    for dep in deps:
        if deps[dep]:
            if isinstance(deps[dep], list):
                for v in deps[dep]:
                    result.append(dep + " (" + v + ")")
            else:
                result.append(dep + " (" + deps[dep] + ")")
        else:
            result.append(dep)
    if commasep:
        return ", ".join(result)
    else:
        return " ".join(result)

def _print_trace(body, line):
    """
    Print the Environment of a Text Body
    """
    error = []
    # print the environment of the method
    min_line = max(1, line-4)
    max_line = min(line + 4, len(body))
    for i in range(min_line, max_line + 1):
        if line == i:
            error.append(' *** %.4d:%s' % (i, body[i-1].rstrip()))
        else:
            error.append('     %.4d:%s' % (i, body[i-1].rstrip()))
    return error

def better_compile(text, file, realfile, mode = "exec"):
    """
    A better compile method. This method
    will print the offending lines.
    """
    try:
        return compile(text, file, mode)
    except Exception as e:
        error = []
        # split the text into lines again
        body = text.split('\n')
        error.append("Error in compiling python function in %s:\n" % realfile)
        if e.lineno:
            error.append("The code lines resulting in this error were:")
            error.extend(_print_trace(body, e.lineno))
        else:
            error.append("The function causing this error was:")
            for line in body:
                error.append(line)
        error.append("%s: %s" % (e.__class__.__name__, str(e)))

        logger.error("\n".join(error))

        e = bb.BBHandledException(e)
        raise e

def _print_exception(t, value, tb, realfile, text, context):
    error = []
    try:
        exception = traceback.format_exception_only(t, value)
        error.append('Error executing a python function in %s:\n' % realfile)

        # Strip 'us' from the stack (better_exec call)
        tb = tb.tb_next

        textarray = text.split('\n')

        linefailed = tb.tb_lineno

        tbextract = traceback.extract_tb(tb)
        tbformat = traceback.format_list(tbextract)
        error.append("The stack trace of python calls that resulted in this exception/failure was:")
        error.append("File: '%s', lineno: %s, function: %s" % (tbextract[0][0], tbextract[0][1], tbextract[0][2]))
        error.extend(_print_trace(textarray, linefailed))

        # See if this is a function we constructed and has calls back into other functions in
        # "text". If so, try and improve the context of the error by diving down the trace
        level = 0
        nexttb = tb.tb_next
        while nexttb is not None and (level+1) < len(tbextract):
            error.append("File: '%s', lineno: %s, function: %s" % (tbextract[level+1][0], tbextract[level+1][1], tbextract[level+1][2]))
            if tbextract[level][0] == tbextract[level+1][0] and tbextract[level+1][2] == tbextract[level][0]:
                # The code was possibly in the string we compiled ourselves
                error.extend(_print_trace(textarray, tbextract[level+1][1]))
            elif tbextract[level+1][0].startswith("/"):
                # The code looks like it might be in a file, try and load it
                try:
                    with open(tbextract[level+1][0], "r") as f:
                        text = f.readlines()
                        error.extend(_print_trace(text, tbextract[level+1][1]))
                except:
                    error.append(tbformat[level+1])
            elif "d" in context and tbextract[level+1][2]:
                # Try and find the code in the datastore based on the functionname
                d = context["d"]
                functionname = tbextract[level+1][2]
                text = d.getVar(functionname, True)
                if text:
                    error.extend(_print_trace(text.split('\n'), tbextract[level+1][1]))
                else:
                    error.append(tbformat[level+1])
            else:
                error.append(tbformat[level+1])
            nexttb = tb.tb_next
            level = level + 1

        error.append("Exception: %s" % ''.join(exception))
    finally:
        logger.error("\n".join(error))

def better_exec(code, context, text = None, realfile = "<code>"):
    """
    Similiar to better_compile, better_exec will
    print the lines that are responsible for the
    error.
    """
    import bb.parse
    if not text:
        text = code
    if not hasattr(code, "co_filename"):
        code = better_compile(code, realfile, realfile)
    try:
        exec(code, get_context(), context)
    except (bb.BBHandledException, bb.parse.SkipRecipe, bb.build.FuncFailed, bb.data_smart.ExpansionError):
        # Error already shown so passthrough, no need for traceback
        raise
    except Exception as e:
        (t, value, tb) = sys.exc_info()
        try:
            _print_exception(t, value, tb, realfile, text, context)
        except Exception as e:
            logger.error("Exception handler error: %s" % str(e))

        e = bb.BBHandledException(e)
        raise e

def simple_exec(code, context):
    exec(code, get_context(), context)

def better_eval(source, locals):
    return eval(source, get_context(), locals)

@contextmanager
def fileslocked(files):
    """Context manager for locking and unlocking file locks."""
    locks = []
    if files:
        for lockfile in files:
            locks.append(bb.utils.lockfile(lockfile))

    yield

    for lock in locks:
        bb.utils.unlockfile(lock)

@contextmanager
def timeout(seconds):
    def timeout_handler(signum, frame):
        pass

    original_handler = signal.signal(signal.SIGALRM, timeout_handler)

    try:
        signal.alarm(seconds)
        yield
    finally:
        signal.alarm(0)
        signal.signal(signal.SIGALRM, original_handler)

def lockfile(name, shared=False, retry=True, block=False):
    """
    Use the specified file as a lock file, return when the lock has
    been acquired. Returns a variable to pass to unlockfile().
    Parameters:
        retry: True to re-try locking if it fails, False otherwise
        block: True to block until the lock succeeds, False otherwise
    The retry and block parameters are kind of equivalent unless you
    consider the possibility of sending a signal to the process to break
    out - at which point you want block=True rather than retry=True.
    """
    dirname = os.path.dirname(name)
    mkdirhier(dirname)

    if not os.access(dirname, os.W_OK):
        logger.error("Unable to acquire lock '%s', directory is not writable",
                     name)
        sys.exit(1)

    op = fcntl.LOCK_EX
    if shared:
        op = fcntl.LOCK_SH
    if not retry and not block:
        op = op | fcntl.LOCK_NB

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
            lf = open(name, 'a+')
            fileno = lf.fileno()
            fcntl.flock(fileno, op)
            statinfo = os.fstat(fileno)
            if os.path.exists(lf.name):
                statinfo2 = os.stat(lf.name)
                if statinfo.st_ino == statinfo2.st_ino:
                    return lf
            lf.close()
        except Exception:
            try:
                lf.close()
            except Exception:
                pass
            pass
        if not retry:
            return None

def unlockfile(lf):
    """
    Unlock a file locked using lockfile()
    """
    try:
        # If we had a shared lock, we need to promote to exclusive before
        # removing the lockfile. Attempt this, ignore failures.
        fcntl.flock(lf.fileno(), fcntl.LOCK_EX|fcntl.LOCK_NB)
        os.unlink(lf.name)
    except (IOError, OSError):
        pass
    fcntl.flock(lf.fileno(), fcntl.LOCK_UN)
    lf.close()

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

    with open(filename, "rb") as f:
        for line in f:
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
    with open(filename, "rb") as f:
        for line in f:
            s.update(line)
    return s.hexdigest()

def preserved_envvars_exported():
    """Variables which are taken from the environment and placed in and exported
    from the metadata"""
    return [
        'BB_TASKHASH',
        'HOME',
        'LOGNAME',
        'PATH',
        'PWD',
        'SHELL',
        'TERM',
        'USER',
    ]

def preserved_envvars():
    """Variables which are taken from the environment and placed in the metadata"""
    v = [
        'BBPATH',
        'BB_PRESERVE_ENV',
        'BB_ENV_WHITELIST',
        'BB_ENV_EXTRAWHITE',
    ]
    return v + preserved_envvars_exported()

def filter_environment(good_vars):
    """
    Create a pristine environment for bitbake. This will remove variables that
    are not known and may influence the build in a negative way.
    """

    removed_vars = {}
    for key in os.environ.keys():
        if key in good_vars:
            continue

        removed_vars[key] = os.environ[key]
        os.unsetenv(key)
        del os.environ[key]

    if len(removed_vars):
        logger.debug(1, "Removed the following variables from the environment: %s", ", ".join(removed_vars.keys()))

    return removed_vars

def approved_variables():
    """
    Determine and return the list of whitelisted variables which are approved
    to remain in the environment.
    """
    if 'BB_PRESERVE_ENV' in os.environ:
        return os.environ.keys()
    approved = []
    if 'BB_ENV_WHITELIST' in os.environ:
        approved = os.environ['BB_ENV_WHITELIST'].split()
        approved.extend(['BB_ENV_WHITELIST'])
    else:
        approved = preserved_envvars()
    if 'BB_ENV_EXTRAWHITE' in os.environ:
        approved.extend(os.environ['BB_ENV_EXTRAWHITE'].split())
        if 'BB_ENV_EXTRAWHITE' not in approved:
            approved.extend(['BB_ENV_EXTRAWHITE'])
    return approved

def clean_environment():
    """
    Clean up any spurious environment variables. This will remove any
    variables the user hasn't chosen to preserve.
    """
    if 'BB_PRESERVE_ENV' not in os.environ:
        good_vars = approved_variables()
        return filter_environment(good_vars)

    return {}

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
    import bb.data
    for var in bb.data.keys(d):
        export = d.getVarFlag(var, "export")
        if export:
            os.environ[var] = d.getVar(var, True) or ""

def _check_unsafe_delete_path(path):
    """
    Basic safeguard against recursively deleting something we shouldn't. If it returns True,
    the caller should raise an exception with an appropriate message.
    NOTE: This is NOT meant to be a security mechanism - just a guard against silly mistakes
    with potentially disastrous results.
    """
    extra = ''
    # HOME might not be /home/something, so in case we can get it, check against it
    homedir = os.environ.get('HOME', '')
    if homedir:
        extra = '|%s' % homedir
    if re.match('(/|//|/home|/home/[^/]*%s)$' % extra, os.path.abspath(path)):
        return True
    return False

def remove(path, recurse=False):
    """Equivalent to rm -f or rm -rf"""
    if not path:
        return
    if recurse:
        for name in glob.glob(path):
            if _check_unsafe_delete_path(path):
                raise Exception('bb.utils.remove: called with dangerous path "%s" and recurse=True, refusing to delete!' % path)
        # shutil.rmtree(name) would be ideal but its too slow
        subprocess.call(['rm', '-rf'] + glob.glob(path))
        return
    for name in glob.glob(path):
        try:
            os.unlink(name)
        except OSError as exc:
            if exc.errno != errno.ENOENT:
                raise

def prunedir(topdir):
    # Delete everything reachable from the directory named in 'topdir'.
    # CAUTION:  This is dangerous!
    if _check_unsafe_delete_path(topdir):
        raise Exception('bb.utils.prunedir: called with dangerous path "%s", refusing to delete!' % topdir)
    for root, dirs, files in os.walk(topdir, topdown = False):
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

def mkdirhier(directory):
    """Create a directory like 'mkdir -p', but does not complain if
    directory already exists like os.makedirs
    """

    try:
        os.makedirs(directory)
    except OSError as e:
        if e.errno != errno.EEXIST:
            raise e

def movefile(src, dest, newmtime = None, sstat = None):
    """Moves a file from src to dest, preserving all permissions and
    attributes; mtime will be preserved even when moving across
    filesystems.  Returns true on success and false on failure. Move is
    atomic.
    """

    #print "movefile(" + src + "," + dest + "," + str(newmtime) + "," + str(sstat) + ")"
    try:
        if not sstat:
            sstat = os.lstat(src)
    except Exception as e:
        print("movefile: Stating source file failed...", e)
        return None

    destexists = 1
    try:
        dstat = os.lstat(dest)
    except:
        dstat = os.lstat(os.path.dirname(dest))
        destexists = 0

    if destexists:
        if stat.S_ISLNK(dstat[stat.ST_MODE]):
            try:
                os.unlink(dest)
                destexists = 0
            except Exception as e:
                pass

    if stat.S_ISLNK(sstat[stat.ST_MODE]):
        try:
            target = os.readlink(src)
            if destexists and not stat.S_ISDIR(dstat[stat.ST_MODE]):
                os.unlink(dest)
            os.symlink(target, dest)
            #os.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
            os.unlink(src)
            return os.lstat(dest)
        except Exception as e:
            print("movefile: failed to properly create symlink:", dest, "->", target, e)
            return None

    renamefailed = 1
    if sstat[stat.ST_DEV] == dstat[stat.ST_DEV]:
        try:
            os.rename(src, dest)
            renamefailed = 0
        except Exception as e:
            if e[0] != errno.EXDEV:
                # Some random error.
                print("movefile: Failed to move", src, "to", dest, e)
                return None
            # Invalid cross-device-link 'bind' mounted or actually Cross-Device

    if renamefailed:
        didcopy = 0
        if stat.S_ISREG(sstat[stat.ST_MODE]):
            try: # For safety copy then move it over.
                shutil.copyfile(src, dest + "#new")
                os.rename(dest + "#new", dest)
                didcopy = 1
            except Exception as e:
                print('movefile: copy', src, '->', dest, 'failed.', e)
                return None
        else:
            #we don't yet handle special, so we need to fall back to /bin/mv
            a = getstatusoutput("/bin/mv -f " + "'" + src + "' '" + dest + "'")
            if a[0] != 0:
                print("movefile: Failed to move special file:" + src + "' to '" + dest + "'", a)
                return None # failure
        try:
            if didcopy:
                os.lchown(dest, sstat[stat.ST_UID], sstat[stat.ST_GID])
                os.chmod(dest, stat.S_IMODE(sstat[stat.ST_MODE])) # Sticky is reset on chown
                os.unlink(src)
        except Exception as e:
            print("movefile: Failed to chown/chmod/unlink", dest, e)
            return None

    if newmtime:
        os.utime(dest, (newmtime, newmtime))
    else:
        os.utime(dest, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))
        newmtime = sstat[stat.ST_MTIME]
    return newmtime

def copyfile(src, dest, newmtime = None, sstat = None):
    """
    Copies a file from src to dest, preserving all permissions and
    attributes; mtime will be preserved even when moving across
    filesystems.  Returns true on success and false on failure.
    """
    #print "copyfile(" + src + "," + dest + "," + str(newmtime) + "," + str(sstat) + ")"
    try:
        if not sstat:
            sstat = os.lstat(src)
    except Exception as e:
        logger.warn("copyfile: stat of %s failed (%s)" % (src, e))
        return False

    destexists = 1
    try:
        dstat = os.lstat(dest)
    except:
        dstat = os.lstat(os.path.dirname(dest))
        destexists = 0

    if destexists:
        if stat.S_ISLNK(dstat[stat.ST_MODE]):
            try:
                os.unlink(dest)
                destexists = 0
            except Exception as e:
                pass

    if stat.S_ISLNK(sstat[stat.ST_MODE]):
        try:
            target = os.readlink(src)
            if destexists and not stat.S_ISDIR(dstat[stat.ST_MODE]):
                os.unlink(dest)
            os.symlink(target, dest)
            #os.lchown(dest,sstat[stat.ST_UID],sstat[stat.ST_GID])
            return os.lstat(dest)
        except Exception as e:
            logger.warn("copyfile: failed to create symlink %s to %s (%s)" % (dest, target, e))
            return False

    if stat.S_ISREG(sstat[stat.ST_MODE]):
        try:
            srcchown = False
            if not os.access(src, os.R_OK):
                # Make sure we can read it
                srcchown = True
                os.chmod(src, sstat[stat.ST_MODE] | stat.S_IRUSR)

            # For safety copy then move it over.
            shutil.copyfile(src, dest + "#new")
            os.rename(dest + "#new", dest)
        except Exception as e:
            logger.warn("copyfile: copy %s to %s failed (%s)" % (src, dest, e))
            return False
        finally:
            if srcchown:
                os.chmod(src, sstat[stat.ST_MODE])
                os.utime(src, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))

    else:
        #we don't yet handle special, so we need to fall back to /bin/mv
        a = getstatusoutput("/bin/cp -f " + "'" + src + "' '" + dest + "'")
        if a[0] != 0:
            logger.warn("copyfile: failed to copy special file %s to %s (%s)" % (src, dest, a))
            return False # failure
    try:
        os.lchown(dest, sstat[stat.ST_UID], sstat[stat.ST_GID])
        os.chmod(dest, stat.S_IMODE(sstat[stat.ST_MODE])) # Sticky is reset on chown
    except Exception as e:
        logger.warn("copyfile: failed to chown/chmod %s (%s)" % (dest, e))
        return False

    if newmtime:
        os.utime(dest, (newmtime, newmtime))
    else:
        os.utime(dest, (sstat[stat.ST_ATIME], sstat[stat.ST_MTIME]))
        newmtime = sstat[stat.ST_MTIME]
    return newmtime

def which(path, item, direction = 0, history = False):
    """
    Locate a file in a PATH
    """

    hist = []
    paths = (path or "").split(':')
    if direction != 0:
        paths.reverse()

    for p in paths:
        next = os.path.join(p, item)
        hist.append(next)
        if os.path.exists(next):
            if not os.path.isabs(next):
                next = os.path.abspath(next)
            if history:
                return next, hist
            return next

    if history:
        return "", hist
    return ""

def to_boolean(string, default=None):
    if not string:
        return default

    normalized = string.lower()
    if normalized in ("y", "yes", "1", "true"):
        return True
    elif normalized in ("n", "no", "0", "false"):
        return False
    else:
        raise ValueError("Invalid value for to_boolean: %s" % string)

def contains(variable, checkvalues, truevalue, falsevalue, d):
    val = d.getVar(variable, True)
    if not val:
        return falsevalue
    val = set(val.split())
    if isinstance(checkvalues, basestring):
        checkvalues = set(checkvalues.split())
    else:
        checkvalues = set(checkvalues)
    if checkvalues.issubset(val): 
        return truevalue
    return falsevalue

def contains_any(variable, checkvalues, truevalue, falsevalue, d):
    val = d.getVar(variable, True)
    if not val:
        return falsevalue
    val = set(val.split())
    if isinstance(checkvalues, basestring):
        checkvalues = set(checkvalues.split())
    else:
        checkvalues = set(checkvalues)
    if checkvalues & val:
        return truevalue
    return falsevalue

def cpu_count():
    return multiprocessing.cpu_count()

def nonblockingfd(fd):
    fcntl.fcntl(fd, fcntl.F_SETFL, fcntl.fcntl(fd, fcntl.F_GETFL) | os.O_NONBLOCK)

def process_profilelog(fn):
    pout = open(fn + '.processed', 'w')
   
    import pstats
    p = pstats.Stats(fn, stream=pout)
    p.sort_stats('time')
    p.print_stats()
    p.print_callers()
    p.sort_stats('cumulative')
    p.print_stats()

    pout.flush()
    pout.close()  

#
# Was present to work around multiprocessing pool bugs in python < 2.7.3
#
def multiprocessingpool(*args, **kwargs):

    import multiprocessing.pool
    #import multiprocessing.util
    #multiprocessing.util.log_to_stderr(10)
    # Deal with a multiprocessing bug where signals to the processes would be delayed until the work
    # completes. Putting in a timeout means the signals (like SIGINT/SIGTERM) get processed.
    def wrapper(func):
        def wrap(self, timeout=None):
            return func(self, timeout=timeout if timeout is not None else 1e100)
        return wrap
    multiprocessing.pool.IMapIterator.next = wrapper(multiprocessing.pool.IMapIterator.next)

    return multiprocessing.Pool(*args, **kwargs)

