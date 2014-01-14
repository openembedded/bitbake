"""
This file demonstrates writing tests using the unittest module. These will pass
when you run "manage.py test".

Replace this with more appropriate tests for your application.
"""
from django.test import TestCase
from django.test.client import Client
from django.db.models import Count, Q
from orm.models import Target, Recipe, Recipe_Dependency, Layer_Version, Target_Installed_Package
from orm.models import Build, Task, Layer, Package, Package_File, LogMessage, Variable, VariableHistory
import json, os, re, urllib, shlex


class Tests(TestCase):
    fixtures = ['orm_views_testdata.json']

    def test_builds(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/builds')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            self.assertTrue(fields["machine"] == "qemux86")
            self.assertTrue(fields["distro"] == "poky")
            self.assertTrue(fields["image_fstypes"] == "tar.bz2 ext3")
            self.assertTrue(fields["bitbake_version"] == "1.21.1")
            self.assertTrue("1.5+snapshot-" in fields["distro_version"])
            self.assertEqual(fields["outcome"], 0)
            self.assertEqual(fields["errors_no"], 0)
            log_path = "/tmp/log/cooker/qemux86/"
            self.assertTrue(log_path in fields["cooker_log_path"])
            self.assertTrue(".log" in fields["cooker_log_path"])

    def test_targets(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/targets')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            self.assertTrue(fields["is_image"] == True)
            self.assertTrue(fields["target"] == "core-image-minimal")

    def test_tasks(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/tasks')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        recipe_id = self.get_recipes_id("pseudo-native")
        print recipe_id
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["build"] == 1 and fields["task_name"] == "do_populate_lic_setscene" and fields["recipe"] == recipe_id and fields["task_executed"] == True:
                self.assertTrue(fields["message"] == "recipe pseudo-native-1.5.1-r4: task do_populate_lic_setscene: Succeeded")
                self.assertTrue(fields["cpu_usage"] == "6.3")
                self.assertTrue(fields["disk_io"] == 124)
                self.assertTrue(fields["script_type"] == 2)
                self.assertTrue(fields["path_to_sstate_obj"] == "")
                self.assertTrue(fields["elapsed_time"] == "0.103494")
                self.assertTrue("tmp/work/i686-linux/pseudo-native/1.5.1-r4/temp/log.do_populate_lic_setscene.5867" in fields["logfile"])
                self.assertTrue(fields["sstate_result"] == 0)
                self.assertTrue(fields["outcome"] == 0)
            if fields["build"] == 1 and fields["task_name"] == "do_populate_lic" and fields["recipe"] == recipe_id and fields["task_executed"] == True:
                self.assertTrue(fields["cpu_usage"] == None)
                self.assertTrue(fields["disk_io"] == None)
                self.assertTrue(fields["script_type"] == 2)
                self.assertTrue(fields["path_to_sstate_obj"] == "")
                self.assertTrue(fields["elapsed_time"] == "0")
                self.assertTrue(fields["logfile"], None)
                self.assertTrue(fields["sstate_result"] == 3)
                self.assertTrue(fields["outcome"] == 2)

    def test_layers(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/layers')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["name"] == "meta-yocto-bsp":
                self.assertTrue(fields["local_path"].endswith("meta-yocto-bsp"))
                self.assertTrue(fields["layer_index_url"] == "http://layers.openembedded.org/layerindex/layer/meta-yocto-bsp/")
            elif fields["name"] == "meta":
                self.assertTrue(fields["local_path"].endswith("/meta"))
                self.assertTrue(fields["layer_index_url"] == "http://layers.openembedded.org/layerindex/layer/openembedded-core/")
            elif fields["name"] == "meta-yocto":
                self.assertTrue(fields["local_path"].endswith("/meta-yocto"))
                self.assertTrue(fields["layer_index_url"] == "http://layers.openembedded.org/layerindex/layer/meta-yocto/")

    def test_layerversions(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/layerversions')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        layer_id = self.get_layer_id("meta")
        find = False
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["layer"] == layer_id:
                find = True
                self.assertTrue(fields["build"] == 1)
                self.assertTrue(fields["priority"] == 5)
                self.assertTrue(fields["branch"] == "master")
        self.assertTrue(find == True)

    def test_recipes(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/recipes')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        find = False
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["name"] == "busybox":
                find = True
                self.assertTrue(fields["version"] == "1.21.1-r0")
                self.assertTrue(fields["license"] == "GPLv2 & bzip2")
                self.assertTrue(fields["file_path"].endswith("/meta/recipes-core/busybox/busybox_1.21.1.bb"))
                self.assertTrue(fields["summary"] == "Tiny versions of many common UNIX utilities in a single small executable.")
                self.assertTrue(fields["description"] == "BusyBox combines tiny versions of many common UNIX utilities into a single small executable. It provides minimalist replacements for most of the utilities you usually find in GNU fileutils, shellutils, etc. The utilities in BusyBox generally have fewer options than their full-featured GNU cousins; however, the options that are included provide the expected functionality and behave very much like their GNU counterparts. BusyBox provides a fairly complete POSIX environment for any small or embedded system.")
                self.assertTrue(fields["bugtracker"] == "https://bugs.busybox.net/")
                self.assertTrue(fields["homepage"] == "http://www.busybox.net")
                self.assertTrue(fields["section"] == "base")
        self.assertTrue(find == True)

    def test_task_dependencies(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/task_dependencies')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        ids = self.get_task_id()
        do_install = ids["do_install"]
        do_compile = ids["do_compile"]
        entry = False
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["task"] == do_install and fields["depends_on"] == do_compile:
                entry = True
        self.assertTrue(entry == True)

    def test_target_installed_package(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/target_installed_packages')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        package = self.get_package_id("udev-utils")
        find = False
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["package"] == package:
                self.assertTrue(fields["target"], 1)
                find = True
        self.assertTrue(find, True)

    def test_packages(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/packages')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(response['count'] > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["name"] == "base-files-dev":
                self.assertTrue(fields["license"] == "GPLv2")
                self.assertTrue(fields["description"] == "The base-files package creates the basic system directory structure and provides a small set of key configuration files for the system.  This package contains symbolic links, header files, and related items necessary for software development.")
                self.assertTrue(fields["summary"] == "Miscellaneous files for the base system. - Development files")
                self.assertTrue(fields["version"] == "3.0.14")
                self.assertTrue(fields["build"] == 1)
                self.assertTrue(fields["section"] == "devel")
                self.assertTrue(fields["revision"] == "r73")
                self.assertTrue(fields["size"] == 0)
                self.assertTrue(fields["installed_size"] == 0)
                self.assertTrue(self.get_recipe_name(fields["recipe"]) == "base-files")

    def test_package_dependencies(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/package_dependencies')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        build_package = self.get_package_id("busybox")
        build_package_id = self.get_package_id("busybox-syslog")
        entry = False
        for item in json.loads(response['list']):
            fields = item['fields']
            self.assertTrue(fields["target"] == 1)
            if fields["package"] == build_package and fields["dep_type"] == 7 and fields["depends_on"] == build_package_id:
                entry = True
        self.assertTrue(entry == True)

    def test_recipe_dependencies(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/recipe_dependencies')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        depends_on = self.get_recipes_id("autoconf-native")
        recipe = self.get_recipes_id("ncurses")
        entry = False
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["recipe"] == recipe and fields["depends_on"] == depends_on and fields["dep_type"] == 0:
                entry = True
        self.assertTrue(entry == True)

    def test_package_files(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/package_files')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        build_package = self.get_package_id("base-files")
        entry = False
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["path"] == "/etc/motd" and fields["package"] == build_package and fields["size"] == 0:
                entry = True
        self.assertTrue(entry == True)

    def test_Variable(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/variables')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            self.assertTrue(fields["build"] == 1)
            if fields["variable_name"] == "USRBINPATH":
                self.assertTrue(fields["variable_value"] == "/usr/bin")
                self.assertTrue(fields["changed"] == False)
                self.assertTrue(fields["description"] == "")
            if fields["variable_name"] == "PREFERRED_PROVIDER_virtual/libx11":
                self.assertTrue(fields["variable_value"] == "libx11")
                self.assertTrue(fields["changed"] == False)
                self.assertTrue(fields["description"] == "If multiple recipes provide an item, this variable determines which recipe should be given preference.")
            if fields["variable_name"] == "base_libdir_nativesdk":
                self.assertTrue(fields["variable_value"] == "/lib")

    def test_VariableHistory(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/variableshistory')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        variable_id = self.get_variable_id("STAGING_INCDIR_NATIVE")
        find = False
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["variable"] == variable_id:
                find = True
                self.assertTrue(fields["file_name"] == "conf/bitbake.conf")
                self.assertTrue(fields["operation"] == "set")
                self.assertTrue(fields["line_number"] == 358)
        self.assertTrue(find == True)

    def get_task_id(self):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/tasks')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["recipe"] == 7 and fields["task_name"] == "do_install":
                do_install = item["pk"]
            if fields["recipe"] == 7 and fields["task_name"] == "do_compile":
                do_compile = item["pk"]
        result = {}
        result["do_install"] = do_install
        result["do_compile"] = do_compile
        return result

    def get_recipes_id(self, value):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/recipes')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["name"] == value:
                return item["pk"]
        return None

    def get_recipe_name(self, value):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/recipes')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if item["pk"] == value:
                return fields["name"]
        return None

    def get_layer_id(self, value):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/layers')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["name"] == value:
                return item["pk"]
        return None

    def get_package_id(self, field):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/packages')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(response['count'] > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["name"] == field:
                return item["pk"]
        return None

    def get_variable_id(self, field):
        client = Client()
        resp = client.get('http://localhost:8000/api/1.0/variables')
        self.assertEqual(resp.status_code, 200)
        response = json.loads(resp.content)
        self.assertTrue(len(json.loads(response['list'])) > 0)
        for item in json.loads(response['list']):
            fields = item['fields']
            if fields["variable_name"] == field:
                return item["pk"]
        return None
