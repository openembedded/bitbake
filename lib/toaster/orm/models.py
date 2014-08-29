#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
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

from django.db import models
from django.db.models import F
from django.utils.encoding import python_2_unicode_compatible
from django.utils import timezone

class ToasterSetting(models.Model):
    name = models.CharField(max_length=63)
    helptext = models.TextField()
    value = models.CharField(max_length=255)

class ToasterSettingDefaultLayer(models.Model):
    layer_version = models.ForeignKey('Layer_Version')

class ProjectManager(models.Manager):
    def create_project(self, name, release):
        prj = self.model(name = name, bitbake_version = release.bitbake_version, release = release)
        prj.save()

        for defaultconf in ToasterSetting.objects.filter(name__startswith="DEFCONF_"):
            name = defaultconf.name[8:]
            ProjectVariable.objects.create( project = prj,
                name = name,
                value = defaultconf.value)

        for layer in map(lambda x: x.layer, ReleaseDefaultLayer.objects.filter(release = release)):
            for branches in Branch.objects.filter(name = release.branch):
                for lv in Layer_Version.objects.filter(layer = layer, up_branch = branches ):
                    ProjectLayer.objects.create( project = prj,
                        layercommit = lv,
                        optional = False )

        return prj

    def create(self, *args, **kwargs):
        raise Exception("Invalid call to Project.objects.create. Use Project.objects.create_project() to create a project")

    def get_or_create(self, *args, **kwargs):
        raise Exception("Invalid call to Project.objects.get_or_create. Use Project.objects.create_project() to create a project")

class Project(models.Model):
    name = models.CharField(max_length=100)
    short_description = models.CharField(max_length=50, blank=True)
    bitbake_version = models.ForeignKey('BitbakeVersion')
    release     = models.ForeignKey("Release")
    created     = models.DateTimeField(auto_now_add = True)
    updated     = models.DateTimeField(auto_now = True)
    # This is a horrible hack; since Toaster has no "User" model available when
    # running in interactive mode, we can't reference the field here directly
    # Instead, we keep a possible null reference to the User id, as not to force
    # hard links to possibly missing models
    user_id     = models.IntegerField(null = True)
    objects     = ProjectManager()


    def schedule_build(self):
        from bldcontrol.models import BuildRequest, BRTarget, BRLayer, BRVariable, BRBitbake
        br = BuildRequest.objects.create(project = self)

        BRBitbake.objects.create(req = br,
            giturl = self.bitbake_version.giturl,
            commit = self.bitbake_version.branch,
            dirpath = self.bitbake_version.dirpath)

        for l in self.projectlayer_set.all():
            BRLayer.objects.create(req = br, name = l.layercommit.layer.name, giturl = l.layercommit.layer.vcs_url, commit = l.layercommit.commit, dirpath = l.layercommit.dirpath)
        for t in self.projecttarget_set.all():
            BRTarget.objects.create(req = br, target = t.target, task = t.task)
        for v in self.projectvariable_set.all():
            BRVariable.objects.create(req = br, name = v.name, value = v.value)

        br.state = BuildRequest.REQ_QUEUED
        br.save()
        return br

class Build(models.Model):
    SUCCEEDED = 0
    FAILED = 1
    IN_PROGRESS = 2

    BUILD_OUTCOME = (
        (SUCCEEDED, 'Succeeded'),
        (FAILED, 'Failed'),
        (IN_PROGRESS, 'In Progress'),
    )

    search_allowed_fields = ['machine', 'cooker_log_path', "target__target", "target__target_image_file__file_name"]

    project = models.ForeignKey(Project, null = True)
    machine = models.CharField(max_length=100)
    distro = models.CharField(max_length=100)
    distro_version = models.CharField(max_length=100)
    started_on = models.DateTimeField()
    completed_on = models.DateTimeField()
    timespent = models.IntegerField(default=0)
    outcome = models.IntegerField(choices=BUILD_OUTCOME, default=IN_PROGRESS)
    errors_no = models.IntegerField(default=0)
    warnings_no = models.IntegerField(default=0)
    cooker_log_path = models.CharField(max_length=500)
    build_name = models.CharField(max_length=100)
    bitbake_version = models.CharField(max_length=50)

    def completeper(self):
        tf = Task.objects.filter(build = self)
        tfc = tf.count()
        if tfc > 0:
            completeper = tf.exclude(order__isnull=True).count()*100/tf.count()
        else:
            completeper = 0
        return completeper

    def eta(self):
        from django.utils import timezone
        eta = 0
        completeper = self.completeper()
        if self.completeper() > 0:
            eta = timezone.now() + ((timezone.now() - self.started_on)*(100-completeper)/completeper)
        return eta


    def get_sorted_target_list(self):
        tgts = Target.objects.filter(build_id = self.id).order_by( 'target' );
        return( tgts );

