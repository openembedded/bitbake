import hashlib
import logging
import os
import re
import bb.data

logger = logging.getLogger('BitBake.SigGen')

try:
    import cPickle as pickle
except ImportError:
    import pickle
    logger.info('Importing cPickle failed.  Falling back to a very slow implementation.')

def init(d):
    siggens = [obj for obj in globals().itervalues()
                      if type(obj) is type and issubclass(obj, SignatureGenerator)]

    desired = bb.data.getVar("BB_SIGNATURE_HANDLER", d, True) or "noop"
    for sg in siggens:
        if desired == sg.name:
            return sg(d)
            break
    else:
        logger.error("Invalid signature generator '%s', using default 'noop'\n"
                     "Available generators: %s",
                     ', '.join(obj.name for obj in siggens))
        return SignatureGenerator(d)

class SignatureGenerator(object):
    """
    """
    name = "noop"

    def __init__(self, data):
        return

    def finalise(self, fn, d, varient):
        return

    def get_taskhash(self, fn, task, deps, dataCache):
        return "0"

    def set_taskdata(self, hashes, deps):
        return

    def stampfile(self, stampbase, file_name, taskname, extrainfo):
        return ("%s.%s.%s" % (stampbase, taskname, extrainfo)).rstrip('.')

    def dump_sigtask(self, fn, task, stampbase, runtime):
        return

