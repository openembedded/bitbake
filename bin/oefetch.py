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

def fetch_with_wget(loc,mydigests, type,host,path,user,pswd):
	myfile = os.path.basename(path)
	dlfile = os.path.join(getenv("DL_DIR"), myfile)

	try:
		mystat = os.stat(dlfile)
		if mydigests.has_key(myfile):
			# if we have the digest file, we know the final size and can resume the download.
			if mystat[ST_SIZE] < mydigests[myfile]["size"]:
				fetched = 1
			else:
				# we already have it downloaded, skip
				# if our file is bigger than the recorded size, digestcheck should catch it.
				fetched = 2
		else:
			# we don't have the digest file, but the file exists.  Assume it is fully downloaded.
			fetched = 2
	except (OSError,IOError),e:
		fetched = 0

	# we either need to resume or start the download
	if fetched != 2:
		# you can't use "continue" when you're inside a "try" block
		if fetched == 1:
			# resume mode:
			note("Resuming download...")
			myfetch = getenv("FETCHCOMMAND")
		else:
			# normal mode:
			myfetch = getenv("RESUMECOMMAND")
		note("fetch " +loc)
		myfetch = myfetch.replace("${URI}",loc)
		myfetch = myfetch.replace("${FILE}",myfile)
		debug(2,myfetch)
		myret = os.system(myfetch)

		if mydigests.has_key(myfile):
			print "0"
			try:
				mystat = os.stat(dlfile)
				print "1", myret
				# no exception?  file exists. let digestcheck() report
				# an appropriately for size or md5 errors
				if myret and (mystat[ST_SIZE] < mydigests[myfile]["size"]):
					print "2"
					# Fetch failed... Try the next one... Kill 404 files though.
					if (mystat[ST_SIZE]<100000) and (len(myfile)>4) and not ((myfile[-5:]==".html") or (myfile[-4:]==".htm")):
						print "3"
						html404 = re.compile("<title>.*(not found|404).*</title>",re.I|re.M)
						try:
							if html404.search(open(dlfile).read()):
								try:
									os.unlink(dlfile)
									note("deleting invalid distfile (improper 404 redirect from server)")
								except:
									pass
						except:
							pass
					print "What to do?"
					return 1
				return 2
			except (OSError,IOError),e:
				fetched = 0
		else:
			if not myret:
				return 2

	if fetched != 2:
		error("Couldn't download "+ myfile)
		return 0
	return fetched


def fetch(urls):
	digestfn  = env["FILESDIR"]+"/digest-"+env["PF"]
	mydigests = {}
	if os.path.exists(digestfn):
		debug(3, "checking digest "+ digestfn)
		myfile    = open(digestfn,"r")
		mylines   = myfile.readlines()
		for x in mylines:
			myline = string.split(x)
			if len(myline)<4:
				# invalid line
				oe.fatal("The digest %s appears to be corrupt" % digestfn);
			try:
				mydigests[myline[2]] = {"md5" : myline[1], "size" : string.atol(myline[3])}
			except ValueError:
				oe.fatal("The digest %s appears to be corrupt" % digestfn);

	for loc in urls.split():
		debug(2,"fetching %s" % loc)
		(type, host, path, user, pswd, parm) = decodeurl(expand(loc))

		if type in ['http','https','ftp']:
			fetched = fetch_with_wget(loc,mydigests, type,host,path,user,pswd)
		elif type in ['cvs', 'pserver']:
			fetched = fetch_with_cvs(mydigests, type,host,path,user,pswd,parm)
		elif type == 'bk':
			fetched = fetch_with_bk(mydigests, type,host,path,user,pswd,parm)
		else:
			fatal("can't fetch with method '%s'" % type)
		if fetched != 2:
			error("Couldn't download "+ loc)
			return 0

	return 1

class FetchUrls:
	__methods = { "Wget" : None, "Cvs" : None, "Bk" : None }

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
			else:
				__supported = 0
				print "Warning: no fetch method for %s" % url
	
	def go(self):
		for method in self.__methods.keys():
			if self.__methods[method] is None:
				continue
			print "Obtaining urls via %s method..." % method
			self.__methods[method].go()

class Fetch(object):
	def __init__(self, urls = []):
		self.urls = []
		for url in urls:
			if self.supports(decodeurl(url)) is 1:
				self.urls.append(url)

	def supports(decoded = []):
		return 1
	supports = staticmethod(supports)

	def addUrl(self, url):
		self.urls.append(url)

	def go(self, urls = []):
		if not urls:
			urls = self.urls
		fatal("No implementation to obtain urls: %s" % urls)
		return 1

class Wget(Fetch):
	def supports(decoded = []):
		(type, host, path, user, pswd, parm) = decoded
		if type in ['http','https','ftp']:
			return 1
		else:
			return 0
	supports = staticmethod(supports)

	def go(self, urls = []):
		if not urls:
			urls = self.urls
		for loc in urls:
			(type, host, path, user, pswd, parm) = decodeurl(expand(loc))
			fetched = fetch_with_wget(loc,{},type,host,path,user,pswd)
		return 1

class Cvs(Fetch):
	def supports(decoded = []):
		(type, host, path, user, pswd, parm) = decoded
		if type in ['cvs', 'pserver']:
			return 1
		else:
			return 0
	supports = staticmethod(supports)

class Bk(Fetch):
	def supports(decoded = []):
		(type, host, path, user, pswd, parm) = decoded
		if type in ['bk']:
			return 1
		else:
		 	return 0
	supports = staticmethod(supports)