class ProjectTarget(models.Model):
    project = models.ForeignKey(Project)
    target = models.CharField(max_length=100)
    task = models.CharField(max_length=100, null=True)

@python_2_unicode_compatible
class Target(models.Model):
    search_allowed_fields = ['target', 'file_name']
    build = models.ForeignKey(Build)
    target = models.CharField(max_length=100)
    is_image = models.BooleanField(default = False)
    image_size = models.IntegerField(default=0)
    license_manifest_path = models.CharField(max_length=500, null=True)

    def package_count(self):
        return Target_Installed_Package.objects.filter(target_id__exact=self.id).count()

    def __str__(self):
        return self.target

class Target_Image_File(models.Model):
    target = models.ForeignKey(Target)
    file_name = models.FilePathField(max_length=254)
    file_size = models.IntegerField()

class Target_File(models.Model):
    ITYPE_REGULAR = 1
    ITYPE_DIRECTORY = 2
    ITYPE_SYMLINK = 3
    ITYPE_SOCKET = 4
    ITYPE_FIFO = 5
    ITYPE_CHARACTER = 6
    ITYPE_BLOCK = 7
    ITYPES = ( (ITYPE_REGULAR ,'regular'),
        ( ITYPE_DIRECTORY ,'directory'),
        ( ITYPE_SYMLINK ,'symlink'),
        ( ITYPE_SOCKET ,'socket'),
        ( ITYPE_FIFO ,'fifo'),
        ( ITYPE_CHARACTER ,'character'),
        ( ITYPE_BLOCK ,'block'),
        )

    target = models.ForeignKey(Target)
    path = models.FilePathField()
    size = models.IntegerField()
    inodetype = models.IntegerField(choices = ITYPES)
    permission = models.CharField(max_length=16)
    owner = models.CharField(max_length=128)
    group = models.CharField(max_length=128)
    directory = models.ForeignKey('Target_File', related_name="directory_set", null=True)
    sym_target = models.ForeignKey('Target_File', related_name="symlink_set", null=True)


class TaskManager(models.Manager):
    def related_setscene(self, task_object):
        return Task.objects.filter(task_executed=True, build = task_object.build, recipe = task_object.recipe, task_name=task_object.task_name+"_setscene")

