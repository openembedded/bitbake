#! /usr/bin/env python3 #
# BitBake Toaster UI tests implementation
#
# Copyright (C) 2023 Savoir-faire Linux
#
# SPDX-License-Identifier: GPL-2.0-only
#

import pytest
from django.urls import reverse
from selenium.webdriver.support.select import Select
from tests.functional.functional_helpers import SeleniumFunctionalTestCase
from selenium.webdriver.common.by import By


@pytest.mark.django_db
class TestProjectPage(SeleniumFunctionalTestCase):

    def setUp(self):
        super().setUp()
        release = '3'
        project_name = 'projectmaster'
        self._create_test_new_project(
            project_name,
            release,
            False,
        )

    def _create_test_new_project(
        self,
        project_name,
        release,
        merge_toaster_settings,
    ):
        """ Create/Test new project using:
          - Project Name: Any string
          - Release: Any string
          - Merge Toaster settings: True or False
        """
        self.get(reverse('newproject'))
        self.driver.find_element(By.ID,
                                 "new-project-name").send_keys(project_name)

        select = Select(self.find('#projectversion'))
        select.select_by_value(release)

        # check merge toaster settings
        checkbox = self.find('.checkbox-mergeattr')
        if merge_toaster_settings:
            if not checkbox.is_selected():
                checkbox.click()
        else:
            if checkbox.is_selected():
                checkbox.click()

        self.driver.find_element(By.ID, "create-project-button").click()

    def test_page_header_on_project_page(self):
        """ Check page header in project page:
          - AT LEFT -> Logo of Yocto project, displayed, clickable
          - "Toaster"+" Information icon", displayed, clickable
          - "Server Icon" + "All builds", displayed, clickable
          - "Directory Icon" + "All projects", displayed, clickable
          - "Book Icon" + "Documentation", displayed, clickable
          - AT RIGHT -> button "New project", displayed, clickable
        """
        # navigate to the project page
        url = reverse("project", args=(1,))
        self.get(url)

        # check page header
        # AT LEFT -> Logo of Yocto project
        logo = self.driver.find_element(
            By.XPATH,
            "//div[@class='toaster-navbar-brand']",
        )
        logo_img = logo.find_element(By.TAG_NAME, 'img')
        self.assertTrue(logo_img.is_displayed(),
                        'Logo of Yocto project not found')
        self.assertTrue(
            '/static/img/logo.png' in str(logo_img.get_attribute('src')),
            'Logo of Yocto project not found'
        )
        # "Toaster"+" Information icon", clickable
        toaster = self.driver.find_element(
            By.XPATH,
            "//div[@class='toaster-navbar-brand']//a[@class='brand']",
        )
        self.assertTrue(toaster.is_displayed(), 'Toaster not found')
        self.assertTrue(toaster.text == 'Toaster')
        info_sign = self.find('.glyphicon-info-sign')
        self.assertTrue(info_sign.is_displayed())

        # "Server Icon" + "All builds"
        all_builds = self.find('#navbar-all-builds')
        all_builds_link = all_builds.find_element(By.TAG_NAME, 'a')
        self.assertTrue("All builds" in all_builds_link.text)
        self.assertTrue(
            '/toastergui/builds/' in str(all_builds_link.get_attribute('href'))
        )
        server_icon = all_builds.find_element(By.TAG_NAME, 'i')
        self.assertTrue(
            server_icon.get_attribute('class') == 'glyphicon glyphicon-tasks'
        )
        self.assertTrue(server_icon.is_displayed())

        # "Directory Icon" + "All projects"
        all_projects = self.find('#navbar-all-projects')
        all_projects_link = all_projects.find_element(By.TAG_NAME, 'a')
        self.assertTrue("All projects" in all_projects_link.text)
        self.assertTrue(
            '/toastergui/projects/' in str(all_projects_link.get_attribute(
                'href'))
        )
        dir_icon = all_projects.find_element(By.TAG_NAME, 'i')
        self.assertTrue(
            dir_icon.get_attribute('class') == 'icon-folder-open'
        )
        self.assertTrue(dir_icon.is_displayed())

        # "Book Icon" + "Documentation"
        toaster_docs_link = self.find('#navbar-docs')
        toaster_docs_link_link = toaster_docs_link.find_element(By.TAG_NAME,
                                                                'a')
        self.assertTrue("Documentation" in toaster_docs_link_link.text)
        self.assertTrue(
            toaster_docs_link_link.get_attribute('href') == 'http://docs.yoctoproject.org/toaster-manual/index.html#toaster-user-manual'
        )
        book_icon = toaster_docs_link.find_element(By.TAG_NAME, 'i')
        self.assertTrue(
            book_icon.get_attribute('class') == 'glyphicon glyphicon-book'
        )
        self.assertTrue(book_icon.is_displayed())

        # AT RIGHT -> button "New project"
        new_project_button = self.find('#new-project-button')
        self.assertTrue(new_project_button.is_displayed())
        self.assertTrue(new_project_button.text == 'New project')
        new_project_button.click()
        self.assertTrue(
            '/toastergui/newproject/' in str(self.driver.current_url)
        )
