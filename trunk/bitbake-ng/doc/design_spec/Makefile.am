BUILT_SOURCES = html/index.html
xmldoc = design_spec.xml
cssfile = html.css
docbooktypes = html


html/index.html: $(xmldoc) html/docbook.css
	$(XMLLINT) --xinclude --postvalid --noout $(xmldoc)
	$(XSLTPROC) --stringparam base.dir html/ --stringparam html.stylesheet docbook.css http://docbook.sourceforge.net/release/xsl/current/html/chunk.xsl $(xmldoc)

html/docbook.css:
	install -d html
	install -m 0644 $(cssfile) $@

install-hook: install-design-spec
install-design-spec:
	install -d $(docdir)/design_spec/html
	install -m 0644 html/*.html $(docdir)/design_spec/html

CLEANFILES = html/*