class Task(models.Model):

    SSTATE_NA = 0
    SSTATE_MISS = 1
    SSTATE_FAILED = 2
    SSTATE_RESTORED = 3

    SSTATE_RESULT = (
        (SSTATE_NA, 'Not Applicable'), # For rest of tasks, but they still need checking.
        (SSTATE_MISS, 'File not in cache'), # the sstate object was not found
        (SSTATE_FAILED, 'Failed'), # there was a pkg, but the script failed
        (SSTATE_RESTORED, 'Succeeded'), # successfully restored
    )

    CODING_NA = 0
    CODING_PYTHON = 2
    CODING_SHELL = 3

    TASK_CODING = (
        (CODING_NA, 'N/A'),
        (CODING_PYTHON, 'Python'),
        (CODING_SHELL, 'Shell'),
    )

    OUTCOME_NA = -1
    OUTCOME_SUCCESS = 0
    OUTCOME_COVERED = 1
    OUTCOME_CACHED = 2
    OUTCOME_PREBUILT = 3
    OUTCOME_FAILED = 4
    OUTCOME_EMPTY = 5

    TASK_OUTCOME = (
        (OUTCOME_NA, 'Not Available'),
        (OUTCOME_SUCCESS, 'Succeeded'),
        (OUTCOME_COVERED, 'Covered'),
        (OUTCOME_CACHED, 'Cached'),
        (OUTCOME_PREBUILT, 'Prebuilt'),
        (OUTCOME_FAILED, 'Failed'),
        (OUTCOME_EMPTY, 'Empty'),
    )

    TASK_OUTCOME_HELP = (
        (OUTCOME_SUCCESS, 'This task successfully completed'),
        (OUTCOME_COVERED, 'This task did not run because its output is provided by another task'),
        (OUTCOME_CACHED, 'This task restored output from the sstate-cache directory or mirrors'),
        (OUTCOME_PREBUILT, 'This task did not run because its outcome was reused from a previous build'),
        (OUTCOME_FAILED, 'This task did not complete'),
        (OUTCOME_EMPTY, 'This task has no executable content'),
        (OUTCOME_NA, ''),
    )

    search_allowed_fields = [ "recipe__name", "recipe__version", "task_name", "logfile" ]

    objects = TaskManager()

    def get_related_setscene(self):
        return Task.objects.related_setscene(self)

    def get_outcome_text(self):
        return Task.TASK_OUTCOME[self.outcome + 1][1]

    def get_outcome_help(self):
        return Task.TASK_OUTCOME_HELP[self.outcome][1]

    def get_sstate_text(self):
        if self.sstate_result==Task.SSTATE_NA:
            return ''
        else:
            return Task.SSTATE_RESULT[self.sstate_result][1]

    def get_executed_display(self):
        if self.task_executed:
            return "Executed"
        return "Not Executed"

    def get_description(self):
        helptext = HelpText.objects.filter(key=self.task_name, area=HelpText.VARIABLE, build=self.build)
        try:
            return helptext[0].text
        except IndexError:
            return ''

    build = models.ForeignKey(Build, related_name='task_build')
    order = models.IntegerField(null=True)
    task_executed = models.BooleanField(default=False) # True means Executed, False means Not/Executed
    outcome = models.IntegerField(choices=TASK_OUTCOME, default=OUTCOME_NA)
    sstate_checksum = models.CharField(max_length=100, blank=True)
    path_to_sstate_obj = models.FilePathField(max_length=500, blank=True)
    recipe = models.ForeignKey('Recipe', related_name='build_recipe')
    task_name = models.CharField(max_length=100)
    source_url = models.FilePathField(max_length=255, blank=True)
    work_directory = models.FilePathField(max_length=255, blank=True)
    script_type = models.IntegerField(choices=TASK_CODING, default=CODING_NA)
    line_number = models.IntegerField(default=0)
    disk_io = models.IntegerField(null=True)
    cpu_usage = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    elapsed_time = models.DecimalField(max_digits=6, decimal_places=2, null=True)
    sstate_result = models.IntegerField(choices=SSTATE_RESULT, default=SSTATE_NA)
    message = models.CharField(max_length=240)
    logfile = models.FilePathField(max_length=255, blank=True)

    outcome_text = property(get_outcome_text)
    sstate_text  = property(get_sstate_text)

    class Meta:
        ordering = ('order', 'recipe' ,)
        unique_together = ('build', 'recipe', 'task_name', )


class Task_Dependency(models.Model):
    task = models.ForeignKey(Task, related_name='task_dependencies_task')
    depends_on = models.ForeignKey(Task, related_name='task_dependencies_depends')

class Package(models.Model):
    search_allowed_fields = ['name', 'version', 'revision', 'recipe__name', 'recipe__version', 'recipe__license', 'recipe__layer_version__layer__name', 'recipe__layer_version__branch', 'recipe__layer_version__commit', 'recipe__layer_version__layer__local_path', 'installed_name']
    build = models.ForeignKey('Build')
    recipe = models.ForeignKey('Recipe', null=True)
    name = models.CharField(max_length=100)
    installed_name = models.CharField(max_length=100, default='')
    version = models.CharField(max_length=100, blank=True)
    revision = models.CharField(max_length=32, blank=True)
    summary = models.CharField(max_length=200, blank=True)
    description = models.TextField(blank=True)
    size = models.IntegerField(default=0)
    installed_size = models.IntegerField(default=0)
    section = models.CharField(max_length=80, blank=True)
    license = models.CharField(max_length=80, blank=True)

class Package_DependencyManager(models.Manager):
    use_for_related_fields = True

    def get_query_set(self):
        return super(Package_DependencyManager, self).get_query_set().exclude(package_id = F('depends_on__id'))

