"""
BitBake 'Fetch' git implementation

git fetcher support the SRC_URI with format of:
SRC_URI = "git://some.host/somepath;OptionA=xxx;OptionB=xxx;..."

Supported SRC_URI options are:

- branch
   The git branch to retrieve from. The default is "master"

- tag
    The git tag to retrieve. The default is "master"

- protocol
   The method to use to access the repository. Common options are "git",
   "http", "https", "file", "ssh" and "rsync". The default is "git".

- rebaseable
   rebaseable indicates that the upstream git repo may rebase in the future,
   and current revision may disappear from upstream repo. This option will
   remind fetcher to preserve local cache carefully for future use.
   The default value is "0", set rebaseable=1 for rebaseable git repo.

- nocheckout
   Don't checkout source code when unpacking. set this option for the recipe
   who has its own routine to checkout code.
   The default is "0", set nocheckout=1 if needed.

- bareclone
   Create a bare clone of the source code and don't checkout the source code
   when unpacking. Set this option for the recipe who has its own routine to
   checkout code and tracking branch requirements.
   The default is "0", set bareclone=1 if needed.

- nobranch
   Don't check the SHA validation for branch. set this option for the recipe
   referring to commit which is valid in any namespace (branch, tag, ...)
   instead of branch.
   The default is "0", set nobranch=1 if needed.

- subpath
   Limit the checkout to a specific subpath of the tree.
   By default, checkout the whole tree, set subpath=<path> if needed

- destsuffix
   The name of the path in which to place the checkout.
   By default, the path is git/, set destsuffix=<suffix> if needed

- usehead
   For local git:// urls to use the current branch HEAD as the revision for use with
   AUTOREV. Implies nobranch.

- lfs
    Enable the checkout to use LFS for large files. This will download all LFS files
    in the download step, as the unpack step does not have network access.
    The default is "1", set lfs=0 to skip.

"""

# Copyright (C) 2005 Richard Purdie
#
# SPDX-License-Identifier: GPL-2.0-only
#

import collections
import errno
import fnmatch
import os
import re
import shlex
import shutil
import subprocess
import tempfile
import urllib
import bb
import bb.progress
from contextlib import contextmanager
from   bb.fetch2 import FetchMethod
from   bb.fetch2 import runfetchcmd
from   bb.fetch2 import logger
from   bb.fetch2 import trusted_network


sha1_re = re.compile(r'^[0-9a-f]{40}$')
slash_re = re.compile(r"/+")

class GitProgressHandler(bb.progress.LineFilterProgressHandler):
    """Extract progress information from git output"""
    def __init__(self, d):
        self._buffer = ''
        self._count = 0
        super(GitProgressHandler, self).__init__(d)
        # Send an initial progress event so the bar gets shown
        self._fire_progress(-1)

    def write(self, string):
        self._buffer += string
        stages = ['Counting objects', 'Compressing objects', 'Receiving objects', 'Resolving deltas']
        stage_weights = [0.2, 0.05, 0.5, 0.25]
        stagenum = 0
        for i, stage in reversed(list(enumerate(stages))):
            if stage in self._buffer:
                stagenum = i
                self._buffer = ''
                break
        self._status = stages[stagenum]
        percs = re.findall(r'(\d+)%', string)
        if percs:
            progress = int(round((int(percs[-1]) * stage_weights[stagenum]) + (sum(stage_weights[:stagenum]) * 100)))
            rates = re.findall(r'([\d.]+ [a-zA-Z]*/s+)', string)
            if rates:
                rate = rates[-1]
            else:
                rate = None
            self.update(progress, rate)
        else:
            if stagenum == 0:
                percs = re.findall(r': (\d+)', string)
                if percs:
                    count = int(percs[-1])
                    if count > self._count:
                        self._count = count
                        self._fire_progress(-count)
        super(GitProgressHandler, self).write(string)


