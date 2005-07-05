# get our package versions
m4_include([config/version.m4])


# initialization
AC_INIT(bitbake-ng, BITBAKE_VER, bitbake-dev@lists.berlios.de)
AC_PREREQ(2.57)

AC_CONFIG_SRCDIR([include/bitbake.h])
AC_CONFIG_AUX_DIR(config)
AM_CONFIG_HEADER([config.h])

AM_INIT_AUTOMAKE


PACKAGE_DESCRIPTION="A library for the execution of recipes."
AC_SUBST([PACKAGE_DESCRIPTION])

# library versioning
LT_RELEASE=BITBAKE_LT_REL
AC_SUBST([LT_RELEASE])

LT_CURRENT=BITBAKE_LT_CUR
AC_SUBST([LT_CURRENT])

LT_REVISION=BITBAKE_LT_REV
AC_SUBST([LT_REVISION])

LT_AGE=BITBAKE_LT_AGE
AC_SUBST([LT_AGE])


# system
AC_CANONICAL_SYSTEM


# paths
auxdir="\$(top_srcdir)/$ac_aux_dir"
AC_SUBST(auxdir)

reldatadir="\$(datadir)/bitbake-\$(LT_RELEASE)"
rellibdir="\$(libdir)/bitbake-\$(LT_RELEASE)"
relincludedir="\$(includedir)/bitbake-\$(LT_RELEASE)"
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


# docbook documentation
AC_CHECK_PROGS([XMLLINT], [xmllint])
AC_CHECK_PROGS([XSLTPROC], [xsltproc])

# doxygen documentation
DX_HTML_FEATURE(ON)
DX_CHM_FEATURE(OFF)
DX_CHI_FEATURE(OFF)
DX_MAN_FEATURE(ON)
DX_RTF_FEATURE(OFF)
DX_XML_FEATURE(OFF)
DX_PDF_FEATURE(ON)
DX_PS_FEATURE(OFF)
DX_INIT_DOXYGEN($PACKAGE, [doc/doxygen.cfg], [doc/doxygen])


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
AM_BINRELOC


# This variable is used to indicate whether we're compiling
# a part of our library itself, or external binaries.
BBDLL_EXPORTS="-DBBDLL_EXPORTS"
AC_SUBST([BBDLL_EXPORTS])


# output
AC_CONFIG_FILES([Makefile
		 include/Makefile
		 src/Makefile
		 tests/Makefile
		 doc/Makefile
		 doc/design_spec/Makefile
		 bitbake-0.0.pc])
AC_OUTPUT
