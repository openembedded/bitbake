<?xml version='1.0'?>
<xsl:stylesheet xmlns:xsl="http://www.w3.org/1999/XSL/Transform" xmlns="http://www.w3.org/1999/xhtml" xmlns:fo="http://www.w3.org/1999/XSL/Format" version="1.0">

  <xsl:import href="http://docbook.sourceforge.net/release/xsl/current/xhtml/docbook.xsl" />

  <xsl:param name="html.stylesheet" select="'user-manual-style.css'" />
  <xsl:param name="chapter.autolabel" select="1" />
<!--  <xsl:param name="appendix.autolabel" select="A" /> -->
  <xsl:param name="section.autolabel" select="1" />
  <xsl:param name="section.label.includes.component.label" select="1" />
  <xsl:param name="appendix.autolabel">A</xsl:param>

<!--  <xsl:param name="generate.toc" select="'article nop'"></xsl:param>  -->

</xsl:stylesheet>
