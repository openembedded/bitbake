"""
OpenEmbedded 'Fetch' implementations

Classes for obtaining upstream sources for the
OpenEmbedded (http://openembedded.org) build infrastructure.

NOTE that it requires Python 2.x due to its use of static methods.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

import os, re
from oe import *

class FetchUrls:
	__methods = { "Wget" : None, "Cvs" : None, "Bk" : None, "Local" : None }

	def init(self, urls = []):
		for url in urls:
			__supported = 1
			if Wget.supports(decodeurl(url)):
				if self.__methods["Wget"] is None:
					self.__methods["Wget"] = Wget()
				self.__methods["Wget"].addUrl(url) 
			elif Cvs.supports(decodeurl(url)):
				if self.__methods["Cvs"] is None:
					self.__methods["Cvs"] = Cvs()
				self.__methods["Cvs"].addUrl(url) 
			elif Bk.supports(decodeurl(url)):
				if self.__methods["Bk"] is None:
					self.__methods["Bk"] = Bk()
				self.__methods["Bk"].addUrl(url) 
			elif Local.supports(decodeurl(url)):
				if self.__methods["Local"] is None:
					self.__methods["Local"] = Local()
				self.__methods["Local"].addUrl(url) 
			else:
				__supported = 0
				fatal("Warning: no fetch method for %s" % url)
	
	def go(self):
		for method in self.__methods.keys():
			if self.__methods[method] is None:
				continue
			debug(2,"Obtaining urls via %s method..." % method)
			self.__methods[method].go()

class Fetch(object):
	def __init__(self, urls = []):
		self.urls = []
		for url in urls:
			if self.supports(decodeurl(url)) is 1:
				self.urls.append(url)

	def supports(decoded = []):
		"""Check to see if this fetch class supports a given url.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		return 1
	supports = staticmethod(supports)

	def localpath(url):
		"""Return the local filename of a given url assuming a successful fetch.
		"""
		return url
	localpath = staticmethod(localpath)

	def addUrl(self, url):
		self.urls.append(url)

	def go(self, urls = []):
		if not urls:
			urls = self.urls
		fatal("No implementation to obtain urls: %s" % urls)
		return 1

class Wget(Fetch):
	def supports(decoded = []):
		"""Check to see if a given url can be fetched using wget.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = decoded
		if type in ['http','https','ftp']:
			return 1
		else:
			return 0
	supports = staticmethod(supports)

	def localpath(url):
		return os.path.join(getenv("DL_DIR"), os.path.basename(url))
	localpath = staticmethod(localpath)

	def go(self, urls = []):
		if not urls:
			urls = self.urls

		for loc in urls:
			(type, host, path, user, pswd, parm) = decodeurl(expand(loc))
			myfile = os.path.basename(path)
			if parm.has_key("localpath"):
				# if user overrides local path, use it.
				dlfile = parm["localpath"]
			else:
				dlfile = self.localpath(loc)

			myfetch = getenv("RESUMECOMMAND")
			note("fetch " +loc)
			myfetch = myfetch.replace("${URI}",loc)
			myfetch = myfetch.replace("${FILE}",myfile)
			debug(2,myfetch)
			myret = os.system(myfetch)
			if not myret:
				error("Couldn't download "+ myfile)
				return 0
		return 1

class Cvs(Fetch):
	def supports(decoded = []):
		"""Check to see if a given url can be fetched with cvs.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = decoded
		if type in ['cvs', 'pserver']:
			return 1
		else:
			return 0
	supports = staticmethod(supports)

class Bk(Fetch):
	def supports(decoded = []):
		"""Check to see if a given url can be fetched via bitkeeper.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = decoded
		if type in ['bk']:
			return 1
		else:
		 	return 0
	supports = staticmethod(supports)

class Local(Fetch):
	def supports(decoded = []):
		"""Check to see if a given url can be fetched in the local filesystem.
		   Expects supplied url in list form, as outputted by oe.decodeurl().
		"""
		(type, host, path, user, pswd, parm) = decoded
		if type in ['file']:
			return 1
		else:
			return 0
	supports = staticmethod(supports)

	def localpath(url):
		"""Return the local filename of a given url assuming a successful fetch.
		"""
		return url[7:]
	localpath = staticmethod(localpath)