class SignatureGeneratorBasic(SignatureGenerator):
    """
    """
    name = "basic"

    def __init__(self, data):
        self.basehash = {}
        self.taskhash = {}
        self.taskdeps = {}
        self.runtaskdeps = {}
        self.gendeps = {}
        self.lookupcache = {}
        self.basewhitelist = set((data.getVar("BB_HASHBASE_WHITELIST", True) or "").split())
        self.taskwhitelist = data.getVar("BB_HASHTASK_WHITELIST", True) or None

        if self.taskwhitelist:
            self.twl = re.compile(self.taskwhitelist)
        else:
            self.twl = None

    def _build_data(self, fn, d):

        tasklist, gendeps, lookupcache = bb.data.generate_dependencies(d)

        taskdeps = {}
        basehash = {}

        for task in tasklist:
            data = d.getVar(task, False)
            lookupcache[task] = data

            if data is None:
                bb.error("Task %s from %s seems to be empty?!" % (task, fn))
                data = ''

            newdeps = gendeps[task]
            seen = set()
            while newdeps:
                nextdeps = newdeps
                seen |= nextdeps
                newdeps = set()
                for dep in nextdeps:
                    if dep in self.basewhitelist:
                        continue
                    newdeps |= gendeps[dep]
                newdeps -= seen

            alldeps = seen - self.basewhitelist

            for dep in sorted(alldeps):
                data = data + dep
                if dep in lookupcache:
                    var = lookupcache[dep]
                else:
                    var = d.getVar(dep, False)
                    lookupcache[dep] = var
                if var:
                    data = data + str(var)
            self.basehash[fn + "." + task] = hashlib.md5(data).hexdigest()
            taskdeps[task] = sorted(alldeps)

        self.taskdeps[fn] = taskdeps
        self.gendeps[fn] = gendeps
        self.lookupcache[fn] = lookupcache

        return taskdeps

    def finalise(self, fn, d, variant):

        if variant:
            fn = "virtual:" + variant + ":" + fn

        taskdeps = self._build_data(fn, d)

        #Slow but can be useful for debugging mismatched basehashes
        #for task in self.taskdeps[fn]:
        #    self.dump_sigtask(fn, task, d.getVar("STAMP", True), False)

        for task in taskdeps:
            d.setVar("BB_BASEHASH_task-%s" % task, self.basehash[fn + "." + task])

    def get_taskhash(self, fn, task, deps, dataCache):
        k = fn + "." + task
        data = dataCache.basetaskhash[k]
        self.runtaskdeps[k] = []
        for dep in sorted(deps, key=clean_basepath):
            # We only manipulate the dependencies for packages not in the whitelist
            if self.twl and not self.twl.search(dataCache.pkg_fn[fn]):
                # then process the actual dependencies
                dep_fn = re.search("(?P<fn>.*)\..*", dep).group('fn')
                if self.twl.search(dataCache.pkg_fn[dep_fn]):
                    continue
            if dep not in self.taskhash:
                bb.fatal("%s is not in taskhash, caller isn't calling in dependency order?", dep)
            data = data + self.taskhash[dep]
            self.runtaskdeps[k].append(dep)
        h = hashlib.md5(data).hexdigest()
        self.taskhash[k] = h
        #d.setVar("BB_TASKHASH_task-%s" % task, taskhash[task])
        return h

    def set_taskdata(self, hashes, deps):
        self.runtaskdeps = deps
        self.taskhash = hashes

    def dump_sigtask(self, fn, task, stampbase, runtime):
        k = fn + "." + task
        if runtime == "customfile":
            sigfile = stampbase
        elif runtime and k in self.taskhash:
            sigfile = stampbase + "." + task + ".sigdata" + "." + self.taskhash[k]
        else:
            sigfile = stampbase + "." + task + ".sigbasedata" + "." + self.basehash[k]

        bb.utils.mkdirhier(os.path.dirname(sigfile))

        data = {}
        data['basewhitelist'] = self.basewhitelist
        data['taskwhitelist'] = self.taskwhitelist
        data['taskdeps'] = self.taskdeps[fn][task]
        data['basehash'] = self.basehash[k]
        data['gendeps'] = {}
        data['varvals'] = {}
        data['varvals'][task] = self.lookupcache[fn][task]
        for dep in self.taskdeps[fn][task]:
            if dep in self.basewhitelist:
                continue
            data['gendeps'][dep] = self.gendeps[fn][dep]
            data['varvals'][dep] = self.lookupcache[fn][dep]

        if runtime and k in self.taskhash:
            data['runtaskdeps'] = self.runtaskdeps[k]
            data['runtaskhashes'] = {}
            for dep in data['runtaskdeps']:
                data['runtaskhashes'][dep] = self.taskhash[dep]

        p = pickle.Pickler(file(sigfile, "wb"), -1)
        p.dump(data)

    def dump_sigs(self, dataCache):
        for fn in self.taskdeps:
            for task in self.taskdeps[fn]:
                k = fn + "." + task
                if k not in self.taskhash:
                    continue
                if dataCache.basetaskhash[k] != self.basehash[k]:
                    bb.error("Bitbake's cached basehash does not match the one we just generated (%s)!" % k)
                    bb.error("The mismatched hashes were %s and %s" % (dataCache.basetaskhash[k], self.basehash[k]))
                self.dump_sigtask(fn, task, dataCache.stamp[fn], True)

class SignatureGeneratorBasicHash(SignatureGeneratorBasic):
    name = "basichash"

    def stampfile(self, stampbase, fn, taskname, extrainfo):
        if taskname != "do_setscene" and taskname.endswith("_setscene"):
            k = fn + "." + taskname[:-9]
        else:
            k = fn + "." + taskname
        h = self.taskhash[k]
        return ("%s.%s.%s.%s" % (stampbase, taskname, h, extrainfo)).rstrip('.')

def dump_this_task(outfile, d):
    import bb.parse
    fn = d.getVar("BB_FILENAME", True)
    task = "do_" + d.getVar("BB_CURRENTTASK", True)
    bb.parse.siggen.dump_sigtask(fn, task, outfile, "customfile")

def clean_basepath(a):
    if a.startswith("virtual:"):
        b = a.rsplit(":", 1)[0] + a.rsplit("/", 1)[1]
    else:
        b = a.rsplit("/", 1)[1]
    return b

def clean_basepaths(a):
    b = {}
    for x in a:
        b[clean_basepath(x)] = a[x]
    return b

