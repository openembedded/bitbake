#
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# BitBake Toaster Implementation
#
# Copyright (C) 2016        Intel Corporation
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

from django.core.management.base import NoArgsCommand

from orm.models import LayerSource, Layer, Release, Layer_Version
from orm.models import LayerVersionDependency, Machine, Recipe

import os
import json
import logging
logger = logging.getLogger("toaster")

DEFAULT_LAYERINDEX_SERVER = "http://layers.openembedded.org/layerindex/api/"


class Command(NoArgsCommand):
    args = ""
    help = "Updates locally cached information from a layerindex server"

    def update(self):
        """
            Fetches layer, recipe and machine information from a layerindex
            server
        """

        self.apiurl = DEFAULT_LAYERINDEX_SERVER

        assert self.apiurl is not None
        try:
            from urllib.request import urlopen, URLError
            from urllib.parse import urlparse
        except ImportError:
            from urllib2 import urlopen, URLError
            from urlparse import urlparse

        proxy_settings = os.environ.get("http_proxy", None)
        oe_core_layer = 'openembedded-core'

        def _get_json_response(apiurl=DEFAULT_LAYERINDEX_SERVER):
            _parsedurl = urlparse(apiurl)
            path = _parsedurl.path

            # logger.debug("Fetching %s", apiurl)
            try:
                res = urlopen(apiurl)
            except URLError as e:
                raise Exception("Failed to read %s: %s" % (path, e.reason))

            return json.loads(res.read().decode('utf-8'))

        # verify we can get the basic api
        try:
            apilinks = _get_json_response()
        except Exception as e:
            import traceback
            if proxy_settings is not None:
                logger.info("EE: Using proxy %s" % proxy_settings)
            logger.warning("EE: could not connect to %s, skipping update:"
                           "%s\n%s" % (self.apiurl, e, traceback.format_exc()))
            return

        # update branches; only those that we already have names listed in the
        # Releases table
        whitelist_branch_names = [rel.branch_name
                                  for rel in Release.objects.all()]
        if len(whitelist_branch_names) == 0:
            raise Exception("Failed to make list of branches to fetch")

        logger.debug("Fetching branches")

        # keep a track of the id mappings so that layer_versions can be created
        # for these layers later on
        li_layer_id_to_toaster_layer_id = {}

        # We may need this? TODO
        #branches_info = _get_json_response(apilinks['branches'] +
        #                                   "?filter=name:%s"
        #                                   % "OR".join(whitelist_branch_names))

        # update layers
        layers_info = _get_json_response(apilinks['layerItems'])

        for li in layers_info:
            # Special case for the openembedded-core layer
            if li['name'] == oe_core_layer:
                try:
                    # If we have an existing openembedded-core for example
                    # from the toasterconf.json augment the info using the
                    # layerindex rather than duplicate it
                    oe_core_l = Layer.objects.get(name=oe_core_layer)
                    # Take ownership of the layer as now coming from the
                    # layerindex
                    oe_core_l.summary = li['summary']
                    oe_core_l.description = li['description']
                    oe_core_l.save()
                    li_layer_id_to_toaster_layer_id[li['id']] = oe_core_l.pk
                    continue

                except Layer.DoesNotExist:
                    pass

            l, created = Layer.objects.get_or_create(name=li['name'])
            l.up_date = li['updated']
            l.vcs_url = li['vcs_url']
            l.vcs_web_url = li['vcs_web_url']
            l.vcs_web_tree_base_url = li['vcs_web_tree_base_url']
            l.vcs_web_file_base_url = li['vcs_web_file_base_url']
            l.summary = li['summary']
            l.description = li['description']
            l.save()

            li_layer_id_to_toaster_layer_id[li['id']] = l.pk

        # update layerbranches/layer_versions
        logger.debug("Fetching layer information")
        layerbranches_info = _get_json_response(
            apilinks['layerBranches'] + "?filter=branch__name:%s" %
            "OR".join(whitelist_branch_names))

        # Map Layer index layer_branch object id to
        # layer_version toaster object id
        li_layer_branch_id_to_toaster_lv_id = {}

        for lbi in layerbranches_info:

            try:
                lv, created = Layer_Version.objects.get_or_create(
                    layer_source=LayerSource.TYPE_LAYERINDEX,
                    layer=Layer.objects.get(
                        pk=li_layer_id_to_toaster_layer_id[lbi['layer']])
                )
            except KeyError:
                print("No such layerindex layer referenced by layerbranch %d" %
                      lbi['layer'])
                continue

            lv.up_date = lbi['updated']
            lv.commit = lbi['actual_branch']
            lv.dirpath = lbi['vcs_subdir']
            lv.save()

            li_layer_branch_id_to_toaster_lv_id[lbi['id']] =\
                lv.pk

        # update layer dependencies
        layerdependencies_info = _get_json_response(
            apilinks['layerDependencies'] +
            "?filter=layerbranch__branch__name:%s" %
            "OR".join(whitelist_branch_names))

        dependlist = {}
        for ldi in layerdependencies_info:
            try:
                lv = Layer_Version.objects.get(
                    pk=li_layer_branch_id_to_toaster_lv_id[ldi['layerbranch']])
            except Layer_Version.DoesNotExist as e:
                continue

            if lv not in dependlist:
                dependlist[lv] = []
            try:
                layer_id = li_layer_id_to_toaster_layer_id[ldi['dependency']]

                dependlist[lv].append(
                    Layer_Version.objects.get(
                        layer_source=LayerSource.TYPE_LAYERINDEX,
                        layer__pk=layer_id))

            except Layer_Version.DoesNotExist:
                logger.warning("Cannot find layer version (ls:%s),"
                               "up_id:%s lv:%s" %
                               (self, ldi['dependency'], lv))

        for lv in dependlist:
            LayerVersionDependency.objects.filter(layer_version=lv).delete()
            for lvd in dependlist[lv]:
                LayerVersionDependency.objects.get_or_create(layer_version=lv,
                                                             depends_on=lvd)

        # update machines
        logger.debug("Fetching machine information")
        machines_info = _get_json_response(
            apilinks['machines'] + "?filter=layerbranch__branch__name:%s" %
            "OR".join(whitelist_branch_names))

        for mi in machines_info:
            mo, created = Machine.objects.get_or_create(
                name=mi['name'],
                layer_version=Layer_Version.objects.get(
                    pk=li_layer_branch_id_to_toaster_lv_id[mi['layerbranch']]))
            mo.up_date = mi['updated']
            mo.name = mi['name']
            mo.description = mi['description']
            mo.save()

        # update recipes; paginate by layer version / layer branch
        logger.debug("Fetching target information")
        recipes_info = _get_json_response(
            apilinks['recipes'] + "?filter=layerbranch__branch__name:%s" %
            "OR".join(whitelist_branch_names))

        for ri in recipes_info:
            try:
                lv_id = li_layer_branch_id_to_toaster_lv_id[ri['layerbranch']]
                lv = Layer_Version.objects.get(pk=lv_id)

                ro, created = Recipe.objects.get_or_create(
                    layer_version=lv,
                    name=ri['pn']
                )

                ro.layer_version = lv
                ro.up_date = ri['updated']
                ro.name = ri['pn']
                ro.version = ri['pv']
                ro.summary = ri['summary']
                ro.description = ri['description']
                ro.section = ri['section']
                ro.license = ri['license']
                ro.homepage = ri['homepage']
                ro.bugtracker = ri['bugtracker']
                ro.file_path = ri['filepath'] + "/" + ri['filename']
                if 'inherits' in ri:
                    ro.is_image = 'image' in ri['inherits'].split()
                else:  # workaround for old style layer index
                    ro.is_image = "-image-" in ri['pn']
                ro.save()
            except Exception as e:
                logger.debug("Failed saving recipe %s", e)

    def handle_noargs(self, **options):
            self.update()
