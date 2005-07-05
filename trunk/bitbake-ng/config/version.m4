dnl bitbake-ng package version
m4_define([BITBAKE_VER], [0.1])

dnl bitbake-ng library "release" version
dnl "0.0" in bitbake-ng-0.0.so
dnl Increment on API break.
m4_define([BITBAKE_LT_REL], [0.0])

dnl bitbake-ng libtool library version

dnl Current, increment on ABI break
m4_define([BITBAKE_LT_CUR], [0])
dnl Revision, increment at release
m4_define([BITBAKE_LT_REV], [0])
dnl Age
m4_define([BITBAKE_LT_AGE], [0])