class Git(FetchMethod):
    bitbake_dir = os.path.abspath(os.path.join(os.path.dirname(os.path.join(os.path.abspath(__file__))), '..', '..', '..'))
    make_shallow_path = os.path.join(bitbake_dir, 'bin', 'git-make-shallow')

    """Class to fetch a module or modules from git repositories"""
    def init(self, d):
        pass

    def supports(self, ud, d):
        """
        Check to see if a given url can be fetched with git.
        """
        return ud.type in ['git']

    def supports_checksum(self, urldata):
        return False

    def cleanup_upon_failure(self):
        return False

    def urldata_init(self, ud, d):
        """
        init git specific variable within url data
        so that the git method like latest_revision() can work
        """
        if 'protocol' in ud.parm:
            ud.proto = ud.parm['protocol']
        elif not ud.host:
            ud.proto = 'file'
        else:
            ud.proto = "git"
        if ud.host == "github.com" and ud.proto == "git":
            # github stopped supporting git protocol
            # https://github.blog/2021-09-01-improving-git-protocol-security-github/#no-more-unauthenticated-git
            ud.proto = "https"
            bb.warn("URL: %s uses git protocol which is no longer supported by github. Please change to ;protocol=https in the url." % ud.url)

        if not ud.proto in ('git', 'file', 'ssh', 'http', 'https', 'rsync'):
            raise bb.fetch2.ParameterError("Invalid protocol type", ud.url)

        ud.nocheckout = ud.parm.get("nocheckout","0") == "1"

        ud.rebaseable = ud.parm.get("rebaseable","0") == "1"

        ud.nobranch = ud.parm.get("nobranch","0") == "1"

        # usehead implies nobranch
        ud.usehead = ud.parm.get("usehead","0") == "1"
        if ud.usehead:
            if ud.proto != "file":
                 raise bb.fetch2.ParameterError("The usehead option is only for use with local ('protocol=file') git repositories", ud.url)
            ud.nobranch = 1

        # bareclone implies nocheckout
        ud.bareclone = ud.parm.get("bareclone","0") == "1"
        if ud.bareclone:
            ud.nocheckout = 1

        ud.unresolvedrev = ""
        ud.branch = ud.parm.get("branch", "")
        if not ud.branch and not ud.nobranch:
            raise bb.fetch2.ParameterError("The url does not set any branch parameter or set nobranch=1.", ud.url)

        ud.noshared = d.getVar("BB_GIT_NOSHARED") == "1"

        ud.cloneflags = "-n"
        if not ud.noshared:
            ud.cloneflags += " -s"
        if ud.bareclone:
            ud.cloneflags += " --mirror"

        ud.shallow_skip_fast = False
        ud.shallow = d.getVar("BB_GIT_SHALLOW") == "1"
        ud.shallow_extra_refs = (d.getVar("BB_GIT_SHALLOW_EXTRA_REFS") or "").split()
        if 'tag' in ud.parm:
            ud.shallow_extra_refs.append("refs/tags/" + ud.parm['tag'])

        depth_default = d.getVar("BB_GIT_SHALLOW_DEPTH")
        if depth_default is not None:
            try:
                depth_default = int(depth_default or 0)
            except ValueError:
                raise bb.fetch2.FetchError("Invalid depth for BB_GIT_SHALLOW_DEPTH: %s" % depth_default)
            else:
                if depth_default < 0:
                    raise bb.fetch2.FetchError("Invalid depth for BB_GIT_SHALLOW_DEPTH: %s" % depth_default)
        else:
            depth_default = 1
        ud.shallow_depths = collections.defaultdict(lambda: depth_default)

        revs_default = d.getVar("BB_GIT_SHALLOW_REVS")
        ud.shallow_revs = []

        ud.unresolvedrev = ud.branch

        shallow_depth = d.getVar("BB_GIT_SHALLOW_DEPTH_%s" % ud.name)
        if shallow_depth is not None:
            try:
                shallow_depth = int(shallow_depth or 0)
            except ValueError:
                raise bb.fetch2.FetchError("Invalid depth for BB_GIT_SHALLOW_DEPTH_%s: %s" % (ud.name, shallow_depth))
            else:
                if shallow_depth < 0:
                    raise bb.fetch2.FetchError("Invalid depth for BB_GIT_SHALLOW_DEPTH_%s: %s" % (ud.name, shallow_depth))
                ud.shallow_depths[ud.name] = shallow_depth

        revs = d.getVar("BB_GIT_SHALLOW_REVS_%s" % ud.name)
        if revs is not None:
            ud.shallow_revs.extend(revs.split())
        elif revs_default is not None:
            ud.shallow_revs.extend(revs_default.split())

        if ud.shallow and not ud.shallow_revs and ud.shallow_depths[ud.name] == 0:
            # Shallow disabled for this URL
            ud.shallow = False

        if ud.usehead:
            # When usehead is set let's associate 'HEAD' with the unresolved
            # rev of this repository. This will get resolved into a revision
            # later. If an actual revision happens to have also been provided
            # then this setting will be overridden.
            ud.unresolvedrev = 'HEAD'

        ud.basecmd = d.getVar("FETCHCMD_git") or "git -c gc.autoDetach=false -c core.pager=cat -c safe.bareRepository=all -c clone.defaultRemoteName=origin"

        write_tarballs = d.getVar("BB_GENERATE_MIRROR_TARBALLS") or "0"
        ud.write_tarballs = write_tarballs != "0" or ud.rebaseable
        ud.write_shallow_tarballs = (d.getVar("BB_GENERATE_SHALLOW_TARBALLS") or write_tarballs) != "0"

        ud.setup_revisions(d)

        # Ensure any revision that doesn't look like a SHA-1 is translated into one
        if not sha1_re.match(ud.revision or ''):
            if ud.revision:
                ud.unresolvedrev = ud.revision
            ud.revision = self.latest_revision(ud, d, ud.name)

        gitsrcname = '%s%s' % (ud.host.replace(':', '.'), ud.path.replace('/', '.').replace('*', '.').replace(' ','_').replace('(', '_').replace(')', '_'))
        if gitsrcname.startswith('.'):
            gitsrcname = gitsrcname[1:]

        # For a rebaseable git repo, it is necessary to keep a mirror tar ball
        # per revision, so that even if the revision disappears from the
        # upstream repo in the future, the mirror will remain intact and still
        # contain the revision
        if ud.rebaseable:
            gitsrcname = gitsrcname + '_' + ud.revision

        dl_dir = d.getVar("DL_DIR")
        gitdir = d.getVar("GITDIR") or (dl_dir + "/git2")
        ud.clonedir = os.path.join(gitdir, gitsrcname)
        ud.localfile = ud.clonedir

        mirrortarball = 'git2_%s.tar.gz' % gitsrcname
        ud.fullmirror = os.path.join(dl_dir, mirrortarball)
        ud.mirrortarballs = [mirrortarball]
        if ud.shallow:
            tarballname = gitsrcname
            if ud.bareclone:
                tarballname = "%s_bare" % tarballname

            if ud.shallow_revs:
                tarballname = "%s_%s" % (tarballname, "_".join(sorted(ud.shallow_revs)))

            tarballname = "%s_%s" % (tarballname, ud.revision[:7])
            depth = ud.shallow_depths[ud.name]
            if depth:
                tarballname = "%s-%s" % (tarballname, depth)

            shallow_refs = []
            if not ud.nobranch:
                shallow_refs.append(ud.branch)
            if ud.shallow_extra_refs:
                shallow_refs.extend(r.replace('refs/heads/', '').replace('*', 'ALL') for r in ud.shallow_extra_refs)
            if shallow_refs:
                tarballname = "%s_%s" % (tarballname, "_".join(sorted(shallow_refs)).replace('/', '.'))

            fetcher = self.__class__.__name__.lower()
            ud.shallowtarball = '%sshallow_%s.tar.gz' % (fetcher, tarballname)
            ud.fullshallow = os.path.join(dl_dir, ud.shallowtarball)
            ud.mirrortarballs.insert(0, ud.shallowtarball)

    def localpath(self, ud, d):
        return ud.clonedir

    def need_update(self, ud, d):
        return self.clonedir_need_update(ud, d) \
                or self.shallow_tarball_need_update(ud) \
                or self.tarball_need_update(ud) \
                or self.lfs_need_update(ud, d)

    def clonedir_need_update(self, ud, d):
        if not os.path.exists(ud.clonedir):
            return True
        if ud.shallow and ud.write_shallow_tarballs and self.clonedir_need_shallow_revs(ud, d):
            return True
        if not self._contains_ref(ud, d, ud.name, ud.clonedir):
            return True
        if 'tag' in ud.parm and not self._contains_ref(ud, d, ud.name, ud.clonedir, tag=True):
            return True
        return False

    def lfs_need_update(self, ud, d):
        if not self._need_lfs(ud):
            return False

        if self.clonedir_need_update(ud, d):
            return True

        if not self._lfs_objects_downloaded(ud, d, ud.clonedir):
            return True
        return False

    def clonedir_need_shallow_revs(self, ud, d):
        for rev in ud.shallow_revs:
            try:
                runfetchcmd('%s rev-parse -q --verify %s' % (ud.basecmd, rev), d, quiet=True, workdir=ud.clonedir)
            except bb.fetch2.FetchError:
                return rev
        return None

    def shallow_tarball_need_update(self, ud):
        return ud.shallow and ud.write_shallow_tarballs and not os.path.exists(ud.fullshallow)

    def tarball_need_update(self, ud):
        return ud.write_tarballs and not os.path.exists(ud.fullmirror)

    def update_mirror_links(self, ud, origud):
        super().update_mirror_links(ud, origud)
        # When using shallow mode, add a symlink to the original fullshallow
        # path to ensure a valid symlink even in the `PREMIRRORS` case
        if ud.shallow and not os.path.exists(origud.fullshallow):
            self.ensure_symlink(ud.localpath, origud.fullshallow)

    def try_premirror(self, ud, d):
        # If we don't do this, updating an existing checkout with only premirrors
        # is not possible
        if bb.utils.to_boolean(d.getVar("BB_FETCH_PREMIRRORONLY")):
            return True
        # If the url is not in trusted network, that is, BB_NO_NETWORK is set to 0
        # and BB_ALLOWED_NETWORKS does not contain the host that ud.url uses, then
        # we need to try premirrors first as using upstream is destined to fail.
        if not trusted_network(d, ud.url):
            return True
        # the following check is to ensure incremental fetch in downloads, this is
        # because the premirror might be old and does not contain the new rev required,
        # and this will cause a total removal and new clone. So if we can reach to
        # network, we prefer upstream over premirror, though the premirror might contain
        # the new rev.
        if os.path.exists(ud.clonedir):
            return False
        return True

    def download(self, ud, d):
        """Fetch url"""

        # A current clone is preferred to either tarball, a shallow tarball is
        # preferred to an out of date clone, and a missing clone will use
        # either tarball.
        if ud.shallow and os.path.exists(ud.fullshallow) and self.need_update(ud, d):
            ud.localpath = ud.fullshallow
            return
        elif os.path.exists(ud.fullmirror) and self.need_update(ud, d):
            if not os.path.exists(ud.clonedir):
                bb.utils.mkdirhier(ud.clonedir)
                runfetchcmd("tar -xzf %s" % ud.fullmirror, d, workdir=ud.clonedir)
            else:
                tmpdir = tempfile.mkdtemp(dir=d.getVar('DL_DIR'))
                runfetchcmd("tar -xzf %s" % ud.fullmirror, d, workdir=tmpdir)
                output = runfetchcmd("%s remote" % ud.basecmd, d, quiet=True, workdir=ud.clonedir)
                if 'mirror' in output:
                    runfetchcmd("%s remote rm mirror" % ud.basecmd, d, workdir=ud.clonedir)
                runfetchcmd("%s remote add --mirror=fetch mirror %s" % (ud.basecmd, tmpdir), d, workdir=ud.clonedir)
                fetch_cmd = "LANG=C %s fetch -f --update-head-ok  --progress mirror " % (ud.basecmd)
                runfetchcmd(fetch_cmd, d, workdir=ud.clonedir)
        repourl = self._get_repo_url(ud)

        needs_clone = False
        if os.path.exists(ud.clonedir):
            # The directory may exist, but not be the top level of a bare git
            # repository in which case it needs to be deleted and re-cloned.
            try:
                # Since clones can be bare, use --absolute-git-dir instead of --show-toplevel
                output = runfetchcmd("LANG=C %s rev-parse --absolute-git-dir" % ud.basecmd, d, workdir=ud.clonedir)
                toplevel = output.rstrip()

                if not bb.utils.path_is_descendant(toplevel, ud.clonedir):
                    logger.warning("Top level directory '%s' is not a descendant of '%s'. Re-cloning", toplevel, ud.clonedir)
                    needs_clone = True
            except bb.fetch2.FetchError as e:
                logger.warning("Unable to get top level for %s (not a git directory?): %s", ud.clonedir, e)
                needs_clone = True
            except FileNotFoundError as e:
                logger.warning("%s", e)
                needs_clone = True

            if needs_clone:
                shutil.rmtree(ud.clonedir)
        else:
            needs_clone = True

        # If the repo still doesn't exist, fallback to cloning it
        if needs_clone:
            # We do this since git will use a "-l" option automatically for local urls where possible,
            # but it doesn't work when git/objects is a symlink, only works when it is a directory.
            if repourl.startswith("file://"):
                repourl_path = repourl[7:]
                objects = os.path.join(repourl_path, 'objects')
                if os.path.isdir(objects) and not os.path.islink(objects):
                    repourl = repourl_path
            clone_cmd = "LANG=C %s clone --bare --mirror %s %s --progress" % (ud.basecmd, shlex.quote(repourl), ud.clonedir)
            if ud.proto.lower() != 'file':
                bb.fetch2.check_network_access(d, clone_cmd, ud.url)
            progresshandler = GitProgressHandler(d)

            # Try creating a fast initial shallow clone
            # Enabling ud.shallow_skip_fast will skip this
            # If the Git error "Server does not allow request for unadvertised object"
            # occurs, shallow_skip_fast is enabled automatically.
            # This may happen if the Git server does not allow the request
            # or if the Git client has issues with this functionality.
            if ud.shallow and not ud.shallow_skip_fast:
                try:
                    self.clone_shallow_with_tarball(ud, d)
                    # When the shallow clone has succeeded, use the shallow tarball
                    ud.localpath = ud.fullshallow
                    return
                except:
                    logger.warning("Creating fast initial shallow clone failed, try initial regular clone now.")

            # When skipping fast initial shallow or the fast inital shallow clone failed:
            # Try again with an initial regular clone
            runfetchcmd(clone_cmd, d, log=progresshandler)

        # Update the checkout if needed
        if self.clonedir_need_update(ud, d):
            output = runfetchcmd("%s remote" % ud.basecmd, d, quiet=True, workdir=ud.clonedir)
            if "origin" in output:
              runfetchcmd("%s remote rm origin" % ud.basecmd, d, workdir=ud.clonedir)

            runfetchcmd("%s remote add --mirror=fetch origin %s" % (ud.basecmd, shlex.quote(repourl)), d, workdir=ud.clonedir)

            if ud.nobranch:
                fetch_cmd = "LANG=C %s fetch -f --progress %s refs/*:refs/*" % (ud.basecmd, shlex.quote(repourl))
            else:
                fetch_cmd = "LANG=C %s fetch -f --progress %s refs/heads/*:refs/heads/* refs/tags/*:refs/tags/*" % (ud.basecmd, shlex.quote(repourl))
            if ud.proto.lower() != 'file':
                bb.fetch2.check_network_access(d, fetch_cmd, ud.url)
            progresshandler = GitProgressHandler(d)
            runfetchcmd(fetch_cmd, d, log=progresshandler, workdir=ud.clonedir)
            runfetchcmd("%s prune-packed" % ud.basecmd, d, workdir=ud.clonedir)
            runfetchcmd("%s pack-refs --all" % ud.basecmd, d, workdir=ud.clonedir)
            runfetchcmd("%s pack-redundant --all | xargs -r rm" % ud.basecmd, d, workdir=ud.clonedir)
            try:
                os.unlink(ud.fullmirror)
            except OSError as exc:
                if exc.errno != errno.ENOENT:
                    raise

        if not self._contains_ref(ud, d, ud.name, ud.clonedir):
            raise bb.fetch2.FetchError("Unable to find revision %s in branch %s even from upstream" % (ud.revision, ud.branch))

        if ud.shallow and ud.write_shallow_tarballs:
            missing_rev = self.clonedir_need_shallow_revs(ud, d)
            if missing_rev:
                raise bb.fetch2.FetchError("Unable to find revision %s even from upstream" % missing_rev)

        if self.lfs_need_update(ud, d):
            self.lfs_fetch(ud, d, ud.clonedir, ud.revision)

    def lfs_fetch(self, ud, d, clonedir, revision, fetchall=False, progresshandler=None):
        """Helper method for fetching Git LFS data"""
        try:
            if self._need_lfs(ud) and self._contains_lfs(ud, d, clonedir) and len(revision):
                self._ensure_git_lfs(d, ud)

                # Using worktree with the revision because .lfsconfig may exists
                worktree_add_cmd = "%s worktree add wt %s" % (ud.basecmd, revision)
                runfetchcmd(worktree_add_cmd, d, log=progresshandler, workdir=clonedir)
                lfs_fetch_cmd = "%s lfs fetch %s" % (ud.basecmd, "--all" if fetchall else "")
                runfetchcmd(lfs_fetch_cmd, d, log=progresshandler, workdir=(clonedir + "/wt"))
                worktree_rem_cmd = "%s worktree remove -f wt" % ud.basecmd
                runfetchcmd(worktree_rem_cmd, d, log=progresshandler, workdir=clonedir)
        except:
            logger.warning("Fetching LFS did not succeed.")

    @contextmanager
    def create_atomic(self, filename):
        """Create as a temp file and move atomically into position to avoid races"""
        fd, tfile = tempfile.mkstemp(dir=os.path.dirname(filename))
        try:
            yield tfile
            umask = os.umask(0o666)
            os.umask(umask)
            os.chmod(tfile, (0o666 & ~umask))
            os.rename(tfile, filename)
        finally:
            os.close(fd)

    def build_mirror_data(self, ud, d):
        if ud.shallow and ud.write_shallow_tarballs:
            if not os.path.exists(ud.fullshallow):
                if os.path.islink(ud.fullshallow):
                    os.unlink(ud.fullshallow)
                self.clone_shallow_with_tarball(ud, d)
        elif ud.write_tarballs and not os.path.exists(ud.fullmirror):
            if os.path.islink(ud.fullmirror):
                os.unlink(ud.fullmirror)

            logger.info("Creating tarball of git repository")
            with self.create_atomic(ud.fullmirror) as tfile:
                mtime = runfetchcmd("{} log --all -1 --format=%cD".format(ud.basecmd), d,
                        quiet=True, workdir=ud.clonedir)
                runfetchcmd("tar -czf %s --owner oe:0 --group oe:0 --mtime \"%s\" ."
                        % (tfile, mtime), d, workdir=ud.clonedir)
            runfetchcmd("touch %s.done" % ud.fullmirror, d)

    def clone_shallow_with_tarball(self, ud, d):
        ret = False
        tempdir = tempfile.mkdtemp(dir=d.getVar('DL_DIR'))
        shallowclone = os.path.join(tempdir, 'git')
        try:
            try:
                self.clone_shallow_local(ud, shallowclone, d)
            except:
                logger.warning("Fast shallow clone failed, try to skip fast mode now.")
                bb.utils.remove(tempdir, recurse=True)
                os.mkdir(tempdir)
                ud.shallow_skip_fast = True
                self.clone_shallow_local(ud, shallowclone, d)
            logger.info("Creating tarball of git repository")
            with self.create_atomic(ud.fullshallow) as tfile:
                runfetchcmd("tar -czf %s ." % tfile, d, workdir=shallowclone)
            runfetchcmd("touch %s.done" % ud.fullshallow, d)
            ret = True
        finally:
            bb.utils.remove(tempdir, recurse=True)

        return ret

    def clone_shallow_local(self, ud, dest, d):
        """
        Shallow fetch from ud.clonedir (${DL_DIR}/git2/<gitrepo> by default):
        - For BB_GIT_SHALLOW_DEPTH: git fetch --depth <depth> rev
        - For BB_GIT_SHALLOW_REVS: git fetch --shallow-exclude=<revs> rev
        """

        progresshandler = GitProgressHandler(d)
        repourl = self._get_repo_url(ud)
        bb.utils.mkdirhier(dest)
        init_cmd = "%s init -q" % ud.basecmd
        if ud.bareclone:
            init_cmd += " --bare"
        runfetchcmd(init_cmd, d, workdir=dest)
        # Use repourl when creating a fast initial shallow clone
        # Prefer already existing full bare clones if available
        if not ud.shallow_skip_fast and not os.path.exists(ud.clonedir):
            remote = shlex.quote(repourl)
        else:
            remote = ud.clonedir
        runfetchcmd("%s remote add origin %s" % (ud.basecmd, remote), d, workdir=dest)

        # Check the histories which should be excluded
        shallow_exclude = ''
        for revision in ud.shallow_revs:
            shallow_exclude += " --shallow-exclude=%s" % revision

        revision = ud.revision
        depth = ud.shallow_depths[ud.name]

        # The --depth and --shallow-exclude can't be used together
        if depth and shallow_exclude:
            raise bb.fetch2.FetchError("BB_GIT_SHALLOW_REVS is set, but BB_GIT_SHALLOW_DEPTH is not 0.")

        # For nobranch, we need a ref, otherwise the commits will be
        # removed, and for non-nobranch, we truncate the branch to our
        # srcrev, to avoid keeping unnecessary history beyond that.
        branch = ud.branch
        if ud.nobranch:
            ref = "refs/shallow/%s" % ud.name
        elif ud.bareclone:
            ref = "refs/heads/%s" % branch
        else:
            ref = "refs/remotes/origin/%s" % branch

        fetch_cmd = "%s fetch origin %s" % (ud.basecmd, revision)
        if depth:
            fetch_cmd += " --depth %s" % depth

        if shallow_exclude:
            fetch_cmd += shallow_exclude

        # Advertise the revision for lower version git such as 2.25.1:
        # error: Server does not allow request for unadvertised object.
        # The ud.clonedir is a local temporary dir, will be removed when
        # fetch is done, so we can do anything on it.
        adv_cmd = 'git branch -f advertise-%s %s' % (revision, revision)
        if ud.shallow_skip_fast:
            runfetchcmd(adv_cmd, d, workdir=ud.clonedir)

        runfetchcmd(fetch_cmd, d, workdir=dest)
        runfetchcmd("%s update-ref %s %s" % (ud.basecmd, ref, revision), d, workdir=dest)
        # Fetch Git LFS data
        self.lfs_fetch(ud, d, dest, ud.revision)

        # Apply extra ref wildcards
        all_refs_remote = runfetchcmd("%s ls-remote origin 'refs/*'" % ud.basecmd, \
                                        d, workdir=dest).splitlines()
        all_refs = []
        for line in all_refs_remote:
            all_refs.append(line.split()[-1])
        extra_refs = []
        for r in ud.shallow_extra_refs:
            if not ud.bareclone:
                r = r.replace('refs/heads/', 'refs/remotes/origin/')

            if '*' in r:
                matches = filter(lambda a: fnmatch.fnmatchcase(a, r), all_refs)
                extra_refs.extend(matches)
            else:
                extra_refs.append(r)

        for ref in extra_refs:
            ref_fetch = ref.replace('refs/heads/', '').replace('refs/remotes/origin/', '').replace('refs/tags/', '')
            runfetchcmd("%s fetch origin --depth 1 %s" % (ud.basecmd, ref_fetch), d, workdir=dest)
            revision = runfetchcmd("%s rev-parse FETCH_HEAD" % ud.basecmd, d, workdir=dest)
            runfetchcmd("%s update-ref %s %s" % (ud.basecmd, ref, revision), d, workdir=dest)

        # The url is local ud.clonedir, set it to upstream one
        runfetchcmd("%s remote set-url origin %s" % (ud.basecmd, shlex.quote(repourl)), d, workdir=dest)

    def unpack(self, ud, destdir, d):
        """ unpack the downloaded src to destdir"""

        subdir = ud.parm.get("subdir")
        subpath = ud.parm.get("subpath")
        readpathspec = ""
        def_destsuffix = (d.getVar("BB_GIT_DEFAULT_DESTSUFFIX") or "git") + "/"

        if subpath:
            readpathspec = ":%s" % subpath
            def_destsuffix = "%s/" % os.path.basename(subpath.rstrip('/'))

        if subdir:
            # If 'subdir' param exists, create a dir and use it as destination for unpack cmd
            if os.path.isabs(subdir):
                if not os.path.realpath(subdir).startswith(os.path.realpath(destdir)):
                    raise bb.fetch2.UnpackError("subdir argument isn't a subdirectory of unpack root %s" % destdir, ud.url)
                destdir = subdir
            else:
                destdir = os.path.join(destdir, subdir)
            def_destsuffix = ""

        destsuffix = ud.parm.get("destsuffix", def_destsuffix)
        destdir = ud.destdir = os.path.join(destdir, destsuffix)
        if os.path.exists(destdir):
            bb.utils.prunedir(destdir)
        if not ud.bareclone:
            ud.unpack_tracer.unpack("git", destdir)

        need_lfs = self._need_lfs(ud)

        if not need_lfs:
            ud.basecmd = "GIT_LFS_SKIP_SMUDGE=1 " + ud.basecmd

        source_found = False
        source_error = []

        clonedir_is_up_to_date = not self.clonedir_need_update(ud, d)
        if clonedir_is_up_to_date:
            runfetchcmd("%s clone %s %s/ %s" % (ud.basecmd, ud.cloneflags, ud.clonedir, destdir), d)
            source_found = True
        else:
            source_error.append("clone directory not available or not up to date: " + ud.clonedir)

        if not source_found:
            if ud.shallow:
                if os.path.exists(ud.fullshallow):
                    bb.utils.mkdirhier(destdir)
                    runfetchcmd("tar -xzf %s" % ud.fullshallow, d, workdir=destdir)
                    source_found = True
                else:
                    source_error.append("shallow clone not available: " + ud.fullshallow)
            else:
                source_error.append("shallow clone not enabled")

        if not source_found:
            raise bb.fetch2.UnpackError("No up to date source found: " + "; ".join(source_error), ud.url)

        # If there is a tag parameter in the url and we also have a fixed srcrev, check the tag
        # matches the revision
        if 'tag' in ud.parm and sha1_re.match(ud.revision):
            output = runfetchcmd("%s rev-list -n 1 %s" % (ud.basecmd, ud.parm['tag']), d, workdir=destdir)
            output = output.strip()
            if output != ud.revision:
                # It is possible ud.revision is the revision on an annotated tag which won't match the output of rev-list
                # If it resolves to the same thing there isn't a problem.
                output2 = runfetchcmd("%s rev-list -n 1 %s" % (ud.basecmd, ud.revision), d, workdir=destdir)
                output2 = output2.strip()
                if output != output2:
                    raise bb.fetch2.FetchError("The revision the git tag '%s' resolved to didn't match the SRCREV in use (%s vs %s)" % (ud.parm['tag'], output, ud.revision), ud.url)

        repourl = self._get_repo_url(ud)
        runfetchcmd("%s remote set-url origin %s" % (ud.basecmd, shlex.quote(repourl)), d, workdir=destdir)

        if self._contains_lfs(ud, d, destdir):
            if not need_lfs:
                bb.note("Repository %s has LFS content but it is not being fetched" % (repourl))
            else:
                self._ensure_git_lfs(d, ud)

                runfetchcmd("%s lfs install --local" % ud.basecmd, d, workdir=destdir)

        if not ud.nocheckout:
            if subpath:
                runfetchcmd("%s read-tree %s%s" % (ud.basecmd, ud.revision, readpathspec), d,
                            workdir=destdir)
                runfetchcmd("%s checkout-index -q -f -a" % ud.basecmd, d, workdir=destdir)
            elif not ud.nobranch:
                branchname =  ud.branch
                runfetchcmd("%s checkout -B %s %s" % (ud.basecmd, branchname, \
                            ud.revision), d, workdir=destdir)
                runfetchcmd("%s branch %s --set-upstream-to origin/%s" % (ud.basecmd, branchname, \
                            branchname), d, workdir=destdir)
            else:
                runfetchcmd("%s checkout %s" % (ud.basecmd, ud.revision), d, workdir=destdir)

        return True

    def clean(self, ud, d):
        """ clean the git directory """

        to_remove = [ud.localpath, ud.fullmirror, ud.fullmirror + ".done"]
        # The localpath is a symlink to clonedir when it is cloned from a
        # mirror, so remove both of them.
        if os.path.islink(ud.localpath):
            clonedir = os.path.realpath(ud.localpath)
            to_remove.append(clonedir)

        # Remove shallow mirror tarball
        if ud.shallow:
            to_remove.append(ud.fullshallow)
            to_remove.append(ud.fullshallow + ".done")

        for r in to_remove:
            if os.path.exists(r) or os.path.islink(r):
                bb.note('Removing %s' % r)
                bb.utils.remove(r, True)

    def supports_srcrev(self):
        return True

    def _contains_ref(self, ud, d, name, wd, tag=False):
        cmd = ""
        git_ref_name = 'refs/tags/%s' % ud.parm['tag'] if tag else ud.revision

        if ud.nobranch:
            cmd = "%s log --pretty=oneline -n 1 %s -- 2> /dev/null | wc -l" % (
                ud.basecmd, git_ref_name)
        else:
            cmd =  "%s branch --contains %s --list %s 2> /dev/null | wc -l" % (
                ud.basecmd, git_ref_name, ud.branch)
        try:
            output = runfetchcmd(cmd, d, quiet=True, workdir=wd)
        except bb.fetch2.FetchError:
            return False
        if len(output.split()) > 1:
            raise bb.fetch2.FetchError("The command '%s' gave output with more then 1 line unexpectedly, output: '%s'" % (cmd, output))
        return output.split()[0] != "0"

    def _lfs_objects_downloaded(self, ud, d, wd):
        """
        Verifies whether the LFS objects for requested revisions have already been downloaded
        """
        # Bail out early if this repository doesn't use LFS
        if not self._contains_lfs(ud, d, wd):
            return True

        self._ensure_git_lfs(d, ud)

        # The Git LFS specification specifies ([1]) the LFS folder layout so it should be safe to check for file
        # existence.
        # [1] https://github.com/git-lfs/git-lfs/blob/main/docs/spec.md#intercepting-git
        cmd = "%s lfs ls-files -l %s" \
                % (ud.basecmd, ud.revision)
        output = runfetchcmd(cmd, d, quiet=True, workdir=wd).rstrip()
        # Do not do any further matching if no objects are managed by LFS
        if not output:
            return True

        # Match all lines beginning with the hexadecimal OID
        oid_regex = re.compile("^(([a-fA-F0-9]{2})([a-fA-F0-9]{2})[A-Fa-f0-9]+)")
        for line in output.split("\n"):
            oid = re.search(oid_regex, line)
            if not oid:
                bb.warn("git lfs ls-files output '%s' did not match expected format." % line)
            if not os.path.exists(os.path.join(wd, "lfs", "objects", oid.group(2), oid.group(3), oid.group(1))):
                return False

        return True

    def _need_lfs(self, ud):
        return ud.parm.get("lfs", "1") == "1"

    def _contains_lfs(self, ud, d, wd):
        """
        Check if the repository has 'lfs' (large file) content
        """
        cmd = "%s grep '^[^#].*lfs' %s:.gitattributes | wc -l" % (
            ud.basecmd, ud.revision)

        try:
            output = runfetchcmd(cmd, d, quiet=True, workdir=wd)
            if int(output) > 0:
                return True
        except (bb.fetch2.FetchError,ValueError):
            pass
        return False

    def _ensure_git_lfs(self, d, ud):
        """
        Ensures that git-lfs is available, raising a FetchError if it isn't.
        """
        if shutil.which("git-lfs", path=d.getVar('PATH')) is None:
            raise bb.fetch2.FetchError(
                "Repository %s has LFS content, install git-lfs on host to download (or set lfs=0 "
                "to ignore it)" % self._get_repo_url(ud))

    def _get_repo_url(self, ud):
        """
        Return the repository URL
        """
        # Note that we do not support passwords directly in the git urls. There are several
        # reasons. SRC_URI can be written out to things like buildhistory and people don't
        # want to leak passwords like that. Its also all too easy to share metadata without
        # removing the password. ssh keys, ~/.netrc and ~/.ssh/config files can be used as
        # alternatives so we will not take patches adding password support here.
        if ud.user:
            if us.pswd:
                username = ud.user + ':' + us.pswd + '@'
            else:
                username = ud.user + '@'
        else:
            username = ""
        return "%s://%s%s%s" % (ud.proto, username, ud.host, urllib.parse.quote(ud.path))

    def _revision_key(self, ud, d, name):
        """
        Return a unique key for the url
        """
        # Collapse adjacent slashes
        return "git:" + ud.host + slash_re.sub(".", ud.path) + ud.unresolvedrev

    def _lsremote(self, ud, d, search):
        """
        Run git ls-remote with the specified search string
        """
        # Prevent recursion e.g. in OE if SRCPV is in PV, PV is in WORKDIR,
        # and WORKDIR is in PATH (as a result of RSS), our call to
        # runfetchcmd() exports PATH so this function will get called again (!)
        # In this scenario the return call of the function isn't actually
        # important - WORKDIR isn't needed in PATH to call git ls-remote
        # anyway.
        if d.getVar('_BB_GIT_IN_LSREMOTE', False):
            return ''
        d.setVar('_BB_GIT_IN_LSREMOTE', '1')
        try:
            repourl = self._get_repo_url(ud)
            cmd = "%s ls-remote %s %s" % \
                (ud.basecmd, shlex.quote(repourl), search)
            if ud.proto.lower() != 'file':
                bb.fetch2.check_network_access(d, cmd, repourl)
            output = runfetchcmd(cmd, d, True)
            if not output:
                raise bb.fetch2.FetchError("The command %s gave empty output unexpectedly" % cmd, ud.url)
        finally:
            d.delVar('_BB_GIT_IN_LSREMOTE')
        return output

    def _latest_revision(self, ud, d, name):
        """
        Compute the HEAD revision for the url
        """
        if not d.getVar("__BBSRCREV_SEEN"):
            raise bb.fetch2.FetchError("Recipe uses a floating tag/branch '%s' for repo '%s' without a fixed SRCREV yet doesn't call bb.fetch2.get_srcrev() (use SRCPV in PV for OE)." % (ud.unresolvedrev, ud.host+ud.path))

        # Ensure we mark as not cached
        bb.fetch2.mark_recipe_nocache(d)

        output = self._lsremote(ud, d, "")
        # Tags of the form ^{} may not work, need to fallback to other form
        if ud.unresolvedrev[:5] == "refs/" or ud.usehead:
            head = ud.unresolvedrev
            tag = ud.unresolvedrev
        else:
            head = "refs/heads/%s" % ud.unresolvedrev
            tag = "refs/tags/%s" % ud.unresolvedrev
        for s in [head, tag + "^{}", tag]:
            for l in output.strip().split('\n'):
                sha1, ref = l.split()
                if s == ref:
                    return sha1
        raise bb.fetch2.FetchError("Unable to resolve '%s' in upstream git repository in git ls-remote output for %s" % \
            (ud.unresolvedrev, ud.host+ud.path))

    def latest_versionstring(self, ud, d):
        """
        Compute the latest release name like "x.y.x" in "x.y.x+gitHASH"
        by searching through the tags output of ls-remote, comparing
        versions and returning the highest match.
        """
        pupver = ('', '')

        try:
            output = self._lsremote(ud, d, "refs/tags/*")
        except (bb.fetch2.FetchError, bb.fetch2.NetworkAccess) as e:
            bb.note("Could not list remote: %s" % str(e))
            return pupver

        rev_tag_re = re.compile(r"([0-9a-f]{40})\s+refs/tags/(.*)")
        pver_re = re.compile(d.getVar('UPSTREAM_CHECK_GITTAGREGEX') or r"(?P<pver>([0-9][\.|_]?)+)")
        nonrel_re = re.compile(r"(alpha|beta|rc|final)+")

        verstring = ""
        for line in output.split("\n"):
            if not line:
                break

            m = rev_tag_re.match(line)
            if not m:
                continue

            (revision, tag) = m.groups()

            # Ignore non-released branches
            if nonrel_re.search(tag):
                continue

            # search for version in the line
            m = pver_re.search(tag)
            if not m:
                continue

            pver = m.group('pver').replace("_", ".")

            if verstring and bb.utils.vercmp(("0", pver, ""), ("0", verstring, "")) < 0:
                continue

            verstring = pver
            pupver = (verstring, revision)

        return pupver

    def _build_revision(self, ud, d, name):
        return ud.revision

    def gitpkgv_revision(self, ud, d, name):
        """
        Return a sortable revision number by counting commits in the history
        Based on gitpkgv.bblass in meta-openembedded
        """
        rev = ud.revision
        localpath = ud.localpath
        rev_file = os.path.join(localpath, "oe-gitpkgv_" + rev)
        if not os.path.exists(localpath):
            commits = None
        else:
            if not os.path.exists(rev_file) or not os.path.getsize(rev_file):
                commits = bb.fetch2.runfetchcmd(
                        "git rev-list %s -- | wc -l" % shlex.quote(rev),
                        d, quiet=True).strip().lstrip('0')
                if commits:
                    open(rev_file, "w").write("%d\n" % int(commits))
            else:
                commits = open(rev_file, "r").readline(128).strip()
        if commits:
            return False, "%s+%s" % (commits, rev[:7])
        else:
            return True, str(rev)

    def checkstatus(self, fetch, ud, d):
        try:
            self._lsremote(ud, d, "")
            return True
        except bb.fetch2.FetchError:
            return False
