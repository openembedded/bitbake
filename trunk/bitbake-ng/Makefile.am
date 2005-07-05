SUBDIRS = include src tests doc

ACLOCAL_AMFLAGS = -I m4/internal -I m4/external
AUTOMAKE_OPTIONS = foreign 1.6

MAINT_CLEAN_FILES_AUX = config.guess config.sub depcomp \
			install-sh missing ltmain.sh \
			compile mkinstalldirs
MAINT_CLEAN_FILES_TOP = config.h.in aclocal.m4 \
			configure Makefile.in stamp-h.in
MAINT_CLEAN_FILES = $(foreach f,$(MAINT_CLEAN_FILES_TOP),$(top_srcdir)/$(f) $(top_srcdir)/$(f)\~) \
		    $(foreach f,$(MAINT_CLEAN_FILES_AUX),$(auxdir)/$(f) $(auxdir)/$(f)\~)

maintainer-clean-local:
	rm -f $(MAINT_CLEAN_FILES)

.PHONY: test
test:
	@$(MAKE) -C tests $@