class Package_Dependency(models.Model):
    TYPE_RDEPENDS = 0
    TYPE_TRDEPENDS = 1
    TYPE_RRECOMMENDS = 2
    TYPE_TRECOMMENDS = 3
    TYPE_RSUGGESTS = 4
    TYPE_RPROVIDES = 5
    TYPE_RREPLACES = 6
    TYPE_RCONFLICTS = 7
    ' TODO: bpackage should be changed to remove the DEPENDS_TYPE access '
    DEPENDS_TYPE = (
        (TYPE_RDEPENDS, "depends"),
        (TYPE_TRDEPENDS, "depends"),
        (TYPE_TRECOMMENDS, "recommends"),
        (TYPE_RRECOMMENDS, "recommends"),
        (TYPE_RSUGGESTS, "suggests"),
        (TYPE_RPROVIDES, "provides"),
        (TYPE_RREPLACES, "replaces"),
        (TYPE_RCONFLICTS, "conflicts"),
    )
    ''' Indexed by dep_type, in view order, key for short name and help
        description which when viewed will be printf'd with the
        package name.
    '''
    DEPENDS_DICT = {
        TYPE_RDEPENDS :     ("depends", "%s is required to run %s"),
        TYPE_TRDEPENDS :    ("depends", "%s is required to run %s"),
        TYPE_TRECOMMENDS :  ("recommends", "%s extends the usability of %s"),
        TYPE_RRECOMMENDS :  ("recommends", "%s extends the usability of %s"),
        TYPE_RSUGGESTS :    ("suggests", "%s is suggested for installation with %s"),
        TYPE_RPROVIDES :    ("provides", "%s is provided by %s"),
        TYPE_RREPLACES :    ("replaces", "%s is replaced by %s"),
        TYPE_RCONFLICTS :   ("conflicts", "%s conflicts with %s, which will not be installed if this package is not first removed"),
    }

    package = models.ForeignKey(Package, related_name='package_dependencies_source')
    depends_on = models.ForeignKey(Package, related_name='package_dependencies_target')   # soft dependency
    dep_type = models.IntegerField(choices=DEPENDS_TYPE)
    target = models.ForeignKey(Target, null=True)
    objects = Package_DependencyManager()

class Target_Installed_Package(models.Model):
    target = models.ForeignKey(Target)
    package = models.ForeignKey(Package, related_name='buildtargetlist_package')

class Package_File(models.Model):
    package = models.ForeignKey(Package, related_name='buildfilelist_package')
    path = models.FilePathField(max_length=255, blank=True)
    size = models.IntegerField()

class Recipe(models.Model):
    search_allowed_fields = ['name', 'version', 'file_path', 'section', 'license', 'layer_version__layer__name', 'layer_version__branch', 'layer_version__commit', 'layer_version__layer__local_path']

    layer_source = models.ForeignKey('LayerSource', default = None, null = True)  # from where did we get this recipe
    up_id = models.IntegerField(null = True, default = None)                    # id of entry in the source
    up_date = models.DateTimeField(null = True, default = None)

    name = models.CharField(max_length=100, blank=True)                 # pn
    version = models.CharField(max_length=100, blank=True)              # pv
    layer_version = models.ForeignKey('Layer_Version', related_name='recipe_layer_version')
    summary = models.CharField(max_length=100, blank=True)
    description = models.TextField(blank=True)
    section = models.CharField(max_length=100, blank=True)
    license = models.CharField(max_length=200, blank=True)
    homepage = models.URLField(blank=True)
    bugtracker = models.URLField(blank=True)
    file_path = models.FilePathField(max_length=255)

    def get_vcs_link_url(self):
        if self.layer_version.layer.vcs_web_file_base_url is None:
            return ""
        return self.layer_version.layer.vcs_web_file_base_url.replace('%path%', self.file_path).replace('%branch%', self.layer_version.up_branch.name)

    def get_layersource_view_url(self):
        if self.layer_source is None:
            return ""

        url = self.layer_source.get_object_view(self.layer_version.up_branch, "recipes", self.name)
        return url

    def __unicode__(self):
        return "Recipe " + self.name + ":" + self.version

class Recipe_DependencyManager(models.Manager):
    use_for_related_fields = True

    def get_query_set(self):
        return super(Recipe_DependencyManager, self).get_query_set().exclude(recipe_id = F('depends_on__id'))

class Recipe_Dependency(models.Model):
    TYPE_DEPENDS = 0
    TYPE_RDEPENDS = 1

    DEPENDS_TYPE = (
        (TYPE_DEPENDS, "depends"),
        (TYPE_RDEPENDS, "rdepends"),
    )
    recipe = models.ForeignKey(Recipe, related_name='r_dependencies_recipe')
    depends_on = models.ForeignKey(Recipe, related_name='r_dependencies_depends')
    dep_type = models.IntegerField(choices=DEPENDS_TYPE)
    objects = Recipe_DependencyManager()


