#!/usr/bin/python
"""
OpenEmbedded 'Fetch' implementations

Classes for obtaining upstream sources for the
OpenEmbedded (http://openembedded.org) build infrastructure.

NOTE that it requires Python 2.x due to its use of static methods.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

import os, re, string
import oe

class FetchError(Exception):
	"""Exception raised when a download fails"""

class NoMethodError(Exception):
	"""Exception raised when there is no method to obtain a supplied url or set of urls"""

class MissingParameterError(Exception):
	"""Exception raised when a fetch method is missing a critical parameter in the url"""

methods = []

def init(urls = [], d = oe.data.init()):
	for m in methods:
		m.urls = []

	for u in urls:
		for m in methods:
			m.data = d
			if m.supports(u):
				m.urls.append(u)
	
def go(d = oe.data.init()):
	"""Fetch all urls"""
	for m in methods:
		if m.urls:
			m.go(d)

def localpaths(d):
	"""Return a list of the local filenames, assuming successful fetch"""
	local = []
	for m in methods:
		for u in m.urls:
			local.append(m.localpath(u, d))
	return local

def localpath(url, d = oe.data.init()):
	for m in methods:
		if m.supports(url):
			return m.localpath(url, d)
	return url 

class Fetch(object):
	"""Base class for 'fetch'ing data"""
	
	def __init__(self, urls = []):
		self.urls = []
		for url in urls:
			if self.supports(oe.decodeurl(url)) is 1:
				self.urls.append(url)

	def supports(url):
		"""Check to see if this fetch class supports a given url.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		return 0
	supports = staticmethod(supports)

	def localpath(url, d = oe.data.init()):
		"""Return the local filename of a given url assuming a successful fetch.
		"""
		return url
	localpath = staticmethod(localpath)

	def setUrls(self, urls):
		self.__urls = urls

	def getUrls(self):
		return self.__urls

	urls = property(getUrls, setUrls, None, "Urls property")

	def setData(self, data):
		self.__data = data

	def getData(self):
		return self.__data

	data = property(getData, setData, None, "Data property")

	def go(self, urls = []):
		"""Fetch urls"""
		raise NoMethodError("Missing implementation for url")

class Wget(Fetch):
	"""Class to fetch urls via 'wget'"""
	def supports(url):
		"""Check to see if a given url can be fetched using wget.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(url))
		return type in ['http','https','ftp']
	supports = staticmethod(supports)

	def localpath(url, d):
		# strip off parameters
		(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(url))
		if parm.has_key("localpath"):
			# if user overrides local path, use it.
			return parm["localpath"]
		url = oe.encodeurl([type, host, path, user, pswd, {}])
		return os.path.join(oe.data.getVar("DL_DIR", d), os.path.basename(url))
	localpath = staticmethod(localpath)

	def go(self, d = oe.data.init(), urls = []):
		"""Fetch urls"""
		if not urls:
			urls = self.urls

		from copy import deepcopy
		localdata = deepcopy(d)
		oe.data.setVar('OVERRIDES', "wget:%s" % oe.data.getVar('OVERRIDES', localdata), localdata)
		oe.data.update_data(localdata)

		for loc in urls:
			(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(loc))
			myfile = os.path.basename(path)
			dlfile = self.localpath(loc, d)
			dlfile = oe.data.expand(dlfile, localdata)
			md5file = "%s.md5" % dlfile

			if os.path.exists(md5file):
				# complete, nothing to see here..
				continue

			if os.path.exists(dlfile):
				# file exists, but we didnt complete it.. trying again..
				myfetch = oe.data.expand(oe.data.getVar("RESUMECOMMAND", localdata), localdata)
			else:
				myfetch = oe.data.expand(oe.data.getVar("FETCHCOMMAND", localdata), localdata)

			oe.note("fetch " +loc)
			myfetch = myfetch.replace("${URI}",oe.encodeurl([type, host, path, user, pswd, {}]))
			myfetch = myfetch.replace("${FILE}",myfile)
			oe.debug(2,myfetch)
			myret = os.system(myfetch)
			if myret != 0:
				raise FetchError(myfile)

			# supposedly complete.. write out md5sum
			if oe.which(oe.data.getVar('PATH', d, 1), 'md5sum'):
				md5pipe = os.popen('md5sum %s' % dlfile)
				md5 = md5pipe.readline().split()[0]
				md5pipe.close()
				md5out = file(md5file, 'w')
				md5out.write(md5)
				md5out.close()
			else:
				md5out = file(md5file, 'w')
				md5out.write("")
				md5out.close()
		del localdata
						

methods.append(Wget())

class Cvs(Fetch):
	"""Class to fetch a module or modules from cvs repositories"""
	def supports(url):
		"""Check to see if a given url can be fetched with cvs.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(url))
		return type in ['cvs', 'pserver']
	supports = staticmethod(supports)

	def localpath(url, d):
		(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(url))
		if parm.has_key("localpath"):
			# if user overrides local path, use it.
			return parm["localpath"]

		if not parm.has_key("module"):
			raise MissingParameterError("cvs method needs a 'module' parameter")
		else:
			module = parm["module"]
		if parm.has_key('tag'):
			tag = parm['tag']
		else:
			tag = ""
		if parm.has_key('date'):
			date = parm['date']
		else:
			date = ""

		return os.path.join(oe.data.getVar("DL_DIR", d, 1),oe.data.expand('%s_%s_%s_%s.tar.gz' % (string.replace(module, '/', '.'), host, tag, date), d))
	localpath = staticmethod(localpath)

	def go(self, d = oe.data.init(), urls = []):
		"""Fetch urls"""
		if not urls:
			urls = self.urls

		from copy import deepcopy
		localdata = deepcopy(d)
		oe.data.setVar('OVERRIDES', "cvs:%s" % oe.data.getVar('OVERRIDES', localdata), localdata)
		oe.data.update_data(localdata)

		for loc in urls:
			(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(loc))
			if not parm.has_key("module"):
				raise MissingParameterError("cvs method needs a 'module' parameter")
			else:
				module = parm["module"]

			dlfile = self.localpath(loc, localdata)
			dldir = oe.data.getVar('DL_DIR', localdata, 1)
			# if local path contains the cvs
			# module, consider the dir above it to be the
			# download directory
