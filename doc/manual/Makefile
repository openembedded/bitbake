topdir = .
manual = $(topdir)/usermanual.xml
# types = pdf txt rtf ps xhtml html man tex texi dvi
# types = pdf txt
types = $(xmltotypes) $(htmltypes)
xmltotypes = pdf txt
htmltypes = html xhtml
htmlxsl = $(if $(filter $@,$(foreach type,$(htmltypes),$(type)-nochunks)),http://docbook.sourceforge.net/release/xsl/current/xhtml/docbook.xsl,http://docbook.sourceforge.net/release/xsl/current/$@/chunk.xsl)
htmlcssfile = docbook.css
htmlcss = $(topdir)/html.css
# htmlcssfile =
# htmlcss =
cleanfiles = $(foreach i,$(types),$(topdir)/$(i))

ifdef DEBUG
define command
	$(1)
endef
else
define command
	@echo $(2) $(3) $(4)
	@$(1) >/dev/null
endef
endif

all: $(types)

lint: $(manual) FORCE
	$(call command,xmllint --xinclude --postvalid --noout $(manual),XMLLINT $(manual))

$(types) $(foreach type,$(htmltypes),$(type)-nochunks): lint FORCE

$(foreach type,$(htmltypes),$(type)-nochunks): $(if $(htmlcss),$(htmlcss)) $(manual)
	@mkdir -p $@
ifdef htmlcss
	$(call command,install -m 0644 $(htmlcss) $@/$(htmlcssfile),CP $(htmlcss) $@/$(htmlcssfile))
endif
	$(call command,xsltproc --stringparam base.dir $@/ $(if $(htmlcssfile),--stringparam html.stylesheet $(htmlcssfile)) $(htmlxsl) $(manual) > $@/index.$(patsubst %-nochunks,%,$@),XSLTPROC $@ $(manual))

$(htmltypes): $(if $(htmlcss),$(htmlcss)) $(manual)
	@mkdir -p $@
ifdef htmlcss
	$(call command,install -m 0644 $(htmlcss) $@/$(htmlcssfile),CP $(htmlcss) $@/$(htmlcssfile))
endif
	$(call command,xsltproc --stringparam base.dir $@/ $(if $(htmlcssfile),--stringparam html.stylesheet $(htmlcssfile)) $(htmlxsl) $(manual),XSLTPROC $@ $(manual))

$(xmltotypes): $(manual)
	$(call command,xmlto --with-dblatex --extensions -o $(topdir)/$@ $@ $(manual),XMLTO $@ $(manual))

clean:
	rm -rf $(cleanfiles)

$(foreach i,$(types) $(foreach type,$(htmltypes),$(type)-nochunks),clean-$(i)):
	rm -rf $(patsubst clean-%,%,$@)

FORCE: 