class Machine(models.Model):
    layer_source = models.ForeignKey('LayerSource', default = None, null = True)  # from where did we get this machine
    up_id = models.IntegerField(null = True, default = None)                      # id of entry in the source
    up_date = models.DateTimeField(null = True, default = None)

    layer_version = models.ForeignKey('Layer_Version')
    name = models.CharField(max_length=255)
    description = models.CharField(max_length=255)

    def __unicode__(self):
        return "Machine " + self.name + "(" + self.description + ")"

    class Meta:
        unique_together = ("layer_source", "up_id")


from django.db.models.base import ModelBase

class InheritanceMetaclass(ModelBase):
    def __call__(cls, *args, **kwargs):
        obj = super(InheritanceMetaclass, cls).__call__(*args, **kwargs)
        return obj.get_object()


class LayerSource(models.Model):
    __metaclass__ = InheritanceMetaclass

    class Meta:
        unique_together = (('sourcetype', 'apiurl'), )

    TYPE_LOCAL = 0
    TYPE_LAYERINDEX = 1
    SOURCE_TYPE = (
        (TYPE_LOCAL, "local"),
        (TYPE_LAYERINDEX, "layerindex"),
      )

    name = models.CharField(max_length=63)
    sourcetype = models.IntegerField(choices=SOURCE_TYPE)
    apiurl = models.CharField(max_length=255, null=True, default=None)

    def save(self, *args, **kwargs):
        if isinstance(self, LocalLayerSource):
            self.sourcetype = LayerSource.TYPE_LOCAL
        elif isinstance(self, LayerIndexLayerSource):
            self.sourcetype = LayerSource.TYPE_LAYERINDEX
        elif self.sourcetype == None:
            raise Exception("Invalid LayerSource type")
        return super(LayerSource, self).save(*args, **kwargs)

    def get_object(self):
        if self.sourcetype is not None:
            if self.sourcetype == LayerSource.TYPE_LOCAL:
                self.__class__ = LocalLayerSource
            if self.sourcetype == LayerSource.TYPE_LAYERINDEX:
                self.__class__ = LayerIndexLayerSource
        return self

        return "LS " + self.sourcetype + " " + self.name


class LocalLayerSource(LayerSource):
    class Meta(LayerSource._meta.__class__):
        proxy = True

    def __init__(self, *args, **kwargs):
        super(LocalLayerSource, self).__init__(args, kwargs)
        self.sourcetype = LayerSource.TYPE_LOCAL

    def update(self):
        '''
            Fetches layer, recipe and machine information from local repository
        '''
        pass

