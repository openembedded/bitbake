from django.core.management.base import NoArgsCommand, CommandError
from django.db import transaction
from bldcontrol.bbcontroller import getBuildEnvironmentController, ShellCmdException
from bldcontrol.models import BuildRequest, BuildEnvironment
from orm.models import ToasterSetting
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

    def _get_suggested_sourcedir(self, be):
        if be.betype != BuildEnvironment.TYPE_LOCAL:
            return ""
        return DN(DN(DN(self._find_first_path_for_file(self.guesspath, "toasterconf.json", 4))))

    def _get_suggested_builddir(self, be):
        if be.betype != BuildEnvironment.TYPE_LOCAL:
            return ""
        return DN(self._find_first_path_for_file(DN(self.guesspath), "bblayers.conf", 4))


    def handle(self, **options):
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
            def _verify_be():
                is_changed = False
                print("Verifying the Build Environment type %s id %d." % (be.get_betype_display(), be.pk))
                if len(be.sourcedir) == 0:
                    suggesteddir = self._get_suggested_sourcedir(be)
                    homesourcedir = suggesteddir
                    be.sourcedir = raw_input(" -- Layer sources checkout directory may not be empty [guessed \"%s\"]:" % suggesteddir)
                    if len(be.sourcedir) == 0 and len(suggesteddir) > 0:
                        be.sourcedir = suggesteddir
                    is_changed = True

                if not be.sourcedir.startswith("/"):
                    be.sourcedir = raw_input(" -- Layer sources checkout directory must be an absolute path:")
                    is_changed = True

                if len(be.builddir) == 0:
                    suggesteddir = self._get_suggested_builddir(be)
                    be.builddir = raw_input(" -- Build directory may not be empty [guessed \"%s\"]:" % suggesteddir)
                    if len(be.builddir) == 0 and len(suggesteddir) > 0:
                        be.builddir = suggesteddir
                    is_changed = True

                if not be.builddir.startswith("/"):
                    be.builddir = raw_input(" -- Build directory must be an absolute path:")
                    is_changed = True


                if is_changed:
                    print "Build configuration saved"
                    be.save()

                if is_changed and be.betype == BuildEnvironment.TYPE_LOCAL:
                    baselayerdir = DN(DN(self._find_first_path_for_file(homesourcedir, "toasterconf.json", 3)))
                    if baselayerdir:
                        i = raw_input(" -- Do you want to import basic layer configuration from \"%s\" ? (y/N):" % baselayerdir)
                        if len(i) and i.upper()[0] == 'Y':
                            from loadconf import Command as LoadConfigCommand
                            LoadConfigCommand()._import_layer_config(os.path.join(baselayerdir, "meta/conf/toasterconf.json"))
                            # we run lsupdates after config update
                            print "Updating information from the layer source, please wait."
                            from django.core.management import call_command
                            call_command("lsupdates")
                        pass

                return is_changed

            while (_verify_be()):
                pass

        # verify that default settings are there
        if ToasterSetting.objects.filter(name = 'DEFAULT_RELEASE').count() != 1:
            ToasterSetting.objects.filter(name = 'DEFAULT_RELEASE').delete()
            ToasterSetting.objects.get_or_create(name = 'DEFAULT_RELEASE', value = '')

        return 0
