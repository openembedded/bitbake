
# Copyright (C) 2025 Pierre-Loup GOSSE
#
# SPDX-License-Identifier: GPL-2.0-only
#
# Based on functions from the base bb module, Copyright 2003 Holger Schurig

"""
BitBake 'Fetch' implementation for AWS Codeartifact asset.

Class to fetch AWS Codeartifact asset with the AWS cli.
The aws tool must be correctly installed and configured prior to use.

  SRC_URI = "codeartifact://<domain-owner>@<domain>/<repository>/<namespace>/<package>/<package-version>/<asset>;format=<format>;unpack=0"

The package path should use '/' instead of '.'.
The format of the package is a required URL parameter.
Refer to https://docs.aws.amazon.com/codeartifact/latest/ug/download-assets.html.

For example:

  SRC_URI = "codeartifact://111122223333@my_domain/my_repo/com/google/guava/guava/27.1-jre/guava-27.1-jre.jar;format=maven;unpack=0"

    domain-owner:       111122223333
    domain:             my_domain
    repository:         my_repo
    namespace:          com.google.guava
    package:            guava
    package-version:    27.1-jre
    asset:              guava-27.1-jre.jar
    format:             maven

"""

import os
import bb
import re
import urllib.request, urllib.parse, urllib.error
from bb.fetch2 import Fetch, FetchMethod, FetchError, MalformedUrl, runfetchcmd, check_network_access

class Codeartifact(FetchMethod):
    """Class to fetch AWS Codeartifact asset via 'aws cli'"""

    def supports(self, ud, d):
        """
        Check to see if a given url can be fetched with aws cli.
        """
        return ud.type in ['codeartifact']

    def urldata_init(self, ud, d):
        ud.basename = os.path.basename(ud.path)
        ud.basecmd = d.getVar("FETCHCMD_codeartifact") or "aws codeartifact"
        ud.localfile = d.expand(urllib.parse.unquote(ud.basename))

        if 'format' in ud.parm:
            ud.format = ud.parm['format']

        if not ud.format:
            raise MissingParameterError("Parameter 'format' required", ud.url)

        m = re.compile('/(?P<repository>[^/]+)/(?P<namespace>.+)/(?P<package>[^/]+)/(?P<version>[^/]+)/(?P<file>[^/]+)').match(ud.path)
        if not m:
            raise MalformedUrl(ud.url, "The URL '%s' is invalid: path must contain /<repository>/<namespace>/<package>/<package-version>/<asset>" % ud.url)

        ud.repository = m.group('repository')
        ud.namespace = m.group('namespace').replace("/", ".")
        ud.package = m.group('package')
        ud.version = m.group('version')
        ud.file = m.group('file')

    def download(self, ud, d):
        """
        Fetch urls
        Assumes localpath was called first
        """
        cmd = '%s get-package-version-asset --domain %s --domain-owner %s --repository %s \
                --format %s --namespace %s --package %s --package-version %s --asset %s %s' % \
                (ud.basecmd, ud.host, ud.user, ud.repository, ud.format, ud.namespace, ud.package, ud.version, ud.file, ud.file)
        check_network_access(d, cmd, ud.url)

        return runfetchcmd(cmd, d, False)

    def checkstatus(self, fetch, ud, d):
        """
        Check the status of a URL
        """

        cmd = '%s list-package-version-assets --domain %s --domain-owner %s --repository %s \
                --format %s --namespace %s --package %s --package-version %s' % \
                (ud.basecmd, ud.host, ud.user, ud.repository, ud.format, ud.namespace, ud.package, ud.version)
        check_network_access(d, cmd, ud.url)
        runfetchcmd(cmd, d)

        return True
