#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2003  Chris Larson
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

import os, sys
sys.path.append(os.path.join(os.path.dirname(__file__), "lib"))
from bb import __version__

from glob import glob
from distutils.command.clean import clean
from distutils.command.build import build
from distutils.core import setup


doctype = "html"

class Clean(clean):
    def run(self):
        clean.run(self)
        origpath = os.path.abspath(os.curdir)
        os.chdir(os.path.join(origpath, 'doc', 'manual'))
        make = os.environ.get('MAKE') or 'make'
        os.system('%s clean-%s' % (make, doctype))

class Build(build):
    def run(self):
        build.run(self)
        origpath = os.path.abspath(os.curdir)
        os.chdir(os.path.join(origpath, 'doc', 'manual'))
        make = os.environ.get('MAKE') or 'make'
        ret = os.system('%s %s' % (make, doctype))
        if ret != 0:
            print("ERROR: Unable to generate html documentation.")
            sys.exit(ret)
        os.chdir(origpath)

setup(name='bitbake',
      version = __version__,
      requires = ["ply", "progressbar"],
      package_dir = {"": "lib"},
      packages = ["bb.server", "bb.parse.parse_py", "bb.parse", 
                  "bb.fetch2", "bb.ui.crumbs", "bb.ui", "bb.pysh", "bb", "prserv"],
      py_modules = ["codegen"],
      scripts = ["bin/bitbake", "bin/bitbake-layers", "bin/bitbake-diffsigs", "bin/bitbake-prserv"],
      data_files = [("share/bitbake", glob("conf/*") + glob("classes/*")),
                  ("share/doc/bitbake-%s/manual" % __version__, glob("doc/manual/html/*"))],
      cmdclass = {
          "build": Build,
          "clean": Clean,
      },

      license = 'GPLv2',
      url = 'http://developer.berlios.de/projects/bitbake/',
      description = 'BitBake build tool',
      long_description = 'BitBake is a simple tool for the execution of tasks. It is derived from Portage, which is the package management system used by the Gentoo Linux distribution. It is most commonly used to build packages, as it can easily use its rudimentary inheritance to abstract common operations, such as fetching sources, unpacking them, patching them, compiling them, and so on.  It is the basis of the OpenEmbedded project, which is being used for OpenZaurus, Familiar, and a number of other Linux distributions.',
      author = 'BitBake Development Team',
      author_email = 'bitbake-dev@lists.berlios.de',
)
