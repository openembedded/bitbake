SUBDIRS = design_spec

MOSTLYCLEANFILES = $(DX_CLEANFILES)
EXTRA_DIST = $(DX_CONFIG)

include doxygen.am

all: doxygen-doc

maintainer-clean-local:
	rm -f $(srcdir)/Makefile.in
