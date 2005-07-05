AM_CPPFLAGS = -I$(top_srcdir)/include \
	      $(BBDLL_EXPORTS)
AM_LDFLAGS = -L$(top_srcdir)/src

.PHONY: test
if BB_TESTS
noinst_PROGRAMS = check_bitbake_data
check_bitbake_data_SOURCES = check_bitbake_data.c
check_bitbake_data_CFLAGS = $(GLIB2_CFLAGS) $(CHECK_CFLAGS)
check_bitbake_data_LDADD = $(GLIB2_LIBS) $(CHECK_LIBS) -lbitbake-0.0

test:
	@./check_bitbake_data
else
test:
endif

maintainer-clean-local:
	rm -f $(srcdir)/Makefile.in
