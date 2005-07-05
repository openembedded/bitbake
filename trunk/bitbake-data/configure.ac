# get our package versions
m4_include([config/version.m4])


# initialization
AC_INIT(bitbake-data, BBDATA_VER, bitbake-dev@lists.berlios.de)
AC_PREREQ(2.57)

AC_CONFIG_SRCDIR([include/bitbake-data.h])
AC_CONFIG_AUX_DIR(config)
AM_CONFIG_HEADER([config.h])

AM_INIT_AUTOMAKE


PACKAGE_DESCRIPTION="A supplementary library to the bitbake project to act as a datastore."
AC_SUBST([PACKAGE_DESCRIPTION])

# library versioning
LT_RELEASE=BBDATA_LT_REL
AC_SUBST([LT_RELEASE])

LT_CURRENT=BBDATA_LT_CUR
AC_SUBST([LT_CURRENT])

LT_REVISION=BBDATA_LT_REV
AC_SUBST([LT_REVISION])

LT_AGE=BBDATA_LT_AGE
AC_SUBST([LT_AGE])


# system
AC_CANONICAL_SYSTEM


# paths
auxdir="\$(top_srcdir)/$ac_aux_dir"
AC_SUBST(auxdir)

reldatadir="\$(datadir)/bitbake-data-\$(LT_RELEASE)"
rellibdir="\$(libdir)/bitbake-data-\$(LT_RELEASE)"
relincludedir="\$(includedir)/bitbake-data-\$(LT_RELEASE)"
AC_SUBST([reldatadir])
AC_SUBST([rellibdir])
AC_SUBST([relincludedir])


# programs
BB_DEFAULT_FLAGS

AC_PROG_CC
BB_CC_HIDDEN_VISIBILITY

AC_PROG_LIBTOOL
AC_SUBST(LIBTOOL_DEPS)



# dependencies
PKG_CHECK_MODULES([GLIB2], [glib-2.0])
PKG_CHECK_MODULES([SQLITE3], [sqlite3])


# docbook documentation
# AC_CHECK_PROGS([XMLLINT], [xmllint])
# AC_CHECK_PROGS([XSLTPROC], [xsltproc])

# doxygen documentation
DX_HTML_FEATURE(ON)
DX_CHM_FEATURE(OFF)
DX_CHI_FEATURE(OFF)
DX_MAN_FEATURE(ON)
DX_RTF_FEATURE(OFF)
DX_XML_FEATURE(OFF)
DX_PDF_FEATURE(ON)
DX_PS_FEATURE(OFF)
DX_INIT_DOXYGEN($PACKAGE, [doc/doxygen/doxygen.cfg], [doc/doxygen/output])


# options
AC_MSG_CHECKING([whether user requested building tests])
AC_ARG_ENABLE(tests, 
	AS_HELP_STRING([--enable-tests],
		[Enable building of tests (default=no)]),
	[enable_tests=$enableval],
	[enable_tests=no])
AC_MSG_RESULT($enable_tests)
AM_CONDITIONAL(BB_TESTS, test "$enable_tests" = "yes")

# see if 'check', the unit testing framework, is installed
if test x"$enable_tests" != "xno"; then
  AM_PATH_CHECK
fi


# other
# AM_BINRELOC


# This variable is used to indicate whether we're compiling
# a part of our library itself, or external binaries.
BBDATA_DLL_EXPORTS="-DBBDATA_DLL_EXPORTS"
AC_SUBST([BBDATA_DLL_EXPORTS])


# output
AC_CONFIG_FILES([Makefile
		 src/Makefile
		 doc/Makefile
		 doc/doxygen/Makefile
		 tests/Makefile
		 bitbake-data-$LT_RELEASE.pc:bitbake-data.pc.in])
# AC_CONFIG_FILES([Makefile
# 		 include/Makefile
# 		 doc/design_spec/Makefile
# 		 bitbake-data-0.0.pc])
AC_OUTPUT
