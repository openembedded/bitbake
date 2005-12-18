#!/usr/bin/env python
# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
# Copyright (C) 2003  Chris Larson
#
# This program is free software; you can redistribute it and/or modify it under
# the terms of the GNU General Public License as published by the Free Software
# Foundation; either version 2 of the License, or (at your option) any later
# version.
# 
# This program is distributed in the hope that it will be useful, but WITHOUT
# ANY WARRANTY; without even the implied warranty of MERCHANTABILITY or FITNESS
# FOR A PARTICULAR PURPOSE. See the GNU General Public License for more details.
# 
# You should have received a copy of the GNU General Public License along with
# this program; if not, write to the Free Software Foundation, Inc., 59 Temple
# Place, Suite 330, Boston, MA 02111-1307 USA. 

from distutils.core import setup
import os, sys

# bbdir = os.path.join(sys.prefix, 'share', 'bitbake')
# docdir = os.path.join(sys.prefix, 'share', 'doc')
bbdir = os.path.join('bitbake')
docdir = os.path.join('doc')

def clean_doc(type):
    origpath = os.path.abspath(os.curdir)
    os.chdir(os.path.join(origpath, 'doc', 'manual'))
    make = os.environ.get('MAKE') or 'make'
    os.system('%s clean-%s' % (make, type))

def generate_doc(type):
    origpath = os.path.abspath(os.curdir)
    os.chdir(os.path.join(origpath, 'doc', 'manual'))
    make = os.environ.get('MAKE') or 'make'
    ret = os.system('%s %s' % (make, type))
    if ret != 0:
        print "ERROR: Unable to generate html documentation."
        sys.exit(ret)
    os.chdir(origpath)

if 'bdist' in sys.argv[1:]:
    generate_doc('html')

sys.path.append(os.path.join(os.path.dirname(sys.argv[0]), 'lib'))
import bb
import glob
setup(name='bitbake',
      version=bb.__version__,
      license='GPL',
      url='http://developer.berlios.de/projects/bitbake/',
      description='BitBake build tool',
      long_description='BitBake is a simple tool for the execution of tasks. It is derived from Portage, which is the package management system used by the Gentoo Linux distribution. It is most commonly used to build packages, as it can easily use its rudamentary inheritence to abstract common operations, such as fetching sources, unpacking them, patching them, compiling them, and so on.  It is the basis of the OpenEmbedded project, which is being used for OpenZaurus, Familiar, and a number of other Linux distributions.',
      author='Chris Larson',
      author_email='clarson@elinux.org',
      packages=['bb', 'bb.fetch', 'bb.parse', 'bb.parse.parse_py'],
      package_dir={'bb': os.path.join('lib', 'bb')},
      scripts=[os.path.join('bin', 'bitbake'),
               os.path.join('bin', 'bbimage')],
      data_files=[(os.path.join(bbdir, 'conf'), [os.path.join('conf', 'bitbake.conf')]),
                  (os.path.join(bbdir, 'classes'), [os.path.join('classes', 'base.bbclass')]),
                  (os.path.join(docdir, 'bitbake-%s' % bb.__version__, 'html'), glob.glob(os.path.join('doc', 'manual', 'html', '*.html'))),
                  (os.path.join(docdir, 'bitbake-%s' % bb.__version__, 'pdf'), glob.glob(os.path.join('doc', 'manual', 'pdf', '*.pdf'))),],
     )

if 'bdist' in sys.argv[1:]:
    clean_doc('html')
