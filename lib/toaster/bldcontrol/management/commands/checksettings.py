from django.core.management.base import NoArgsCommand, CommandError
from django.db import transaction
from bldcontrol.bbcontroller import getBuildEnvironmentController, ShellCmdException
from bldcontrol.models import BuildRequest, BuildEnvironment, BRError
from orm.models import ToasterSetting, Build
import os

def DN(path):
    if path is None:
        return ""
    else:
        return os.path.dirname(path)


class Command(NoArgsCommand):
    args = ""
    help = "Verifies that the configured settings are valid and usable, or prompts the user to fix the settings."


    def _find_first_path_for_file(self, startdirectory, filename, level = 0):
        if level < 0:
            return None
        dirs = []
        for i in os.listdir(startdirectory):
            j = os.path.join(startdirectory, i)
            if os.path.isfile(j):
                if i == filename:
                    return startdirectory
            elif os.path.isdir(j):
                dirs.append(j)
        for j in dirs:
            ret = self._find_first_path_for_file(j, filename, level - 1)
            if ret is not None:
                return ret
        return None

    def _recursive_list_directories(self, startdirectory, level = 0):
        if level < 0:
            return []
        dirs = []
        try:
            for i in os.listdir(startdirectory):
                j = os.path.join(startdirectory, i)
                if os.path.isdir(j):
                    dirs.append(j)
        except OSError:
            pass
        for j in dirs:
                dirs = dirs + self._recursive_list_directories(j, level - 1)
        return dirs


    def _get_suggested_sourcedir(self, be):
        if be.betype != BuildEnvironment.TYPE_LOCAL:
            return ""
        return DN(DN(DN(self._find_first_path_for_file(self.guesspath, "toasterconf.json", 4))))

    def _get_suggested_builddir(self, be):
        if be.betype != BuildEnvironment.TYPE_LOCAL:
            return ""
        return DN(self._find_first_path_for_file(DN(self.guesspath), "bblayers.conf", 4))


    def _verify_artifact_storage_dir(self):
        # verify that we have a settings for downloading artifacts
        while ToasterSetting.objects.filter(name="ARTIFACTS_STORAGE_DIR").count() == 0:
            guessedpath = os.getcwd() + "/toaster_build_artifacts/"
            print("Toaster needs to know in which directory it can download build log files and other artifacts.\n Toaster suggests \"%s\"." % guessedpath)
            artifacts_storage_dir = raw_input(" Press Enter to select \"%s\" or type the full path to a different directory: " % guessedpath)
            if len(artifacts_storage_dir) == 0:
                artifacts_storage_dir = guessedpath
            if len(artifacts_storage_dir) > 0 and artifacts_storage_dir.startswith("/"):
                try:
                    os.makedirs(artifacts_storage_dir)
                except OSError as ose:
                    if "File exists" in str(ose):
                        pass
                    else:
                        raise ose
                ToasterSetting.objects.create(name="ARTIFACTS_STORAGE_DIR", value=artifacts_storage_dir)
        return 0


    def _verify_build_environment(self):
        self.guesspath = DN(DN(DN(DN(DN(DN(DN(__file__)))))))
        # refuse to start if we have no build environments
        while BuildEnvironment.objects.count() == 0:
            print(" !! No build environments found. Toaster needs at least one build environment in order to be able to run builds.\n" +
                "You can manually define build environments in the database table bldcontrol_buildenvironment.\n" +
                "Or Toaster can define a simple localhost-based build environment for you.")

            i = raw_input(" --  Do you want to create a basic localhost build environment ? (Y/n) ");
            if not len(i) or i.startswith("y") or i.startswith("Y"):
                BuildEnvironment.objects.create(pk = 1, betype = 0)
            else:
                raise Exception("Toaster cannot start without build environments. Aborting.")


        # we make sure we have builddir and sourcedir for all defined build envionments
        for be in BuildEnvironment.objects.all():
            be.needs_import = False
            def _verify_be():
                is_changed = False
                print("Verifying the Build Environment. If the local Build Environment is not properly configured, you will be asked to configure it.")

                def _update_sourcedir():
                    suggesteddir = self._get_suggested_sourcedir(be)
                    if len(suggesteddir) > 0:
                        be.sourcedir = raw_input("Toaster needs to know in which directory it should check out the layers that will be needed for your builds.\n Toaster suggests \"%s\". If you select this directory, a layer like \"meta-intel\" will end up in \"%s/meta-intel\".\n Press Enter to select \"%s\" or type the full path to a different directory (must be a parent of current checkout directory): " % (suggesteddir, suggesteddir, suggesteddir))
                    else:
                        be.sourcedir = raw_input("Toaster needs to know in which directory it should check out the layers that will be needed for your builds. Type the full path to the directory (for example: \"%s\": " % os.environ.get('HOME', '/tmp/'))
                    if len(be.sourcedir) == 0 and len(suggesteddir) > 0:
                        be.sourcedir = suggesteddir
                    return True

                if len(be.sourcedir) == 0:
                    print "\n -- Validation: The checkout directory must be set."
                    is_changed = _update_sourcedir()

                if not be.sourcedir.startswith("/"):
                    print "\n -- Validation: The checkout directory must be set to an absolute path."
                    is_changed = _update_sourcedir()

                if not be.sourcedir in DN(__file__):
                    print "\n -- Validation: The checkout directory must be a parent of the current checkout."
                    is_changed = _update_sourcedir()

                if is_changed:
                    if be.betype == BuildEnvironment.TYPE_LOCAL:
                        be.needs_import = True
                    return True

                def _update_builddir():
                    suggesteddir = self._get_suggested_builddir(be)
                    if len(suggesteddir) > 0:
                        be.builddir = raw_input("Toaster needs to know where it your build directory is located.\n The build directory is where all the artifacts created by your builds will be stored. Toaster suggests \"%s\".\n Press Enter to select \"%s\" or type the full path to a different directory: " % (suggesteddir, suggesteddir))
                    else:
                        be.builddir = raw_input("Toaster needs to know where is your build directory.\n The build directory is where all the artifacts created by your builds will be stored. Type the full path to the directory (for example: \" %s/build\")" % os.environ.get('HOME','/tmp/'))
                    if len(be.builddir) == 0 and len(suggesteddir) > 0:
                        be.builddir = suggesteddir
                    return True

                if len(be.builddir) == 0:
                    print "\n -- Validation: The build directory must be set."
                    is_changed = _update_builddir()

                if not be.builddir.startswith("/"):
                    print "\n -- Validation: The build directory must to be set to an absolute path."
                    is_changed = _update_builddir()


                if is_changed:
                    print "Build configuration saved"
                    be.save()
                    return True


                if be.needs_import:
                    print "\nToaster can use a SINGLE predefined configuration file to set up default project settings and layer information sources.\n"

                    # find configuration files
                    config_files = []
                    for dirname in self._recursive_list_directories(be.sourcedir,2):
                        if os.path.exists(os.path.join(dirname, ".templateconf")):
                            import subprocess
                            conffilepath, error = subprocess.Popen('bash -c ". '+os.path.join(dirname, ".templateconf")+'; echo \"\$TEMPLATECONF\""', shell=True, stdout=subprocess.PIPE).communicate()
                            conffilepath = os.path.join(conffilepath.strip(), "toasterconf.json")
                            candidatefilepath = os.path.join(dirname, conffilepath)
                            if "toaster_cloned" in candidatefilepath:
                                continue
                            if os.path.exists(candidatefilepath):
                                config_files.append(candidatefilepath)

                    if len(config_files) > 0:
                        print " Toaster will list now the configuration files that it found. Select the number to use the desired configuration file."
                        for cf in config_files:
                            print "  [%d] - %s" % (config_files.index(cf) + 1, cf)
                        print "\n  [0] - Exit without importing any file"
                        try:
                                i = raw_input("\n Enter your option: ")
                                if len(i) and (int(i) - 1 >= 0 and int(i) - 1 < len(config_files)):
                                    print "Importing file: %s" % config_files[int(i)-1]
                                    from loadconf import Command as LoadConfigCommand

                                    LoadConfigCommand()._import_layer_config(config_files[int(i)-1])
                                    # we run lsupdates after config update
                                    print "Layer configuration imported. Updating information from the layer sources, please wait.\n You can re-update any time later by running bitbake/lib/toaster/manage.py lsupdates"
                                    from django.core.management import call_command
                                    call_command("lsupdates")

                                    # we don't look for any other config files
                                    return is_changed
                        except Exception as e:
                            print "Failure while trying to import the toaster config file: %s" % e
                    else:
                        print "\n Toaster could not find a configuration file. You need to configure Toaster manually using the web interface, or create a configuration file and use\n  bitbake/lib/toaster/managepy.py loadconf [filename]\n command to load it. You can use https://wiki.yoctoproject.org/wiki/File:Toasterconf.json.txt.patch as a starting point."




                return is_changed

            while (_verify_be()):
                pass
        return 0

    def _verify_default_settings(self):
        # verify that default settings are there
        if ToasterSetting.objects.filter(name = 'DEFAULT_RELEASE').count() != 1:
            ToasterSetting.objects.filter(name = 'DEFAULT_RELEASE').delete()
            ToasterSetting.objects.get_or_create(name = 'DEFAULT_RELEASE', value = '')
        return 0

    def _verify_builds_in_progress(self):
        # we are just starting up. we must not have any builds in progress, or build environments taken
        for b in BuildRequest.objects.filter(state = BuildRequest.REQ_INPROGRESS):
            BRError.objects.create(req = b, errtype = "toaster", errmsg = "Toaster found this build IN PROGRESS while Toaster started up. This is an inconsistent state, and the build was marked as failed")

        BuildRequest.objects.filter(state = BuildRequest.REQ_INPROGRESS).update(state = BuildRequest.REQ_FAILED)

        BuildEnvironment.objects.update(lock = BuildEnvironment.LOCK_FREE)

        # also mark "In Progress builds as failures"
        from django.utils import timezone
        Build.objects.filter(outcome = Build.IN_PROGRESS).update(outcome = Build.FAILED, completed_on = timezone.now())

        return 0



    def handle(self, **options):
        retval = 0
        retval += self._verify_artifact_storage_dir()
        retval += self._verify_build_environment()
        retval += self._verify_default_settings()
        retval += self._verify_builds_in_progress()

        return retval
