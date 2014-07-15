from django.core.management.base import NoArgsCommand, CommandError
from django.db import transaction
from orm.models import Build
from bldcontrol.bbcontroller import getBuildEnvironmentController, ShellCmdException
from bldcontrol.models import BuildRequest, BuildEnvironment
import os

class Command(NoArgsCommand):
    args = ""
    help = "Verifies thid %dthe configured settings are valid and usable, or prompts the user to fix the settings."

    def handle(self, **options):
        # we make sure we have builddir and sourcedir for all defined build envionments
        for be in BuildEnvironment.objects.all():
            def _verify_be():
                is_changed = False
                print("Verifying the Build Environment type %s id %d." % (be.get_betype_display(), be.pk))
                if len(be.sourcedir) == 0:
                    be.sourcedir = raw_input(" -- sourcedir may not be empty:")
                    is_changed = True
                if not be.sourcedir.startswith("/"):
                    be.sourcedir = raw_input(" -- sourcedir must be an absolute path:")
                    is_changed = True
                if len(be.builddir) == 0:
                    be.builddir = raw_input(" -- builddir may not be empty:")
                    is_changed = True
                if not be.builddir.startswith("/"):
                    be.builddir = raw_input(" -- builddir must be an absolute path:")
                    is_changed = True
                if is_changed:
                    print "saved"
                    be.save()
                return is_changed

            while (_verify_be()):
                pass

            return 0
