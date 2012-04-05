#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2012 Robert Yang
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

import os, logging, re, sys
import bb
logger = logging.getLogger("BitBake.Monitor")

def printErr(info):
    logger.error("%s\n       Disk space monitor will NOT be enabled" % info)

def convertGMK(unit):

    """ Convert the space unit G, M, K, the unit is case-insensitive """

    unitG = re.match('([1-9][0-9]*)[gG]\s?$', unit)
    if unitG:
        return int(unitG.group(1)) * (1024 ** 3)
    unitM = re.match('([1-9][0-9]*)[mM]\s?$', unit)
    if unitM:
        return int(unitM.group(1)) * (1024 ** 2)
    unitK = re.match('([1-9][0-9]*)[kK]\s?$', unit)
    if unitK:
        return int(unitK.group(1)) * 1024
    unitN = re.match('([1-9][0-9]*)\s?$', unit)
    if unitN:
        return int(unitN.group(1))
    else:
        return None

def getMountedDev(path):

    """ Get the device mounted at the path, uses /proc/mounts """

    # Get the mount point of the filesystem containing path
    # st_dev is the ID of device containing file
    parentDev = os.stat(path).st_dev
    currentDev = parentDev
    # When the current directory's device is different from the
    # parrent's, then the current directory is a mount point
    while parentDev == currentDev:
        mountPoint = path
        # Use dirname to get the parrent's directory
        path = os.path.dirname(path)
        # Reach the "/"
        if path == mountPoint:
            break
        parentDev= os.stat(path).st_dev

    try:
        with open("/proc/mounts", "r") as ifp:
            for line in ifp:
                procLines = line.rstrip('\n').split()
                if procLines[1] == mountPoint:
                    return procLines[0]
    except EnvironmentError:
        pass
    return None

def getDiskData(BBDirs, configuration):

    """Prepare disk data for disk space monitor"""

    # Save the device IDs, need the ID to be unique (the dictionary's key is
    # unique), so that when more than one directories are located in the same
    # device, we just monitor it once
    devDict = {}
    for pathSpaceInode in BBDirs.split():
        # The input format is: "dir,space,inode", dir is a must, space
        # and inode are optional
        pathSpaceInodeRe = re.match('([^,]*),([^,]*),([^,]*),?(.*)', pathSpaceInode)
        if not pathSpaceInodeRe:
            printErr("Invalid value in BB_DISKMON_DIRS: %s" % pathSpaceInode)
            return None

        action = pathSpaceInodeRe.group(1)
        if action not in ("ABORT", "STOPTASKS", "WARN"):
            printErr("Unknown disk space monitor action: %s" % action)
            return None

        path = os.path.realpath(pathSpaceInodeRe.group(2))
        if not path:
            printErr("Invalid path value in BB_DISKMON_DIRS: %s" % pathSpaceInode)
            return None

        # The disk space or inode is optional, but it should have a correct
        # value once it is specified
        minSpace = pathSpaceInodeRe.group(3)
        if minSpace:
            minSpace = convertGMK(minSpace)
            if not minSpace:
                printErr("Invalid disk space value in BB_DISKMON_DIRS: %s" % pathSpaceInodeRe.group(3))
                return None
        else:
            # 0 means that it is not specified
            minSpace = None

        minInode = pathSpaceInodeRe.group(4)
        if minInode:
            minInode = convertGMK(minInode)
            if not minInode:
                printErr("Invalid inode value in BB_DISKMON_DIRS: %s" % pathSpaceInodeRe.group(4))
                return None
        else:
            # 0 means that it is not specified
            minInode = None

        if minSpace is None and minInode is None:
            printErr("No disk space or inode value in found BB_DISKMON_DIRS: %s" % pathSpaceInode)
            return None
        # mkdir for the directory since it may not exist, for example the
        # DL_DIR may not exist at the very beginning
        if not os.path.exists(path):
            bb.utils.mkdirhier(path)
        mountedDev = getMountedDev(path)
        devDict[mountedDev] = action, path, minSpace, minInode

    return devDict

