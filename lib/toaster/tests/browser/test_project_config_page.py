#! /usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2013-2016 Intel Corporation
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

import re

from django.core.urlresolvers import reverse
from django.utils import timezone
from tests.browser.selenium_helpers import SeleniumTestCase

from orm.models import BitbakeVersion, Release, Project, ProjectVariable

class TestProjectConfigsPage(SeleniumTestCase):
    """ Test data at /project/X/builds is displayed correctly """

    PROJECT_NAME = 'test project'

    def setUp(self):
        bbv = BitbakeVersion.objects.create(name='bbv1', giturl='/tmp/',
                                            branch='master', dirpath='')
        release = Release.objects.create(name='release1',
                                         bitbake_version=bbv)
        self.project1 = Project.objects.create_project(name=self.PROJECT_NAME,
                                                       release=release)
        self.project1.save()


    def test_no_underscore_iamgefs_type(self):
        """
        Should not accept IMAGEFS_TYPE with an underscore
        """

        imagefs_type = "foo_bar"

        ProjectVariable.objects.get_or_create(project = self.project1, name = "IMAGE_FSTYPES", value = "abcd ")
        url = reverse('projectconf', args=(self.project1.id,));
        self.get(url);

        self.click('#change-image_fstypes-icon')

        self.enter_text('#new-imagefs_types', imagefs_type)

        element = self.wait_until_visible('#hintError-image-fs_type')

        self.assertTrue(("A valid image type cannot include underscores" in element.text),
                        "Did not find underscore error message")


    def test_checkbox_verification(self):
        """
        Should automatically check the checkbox if user enters value
        text box, if value is there in the checkbox.
        """
        imagefs_type = "btrfs"

        ProjectVariable.objects.get_or_create(project = self.project1, name = "IMAGE_FSTYPES", value = "abcd ")
        url = reverse('projectconf', args=(self.project1.id,));
        self.get(url);

        self.click('#change-image_fstypes-icon')

        self.enter_text('#new-imagefs_types', imagefs_type)

        checkboxes = self.driver.find_elements_by_xpath("//input[@class='fs-checkbox-fstypes']")

        for checkbox in checkboxes:
            if checkbox.get_attribute("value") == "btrfs":
               self.assertEqual(checkbox.is_selected(), True)


    def test_textbox_with_checkbox_verification(self):
        """
        Should automatically add or remove value in textbox, if user checks
        or unchecks checkboxes.
        """

        ProjectVariable.objects.get_or_create(project = self.project1, name = "IMAGE_FSTYPES", value = "abcd ")
        url = reverse('projectconf', args=(self.project1.id,));
        self.get(url);

        self.click('#change-image_fstypes-icon')

        self.wait_until_visible('#new-imagefs_types')

        checkboxes_selector = '.fs-checkbox-fstypes'

        self.wait_until_visible(checkboxes_selector)
        checkboxes = self.find_all(checkboxes_selector)

        for checkbox in checkboxes:
            if checkbox.get_attribute("value") == "cpio":
               checkbox.click()
               element = self.driver.find_element_by_id('new-imagefs_types')

               self.wait_until_visible('#new-imagefs_types')

               self.assertTrue(("cpio" in element.get_attribute('value'),
                               "Imagefs not added into the textbox"))
               checkbox.click()
               self.assertTrue(("cpio" not in element.text),
                               "Image still present in the textbox")
