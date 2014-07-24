#
# BitBake ToasterUI Implementation
# based on (No)TTY UI Implementation by Richard Purdie
#
# Handling output to TTYs or files (no TTY)
#
# Copyright (C) 2006-2012 Richard Purdie
# Copyright (C) 2013      Intel Corporation
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

from __future__ import division
try:
    import bb
except RuntimeError as exc:
    sys.exit(str(exc))

from bb.ui import uihelper
from bb.ui.buildinfohelper import BuildInfoHelper

import bb.msg
import copy
import fcntl
import logging
import os
import progressbar
import signal
import struct
import sys
import time
import xmlrpclib

featureSet = [bb.cooker.CookerFeatures.HOB_EXTRA_CACHES, bb.cooker.CookerFeatures.SEND_DEPENDS_TREE, bb.cooker.CookerFeatures.BASEDATASTORE_TRACKING]

logger = logging.getLogger("BitBake")
interactive = sys.stdout.isatty()



def _log_settings_from_server(server):
    # Get values of variables which control our output
    includelogs, error = server.runCommand(["getVariable", "BBINCLUDELOGS"])
    if error:
        logger.error("Unable to get the value of BBINCLUDELOGS variable: %s" % error)
        raise BaseException(error)
    loglines, error = server.runCommand(["getVariable", "BBINCLUDELOGS_LINES"])
    if error:
        logger.error("Unable to get the value of BBINCLUDELOGS_LINES variable: %s" % error)
        raise BaseException(error)
    return includelogs, loglines