class LayerIndexLayerSource(LayerSource):
    class Meta(LayerSource._meta.__class__):
        proxy = True

    def __init__(self, *args, **kwargs):
        super(LayerIndexLayerSource, self).__init__(args, kwargs)
        self.sourcetype = LayerSource.TYPE_LAYERINDEX

    def get_object_view(self, branch, objectype, upid):
        if self != branch.layer_source:
            raise Exception("Invalid branch specification")
        return self.apiurl + "../branch/" + branch.name + "/" + objectype + "/?q=" + str(upid)

    def update(self):
        '''
            Fetches layer, recipe and machine information from remote repository
        '''
        assert self.apiurl is not None

        def _get_json_response(apiurl = self.apiurl):
            import httplib, urlparse, json
            parsedurl = urlparse.urlparse(apiurl)
            (host, port) = parsedurl.netloc.split(":")
            if port is None:
                port = 80
            else:
                port = int(port)
            #print "-- connect to: http://%s:%s%s?%s" % (host, port, parsedurl.path, parsedurl.query)
            conn = httplib.HTTPConnection(host, port)
            conn.request("GET", parsedurl.path + "?" + parsedurl.query)
            r = conn.getresponse()
            if r.status != 200:
                raise Exception("Failed to read " + parsedurl.path + ": %d %s" % (r.status, r.reason))
            return json.loads(r.read())

        # verify we can get the basic api
        try:
            apilinks = _get_json_response()
        except:
            print "EE: could not connect to %s, skipping update" % self.apiurl
            return

        # update branches; only those that we already have names listed in the database
        whitelist_branch_names = map(lambda x: x.name, Branch.objects.all())

        branches_info = _get_json_response(apilinks['branches']
            + "?filter=name:%s" % "OR".join(whitelist_branch_names))
        for bi in branches_info:
            b, created = Branch.objects.get_or_create(layer_source = self, name = bi['name'])
            b.up_id = bi['id']
            b.up_date = bi['updated']
            b.name = bi['name']
            b.bitbake_branch = bi['bitbake_branch']
            b.short_description = bi['short_description']
            b.save()

        # update layers
        layers_info = _get_json_response(apilinks['layerItems'])
        for li in layers_info:
            l, created = Layer.objects.get_or_create(layer_source = self, up_id = li['id'])
            l.up_date = li['updated']
            l.name = li['name']
            l.vcs_url = li['vcs_url']
            l.vcs_web_file_base_url = li['vcs_web_file_base_url']
            l.summary = li['summary']
            l.description = li['description']
            l.save()

        # update layerbranches/layer_versions
        layerbranches_info = _get_json_response(apilinks['layerBranches']
                + "?filter=branch:%s" % "OR".join(map(lambda x: str(x.up_id), Branch.objects.filter(layer_source = self)))
            )
        for lbi in layerbranches_info:
            lv, created = Layer_Version.objects.get_or_create(layer_source = self, up_id = lbi['id'])

            lv.up_date = lbi['updated']
            lv.layer = Layer.objects.get(layer_source = self, up_id = lbi['layer'])
            lv.up_branch = Branch.objects.get(layer_source = self, up_id = lbi['branch'])
            lv.branch = lbi['actual_branch']
            lv.commit = lbi['vcs_last_rev']
            lv.dirpath = lbi['vcs_subdir']
            lv.save()


        # update machines
        machines_info = _get_json_response(apilinks['machines']
                + "?filter=layerbranch:%s" % "OR".join(map(lambda x: str(x.up_id), Layer_Version.objects.filter(layer_source = self)))
            )
        for mi in machines_info:
            mo, created = Machine.objects.get_or_create(layer_source = self, up_id = mi['id'])
            mo.up_date = mi['updated']
            mo.layer_version = Layer_Version.objects.get(layer_source = self, up_id = mi['layerbranch'])
            mo.name = mi['name']
            mo.description = mi['description']
            mo.save()

        # update recipes; paginate by layer version / layer branch
        recipes_info = _get_json_response(apilinks['recipes']
                + "?filter=layerbranch:%s" % "OR".join(map(lambda x: str(x.up_id), Layer_Version.objects.filter(layer_source = self)))
            )
        for ri in recipes_info:
            ro, created = Recipe.objects.get_or_create(layer_source = self, up_id = ri['id'])

            ro.up_date = ri['updated']
            ro.layer_version = Layer_Version.objects.get(layer_source = self, up_id = mi['layerbranch'])

            ro.name = ri['pn']
            ro.version = ri['pv']
            ro.summary = ri['summary']
            ro.description = ri['description']
            ro.section = ri['section']
            ro.license = ri['license']
            ro.homepage = ri['homepage']
            ro.bugtracker = ri['bugtracker']
            ro.file_path = ri['filepath'] + ri['filename']
            ro.save()

        pass

class BitbakeVersion(models.Model):
    name = models.CharField(max_length=32, unique = True)
    giturl = models.URLField()
    branch = models.CharField(max_length=32)
    dirpath = models.CharField(max_length=255)


class Release(models.Model):
    name = models.CharField(max_length=32, unique = True)
    description = models.CharField(max_length=255)
    bitbake_version = models.ForeignKey(BitbakeVersion)
    branch = models.CharField(max_length=32)


class ReleaseDefaultLayer(models.Model):
    release = models.ForeignKey(Release)
    layer = models.ForeignKey('Layer')


# Branch class is synced with layerindex.Branch, branches can only come from remote layer indexes
class Branch(models.Model):
    layer_source = models.ForeignKey('LayerSource', null = True, default = True)
    up_id = models.IntegerField(null = True, default = None)                    # id of branch in the source
    up_date = models.DateTimeField(null = True, default = None)

    name = models.CharField(max_length=50)
    bitbake_branch = models.CharField(max_length=50, blank=True)
    short_description = models.CharField(max_length=50, blank=True)

    class Meta:
        verbose_name_plural = "Branches"
        unique_together = (('layer_source', 'name'),('layer_source', 'up_id'))

    def __unicode__(self):
        return self.name


