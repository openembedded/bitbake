from django.core.management.base import NoArgsCommand, CommandError
from django.db import transaction
from orm.models import Build
from bldcontrol.bbcontroller import getBuildEnvironmentController, ShellCmdException, BuildSetupException
from bldcontrol.models import BuildRequest, BuildEnvironment, BRError
import os

class Command(NoArgsCommand):
    args    = ""
    help    = "Schedules and executes build requests as possible. Does not return (interrupt with Ctrl-C)"


    @transaction.commit_on_success
    def _selectBuildEnvironment(self):
        bec = getBuildEnvironmentController(lock = BuildEnvironment.LOCK_FREE)
        bec.be.lock = BuildEnvironment.LOCK_LOCK
        bec.be.save()
        return bec

    @transaction.commit_on_success
    def _selectBuildRequest(self):
        br = BuildRequest.objects.filter(state = BuildRequest.REQ_QUEUED).order_by('pk')[0]
        br.state = BuildRequest.REQ_INPROGRESS
        br.save()
        return br

    def schedule(self):
        import traceback
        try:
            br = None
            try:
                # select the build environment and the request to build
                br = self._selectBuildRequest()
            except IndexError as e:
                return
            try:
                bec = self._selectBuildEnvironment()
            except IndexError as e:
                # we could not find a BEC; postpone the BR
                br.state = BuildRequest.REQ_QUEUED
                br.save()
                return

            # set up the buid environment with the needed layers
            print "Build %s, Environment %s" % (br, bec.be)
            bec.setLayers(br.brbitbake_set.all(), br.brlayer_set.all())

            # get the bb server running
            bbctrl = bec.getBBController()

            # let toasterui that this is a managed build
            bbctrl.setVariable("TOASTER_BRBE", "%d:%d" % (br.pk, bec.be.pk))

            # set the build configuration
            for variable in br.brvariable_set.all():
                bbctrl.setVariable(variable.name, variable.value)

            # trigger the build command
            bbctrl.build(list(map(lambda x:x.target, br.brtarget_set.all())))

            print "Build launched, exiting"
            # disconnect from the server
            bbctrl.disconnect()

            # cleanup to be performed by toaster when the deed is done


        except Exception as e:
            print " EE Error executing shell command\n", e
            traceback.print_exc(e)
            BRError.objects.create(req = br,
                errtype = str(type(e)),
                errmsg = str(e),
                traceback = traceback.format_exc(e))
            br.state = BuildRequest.REQ_FAILED
            br.save()
            bec.be.lock = BuildEnvironment.LOCK_FREE
            bec.be.save()


    def cleanup(self):
        from django.utils import timezone
        from datetime import timedelta
        # environments locked for more than 30 seconds - they should be unlocked
        BuildEnvironment.objects.filter(lock=BuildEnvironment.LOCK_LOCK).filter(updated__lt = timezone.now() - timedelta(seconds = 30)).update(lock = BuildEnvironment.LOCK_FREE)


    def handle_noargs(self, **options):
        self.cleanup()
        self.schedule()
