from django.core.management.base import BaseCommand, CommandError
from orm.models import LayerSource, ToasterSetting, Layer, Layer_Version
from orm.models import BitbakeVersion, Release, ReleaseDefaultLayer
from django.db import IntegrityError
import os

from .checksettings import DN

import logging
logger = logging.getLogger("toaster")

# Temporary old code to support old toasterconf.json
def _reduce_canon_path(path):
    components = []
    for c in path.split("/"):
        if c == "..":
            del components[-1]
        elif c == ".":
            pass
        else:
            components.append(c)
    if len(components) < 2:
        components.append('')
    return "/".join(components)
# End temp code

class Command(BaseCommand):
    help = "Loads a toasterconf.json file in the database"
    args = "filepath"



    def _import_layer_config(self, filepath):
        if not os.path.exists(filepath) or not os.path.isfile(filepath):
            raise Exception("Failed to find toaster config file %s ." % filepath)

        import json
        data = json.loads(open(filepath, "r").read())

        # verify config file validity before updating settings
        for i in ['bitbake', 'releases', 'defaultrelease', 'config']:
            assert i in data

        def _read_git_url_from_local_repository(address):
            url = None
            # we detect the remote name at runtime
            import subprocess
            (remote, remote_name) = address.split(":", 1)
            cmd = subprocess.Popen("git remote -v", shell=True, cwd = os.path.dirname(filepath), stdout=subprocess.PIPE, stderr = subprocess.PIPE)
            (out,err) = cmd.communicate()
            if cmd.returncode != 0:
                logging.warning("Error while importing layer vcs_url: git error: %s" % err)
            for line in out.decode('utf-8').split("\n"):
                try:
                    (name, path) = line.split("\t", 1)
                    if name == remote_name:
                        url = path.split(" ")[0]
                        break
                except ValueError:
                    pass
            if url == None:
                logging.warning("Error while looking for remote \"%s\" in \"%s\"" % (remote_name, out))
            return url


        # import bitbake data
        for bvi in data['bitbake']:
            bvo, created = BitbakeVersion.objects.get_or_create(name=bvi['name'])
            if bvi['giturl'].startswith("remote:"):
                bvo.giturl = _read_git_url_from_local_repository(bvi['giturl'])
                if bvo.giturl is None:
                    logger.error("The toaster config file references the local git repo, but Toaster cannot detect it.\nYour local configuration for bitbake version %s is invalid. Make sure that the toasterconf.json file is correct." % bvi['name'])

            if bvo.giturl is None:
                bvo.giturl = bvi['giturl']
            bvo.branch = bvi['branch']
            bvo.dirpath = bvi['dirpath']
            bvo.save()

        for ri in data['releases']:
            bvo = BitbakeVersion.objects.get(name = ri['bitbake'])
            assert bvo is not None

            ro, created = Release.objects.get_or_create(name = ri['name'], bitbake_version = bvo, branch_name = ri['branch'])
            ro.description = ri['description']
            ro.helptext = ri['helptext']
            ro.save()

            for dli in ri['defaultlayers']:
                # find layers with the same name
                ReleaseDefaultLayer.objects.get_or_create( release = ro, layer_name = dli)

        # NOTE Temporary old code to handle old toasterconf.json. All this to
        # be removed after rewrite of config loading mechanism
        for lsi in data['layersources']:
            assert 'sourcetype' in lsi
            assert 'apiurl' in lsi
            assert 'name' in lsi
            assert 'branches' in lsi

            if "local" in lsi['sourcetype']:
                ls = LayerSource.TYPE_LOCAL
            else:
                ls = LayerSource.TYPE_LAYERINDEX

            layer_releases = []
            for branchname in lsi['branches']:
                try:
                    release = Release.objects.get(branch_name=branchname)
                    layer_releases.append(release)
                except Release.DoesNotExist:
                    logger.error("Layer set for %s but no release matches this"
                                 "in the config" % branchname)

            apiurl = _reduce_canon_path(
                os.path.join(DN(os.path.abspath(filepath)), lsi['apiurl']))

            if 'layers' in lsi:
                for layerinfo in lsi['layers']:
                    lo, created = Layer.objects.get_or_create(
                        name=layerinfo['name'],
                        vcs_url=layerinfo['vcs_url'],
                    )
                    if layerinfo['local_path'].startswith("/"):
                        lo.local_path = layerinfo['local_path']
                    else:
                        lo.local_path = _reduce_canon_path(
                            os.path.join(apiurl, layerinfo['local_path']))

                    if layerinfo['vcs_url'].startswith("remote:"):
                        lo.vcs_url = _read_git_url_from_local_repository(
                            layerinfo['vcs_url'])
                        if lo.vcs_url is None:
                            logger.error("The toaster config file references"
                                         " the local git repo, but Toaster "
                                         "cannot detect it.\nYour local "
                                         "configuration for layer %s is "
                                         "invalid. Make sure that the "
                                         "toasterconf.json file is correct."
                                         % layerinfo['name'])

                    if lo.vcs_url is None:
                        lo.vcs_url = layerinfo['vcs_url']

                    if 'layer_index_url' in layerinfo:
                        lo.layer_index_url = layerinfo['layer_index_url']
                    lo.save()

                    for release in layer_releases:
                        lvo, created = Layer_Version.objects.get_or_create(
                            layer_source=ls,
                            release=release,
                            commit=release.branch_name,
                            branch=release.branch_name,
                            layer=lo)
                        lvo.dirpath = layerinfo['dirpath']
                        lvo.save()
        # END temporary code


        # set default release
        if ToasterSetting.objects.filter(name = "DEFAULT_RELEASE").count() > 0:
            ToasterSetting.objects.filter(name = "DEFAULT_RELEASE").update(value = data['defaultrelease'])
        else:
            ToasterSetting.objects.create(name = "DEFAULT_RELEASE", value = data['defaultrelease'])

        # set default config variables
        for configname in data['config']:
            if ToasterSetting.objects.filter(name = "DEFCONF_" + configname).count() > 0:
                ToasterSetting.objects.filter(name = "DEFCONF_" + configname).update(value = data['config'][configname])
            else:
                ToasterSetting.objects.create(name = "DEFCONF_" + configname, value = data['config'][configname])


    def handle(self, *args, **options):
        if len(args) == 0:
            raise CommandError("Need a path to the toasterconf.json file")
        filepath = args[0]
        self._import_layer_config(filepath)
