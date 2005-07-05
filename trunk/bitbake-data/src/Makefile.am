AM_CPPFLAGS = -I$(top_srcdir)/include \
	      $(BBDATA_DLL_EXPORTS)

lib_LTLIBRARIES = libbitbake-data-@LT_RELEASE@.la
libbitbake_data_@LT_RELEASE@_la_SOURCES = backend-sqlite3.c
libbitbake_data_@LT_RELEASE@_la_CFLAGS = $(GLIB2_CFLAGS) $(SQLITE3_CFLAGS) \
				-DLOCALSTATEDIR="\"@localstatedir@\""
libbitbake_data_@LT_RELEASE@_la_LIBADD = $(GLIB2_LIBS) $(SQLITE3_LIBS)
libbitbake_data_@LT_RELEASE@_la_LDFLAGS = -version-info $(LT_CURRENT):$(LT_REVISION):$(LT_AGE) \
				 -export-dynamic

maintainer-clean-local:
	rm -f $(srcdir)/Makefile.in
