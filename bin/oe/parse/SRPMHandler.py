"""class for handling .src.rpm files

   Accesses the file and obtains its metadata"""

import re, oe, string, os, sys
import oe
import oe.fetch
from oe import debug, data, fetch, fatal
from oe.parse.ConfHandler import init

_srpm_vartranslate = {
"NAME": "PN",
"VERSION": "PV",
"RELEASE": "PR",
}

def supports(fn, d):
	return fn[-8:] == ".src.rpm"

def handle(fn, d = {}, include = 0):
	init(d)
	oepath = ['.']
	if not os.path.isabs(fn):
		f = None
		voepath = data.getVar("OEPATH", d)
		if voepath:
			oepath += voepath.split(":")
		for p in oepath:
			p = data.expand(p, d)
			if os.access(os.path.join(p, fn), os.R_OK):
				f = open(os.path.join(p, fn), 'r')
		if f is None:
			raise IOError("file not found")
	else:
		f = open(fn,'r')

	srpm_vars = os.popen('rpm --querytags').read().split('\n')
	for v in srpm_vars:
		if v in _srpm_vartranslate:
			var = _srpm_vartranslate[v]
		else:
			var = v
		querycmd = 'rpm -qp --qf \'%%{%s}\' %s 2>/dev/null' % (v, fn)
		value = os.popen(querycmd).read().strip()
		if value == "(none)":
			value = None
		if value:
			data.setVar(var, value, d)

	data.setVar("SRPMFILE", fn, d)

	inheritclasses = data.getVar("INHERIT", d)
	if inheritclasses:
		i = inheritclasses.split()
	else:
		i = []

	if not "base_srpm" in i:
		i[0:0] = ["base_srpm"]

	for c in i:
		oe.parse.handle('classes/%s.oeclass' % c, d)

	set_automatic_vars(fn, d, include)
	set_additional_vars(fn, d, include)
	data.update_data(d)
	return d

def set_automatic_vars(file, d, include):
	"""Deduce per-package environment variables"""

	debug(2, "setting automatic vars")

	data.setVar('CATEGORY', 'srpm', d)
	data.setVar('P', '${PN}-${PV}', d)
	data.setVar('PF', '${P}-${PR}', d)

	for s in ['${TOPDIR}/${CATEGORY}/${PF}', 
		  '${TOPDIR}/${CATEGORY}/${PN}-${PV}',
		  '${TOPDIR}/${CATEGORY}/files',
		  '${TOPDIR}/${CATEGORY}']:
		s = data.expand(s, d)
		if os.access(s, os.R_OK):
			data.setVar('FILESDIR', s, d)
			break

	data.setVar('WORKDIR', '${TMPDIR}/${CATEGORY}/${PF}', d)
	data.setVar('T', '${WORKDIR}/temp', d)
	data.setVar('D', '${WORKDIR}/image', d)
	if not data.getVar('S', d):
		data.setVar('S', '${WORKDIR}/${P}', d)
	data.setVar('SLOT', '0', d)

def set_additional_vars(file, d, include):
	"""Deduce rest of variables, e.g. ${A} out of ${SRC_URI}"""

	debug(2,"set_additional_vars")

	src_uri = data.getVar('SRC_URI', d)
	if not src_uri:
		return
	src_uri = data.expand(src_uri, d)

	a = data.getVar('A', d)
	if a:
		a = data.expand(a, d).split()
	else:
		a = []

	from oe import fetch
	try:
		fetch.init(src_uri.split())
	except fetch.NoMethodError:
		pass

	a += fetch.localpaths(d)
	del fetch
	data.setVar('A', string.join(a), d)


# Add us to the handlers list
from oe.parse import handlers
handlers.append({'supports': supports, 'handle': handle, 'init': init})
del handlers
