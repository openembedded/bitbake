from django.core.management.base import NoArgsCommand, CommandError
from django.db import transaction
from orm.models import Build, ToasterSetting
from bldcontrol.bbcontroller import getBuildEnvironmentController, ShellCmdException, BuildSetupException
from bldcontrol.models import BuildRequest, BuildEnvironment, BRError, BRVariable
import os
import logging

logger = logging.getLogger("toaster")

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
                # logger.debug("runbuilds: No build request")
                return
            try:
                bec = self._selectBuildEnvironment()
            except IndexError as e:
                # we could not find a BEC; postpone the BR
                br.state = BuildRequest.REQ_QUEUED
                br.save()
                logger.debug("runbuilds: No build env")
                return

            logger.debug("runbuilds: starting build %s, environment %s" % (br, bec.be))

            # write the build identification variable
            BRVariable.objects.create(req = br, name="TOASTER_BRBE", value="%d:%d" % (br.pk, bec.be.pk))
            # let the build request know where it is being executed
            br.environment = bec.be
            br.save()

            # set up the buid environment with the needed layers
            bec.setLayers(br.brbitbake_set.all(), br.brlayer_set.all())
            bec.writeConfFile("conf/toaster-pre.conf", br.brvariable_set.all())
            bec.writeConfFile("conf/toaster.conf", raw = "INHERIT+=\"toaster buildhistory\"")

            # get the bb server running with the build req id and build env id
            bbctrl = bec.getBBController()

            # trigger the build command
            task = reduce(lambda x, y: x if len(y)== 0 else y, map(lambda y: y.task, br.brtarget_set.all()))
            if len(task) == 0:
                task = None
            bbctrl.build(list(map(lambda x:x.target, br.brtarget_set.all())), task)

            logger.debug("runbuilds: Build launched, exiting. Follow build logs at %s/toaster_ui.log" % bec.be.builddir)
            # disconnect from the server
            bbctrl.disconnect()

            # cleanup to be performed by toaster when the deed is done


        except Exception as e:
            logger.error("runbuilds: Error executing shell command %s" % e)
            traceback.print_exc(e)
            if "[Errno 111] Connection refused" in str(e):
                # Connection refused, read toaster_server.out
                errmsg = bec.readServerLogFile()
            else:
                errmsg = str(e)

            BRError.objects.create(req = br,
                    errtype = str(type(e)),
                    errmsg = errmsg,
                    traceback = traceback.format_exc(e))
            br.state = BuildRequest.REQ_FAILED
            br.save()
            bec.be.lock = BuildEnvironment.LOCK_FREE
            bec.be.save()

    def archive(self):
        ''' archives data from the builds '''
        artifact_storage_dir = ToasterSetting.objects.get(name="ARTIFACTS_STORAGE_DIR").value
        for br in BuildRequest.objects.filter(state = BuildRequest.REQ_ARCHIVE):
            # save cooker log
            if br.build == None:
                br.state = BuildRequest.REQ_FAILED
                br.save()
                continue
            build_artifact_storage_dir = os.path.join(artifact_storage_dir, "%d" % br.build.pk)
            try:
                os.makedirs(build_artifact_storage_dir)
            except OSError as ose:
                if "File exists" in str(ose):
                    pass
                else:
                    raise ose

            file_name = os.path.join(build_artifact_storage_dir, "cooker_log.txt")
            try:
                with open(file_name, "w") as f:
                    f.write(br.environment.get_artifact(br.build.cooker_log_path).read())
            except IOError:
                os.unlink(file_name)

            br.state = BuildRequest.REQ_COMPLETED
            br.save()

    def cleanup(self):
        from django.utils import timezone
        from datetime import timedelta
        # environments locked for more than 30 seconds - they should be unlocked
        BuildEnvironment.objects.filter(lock=BuildEnvironment.LOCK_LOCK).filter(updated__lt = timezone.now() - timedelta(seconds = 30)).update(lock = BuildEnvironment.LOCK_FREE)


    def handle_noargs(self, **options):
        self.cleanup()
        self.archive()
        self.schedule()
