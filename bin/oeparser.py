"""
OpenEmbedded Parsers

Config file and '.oe' file parsers for the 
OpenEmbedded (http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""

import os, re, string, sys
from oe import expand, debug, fatal, inherit_os_env, getenv, setenv

class FileReader(object):
	"""Generic configuration file reader that opens a file, reads the lines,
	handles continuation lines, comments, empty lines and feed all read lines
	into the feeder method.
	"""
	def __init__(self, filename = "", d = {}):
		self.fn = filename
		self.data = d

	def setFn(self, fn):
		self.__fn = fn

	def getFn(self):
		return self.__fn

	fn = property(getFn, setFn, None, "Filename property")

	def getData(self):
		return self.__data

	def setData(self, data):
		self.__data = data

	data = property(getData, setData, None, "Data property")

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
		projectdir = os.getcwd()
		self.env['TOPDIR'] = projectdir
		self.env['OEDIR'] = os.path.join(sys.prefix, "share/oe")
		self.env['OEPATH'] = "${OEDIR}/bin:${OEDIR}:${TOPDIR}/bin:${TOPDIR}"
		inherit_os_env(1, self.env)
# matches "VAR = VALUE"
		self.config_regexp  = re.compile( r"(?P<exp>export\s*)?(?P<var>\w+)\s*(?P<colon>:)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")

# matches "include FILE"
		self.include_regexp = re.compile( r"include\s+(.+)" )
		self.cacheCheck = self.defaultChecker
		self.cacheAdd = self.defaultAdder

	def setCacheCheck(self, cachechecker):
		"""Set config cache check function to a user supplied function."""
		self.__cacheCheck = cachechecker

	def getCacheCheck(self):
		"""Return config cache check function"""
		return self.__cacheCheck

	cacheCheck = property(getCacheCheck, setCacheCheck, None, "cacheCheck property")

	def setCacheAdd(self, cacheadd):
		"""Set config cache add function to a user supplied function."""
		self.__cacheAdd = cacheadd

	def getCacheAdd(self):
		"""Return config cache add function"""
		return self.__cacheAdd

	cacheAdd = property(getCacheAdd, setCacheAdd, None, "cacheAdd property")

	def getEnv(self):
		"""Returns 'env' data"""
		return self.data["env"]

	env = property(getEnv, None, None, "Env property")

	def getEnvflags(self):
		"""Returns 'envflags' data"""
		return self.data["envflags"]

	envflags = property(getEnvflags, None, None, "Envflags property")

	def reader(self):
		"""Reimplemented reader function.  Implements [optional] config
		   cache check and add functions, and calls the FileReader reader() implementation"""
		if self.cacheCheck(self.fn):
				return
		ret = FileReader.reader(self)
		self.cacheAdd(self.fn)
		return ret

	def include(self, file, new = None):
		if self.fn == file: # prevent infinate recursion
			return 1

		if new is None:
			new = ConfigReader()
		new.fn = file
		new.cacheCheck = self.cacheCheck
		new.cacheAdd = self.cacheAdd
		ret = new.reader()
		for i in new.env.keys():
			self.env[i] = new.env[i]
		for i in new.envflags.keys():
			self.envflags[i] = new.envflags[i]
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
				debug(2, "%s:%d: including %s" % (self.fn, lineno, s)
				inherit_os_env(2, self.env)
				self.include(s, ConfigReader())
			else:
				debug(1, "%s:%d: could not import %s" % (self.fn, lineno, s))
			return

class PackageReader(ConfigReader):
	"""Reads an OpenEmbedded format package metadata file"""
	global oeconf

	def __init__(self, filename = "", d = {}):
		# regular expressions
		self.func_start_regexp = re.compile( r"(\w+)\s*\(\s*\)\s*{$" )
		self.inherit_regexp = re.compile( r"inherit\s+(.+)" )
                self.export_func_regexp = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )

		# state variables
		self.__infunc = ""
		self.__body   = []
		self.__oepath_found = 0

		ConfigReader.__init__(self, filename, d)

		# default the config var expansion to the global cfg data
		self.cfgenv = oeconf.env
		self.cfgenvflags = oeconf.envflags

	def classname(self, fn):
		(base, ext) = os.path.splitext(os.path.basename(fn))
		return base

	def getCfgEnv(self):
		"""Returns config 'env' data"""
		return self.__cfgenv

	def setCfgEnv(self, cfgenv):
		"""Sets config 'env' data"""
		self.__cfgenv = cfgenv

	cfgenv = property(getCfgEnv, setCfgEnv, None, "cfgenv property")

	def getCfgEnvFlags(self):
		"""Returns config 'envflags' data"""
		return self.__cfgenvflags

	def setCfgEnvFlags(self, cfgenvflags):
		"""Sets config 'envflags' data"""
		self.__cfgenvflags = cfgenvflags

	cfgenvflags = property(getCfgEnvFlags, setCfgEnvFlags, None, "cfgenvflags property")

	def feeder(self, lineno, s):
		"""OpenEmbedded package metadata 'feeder'"""

		if self.__infunc:
			if s == '}':
				self.__body.append('')
				self.env[self.__infunc] = string.join(self.__body, '\n')
				self.__infunc = ""
				self.__body = []
			else:
				self.__body.append(s)
			return

		m = self.func_start_regexp.match(s)
		if m:
			self.__infunc = m.group(1)
			return

		__word__ = re.compile(r"\S+")

		m = self.export_func_regexp.match(s)
		if m:
			fns = m.group(1)
			n = __word__.findall(fns)
			for f in n:
				setenv(f, "\t%s_%s\n" % (self.classname(self.fn), f), self.env)
			return

		m = self.inherit_regexp.match(s)
		if m:
			files = m.group(1)
			n = __word__.findall(files)
			for f in n:
				file = expand(expand(f, self.env), self.cfgenv)
				if file[0] != "/":
					if self.cfgenv.has_key('OEPATH'):
						self.__oepath_found = 0
						for dir in expand(self.cfgenv['OEPATH'], self.env).split(":"):
							if os.access(os.path.join(dir, "classes", file + ".oeclass"), os.R_OK):
								file = os.path.join(dir, "classes",file + ".oeclass")
								self.__oepath_found = 1
					if self.__oepath_found == 0:
						debug(1, "unable to locate %s in OEPATH"  % file)

				debug(2, "%s:%d: inheriting %s" % (self.fn, lineno, file)
				if os.access(file, os.R_OK):
#					inherit_os_env(2, self.env)
					self.include(file, PackageReader())
				else:
					debug(1, "%s:%d: could not import %s" % (self.fn, lineno, file))
			return

		return ConfigReader.feeder(self, lineno, s)

oeconf = ConfigReader()

