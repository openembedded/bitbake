#! /usr/bin/env python3 #
# BitBake Toaster UI tests implementation
#
# Copyright (C) 2023 Savoir-faire Linux
#
# SPDX-License-Identifier: GPL-2.0-only
#

from time import sleep
import pytest
from django.urls import reverse
from selenium.webdriver.support.select import Select
from selenium.common.exceptions import NoSuchElementException
from tests.functional.functional_helpers import SeleniumFunctionalTestCase
from selenium.webdriver.common.by import By


@pytest.mark.django_db
class TestProjectConfigTab(SeleniumFunctionalTestCase):

    def setUp(self):
        self.recipe = None
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

    @classmethod
    def _wait_until_build(cls, state):
        while True:
            try:
                last_build_state = cls.driver.find_element(
                    By.XPATH,
                    '//*[@id="latest-builds"]/div[1]//div[@class="build-state"]',
                )
                build_state = last_build_state.get_attribute(
                    'data-build-state')
                state_text = state.lower().split()
                if any(x in str(build_state).lower() for x in state_text):
                    break
            except NoSuchElementException:
                continue
            sleep(1)

    def _create_builds(self):
        # check search box can be use to build recipes
        search_box = self.find('#build-input')
        search_box.send_keys('core-image-minimal')
        self.find('#build-button').click()
        sleep(1)
        self.wait_until_visible('#latest-builds')
        # loop until reach the parsing state
        self._wait_until_build('parsing starting cloning')
        lastest_builds = self.driver.find_elements(
            By.XPATH,
            '//div[@id="latest-builds"]/div',
        )
        last_build = lastest_builds[0]
        self.assertTrue(
            'core-image-minimal' in str(last_build.text)
        )
        cancel_button = last_build.find_element(
            By.XPATH,
            '//span[@class="cancel-build-btn pull-right alert-link"]',
        )
        cancel_button.click()
        sleep(1)
        self._wait_until_build('cancelled')

    def _get_tabs(self):
        # tabs links list
        return self.driver.find_elements(
            By.XPATH,
            '//div[@id="project-topbar"]//li'
        )

    def _get_config_nav_item(self, index):
        config_nav = self.find('#config-nav')
        return config_nav.find_elements(By.TAG_NAME, 'li')[index]

    def test_project_config_nav(self):
        """ Test project config tab navigation:
        - Check if the menu is displayed and contains the right elements:
            - Configuration
            - COMPATIBLE METADATA
            - Custom images
            - Image recipes
            - Software recipes
            - Machines
            - Layers
            - Distro
            - EXTRA CONFIGURATION
            - Bitbake variables
            - Actions
            - Delete project
        """
        # navigate to the project page
        url = reverse("project", args=(1,))
        self.get(url)

        # check if the menu is displayed
        self.wait_until_visible('#config-nav')

        def _get_config_nav_item(index):
            config_nav = self.find('#config-nav')
            return config_nav.find_elements(By.TAG_NAME, 'li')[index]

        def check_config_nav_item(index, item_name, url):
            item = _get_config_nav_item(index)
            self.assertTrue(item_name in item.text)
            self.assertTrue(item.get_attribute('class') == 'active')
            self.assertTrue(url in self.driver.current_url)

        # check if the menu contains the right elements
        # COMPATIBLE METADATA
        compatible_metadata = _get_config_nav_item(1)
        self.assertTrue(
            "compatible metadata" in compatible_metadata.text.lower()
        )
        # EXTRA CONFIGURATION
        extra_configuration = _get_config_nav_item(8)
        self.assertTrue(
            "extra configuration" in extra_configuration.text.lower()
        )
        # Actions
        actions = _get_config_nav_item(10)
        self.assertTrue("actions" in str(actions.text).lower())

        conf_nav_list = [
            [0, 'Configuration', f"/toastergui/project/1"],  # config
            [2, 'Custom images', f"/toastergui/project/1/customimages"],  # custom images
            [3, 'Image recipes', f"/toastergui/project/1/images"],  # image recipes
            [4, 'Software recipes', f"/toastergui/project/1/softwarerecipes"],  # software recipes
            [5, 'Machines', f"/toastergui/project/1/machines"],  # machines
            [6, 'Layers', f"/toastergui/project/1/layers"],  # layers
            [7, 'Distro', f"/toastergui/project/1/distro"],  # distro
            [9, 'BitBake variables', f"/toastergui/project/1/configuration"],  # bitbake variables
        ]
        for index, item_name, url in conf_nav_list:
            item = _get_config_nav_item(index)
            if item.get_attribute('class') != 'active':
                item.click()
            check_config_nav_item(index, item_name, url)