#			pos = dlfile.find(module)
#			if pos:
#				dldir = dlfile[:pos]
#			else:
#				dldir = os.path.dirname(dlfile)

			# setup cvs options
			options = []
			if parm.has_key('tag'):
				tag = parm['tag']
			else:
				tag = ""

			if parm.has_key('date'):
				date = parm['date']
			else:
				date = ""

			if parm.has_key("method"):
				method = parm["method"]
			else:
				method = "pserver"

			tarfn = oe.data.expand('%s_%s_%s_%s.tar.gz' % (string.replace(module, '/', '.'), host, tag, date), localdata)
			oe.data.setVar('TARFILES', dlfile, localdata)
			oe.data.setVar('TARFN', tarfn, localdata)

			if os.access(os.path.join(dldir, tarfn), os.R_OK):
				oe.debug(1, "%s already exists, skipping cvs checkout." % tarfn)
				return

			if date:
				options.append("-D %s" % date)
			if tag:
				options.append("-r %s" % tag)

			olddir = os.path.abspath(os.getcwd())
			os.chdir(oe.data.expand(dldir, localdata))

			# setup cvsroot
			cvsroot = ":" + method + ":" + user
			if pswd:
				cvsroot += ":" + pswd
			cvsroot += "@" + host + ":" + path

			oe.data.setVar('CVSROOT', cvsroot, localdata)
			oe.data.setVar('CVSCOOPTS', string.join(options), localdata)
			oe.data.setVar('CVSMODULE', module, localdata)
			cvscmd = oe.data.getVar('FETCHCOMMAND', localdata, 1)

			# create temp directory
	 		oe.debug(2, "Fetch: creating temporary directory")
			oe.mkdirhier(oe.data.expand('${WORKDIR}', localdata))
			oe.data.setVar('TMPBASE', oe.data.expand('${WORKDIR}/oecvs.XXXXXX', localdata), localdata)
			tmppipe = os.popen(oe.data.getVar('MKTEMPDIRCMD', localdata, 1) or "false")
			tmpfile = tmppipe.readline().strip()
			if not tmpfile:
				oe.error("Fetch: unable to create temporary directory.. make sure 'mktemp' is in the PATH.")
				raise FetchError(module)

			# check out sources there
			os.chdir(tmpfile)
			oe.note("Fetch " + loc)
			oe.debug(1, "Running %s" % cvscmd)
			myret = os.system(cvscmd)
			if myret != 0:
				try:
					os.rmdir(tmpfile)
				except OSError:
					pass
				raise FetchError(module)

			os.chdir(os.path.join(tmpfile, os.path.dirname(module)))
			# tar them up to a defined filename
			myret = os.system("tar -czvf %s %s" % (os.path.join(dldir,tarfn), os.path.basename(module)))
			if myret != 0:
				try:
					os.unlink(tarfn)
				except OSError:
					pass
			# cleanup
			os.system('rm -rf %s' % tmpfile)
			os.chdir(olddir)
		del localdata

methods.append(Cvs())

class Bk(Fetch):
	def supports(url):
		"""Check to see if a given url can be fetched via bitkeeper.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(url))
		return type in ['bk']
	supports = staticmethod(supports)

methods.append(Bk())

class Local(Fetch):
	def supports(url):
		"""Check to see if a given url can be fetched in the local filesystem.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = oe.decodeurl(oe.expand(url))
		return type in ['file','patch']
	supports = staticmethod(supports)

	def localpath(url, d):
		"""Return the local filename of a given url assuming a successful fetch.
		"""
		return url.split("://")[1]
	localpath = staticmethod(localpath)

	def go(self, urls = []):
		"""Fetch urls (no-op for Local method)"""
		# no need to fetch local files, we'll deal with them in place.
		return 1

methods.append(Local())