def compare_sigfiles(a, b):
    p1 = pickle.Unpickler(file(a, "rb"))
    a_data = p1.load()
    p2 = pickle.Unpickler(file(b, "rb"))
    b_data = p2.load()

    def dict_diff(a, b):
        sa = set(a.keys())
        sb = set(b.keys())
        common = sa & sb
        changed = set()
        for i in common:
            if a[i] != b[i]:
                changed.add(i)
        added = sa - sb
        removed = sb - sa
        return changed, added, removed

    if 'basewhitelist' in a_data and a_data['basewhitelist'] != b_data['basewhitelist']:
        print "basewhitelist changed from %s to %s" % (a_data['basewhitelist'], b_data['basewhitelist'])
        print "changed items: %s" % a_data['basewhitelist'].symmetric_difference(b_data['basewhitelist'])

    if 'taskwhitelist' in a_data and a_data['taskwhitelist'] != b_data['taskwhitelist']:
        print "taskwhitelist changed from %s to %s" % (a_data['taskwhitelist'], b_data['taskwhitelist'])
        print "changed items: %s" % a_data['taskwhitelist'].symmetric_difference(b_data['taskwhitelist'])

    if a_data['taskdeps'] != b_data['taskdeps']:
        print "Task dependencies changed from:\n%s\nto:\n%s" % (sorted(a_data['taskdeps']), sorted(b_data['taskdeps']))

    if a_data['basehash'] != b_data['basehash']:
        print "basehash changed from %s to %s" % (a_data['basehash'], b_data['basehash'])

    changed, added, removed = dict_diff(a_data['gendeps'], b_data['gendeps'])
    if changed:
        for dep in changed:
            print "List of dependencies for variable %s changed from %s to %s" % (dep, a_data['gendeps'][dep], b_data['gendeps'][dep])
            print "changed items: %s" % a_data['gendeps'][dep].symmetric_difference(b_data['gendeps'][dep])
    if added:
        for dep in added:
            print "Dependency on variable %s was added" % (dep)
    if removed:
        for dep in removed:
            print "Dependency on Variable %s was removed" % (dep)


    changed, added, removed = dict_diff(a_data['varvals'], b_data['varvals'])
    if changed:
        for dep in changed:
            print "Variable %s value changed from %s to %s" % (dep, a_data['varvals'][dep], b_data['varvals'][dep])

    if 'runtaskhashes' in a_data and 'runtaskhashes' in b_data:
        a = clean_basepaths(a_data['runtaskhashes'])
        b = clean_basepaths(b_data['runtaskhashes'])
        changed, added, removed = dict_diff(a, b)
        if added:
            for dep in added:
                print "Dependency on task %s was added" % (dep)
        if removed:
            for dep in removed:
                print "Dependency on task %s was removed" % (dep)
        if changed:
            for dep in changed:
                print "Hash for dependent task %s changed from %s to %s" % (dep, a[dep], b[dep])
    elif 'runtaskdeps' in a_data and 'runtaskdeps' in b_data and sorted(a_data['runtaskdeps']) != sorted(b_data['runtaskdeps']):
        print "Tasks this task depends on changed from %s to %s" % (sorted(a_data['runtaskdeps']), sorted(b_data['runtaskdeps']))
        print "changed items: %s" % a_data['runtaskdeps'].symmetric_difference(b_data['runtaskdeps'])

def dump_sigfile(a):
    p1 = pickle.Unpickler(file(a, "rb"))
    a_data = p1.load()

    print "basewhitelist: %s" % (a_data['basewhitelist'])

    print "taskwhitelist: %s" % (a_data['taskwhitelist'])

    print "Task dependencies: %s" % (sorted(a_data['taskdeps']))

    print "basehash: %s" % (a_data['basehash'])

    for dep in a_data['gendeps']:
        print "List of dependencies for variable %s is %s" % (dep, a_data['gendeps'][dep])

    for dep in a_data['varvals']:
        print "Variable %s value is %s" % (dep, a_data['varvals'][dep])

    if 'runtaskdeps' in a_data:
        print "Tasks this task depends on: %s" % (a_data['runtaskdeps'])

    if 'runtaskhashes' in a_data:
        for dep in a_data['runtaskhashes']:
            print "Hash for dependent task %s is %s" % (dep, a_data['runtaskhashes'][dep])