def main(server, eventHandler, params ):

    includelogs, loglines = _log_settings_from_server(server)

    # verify and warn
    build_history_enabled = True
    inheritlist, error = server.runCommand(["getVariable", "INHERIT"])
    if not "buildhistory" in inheritlist.split(" "):
        logger.warn("buildhistory is not enabled. Please enable INHERIT += \"buildhistory\" to see image details.")
        build_history_enabled = False

    helper = uihelper.BBUIHelper()

    console = logging.StreamHandler(sys.stdout)
    format_str = "%(levelname)s: %(message)s"
    format = bb.msg.BBLogFormatter(format_str)
    bb.msg.addDefaultlogFilter(console)
    console.setFormatter(format)
    logger.addHandler(console)

    if not params.observe_only:
        logger.error("ToasterUI can only work in observer mode")
        return


    main.shutdown = 0
    interrupted = False
    return_value = 0
    errors = 0
    warnings = 0
    taskfailures = []
    first = True

    buildinfohelper = BuildInfoHelper(server, build_history_enabled)

    while True:
        try:
            event = eventHandler.waitEvent(0.25)
            if first:
                first = False
                logger.info("ToasterUI waiting for events")

            if event is None:
                if main.shutdown > 0:
                    break
                continue

            helper.eventHandler(event)

            if isinstance(event, bb.event.BuildStarted):
                buildinfohelper.store_started_build(event)

            if isinstance(event, (bb.build.TaskStarted, bb.build.TaskSucceeded, bb.build.TaskFailedSilent)):
                buildinfohelper.update_and_store_task(event)
                continue

            if isinstance(event, bb.event.LogExecTTY):
                logger.warn(event.msg)
                continue

            if isinstance(event, logging.LogRecord):
                buildinfohelper.store_log_event(event)
                if event.levelno >= format.ERROR:
                    errors = errors + 1
                    return_value = 1
                elif event.levelno == format.WARNING:
                    warnings = warnings + 1
                # For "normal" logging conditions, don't show note logs from tasks
                # but do show them if the user has changed the default log level to
                # include verbose/debug messages
                if event.taskpid != 0 and event.levelno <= format.NOTE:
                    continue

                logger.handle(event)
                continue

            if isinstance(event, bb.build.TaskFailed):
                buildinfohelper.update_and_store_task(event)
                return_value = 1
                logfile = event.logfile
                if logfile and os.path.exists(logfile):
                    bb.error("Logfile of failure stored in: %s" % logfile)
                continue

            # these events are unprocessed now, but may be used in the future to log
            # timing and error informations from the parsing phase in Toaster
            if isinstance(event, (bb.event.SanityCheckPassed, bb.event.SanityCheck)):
                continue
            if isinstance(event, bb.event.ParseStarted):
                continue
            if isinstance(event, bb.event.ParseProgress):
                continue
            if isinstance(event, bb.event.ParseCompleted):
                continue
            if isinstance(event, bb.event.CacheLoadStarted):
                continue
            if isinstance(event, bb.event.CacheLoadProgress):
                continue
            if isinstance(event, bb.event.CacheLoadCompleted):
                continue
            if isinstance(event, bb.event.MultipleProviders):
                continue
            if isinstance(event, bb.event.NoProvider):
                return_value = 1
                errors = errors + 1
                if event._runtime:
                    r = "R"
                else:
                    r = ""

                if event._dependees:
                    text = "Nothing %sPROVIDES '%s' (but %s %sDEPENDS on or otherwise requires it)" % (r, event._item, ", ".join(event._dependees), r)
                else:
                    text = "Nothing %sPROVIDES '%s'" % (r, event._item)

                logger.error(text)
                if event._reasons:
                    for reason in event._reasons:
                        logger.error("%s", reason)
                        text += reason
                buildinfohelper.store_log_error(text)
                continue

            if isinstance(event, bb.event.ConfigParsed):
                continue
            if isinstance(event, bb.event.RecipeParsed):
                continue

            # end of saved events

            if isinstance(event, (bb.runqueue.sceneQueueTaskStarted, bb.runqueue.runQueueTaskStarted, bb.runqueue.runQueueTaskSkipped)):
                buildinfohelper.store_started_task(event)
                continue

            if isinstance(event, bb.runqueue.runQueueTaskCompleted):
                buildinfohelper.update_and_store_task(event)
                continue

            if isinstance(event, bb.runqueue.runQueueTaskFailed):
                buildinfohelper.update_and_store_task(event)
                taskfailures.append(event.taskstring)
                logger.error("Task %s (%s) failed with exit code '%s'",
                             event.taskid, event.taskstring, event.exitcode)
                continue

            if isinstance(event, (bb.runqueue.sceneQueueTaskCompleted, bb.runqueue.sceneQueueTaskFailed)):
                buildinfohelper.update_and_store_task(event)
                continue


            if isinstance(event, (bb.event.TreeDataPreparationStarted, bb.event.TreeDataPreparationCompleted)):
                continue

            if isinstance(event, (bb.event.BuildCompleted)):
                continue

            if isinstance(event, (bb.command.CommandCompleted,
                                  bb.command.CommandFailed,
                                  bb.command.CommandExit)):
                if (isinstance(event, bb.command.CommandFailed)):
                    event.levelno = format.ERROR
                    event.msg = "Command Failed " + event.error
                    event.pathname = ""
                    event.lineno = 0
                    buildinfohelper.store_log_event(event)
                    errors += 1

                buildinfohelper.update_build_information(event, errors, warnings, taskfailures)
                buildinfohelper.close()


                # we start a new build info
                if buildinfohelper.brbe is not None:

                    print "we are under BuildEnvironment management - after the build, we exit"
                    server.terminateServer()
                else:
                    print "prepared for new build"
                    errors = 0
                    warnings = 0
                    taskfailures = []
                    buildinfohelper = BuildInfoHelper(server, build_history_enabled)

                continue

            if isinstance(event, bb.event.MetadataEvent):
                if event.type == "SinglePackageInfo":
                    buildinfohelper.store_build_package_information(event)
                elif event.type == "LayerInfo":
                    buildinfohelper.store_layer_info(event)
                elif event.type == "BuildStatsList":
                    buildinfohelper.store_tasks_stats(event)
                elif event.type == "ImagePkgList":
                    buildinfohelper.store_target_package_data(event)
                elif event.type == "MissedSstate":
                    buildinfohelper.store_missed_state_tasks(event)
                elif event.type == "ImageFileSize":
                    buildinfohelper.update_target_image_file(event)
                elif event.type == "LicenseManifestPath":
                    buildinfohelper.store_license_manifest_path(event)
                continue

            if isinstance(event, bb.cooker.CookerExit):
                # exit when the server exits
                break

            # ignore
            if isinstance(event, (bb.event.BuildBase,
                                  bb.event.StampUpdate,
                                  bb.event.RecipePreFinalise,
                                  bb.runqueue.runQueueEvent,
                                  bb.runqueue.runQueueExitWait,
                                  bb.event.OperationProgress,
                                  bb.command.CommandFailed,
                                  bb.command.CommandExit,
                                  bb.command.CommandCompleted)):
                continue

            if isinstance(event, bb.event.DepTreeGenerated):
                buildinfohelper.store_dependency_information(event)
                continue

            logger.error("Unknown event: %s", event)

        except EnvironmentError as ioerror:
            # ignore interrupted io
            if ioerror.args[0] == 4:
                pass
        except KeyboardInterrupt:
            main.shutdown = 1
            pass
        except Exception as e:
            logger.error(e)
            import traceback
            traceback.print_exc()
            pass

    if interrupted:
        if return_value == 0:
            return_value = 1

    return return_value