def getInterval(configuration):

    """ Get the disk space interval """

    # The default value is 50M and 5K.
    spaceDefault = 50 * 1024 * 1024
    inodeDefault = 5 * 1024

    interval = configuration.getVar("BB_DISKMON_WARNINTERVAL", True)
    if not interval:
        return spaceDefault, inodeDefault
    else:
        # The disk space or inode interval is optional, but it should
        # have a correct value once it is specified
        intervalRe = re.match('([^,]*),?\s*(.*)', interval)
        if intervalRe:
            intervalSpace = intervalRe.group(1)
            if intervalSpace:
                intervalSpace = convertGMK(intervalSpace)
                if not intervalSpace:
                    printErr("Invalid disk space interval value in BB_DISKMON_WARNINTERVAL: %s" % intervalRe.group(1))
                    return None, None
            else:
                intervalSpace = spaceDefault
            intervalInode = intervalRe.group(2)
            if intervalInode:
                intervalInode = convertGMK(intervalInode)
                if not intervalInode:
                    printErr("Invalid disk inode interval value in BB_DISKMON_WARNINTERVAL: %s" % intervalRe.group(2))
                    return None, None
            else:
                intervalInode = inodeDefault
            return intervalSpace, intervalInode
        else:
            printErr("Invalid interval value in BB_DISKMON_WARNINTERVAL: %s" % interval)
            return None, None

class diskMonitor:

    """Prepare the disk space monitor data"""

    def __init__(self, configuration):

        self.enableMonitor = False

        BBDirs = configuration.getVar("BB_DISKMON_DIRS", True) or None
        if BBDirs:
            self.devDict = getDiskData(BBDirs, configuration)
            if self.devDict:
                self.spaceInterval, self.inodeInterval = getInterval(configuration)
                if self.spaceInterval and self.inodeInterval:
                    self.enableMonitor = True
                    # These are for saving the previous disk free space and inode, we
                    # use them to avoid print too many warning messages
                    self.preFreeS = {}
                    self.preFreeI = {}
                    # This is for STOPTASKS and ABORT, to avoid print the message repeatly
                    # during waiting the tasks to finish
                    self.checked = {}
                    for dev in self.devDict:
                        self.preFreeS[dev] = 0
                        self.preFreeI[dev] = 0
                        self.checked[dev] = False
                    if self.spaceInterval is None and self.inodeInterval is None:
                        self.enableMonitor = False

    def check(self, rq):

        """ Take action for the monitor """

        if self.enableMonitor:
            for dev in self.devDict:
                st = os.statvfs(self.devDict[dev][1])

                # The free space, float point number
                freeSpace = st.f_bavail * st.f_frsize

                if self.devDict[dev][2] and freeSpace < self.devDict[dev][2]:
                    # Always show warning, the self.checked would always be False if the action is WARN
                    if self.preFreeS[dev] == 0 or self.preFreeS[dev] - freeSpace > self.spaceInterval and not self.checked[dev]:
                        logger.warn("The free space of %s is running low (%.3fGB left)" % (dev, freeSpace / 1024 / 1024 / 1024.0))
                        self.preFreeS[dev] = freeSpace

                    if self.devDict[dev][0] == "STOPTASKS" and not self.checked[dev]:
                        logger.error("No new tasks can be excuted since the disk space monitor action is \"STOPTASKS\"!")
                        self.checked[dev] = True
                        rq.finish_runqueue(False)
                    elif self.devDict[dev][0] == "ABORT" and not self.checked[dev]:
                        logger.error("Immediately abort since the disk space monitor action is \"ABORT\"!")
                        self.checked[dev] = True
                        rq.finish_runqueue(True)

                # The free inodes, float point number
                freeInode = st.f_favail

                if self.devDict[dev][3] and freeInode < self.devDict[dev][3]:
                    # Always show warning, the self.checked would always be False if the action is WARN
                    if self.preFreeI[dev] == 0 or self.preFreeI[dev] - freeInode > self.inodeInterval and not self.checked[dev]:
                        logger.warn("The free inode of %s is running low (%.3fK left)" % (dev, freeInode / 1024.0))
                        self.preFreeI[dev] = freeInode

                    if self.devDict[dev][0]  == "STOPTASKS" and not self.checked[dev]:
                        logger.error("No new tasks can be excuted since the disk space monitor action is \"STOPTASKS\"!")
                        self.checked[dev] = True
                        rq.finish_runqueue(False)
                    elif self.devDict[dev][0]  == "ABORT" and not self.checked[dev]:
                        logger.error("Immediately abort since the disk space monitor action is \"ABORT\"!")
                        self.checked[dev] = True
                        rq.finish_runqueue(True)
        return
