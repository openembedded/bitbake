#
# BitBake ToasterUI Implementation
#
# Copyright (C) 2013        Intel Corporation
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

import datetime
import sys
import bb
import re
import ast

os.environ.setdefault("DJANGO_SETTINGS_MODULE", "toaster.toastermain.settings")

import toaster.toastermain.settings as toaster_django_settings
from toaster.orm.models import Build, Task, Recipe, Layer_Version, Layer, Target, LogMessage
from toaster.orm.models import Variable, VariableHistory
from toaster.orm.models import Package, Package_File, Target_Installed_Package
from toaster.orm.models import Task_Dependency, Package_Dependency
from toaster.orm.models import Recipe_Dependency
from bb.msg import BBLogFormatter as format

class ORMWrapper(object):
    """ This class creates the dictionaries needed to store information in the database
        following the format defined by the Django models. It is also used to save this
        information in the database.
    """

    def __init__(self):
        pass


    def create_build_object(self, build_info):

        build = Build.objects.create(
                                    machine=build_info['machine'],
                                    image_fstypes=build_info['image_fstypes'],
                                    distro=build_info['distro'],
                                    distro_version=build_info['distro_version'],
                                    started_on=build_info['started_on'],
                                    completed_on=build_info['completed_on'],
                                    cooker_log_path=build_info['cooker_log_path'],
                                    build_name=build_info['build_name'],
                                    bitbake_version=build_info['bitbake_version'])

        return build

    def create_target_objects(self, target_info):
        targets = []
        for tgt_name in target_info['targets']:
            tgt_object = Target.objects.create( build = target_info['build'],
                                    target = tgt_name,
                                    is_image = False,
                                    file_name = "",
                                    file_size = 0);
            targets.append(tgt_object)
        return targets

    def update_build_object(self, build, errors, warnings, taskfailures):

        outcome = Build.SUCCEEDED
        if errors or taskfailures:
            outcome = Build.FAILED

        build.completed_on = datetime.datetime.now()
        build.timespent = int((build.completed_on - build.started_on).total_seconds())
        build.errors_no = errors
        build.warnings_no = warnings
        build.outcome = outcome
        build.save()


    def get_update_task_object(self, task_information):
        task_object, created = Task.objects.get_or_create(
                                build=task_information['build'],
                                recipe=task_information['recipe'],
                                task_name=task_information['task_name'],
                                )

        for v in vars(task_object):
            if v in task_information.keys():
                vars(task_object)[v] = task_information[v]
        # if we got covered by a setscene task, we're CACHED
        if task_object.outcome == Task.OUTCOME_COVERED and 1 == Task.objects.related_setscene(task_object).count():
            task_object.outcome = Task.OUTCOME_CACHED
            outcome_task_setscene = Task.objects.get(task_executed=True, build = task_object.build,
                                    recipe = task_object.recipe, task_name=task_object.task_name+"_setscene").outcome
            if outcome_task_setscene == Task.OUTCOME_SUCCESS:
                task_object.sstate_result = Task.SSTATE_RESTORED
            elif outcome_task_setscene == Task.OUTCOME_FAILED:
                task_object.sstate_result = Task.SSTATE_FAILED

        # mark down duration if we have a start time
        if 'start_time' in task_information.keys():
            duration = datetime.datetime.now() - task_information['start_time']
            task_object.elapsed_time = duration.total_seconds()

        task_object.save()
        return task_object


    def get_update_recipe_object(self, recipe_information):

        recipe_object, created = Recipe.objects.get_or_create(
                                         layer_version=recipe_information['layer_version'],
                                         file_path=recipe_information['file_path'])

        for v in vars(recipe_object):
            if v in recipe_information.keys():
                vars(recipe_object)[v] = recipe_information[v]

        recipe_object.save()

        return recipe_object

    def get_update_layer_version_object(self, build_obj, layer_obj, layer_version_information):

        layer_version_object = Layer_Version.objects.get_or_create(
                                    build = build_obj,
                                    layer = layer_obj,
                                    branch = layer_version_information['branch'],
                                    commit = layer_version_information['commit'],
                                    priority = layer_version_information['priority']
                                    )

        layer_version_object[0].save()

        return layer_version_object[0]

    def get_update_layer_object(self, layer_information):

        layer_object = Layer.objects.get_or_create(
                                name=layer_information['name'],
                                local_path=layer_information['local_path'],
                                layer_index_url=layer_information['layer_index_url'])
        layer_object[0].save()

        return layer_object[0]


    def save_target_package_information(self, build_obj, target_obj, packagedict, pkgpnmap, recipes):
        for p in packagedict:
            searchname = p
            if 'OPKGN' in pkgpnmap[p].keys():
                searchname = pkgpnmap[p]['OPKGN']

            packagedict[p]['object'], created = Package.objects.get_or_create( build = build_obj, name = searchname )
            if created:
                # package was not build in the current build, but
                # fill in everything we can from the runtime-reverse package data
                try:
                    packagedict[p]['object'].recipe = recipes[pkgpnmap[p]['PN']]
                    packagedict[p]['object'].version = pkgpnmap[p]['PV']
                    packagedict[p]['object'].installed_name = p
                    packagedict[p]['object'].revision = pkgpnmap[p]['PR']
                    packagedict[p]['object'].license = pkgpnmap[p]['LICENSE']
                    packagedict[p]['object'].section = pkgpnmap[p]['SECTION']
                    packagedict[p]['object'].summary = pkgpnmap[p]['SUMMARY']
                    packagedict[p]['object'].description = pkgpnmap[p]['DESCRIPTION']
                    packagedict[p]['object'].size = int(pkgpnmap[p]['PKGSIZE'])

                # no files recorded for this package, so save files info
                    for targetpath in pkgpnmap[p]['FILES_INFO']:
                        targetfilesize = pkgpnmap[p]['FILES_INFO'][targetpath]
                        Package_File.objects.create( package = packagedict[p]['object'],
                            path = targetpath,
                            size = targetfilesize)
                except KeyError as e:
                    print "Key error, package", p, "key", e

            # save disk installed size
            packagedict[p]['object'].installed_size = packagedict[p]['size']
            packagedict[p]['object'].save()

            Target_Installed_Package.objects.create(target = target_obj, package = packagedict[p]['object'])

        for p in packagedict:
            for (px,deptype) in packagedict[p]['depends']:
                if deptype == 'depends':
                    tdeptype = Package_Dependency.TYPE_TRDEPENDS
                elif deptype == 'recommends':
                    tdeptype = Package_Dependency.TYPE_TRECOMMENDS

                Package_Dependency.objects.create( package = packagedict[p]['object'],
                                        depends_on = packagedict[px]['object'],
                                        dep_type = tdeptype,
                                        target = target_obj);


    def create_logmessage(self, log_information):
        log_object = LogMessage.objects.create(
                        build = log_information['build'],
                        level = log_information['level'],
                        message = log_information['message'])

        for v in vars(log_object):
            if v in log_information.keys():
                vars(log_object)[v] = log_information[v]

        return log_object.save()


    def save_build_package_information(self, build_obj, package_info, recipes):
        # create and save the object
	pname = package_info['PKG']
        if 'OPKGN' in package_info.keys():
            pname = package_info['OPKGN']

        bp_object, created = Package.objects.get_or_create( build = build_obj,
                                       name = pname )

        bp_object.installed_name = package_info['PKG']
        bp_object.recipe = recipes[package_info['PN']]
        bp_object.version = package_info['PKGV']
        bp_object.revision = package_info['PKGR']
        bp_object.summary = package_info['SUMMARY']
        bp_object.description = package_info['DESCRIPTION']
        bp_object.size = int(package_info['PKGSIZE'])
        bp_object.section = package_info['SECTION']
        bp_object.license = package_info['LICENSE']
        bp_object.save()

        # save any attached file information
        for path in package_info['FILES_INFO']:
                fo = Package_File.objects.create( package = bp_object,
                                        path = path,
                                        size = package_info['FILES_INFO'][path] )

        def _po_byname(p):
            pkg, created = Package.objects.get_or_create(build = build_obj, name = p)
            if created:
                pkg.size = -1
                pkg.save()
            return pkg

        # save soft dependency information
        if 'RDEPENDS' in package_info and package_info['RDEPENDS']:
            for p in bb.utils.explode_deps(package_info['RDEPENDS']):
                Package_Dependency.objects.get_or_create( package = bp_object,
                    depends_on = _po_byname(p), dep_type = Package_Dependency.TYPE_RDEPENDS)
        if 'RPROVIDES' in package_info and package_info['RPROVIDES']:
            for p in bb.utils.explode_deps(package_info['RPROVIDES']):
                Package_Dependency.objects.get_or_create( package = bp_object,
                    depends_on = _po_byname(p), dep_type = Package_Dependency.TYPE_RPROVIDES)
        if 'RRECOMMENDS' in package_info and package_info['RRECOMMENDS']:
            for p in bb.utils.explode_deps(package_info['RRECOMMENDS']):
                Package_Dependency.objects.get_or_create( package = bp_object,
                    depends_on = _po_byname(p), dep_type = Package_Dependency.TYPE_RRECOMMENDS)
        if 'RSUGGESTS' in package_info and package_info['RSUGGESTS']:
            for p in bb.utils.explode_deps(package_info['RSUGGESTS']):
                Package_Dependency.objects.get_or_create( package = bp_object,
                    depends_on = _po_byname(p), dep_type = Package_Dependency.TYPE_RSUGGESTS)
        if 'RREPLACES' in package_info and package_info['RREPLACES']:
            for p in bb.utils.explode_deps(package_info['RREPLACES']):
                Package_Dependency.objects.get_or_create( package = bp_object,
                    depends_on = _po_byname(p), dep_type = Package_Dependency.TYPE_RREPLACES)
        if 'RCONFLICTS' in package_info and package_info['RCONFLICTS']:
            for p in bb.utils.explode_deps(package_info['RCONFLICTS']):
                Package_Dependency.objects.get_or_create( package = bp_object,
                    depends_on = _po_byname(p), dep_type = Package_Dependency.TYPE_RCONFLICTS)

        return bp_object

    def save_build_variables(self, build_obj, vardump):
        for k in vardump:
            if not bool(vardump[k]['func']):
                value = vardump[k]['v'];
                if value is None:
                    value = ''
                desc = vardump[k]['doc'];
                if desc is None:
                    var_words = [word for word in k.split('_')]
                    root_var = "_".join([word for word in var_words if word.isupper()])
                    if root_var and root_var != k and root_var in vardump:
                        desc = vardump[root_var]['doc']
                if desc is None:
                    desc = ''
                variable_obj = Variable.objects.create( build = build_obj,
                    variable_name = k,
                    variable_value = value,
                    description = desc)
                for vh in vardump[k]['history']:
                    if not 'documentation.conf' in vh['file']:
                        VariableHistory.objects.create( variable = variable_obj,
                                file_name = vh['file'],
                                line_number = vh['line'],
                                operation = vh['op'])

