"""class for handling configuration data files

   Reads the file and obtains its metadata"""

import re, oe.data, os, sys
from oe import debug

__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>[a-zA-Z0-9\-_.]+)\s*(?P<colon>:)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")
__include_regexp__ = re.compile( r"include\s+(.+)" )

def init(data):
	if not oe.data.getVar('TOPDIR', data):
		oe.data.setVar('TOPDIR', os.getcwd(), data)
	if not oe.data.getVar('OEDIR', data):
		oe.data.setVar('OEDIR', os.path.join(sys.prefix, "share/oe"), data)
	if not oe.data.getVar('OEPATH', data):
		oe.data.setVar('OEPATH', "${OEDIR}/bin:${OEDIR}:${TOPDIR}/bin:${TOPDIR}:%s/share/oe" % sys.prefix, data)

	oe.data.setVarFlag("OEFILES", "inherit", "1", data)
	oe.data.setVarFlag("OEPATH", "inherit", "1", data)
	oe.data.setVarFlag("OEPATH", "warnlevel", "3", data)
	oe.data.setVarFlag("PATH", "inherit", "1", data)
	oe.data.setVarFlag("STAMP", "warnlevel", "3", data)
	oe.data.setVarFlag("INHERIT", "inherit", "1", data)

	# directories
	oe.data.setVarFlag("TOPDIR", "warnlevel", "3", data)
	oe.data.setVarFlag("TOPDIR", "inherit", "1", data)
	oe.data.setVarFlag("TMPDIR", "warnlevel", "3", data)
	oe.data.setVarFlag("TMPDIR", "inherit", "1", data)
	oe.data.setVarFlag("DL_DIR", "warnlevel", "3", data)
	oe.data.setVarFlag("OEDIR", "inherit", "1", data)
	oe.data.setVarFlag("OEDIR", "warnlevel", "3", data)
	oe.data.setVarFlag("STAGING_DIR", "warnlevel", "3", data)
	oe.data.setVarFlag("STAGING_BINDIR", "warnlevel", "3", data)
	oe.data.setVarFlag("STAGING_LIBDIR", "warnlevel", "3", data)
	
	# Mirrors and download:
	
	oe.data.setVarFlag("DEBIAN_MIRROR", "warnlevel", "3", data)
	oe.data.setVarFlag("SOURCEFORGE_MIRROR", "warnlevel", "3", data)
	oe.data.setVarFlag("FETCHCOMMAND", "warnlevel", "3", data)
	oe.data.setVarFlag("RESUMECOMMAND", "warnlevel", "3", data)
	
	# Architecture / Board related:
	
	oe.data.setVarFlag("DISTRO", "warnlevel", "0", data)
	oe.data.setVarFlag("BUILD_ARCH", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_ARCH", "warn", "put something like BUILD_ARCH='i686' into conf/local.conf", data)
	oe.data.setVarFlag("ARCH", "warnlevel", "3", data)
	oe.data.setVarFlag("ARCH", "warn", "put something like ARCH='arm' into conf/local.conf", data)
	oe.data.setVarFlag("BUILD_OS", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_OS", "warn", "put something like BUILD_OS='linux' into conf/local.conf", data)
	oe.data.setVarFlag("OS", "warnlevel", "3", data)
	oe.data.setVarFlag("OS", "warn", "put something like OS='linux' into conf/local.conf", data)
	oe.data.setVarFlag("MACHINE", "warnlevel", "3", data)
	oe.data.setVarFlag("MACHINE", "warn", "put something like MACHINE='ramses' into conf/local.conf", data)
	oe.data.setVarFlag("USE", "warnlevel", "2", data)
	oe.data.setVarFlag("USE", "warn", "put something like USE= with a list of features into conf/local.conf", data)
	oe.data.setVarFlag("BUILD_SYS", "warnlevel", "3", data)
	oe.data.setVarFlag("SYS", "warnlevel", "3", data)
	oe.data.setVarFlag("CROSS", "warnlevel", "3", data)
	oe.data.setVarFlag("OVERRIDES", "warnlevel", "2", data)
	oe.data.setVarFlag("ALLOWED_FLAGS", "warnlevel", "2", data)
	oe.data.setVarFlag("FULL_OPTIMIZATION", "warnlevel", "2", data)
	oe.data.setVarFlag("OPTIMIZATION", "warnlevel", "2", data)
	oe.data.setVarFlag("CPPFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("CFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("CXXFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("LDFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("CPP", "warnlevel", "3", data)
	oe.data.setVarFlag("CC", "warnlevel", "3", data)
	oe.data.setVarFlag("CXX", "warnlevel", "3", data)
	oe.data.setVarFlag("LD", "warnlevel", "3", data)
	oe.data.setVarFlag("STRIP", "warnlevel", "3", data)
	oe.data.setVarFlag("AR", "warnlevel", "3", data)
	oe.data.setVarFlag("RANLIB", "warnlevel", "3", data)
	oe.data.setVarFlag("MAKE", "warnlevel", "3", data)

	oe.data.setVarFlag("BUILD_CPPFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_CFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_CXXFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_LDFLAGS", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_CPP", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_CC", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_CXX", "warnlevel", "3", data)
	oe.data.setVarFlag("BUILD_LD", "warnlevel", "3", data)

	oe.data.setVarFlag("PKG_CONFIG_PATH", "warnlevel", "3", data)
	
	# Mandatory fields in build files
	
	oe.data.setVarFlag("DESCRIPTION", "warnlevel", "2", data)
	oe.data.setVarFlag("DEPEND", "warnlevel", "1", data)
	oe.data.setVarFlag("PROVIDES", "warnlevel", "0", data)
	oe.data.setVarFlag("SRC_URI", "warnlevel", "1", data)
	oe.data.setVarFlag("LICENSE", "warnlevel", "1", data)
	oe.data.setVarFlag("HOMEPAGE", "warnlevel", "1", data)
	
	# Use when needed
	
	oe.data.setVarFlag("PROVIDE", "warnlevel", "0", data)
	oe.data.setVarFlag("RECOMMEND", "warnlevel", "0", data)
	oe.data.setVarFlag("FOR_TARGET", "warnlevel", "0", data)
	oe.data.setVarFlag("SLOT", "warnlevel", "0", data)
	oe.data.setVarFlag("GET_URI", "warnlevel", "0", data)
	oe.data.setVarFlag("MAINTAINER", "warnlevel", "0", data)
	oe.data.setVarFlag("EXTRA_OECONF", "warnlevel", "0", data)
	oe.data.setVarFlag("EXTRA_OEMAKE", "warnlevel", "0", data)
	oe.data.setVarFlag("BUILDNAME", "inherit", "5", data)
	
	
	oe.data.setVarFlag("P", "warnlevel", "3", data)
	oe.data.setVarFlag("PN", "warnlevel", "3", data)
	oe.data.setVarFlag("PV", "warnlevel", "3", data)
	oe.data.setVarFlag("PR", "warnlevel", "3", data)
	oe.data.setVarFlag("PF", "warnlevel", "3", data)
	oe.data.setVarFlag("S", "warnlevel", "3", data)
	oe.data.setVarFlag("T", "warnlevel", "3", data)
	oe.data.setVarFlag("D", "inherit", "1", data)
	oe.data.setVarFlag("D", "warnlevel", "3", data)
	oe.data.setVarFlag("A", "warnlevel", "3", data)
	oe.data.setVarFlag("CATEGORY", "warnlevel", "2", data)
	oe.data.setVarFlag("FILESDIR", "warnlevel", "3", data)
	oe.data.setVarFlag("WORKDIR", "warnlevel", "3", data)
	
	# Package creation functions:
	
	oe.data.setVarFlag("do_clean", "dirs", [ '${TOPDIR}' ], data)
	oe.data.setVarFlag("do_mrproper", "dirs", [ '${TOPDIR}' ], data)

	oe.data.setVarFlag("do_fetch", "warnlevel", "1", data)
	oe.data.setVarFlag("do_fetch", "dirs", [ '${DL_DIR}' ], data)
	oe.data.setVarFlag("do_unpack", "warnlevel", "1", data)
	oe.data.setVarFlag("do_unpack", "dirs", [ '${WORKDIR}' ], data)
	oe.data.setVarFlag("do_patch", "dirs", [ '${WORKDIR}' ], data)
	oe.data.setVarFlag("do_compile", "warnlevel", "1", data)
	oe.data.setVarFlag("do_compile", "dirs", [ '${S}' ], data)
	oe.data.setVarFlag("do_stage", "warnlevel", "1", data)
	oe.data.setVarFlag("do_stage", "dirs", [ '${STAGING_DIR}', '${STAGING_DIR}/build/include', '${STAGING_DIR}/target/include', '${STAGING_BINDIR}', '${STAGING_LIBDIR}', '${S}' ], data)
	oe.data.setVarFlag("do_install", "warnlevel", "1", data)
	oe.data.setVarFlag("do_install", "dirs", [ '${S}' ], data)
	oe.data.setVarFlag("do_build", "warnlevel", "1", data)
	oe.data.setVarFlag("do_build", "dirs", [ '${S}' ], data)
	oe.data.setVarFlag("pkg_preinst", "warnlevel", "0", data)
	oe.data.setVarFlag("pkg_postinst", "warnlevel", "0", data)
	oe.data.setVarFlag("pkg_postrm", "warnlevel", "0", data)
	oe.data.setVarFlag("pkg_prerm", "warnlevel", "0", data)
	
	# Automatically generated, but overrideable:
	
	oe.data.setVarFlag("OEDEBUG", "inherit", "1", data)

def supports(fn):
	return localpath(fn)[-5:] == ".conf"

def localpath(fn):
	localfn = None
	try:
		localfn = oe.fetch.localpath(fn)
	except oe.MalformedUrl:
		pass

	if not localfn:
		debug(2, "obtain: malformed url: %s" % fn)
		localfn = fn
	return localfn

def obtain(fn, data = {}):
	import sys, oe
	fn = oe.data.expand(fn, data)
	localfn = oe.data.expand(localpath(fn), data)

	if localfn != fn:
		dldir = oe.data.getVar('DL_DIR', data, 1)
		if not dldir:
			debug(1, "obtain: DL_DIR not defined")
			return localfn
		oe.mkdirhier(dldir)
		try:
			oe.fetch.init([fn])
		except oe.fetch.NoMethodError:
			(type, value, traceback) = sys.exc_info()
			debug(1, "obtain: no method: %s" % value)
			return localfn
	
		try:
			oe.fetch.go(data)
		except oe.fetch.MissingParameterError:
			(type, value, traceback) = sys.exc_info()
			debug(1, "obtain: missing parameters: %s" % value)
			return localfn
		except oe.fetch.FetchError:
			(type, value, traceback) = sys.exc_info()
			debug(1, "obtain: failed: %s" % value)
			return localfn
	return localfn


def include(oldfn, fn, data = {}):
	if oldfn == fn: # prevent infinate recursion
		return None

	import oe
	fn = oe.data.expand(fn, data)
	oldfn = oe.data.expand(oldfn, data)

	from oe.parse import handle
	try:
		debug(1, "include: handle(%s, data)" % fn)
		ret = handle(fn, data)
	except IOError:
		debug(1, "include: %s not found" % fn)

def handle(fn, data = {}):
	init(data)
	oe.data.inheritFromOS(1, data)
	fn = obtain(fn, data)
	oepath = ['.']
	if not os.path.isabs(fn):
		f = None
		voepath = oe.data.getVar("OEPATH", data)
		if voepath:
			oepath += voepath.split(":")
		for p in oepath:
			p = oe.data.expand(p, data)
			if os.access(os.path.join(p, fn), os.R_OK):
				f = open(os.path.join(p, fn), 'r')
				break
		if f is None:
			raise IOError("file not found")
	else:
		f = open(fn,'r')
	lineno = 0
	while 1:
		lineno = lineno + 1
		s = f.readline()
		if not s: break
		w = s.strip()
		if not w: continue		# skip empty lines
		s = s.rstrip()
		if s[0] == '#': continue	# skip comments
		while s[-1] == '\\':
			s2 = f.readline()[:-1].strip()
			s = s[:-1] + s2
		feeder(lineno, s, fn, data)
	return data

def feeder(lineno, s, fn, data = {}):
	m = __config_regexp__.match(s)
	if m:
		groupd = m.groupdict()
		key = groupd["var"]
		if groupd.has_key("exp") and groupd["exp"] != None:
			oe.data.setVarFlag(key, "export", 1, data)
		if groupd.has_key("colon") and groupd["colon"] != None:
			val = oe.data.expand(groupd["value"], data)
		else:
			val = groupd["value"]
		oe.data.setVar(key, val, data)
		return

	m = __include_regexp__.match(s)
	if m:
		s = oe.data.expand(m.group(1), data)
		debug(2, "%s:%d: including %s" % (fn, lineno, s))
		oe.data.inheritFromOS(2, data)
		include(fn, s, data)
		return

# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
