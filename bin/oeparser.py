"""
OpenEmbedded Parsers

Config file and '.oe' file parsers for the 
OpenEmbedded (http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

import os, re
from oe import expand, debug

class FileReader:
	"""Generic configuration file reader that opens a file, reads the lines,
	handles continuation lines, comments, empty lines and feed all read lines
	into the feeder method.
	"""
	def __init__(self, filename = ""):
		self.fn = filename
		self.data = {}

		if self.fn:
			self.reader()

	def setFn(self, fn):
		self.fn = fn

	def getFn(self):
		return self.fn

	def reader(self):
		"""Generic configuration file reader that opens a file, reads the lines,
		handles continuation lines, comments, empty lines and feed all read lines
		into the function feeder(lineno, line).
		"""
		
		f = open(self.fn,'r')
		lineno = 0
		while 1:
			lineno = lineno + 1
			s = f.readline()
			if not s: break
			s = s.strip()
			if not s: continue		# skip empty lines
			if s[0] == '#': continue	# skip comments
			while s[-1] == '\\':
				s2 = f.readline()[:-1].strip()
				s = s[:-1] + s2
			self.feeder(lineno, s)

	def feeder(self, lineno, s):
		self.data[lineno] = s

	def getData(self):
		return self.data

class ConfigReader(FileReader):
	"""Reads an OpenEmbedded format configuration file"""

	def defaultChecker(self, fn):
		"""Default config file cache check function.
		   Does nothing by default, as we dont use a cache by default."""
		return 0

	def defaultAdder(self, fn):
		"""Default config file cache add function.
		   Does nothing by default, as we dont use a cache by default."""
		return 0

	def __init__(self, filename = ""):
		if filename:
			self.fn = os.path.abspath(filename)
		else:
			self.fn = filename
		self.data = {}
		self.data["envflags"] = {}
		self.data["env"] = {}
# matches "VAR = VALUE"
		self.config_regexp  = re.compile( r"(?P<exp>export\s*)?(?P<var>\w+)\s*(?P<colon>:)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")

# matches "include FILE"
		self.include_regexp = re.compile( r"include\s+(.+)" )
		self.cacheCheck = self.defaultChecker
		self.cacheAdd = self.defaultAdder

		if self.fn:
			self.reader()

	def setCacheCheck(self, cachechecker):
		"""Set config cache check function to a user supplied function."""
		self.cacheCheck = cachechecker

	def getCacheCheck(self):
		"""Return config cache check function"""
		return self.cacheCheck

	def setCacheAdd(self, cacheadd):
		"""Set config cache add function to a user supplied function."""
		self.cacheAdd = cacheadd

	def getCacheAdd(self):
		"""Return config cache add function"""
		return self.cacheAdd

	def reader(self):
		"""Reimplemented reader function.  Implements [optional] config
		   cache check and add functions, and calls the FileReader reader() implementation"""
		if self.cacheCheck(self.fn):
				return
		ret = FileReader.reader(self)
		self.cacheAdd(self.fn)
		return ret

	def feeder(self, lineno, s):
		"""OpenEmbedded configuration file format 'feeder'"""
		m = self.config_regexp.match(s)
		if m:
			groupd = m.groupdict()
			key = groupd["var"]
			if groupd.has_key("exp") and groupd["exp"] != None:
				if not self.data["envflags"].has_key(key):
					self.data["envflags"][key] = {}
				self.data["envflags"][key]["export"] = 1
			if groupd.has_key("colon") and groupd["colon"] != None:
				self.data["env"][key] = expand(groupd["value"], self.data["env"])
			else:
				self.data["env"][key] = groupd["value"]
#			print key,groupd["value"]
			return

		m = self.include_regexp.match(s)
		if m:
			s = expand(m.group(1), self.data["env"])
			if os.access(s, os.R_OK):
#				if level==0:
#					inherit_os_env(2)
				included = ConfigReader()
				included.setFn(s)
				included.setCacheCheck(self.cacheCheck)
				included.setCacheAdd(self.cacheAdd)
				included.reader()
				for i in included.env().keys():
					self.data["env"][i] = included.env()[i]
				for i in included.envflags().keys():
					self.data["envflags"][i] = included.envflags()[i]

#				__read_config__(s, level+1)
			else:
				debug(1, "%s:%d: could not import %s" % (self.fn, lineno, s))
			return

		print lineno, s

	def getEnv(self):
		"""Returns 'env' data"""
		return self.data["env"]

	def getEnvflags(self):
		"""Returns 'envflags' data"""
		return self.data["envflags"]