# Layer class synced with layerindex.LayerItem
class Layer(models.Model):
    layer_source = models.ForeignKey(LayerSource, null = True, default = None)  # from where did we got this layer
    up_id = models.IntegerField(null = True, default = None)                    # id of layer in the remote source
    up_date = models.DateTimeField(null = True, default = None)

    name = models.CharField(max_length=100)
    local_path = models.FilePathField(max_length=255, null = True, default = None)
    layer_index_url = models.URLField()
    vcs_url = models.URLField(default = None, null = True)
    vcs_web_file_base_url = models.URLField(null = True, default = None)

    summary = models.CharField(max_length=200, help_text='One-line description of the layer', null = True, default = None)
    description = models.TextField(null = True, default = None)

    def __unicode__(self):
        return "L " + self.name

    class Meta:
        unique_together = (("layer_source", "up_id"), ("layer_source", "name"))


# LayerCommit class is synced with layerindex.LayerBranch
class Layer_Version(models.Model):
    search_allowed_fields = ["layer__name", "layer__summary",]
    build = models.ForeignKey(Build, related_name='layer_version_build', default = None, null = True)
    layer = models.ForeignKey(Layer, related_name='layer_version_layer')

    layer_source = models.ForeignKey(LayerSource, null = True, default = None)                   # from where did we get this Layer Version
    up_id = models.IntegerField(null = True, default = None)        # id of layerbranch in the remote source
    up_date = models.DateTimeField(null = True, default = None)
    up_branch = models.ForeignKey(Branch, null = True, default = None)

    branch = models.CharField(max_length=80)            # LayerBranch.actual_branch
    commit = models.CharField(max_length=100)           # LayerBranch.vcs_last_rev
    dirpath = models.CharField(max_length=255, null = True, default = None)          # LayerBranch.vcs_subdir
    priority = models.IntegerField(default = 0)         # if -1, this is a default layer

    def __unicode__(self):
        return "LV " + str(self.layer) + " " + self.commit

    class Meta:
        unique_together = ("layer_source", "up_id")

class LayerVersionDependency(models.Model):
    layer_source = models.ForeignKey(LayerSource, null = True, default = None)  # from where did we got this layer
    up_id = models.IntegerField(null = True, default = None)                    # id of layerbranch in the remote source

    layer_version = models.ForeignKey(Layer_Version, related_name="dependencies")
    depends_on = models.ForeignKey(Layer_Version, related_name="dependees")

    class Meta:
        unique_together = ("layer_source", "up_id")

class ProjectLayer(models.Model):
    project = models.ForeignKey(Project)
    layercommit = models.ForeignKey(Layer_Version, null=True)
    optional = models.BooleanField(default = True)

class ProjectVariable(models.Model):
    project = models.ForeignKey(Project)
    name = models.CharField(max_length=100)
    value = models.TextField(blank = True)

class Variable(models.Model):
    search_allowed_fields = ['variable_name', 'variable_value',
                             'vhistory__file_name', "description"]
    build = models.ForeignKey(Build, related_name='variable_build')
    variable_name = models.CharField(max_length=100)
    variable_value = models.TextField(blank=True)
    changed = models.BooleanField(default=False)
    human_readable_name = models.CharField(max_length=200)
    description = models.TextField(blank=True)

class VariableHistory(models.Model):
    variable = models.ForeignKey(Variable, related_name='vhistory')
    value   = models.TextField(blank=True)
    file_name = models.FilePathField(max_length=255)
    line_number = models.IntegerField(null=True)
    operation = models.CharField(max_length=64)

class HelpText(models.Model):
    VARIABLE = 0
    HELPTEXT_AREA = ((VARIABLE, 'variable'), )

    build = models.ForeignKey(Build, related_name='helptext_build')
    area = models.IntegerField(choices=HELPTEXT_AREA)
    key = models.CharField(max_length=100)
    text = models.TextField()

class LogMessage(models.Model):
    INFO = 0
    WARNING = 1
    ERROR = 2

    LOG_LEVEL = ( (INFO, "info"),
            (WARNING, "warn"),
            (ERROR, "error") )

    build = models.ForeignKey(Build)
    task  = models.ForeignKey(Task, blank = True, null=True)
    level = models.IntegerField(choices=LOG_LEVEL, default=INFO)
    message=models.CharField(max_length=240)
    pathname = models.FilePathField(max_length=255, blank=True)
    lineno = models.IntegerField(null=True)
