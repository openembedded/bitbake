#!/usr/bin/python

# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2015 Alexandru Damian for Intel Corp.
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

# Program to receive review requests by email and log tasks to backlog.txt
# Designed to be run by the email system from a .forward file:
#
# cat .forward
# |[full/path]/recv.py

from __future__ import print_function
import sys, os, config, shellutils
from shellutils import ShellCmdException

from email.parser import Parser

def recv_mail(datastring):
    headers = Parser().parsestr(datastring)
    return headers['subject']


if __name__ == "__main__":
    lf = shellutils.lockfile(shellutils.mk_lock_filename(), retry = True)

    subject = recv_mail(sys.stdin.read())

    subject_parts = subject.split()
    if "[review-request]" in subject_parts:
        task_name = subject_parts[subject_parts.index("[review-request]") + 1]
        with open(os.path.join(os.path.dirname(__file__), config.BACKLOGFILE), "a") as fout:
            line = "%s|%s\n" % (task_name, config.TASKS.PENDING)
            fout.write(line)

    shellutils.unlockfile(lf)