class BuildInfoHelper(object):
    """ This class gathers the build information from the server and sends it
        towards the ORM wrapper for storing in the database
        It is instantiated once per build
        Keeps in memory all data that needs matching before writing it to the database
    """

    def __init__(self, server, has_build_history = False):
        self._configure_django()
        self.internal_state = {}
        self.internal_state['taskdata'] = {}
        self.task_order = 0
        self.server = server
        self.orm_wrapper = ORMWrapper()
        self.has_build_history = has_build_history
        self.tmp_dir = self.server.runCommand(["getVariable", "TMPDIR"])[0]

    def _configure_django(self):
        # Add toaster to sys path for importing modules
        sys.path.append(os.path.join(os.path.dirname(os.path.dirname(os.path.dirname(__file__))), 'toaster'))

    ###################
    ## methods to convert event/external info into objects that the ORM layer uses


    def _get_build_information(self):
        build_info = {}
        # Generate an identifier for each new build

        build_info['machine'] = self.server.runCommand(["getVariable", "MACHINE"])[0]
        build_info['distro'] = self.server.runCommand(["getVariable", "DISTRO"])[0]
        build_info['distro_version'] = self.server.runCommand(["getVariable", "DISTRO_VERSION"])[0]
        build_info['started_on'] = datetime.datetime.now()
        build_info['completed_on'] = datetime.datetime.now()
        build_info['image_fstypes'] = self._remove_redundant(self.server.runCommand(["getVariable", "IMAGE_FSTYPES"])[0] or "")
        build_info['cooker_log_path'] = self.server.runCommand(["getVariable", "BB_CONSOLELOG"])[0]
        build_info['build_name'] = self.server.runCommand(["getVariable", "BUILDNAME"])[0]
        build_info['bitbake_version'] = self.server.runCommand(["getVariable", "BB_VERSION"])[0]

        return build_info

    def _get_task_information(self, event, recipe):


        task_information = {}
        task_information['build'] = self.internal_state['build']
        task_information['outcome'] = Task.OUTCOME_NA
        task_information['recipe'] = recipe
        task_information['task_name'] = event.taskname
        try:
            # some tasks don't come with a hash. and that's ok
            task_information['sstate_checksum'] = event.taskhash
        except AttributeError:
            pass
        return task_information

    def _get_layer_version_for_path(self, path):
        def _slkey(layer_version):
            return len(layer_version.layer.local_path)

        # Heuristics: we always match recipe to the deepest layer path that
        # we can match to the recipe file path
        for bl in sorted(Layer_Version.objects.filter(build = self.internal_state['build']), reverse=True, key=_slkey):
            if (path.startswith(bl.layer.local_path)):
                return bl

        #TODO: if we get here, we didn't read layers correctly
        assert False
        return None

    def _get_recipe_information_from_taskfile(self, taskfile):

        layer_version_obj = self._get_layer_version_for_path(re.split(':', taskfile)[-1])

        recipe_info = {}
        recipe_info['layer_version'] = layer_version_obj
        recipe_info['file_path'] = re.split(':', taskfile)[-1]

        return recipe_info

    def _get_path_information(self, task_object):
        build_stats_format = "{tmpdir}/buildstats/{target}-{machine}/{buildname}/{package}/"
        build_stats_path = []

        for t in self.internal_state['targets']:
            target = t.target
            machine = self.internal_state['build'].machine
            buildname = self.internal_state['build'].build_name
            pe, pv = task_object.recipe.version.split(":",1)
            if len(pe) > 0:
                package = task_object.recipe.name + "-" + pe + "_" + pv
            else:
                package = task_object.recipe.name + "-" + pv

            build_stats_path.append(build_stats_format.format(tmpdir=self.tmp_dir, target=target,
                                                     machine=machine, buildname=buildname,
                                                     package=package))

        return build_stats_path

    def _remove_redundant(self, string):
        ret = []
        for i in string.split():
            if i not in ret:
                ret.append(i)
        return " ".join(sorted(ret))


    ################################
    ## external available methods to store information

    def store_layer_info(self, event):
        layerinfos = event.data
        self.internal_state['lvs'] = {}
        for layer in layerinfos:
            self.internal_state['lvs'][self.orm_wrapper.get_update_layer_object(layerinfos[layer])] = layerinfos[layer]['version']


    def store_started_build(self, event):

        build_information = self._get_build_information()

        build_obj = self.orm_wrapper.create_build_object(build_information)
        self.internal_state['build'] = build_obj

        # save layer version information for this build
        for layer_obj in self.internal_state['lvs']:
            self.orm_wrapper.get_update_layer_version_object(build_obj, layer_obj, self.internal_state['lvs'][layer_obj])

        del self.internal_state['lvs']

        # create target information
        target_information = {}
        target_information['targets'] = event.getPkgs()
        target_information['build'] = build_obj

        self.internal_state['targets'] = self.orm_wrapper.create_target_objects(target_information)

        # Save build configuration
        self.orm_wrapper.save_build_variables(build_obj, self.server.runCommand(["getAllKeysWithFlags", ["doc", "func"]])[0])


    def update_build_information(self, event, errors, warnings, taskfailures):
        if 'build' in self.internal_state:
            self.orm_wrapper.update_build_object(self.internal_state['build'], errors, warnings, taskfailures)

    def store_started_task(self, event):
        identifier = event.taskfile.split(":")[-1] + ":" + event.taskname

        recipe_information = self._get_recipe_information_from_taskfile(event.taskfile)
        recipe = self.orm_wrapper.get_update_recipe_object(recipe_information)

        task_information = self._get_task_information(event, recipe)
        task_information['outcome'] = Task.OUTCOME_NA

        if isinstance(event, bb.runqueue.runQueueTaskSkipped):
            task_information['task_executed'] = False
            if event.reason == "covered":
                task_information['outcome'] = Task.OUTCOME_COVERED
            if event.reason == "existing":
                task_information['outcome'] = Task.OUTCOME_PREBUILT
        else:
            task_information['task_executed'] = True
            if 'noexec' in vars(event) and event.noexec == True:
                task_information['task_executed'] = False
                task_information['outcome'] = Task.OUTCOME_EMPTY
                task_information['script_type'] = Task.CODING_NA

        # do not assign order numbers to scene tasks
        if not isinstance(event, bb.runqueue.sceneQueueTaskStarted):
            self.task_order += 1
            task_information['order'] = self.task_order

        task_obj = self.orm_wrapper.get_update_task_object(task_information)

        self.internal_state['taskdata'][identifier] = {
                        'start_time': datetime.datetime.now(),
                        'outcome': task_information['outcome'],
                    }


    def store_tasks_stats(self, event):
        for (taskfile, taskname, taskstats) in event.data:
            recipe_information = self._get_recipe_information_from_taskfile(taskfile)
            recipe = self.orm_wrapper.get_update_recipe_object(recipe_information)

            task_information = {}
            task_information['build'] = self.internal_state['build']
            task_information['recipe'] = recipe
            task_information['task_name'] = taskname
            task_information['cpu_usage'] = taskstats['cpu_usage']
            task_information['disk_io'] = taskstats['disk_io']
            task_obj = self.orm_wrapper.get_update_task_object(task_information)

    def update_and_store_task(self, event):
        identifier = event.taskfile.split(":")[-1] + ":" + event.taskname
        assert identifier in self.internal_state['taskdata']

        recipe_information = self._get_recipe_information_from_taskfile(event.taskfile)
        recipe = self.orm_wrapper.get_update_recipe_object(recipe_information)
        task_information = self._get_task_information(event,recipe)

        task_information['start_time'] = self.internal_state['taskdata'][identifier]['start_time']
        task_information['outcome'] = self.internal_state['taskdata'][identifier]['outcome']

        if 'logfile' in vars(event):
            task_information['logfile'] = event.logfile

        if '_message' in vars(event):
            task_information['message'] = event._message

        if 'taskflags' in vars(event):
            # with TaskStarted, we get even more information
            if 'python' in event.taskflags.keys() and event.taskflags['python'] == '1':
                task_information['script_type'] = Task.CODING_PYTHON
            else:
                task_information['script_type'] = Task.CODING_SHELL

        if task_information['outcome'] == Task.OUTCOME_NA:
            if isinstance(event, (bb.runqueue.runQueueTaskCompleted, bb.runqueue.sceneQueueTaskCompleted)):
                task_information['outcome'] = Task.OUTCOME_SUCCESS
                del self.internal_state['taskdata'][identifier]

            if isinstance(event, (bb.runqueue.runQueueTaskFailed, bb.runqueue.sceneQueueTaskFailed)):
                task_information['outcome'] = Task.OUTCOME_FAILED
                del self.internal_state['taskdata'][identifier]

        self.orm_wrapper.get_update_task_object(task_information)


    def store_target_package_data(self, event):
        # for all image targets
        for target in self.internal_state['targets']:
            if target.is_image:
                pkgdata = event.data['pkgdata']
                imgdata = event.data['imgdata'][target.target]
                self.orm_wrapper.save_target_package_information(self.internal_state['build'], target, imgdata, pkgdata, self.internal_state['recipes'])

    def store_dependency_information(self, event):
        # save layer version priorities
        if 'layer-priorities' in event._depgraph.keys():
            for lv in event._depgraph['layer-priorities']:
                (name, path, regexp, priority) = lv
                layer_version_obj = self._get_layer_version_for_path(path[1:]) # paths start with a ^
                assert layer_version_obj is not None
                layer_version_obj.priority = priority
                layer_version_obj.save()

        # save recipe information
        self.internal_state['recipes'] = {}
        for pn in event._depgraph['pn']:

            file_name = re.split(':', event._depgraph['pn'][pn]['filename'])[-1]
            layer_version_obj = self._get_layer_version_for_path(re.split(':', file_name)[-1])

            assert layer_version_obj is not None

            recipe_info = {}
            recipe_info['name'] = pn
            recipe_info['version'] = event._depgraph['pn'][pn]['version'].lstrip(":")
            recipe_info['layer_version'] = layer_version_obj
            recipe_info['summary'] = event._depgraph['pn'][pn]['summary']
            recipe_info['license'] = event._depgraph['pn'][pn]['license']
            recipe_info['description'] = event._depgraph['pn'][pn]['description']
            recipe_info['section'] = event._depgraph['pn'][pn]['section']
            recipe_info['licensing_info'] = 'Not Available'
            recipe_info['homepage'] = event._depgraph['pn'][pn]['homepage']
            recipe_info['bugtracker'] = event._depgraph['pn'][pn]['bugtracker']
            recipe_info['file_path'] = file_name
            recipe = self.orm_wrapper.get_update_recipe_object(recipe_info)
            if 'inherits' in event._depgraph['pn'][pn].keys():
                recipe.is_image = True in map(lambda x: x.endswith('image.bbclass'), event._depgraph['pn'][pn]['inherits'])
            else:
                recipe.is_image = False
            if recipe.is_image:
                for t in self.internal_state['targets']:
                    if pn == t.target:
                        t.is_image = True
                        t.save()
            self.internal_state['recipes'][pn] = recipe

        # save recipe dependency
        # buildtime
        for recipe in event._depgraph['depends']:
            try:
                target = self.internal_state['recipes'][recipe]
                for dep in event._depgraph['depends'][recipe]:
                    dependency = self.internal_state['recipes'][dep]
                    Recipe_Dependency.objects.get_or_create( recipe = target,
                            depends_on = dependency, dep_type = Recipe_Dependency.TYPE_DEPENDS)
            except KeyError:    # we'll not get recipes for key w/ values listed in ASSUME_PROVIDED
                pass

        # runtime
        for recipe in event._depgraph['rdepends-pn']:
            try:
                target = self.internal_state['recipes'][recipe]
                for dep in event._depgraph['rdepends-pn'][recipe]:
                    dependency = self.internal_state['recipes'][dep]
                    Recipe_Dependency.objects.get_or_create( recipe = target,
                            depends_on = dependency, dep_type = Recipe_Dependency.TYPE_RDEPENDS)

            except KeyError:    # we'll not get recipes for key w/ values listed in ASSUME_PROVIDED
                pass

        # save all task information
        def _save_a_task(taskdesc):
            spec = re.split(r'\.', taskdesc);
            pn = ".".join(spec[0:-1])
            taskname = spec[-1]
            e = event
            e.taskname = pn
            recipe = self.internal_state['recipes'][pn]
            task_info = self._get_task_information(e, recipe)
            task_info['task_name'] = taskname
            task_obj = self.orm_wrapper.get_update_task_object(task_info)
            return task_obj
 
        # create tasks
        tasks = {}
        for taskdesc in event._depgraph['tdepends']:
            tasks[taskdesc] = _save_a_task(taskdesc)

        # create dependencies between tasks
        for taskdesc in event._depgraph['tdepends']:
            target = tasks[taskdesc]
            for taskdep in event._depgraph['tdepends'][taskdesc]:
                if taskdep not in tasks:
                    # Fetch tasks info is not collected previously
                    dep = _save_a_task(taskdep)
                else:
                    dep = tasks[taskdep]
                Task_Dependency.objects.get_or_create( task = target, depends_on = dep )

    def store_build_package_information(self, event):
        package_info = event.data
        self.orm_wrapper.save_build_package_information(self.internal_state['build'],
                            package_info,
                            self.internal_state['recipes'],
                            )

    def _store_log_information(self, level, text):
        log_information = {}
        log_information['build'] = self.internal_state['build']
        log_information['level'] = level
        log_information['message'] = text
        self.orm_wrapper.create_logmessage(log_information)

    def store_log_info(self, text):
        self._store_log_information(LogMessage.INFO, text)

    def store_log_warn(self, text):
        self._store_log_information(LogMessage.WARNING, text)

    def store_log_error(self, text):
        self._store_log_information(LogMessage.ERROR, text)

    def store_log_event(self, event):
        # look up license files info from insane.bbclass
        m = re.match("([^:]*): md5 checksum matched for ([^;]*)", event.msg)
        if m:
            (pn, fn) = m.groups()
            self.internal_state['recipes'][pn].licensing_info = fn
            self.internal_state['recipes'][pn].save()

        if event.levelno < format.WARNING:
            return
        if not 'build' in self.internal_state:
            return
        log_information = {}
        log_information['build'] = self.internal_state['build']
        if event.levelno >= format.ERROR:
            log_information['level'] = LogMessage.ERROR
        elif event.levelno == format.WARNING:
            log_information['level'] = LogMessage.WARNING
        log_information['message'] = event.msg
        log_information['pathname'] = event.pathname
        log_information['lineno'] = event.lineno
        self.orm_wrapper.create_logmessage(log_information)

