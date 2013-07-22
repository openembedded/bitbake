BitBake
=======

BitBake is a simple tool for the execution of tasks. It is derived from Portage, which is the package management system used by the Gentoo Linux distribution. It is most commonly used to build packages, and is used as the basis of the OpenEmbedded project.

BitBake is now managed using the Git source control system which can be obtained from git://git.openembedded.org/bitbake.git. Releases can be downloaded from http://downloads.yoctoproject.org/releases/bitbake/ and the developer mailing list, bitbake-devel can be found at http://lists.linuxtogo.org/cgi-bin/mailman/listinfo/bitbake-devel.

The user manual is found in the docmentation directory within the source code.

Karfield's addition
===================

1. add gclient fetcher. So the bitbake can support to sync chromium-based project such as chromium, libjingle etc.
   To use this, the SRC_URI for example, could write like this

      SRC_URI = "gclient://libjingle.googlecode.com/svn/trunk;name=libjingle;jobs=8".
