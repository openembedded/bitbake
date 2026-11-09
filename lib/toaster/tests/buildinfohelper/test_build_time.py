#! /usr/bin/env python3
#
# BitBake Toaster Implementation
#
# SPDX-License-Identifier: GPL-2.0-only
#

"""Build start and end times are taken from the events."""

import logging
from datetime import datetime, timezone

import bb.build
import bb.data
import bb.event
from django.test import TransactionTestCase

from bb.ui.buildinfohelper import BuildInfoHelper
from bb.ui.eventreplay import EventPlayer
from orm.models import Build

START = 1700000000.5
END = 1700001500.25


def utc(secs):
    return datetime.fromtimestamp(secs, timezone.utc)


class BuildTimeTests(TransactionTestCase):
    """A replayed event log keeps the times of the original build"""

    def setUp(self):
        variables = {name: {'v': name.lower()} for name in
                     ('BUILDNAME', 'MACHINE', 'DISTRO', 'DISTRO_VERSION',
                      'BB_VERSION', 'TMPDIR')}
        server = EventPlayer(None, variables)
        self.helper = BuildInfoHelper(server)

    def test_times_from_events(self):
        record = logging.LogRecord('BitBake', logging.INFO, '', 0, 'msg',
                                   None, None)
        record.created = START
        self.helper.update_event_time(record)
        self.helper.store_started_build()

        task = bb.build.TaskSucceeded('do_build', 'test.bb', None,
                                      bb.data.init())
        task.time = END
        self.helper.update_event_time(task)
        self.helper.update_build_information(None, 0, 0, [])

        build = Build.objects.get()
        self.assertEqual(build.started_on, utc(START))
        self.assertEqual(build.completed_on, utc(END))
        self.assertEqual(build.outcome, Build.SUCCEEDED)

    def test_events_without_time_keep_the_clock(self):
        before = datetime.now(timezone.utc)
        self.helper.update_event_time(bb.event.BuildStarted('build', []))
        self.helper.store_started_build()
        self.assertGreaterEqual(Build.objects.get().started_on, before)
