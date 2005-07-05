AM_CPPFLAGS = -I$(top_srcdir)/include \
	      $(BBDLL_EXPORTS)

lib_LTLIBRARIES = libbitbake-0.0.la
libbitbake_0_0_la_SOURCES = data.c
libbitbake_0_0_la_CFLAGS = $(GLIB2_CFLAGS)
libbitbake_0_0_la_LIBADD = $(GLIB2_LIBS)
libbitbake_0_0_la_LDFLAGS = -version-info $(LT_CURRENT):$(LT_REVISION):$(LT_AGE) \
			    -export-dynamic

maintainer-clean-local:
	rm -f $(srcdir)/Makefile.in
