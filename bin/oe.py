"""
OpenEmbedded Build System Python Library

Copyright: (c) 2003 by Holger Schurig

Part of this code has been shamelessly stolen from Gentoo's portage.py.
This source had GPL-2 as license, so the same goes for this file.

Please visit http://www.openembedded.org/phpwiki/ for more info.

Try "pydoc ./oe.py" to get some nice output.
"""

import sys,os,string,types,re

#projectdir = os.path.dirname(os.path.dirname(os.path.abspath(sys.argv[0])))
projectdir = os.getcwd()
env = {}

class VarExpandError(Exception):
	pass



#######################################################################
#######################################################################
#
# SECTION: Debug
#
# PURPOSE: little functions to make yourself known
#
#######################################################################
#######################################################################

debug_prepend = ''


def debug(lvl, *args):
	if env.has_key('OEDEBUG') and (env['OEDEBUG'] >= str(lvl)):
		print debug_prepend + 'DEBUG:', string.join(args, '')

def note(*args):
	print debug_prepend + 'NOTE:', string.join(args, '')

def error(*args):
	print debug_prepend + 'ERROR:', string.join(args, '')

def fatal(*args):
	print debug_prepend + 'ERROR:', string.join(args, '')
	sys.exit(1)


#######################################################################
#######################################################################
#
# SECTION: File
#
# PURPOSE: Basic file and directory tree related functions
#
#######################################################################
#######################################################################

def mkdirhier(dir):
	"""Create a directory like 'mkdir -p', but does not complain if
	directory already exists like os.makedirs
	"""

	debug(3, "mkdirhier(%s)" % dir)
	try:
		os.makedirs(dir)
		debug(2, "created " + dir)
	except OSError, e:
		if e.errno != 17: raise e


#######################################################################

def movefile(src,dest,newmtime=None,sstat=None):
	"""Moves a file from src to dest, preserving all permissions and
	attributes; mtime will be preserved even when moving across
	filesystems.  Returns true on success and false on failure. Move is
	atomic.
	"""

	#print "movefile("+src+","+dest+","+str(newmtime)+","+str(sstat)+")"
	try:
		if not sstat:
			sstat=os.lstat(src)
	except Exception, e:
		print "!!! Stating source file failed... movefile()"
		print "!!!",e
		return None

	destexists=1
	try:
		dstat=os.lstat(dest)
	except:
		dstat=os.lstat(os.path.dirname(dest))
		destexists=0

	if destexists:
		if S_ISLNK(dstat[ST_MODE]):
			try:
				os.unlink(dest)
				destexists=0
			except Exception, e:
				pass

	if S_ISLNK(sstat[ST_MODE]):
		try:
			target=os.readlink(src)
			if destexists and not S_ISDIR(dstat[ST_MODE]):
				os.unlink(dest)
			os.symlink(target,dest)
			missingos.lchown(dest,sstat[ST_UID],sstat[ST_GID])
			return os.lstat(dest)
		except Exception, e:
			print "!!! failed to properly create symlink:"
			print "!!!",dest,"->",target
			print "!!!",e
			return None

	renamefailed=1
	if sstat[ST_DEV]==dstat[ST_DEV]:
		try:
			ret=os.rename(src,dest)
			renamefailed=0
		except Exception, e:
			import errno
			if e[0]!=errno.EXDEV:
				# Some random error.
				print "!!! Failed to move",src,"to",dest
				print "!!!",e
				return None
			# Invalid cross-device-link 'bind' mounted or actually Cross-Device

	if renamefailed:
		didcopy=0
		if S_ISREG(sstat[ST_MODE]):
			try: # For safety copy then move it over.
				shutil.copyfile(src,dest+"#new")
				os.rename(dest+"#new",dest)
				didcopy=1
			except Exception, e:
				print '!!! copy',src,'->',dest,'failed.'
				print "!!!",e
				return None
		else:
			#we don't yet handle special, so we need to fall back to /bin/mv
			a=getstatusoutput("/bin/mv -f "+"'"+src+"' '"+dest+"'")
			if a[0]!=0:
				print "!!! Failed to move special file:"
				print "!!! '"+src+"' to '"+dest+"'"
				print "!!!",a
				return None # failure
		try:
			if didcopy:
				missingos.lchown(dest,sstat[ST_UID],sstat[ST_GID])
				os.chmod(dest, S_IMODE(sstat[ST_MODE])) # Sticky is reset on chown
				os.unlink(src)
		except Exception, e:
			print "!!! Failed to chown/chmod/unlink in movefile()"
			print "!!!",dest
			print "!!!",e
			return None

	if newmtime:
		os.utime(dest,(newmtime,newmtime))
	else:
		os.utime(dest, (sstat[ST_ATIME], sstat[ST_MTIME]))
		newmtime=sstat[ST_MTIME]
	return newmtime



#######################################################################
#######################################################################
#
# SECTION: Download
#
# PURPOSE: Download via HTTP, FTP, CVS, BITKEEPER, handling of MD5-signatures
#          and mirrors
#
#######################################################################
#######################################################################

def decodeurl(url):
	"""Decodes an URL into the tokens (scheme, network location, path,
	user, password, parameters). 

	>>> decodeurl("http://www.google.com/index.html")
	('http', 'www.google.com', '/index.html', '', '', {})

	CVS url with username, host and cvsroot. The cvs module to check out is in the
	parameters:

	>>> decodeurl("cvs://anoncvs@cvs.handhelds.org/cvs;module=familiar/dist/ipkg")
	('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', '', {'module': 'familiar/dist/ipkg'})

	Dito, but this time the username has a password part. And we also request a special tag
	to check out.

	>>> decodeurl("cvs://anoncvs:anonymous@cvs.handhelds.org/cvs;module=familiar/dist/ipkg;tag=V0-99-81")
	('cvs', 'cvs.handhelds.org', '/cvs', 'anoncvs', 'anonymous', {'tag': 'V0-99-81', 'module': 'familiar/dist/ipkg'})
	"""

	#debug(3, "decodeurl('%s')" % url)
	m = re.compile('([^:]*):/*(.+@)?([^/]+)(/[^;]+);?(.*)').match(url)
	if not m:
		fatal("Malformed URL '%s'" % url)

	type = m.group(1)
	host = m.group(3)
	path = m.group(4)
	user = m.group(2)
	parm = m.group(5)
	#print "type:", type
	#print "host:", host
	#print "path:", path
	#print "parm:", parm
	if user:
		m = re.compile('([^:]+)(:?(.*))@').match(user)
		if m:
			user = m.group(1)
			pswd = m.group(3)
	else:
		user = ''
		pswd = ''
	#print "user:", user
	#print "pswd:", pswd
	#print
	p = {}
	if parm:
		for s in parm.split(';'):
			s1,s2 = s.split('=')
			p[s1] = s2
			
	return (type, host, path, user, pswd, p)
		

#######################################################################

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


#######################################################################

def fetch_with_cvs(mydigests, type,host,path,user,pswd,parm):
	fatal('fetch via CVS not yet implemented')


#######################################################################

def fetch_with_bk(mydigests, type,host,path,user,pswd,parm):
	fatal('fetch via BitKeeper not yet implemented')


#######################################################################

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
		

#######################################################################
#######################################################################
#
# SECTION: Dependency
#
# PURPOSE: Compare build & run dependencies
#
#######################################################################
#######################################################################

def tokenize(mystring):
	"""Breaks a string like 'foo? (bar) oni? (blah (blah))' into (possibly embedded) lists:

	>>> tokenize("x")
	['x']
	>>> tokenize("x y")
	['x', 'y']
	>>> tokenize("(x y)")
	[['x', 'y']]
	>>> tokenize("(x y) b c")
	[['x', 'y'], 'b', 'c']
	>>> tokenize("foo? (bar) oni? (blah (blah))")
	['foo?', ['bar'], 'oni?', ['blah', ['blah']]]
	>>> tokenize("sys-apps/linux-headers nls? (sys-devel/gettext)")
	['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']]
	"""

	newtokens = []
	curlist   = newtokens
	prevlists = []
	level     = 0
	accum     = ""
	for x in mystring:
		if x=="(":
			if accum:
				curlist.append(accum)
				accum=""
			prevlists.append(curlist)
			curlist=[]
			level=level+1
		elif x==")":
			if accum:
				curlist.append(accum)
				accum=""
			if level==0:
				print "!!! tokenizer: Unmatched left parenthesis in:\n'"+mystring+"'"
				return None
			newlist=curlist
			curlist=prevlists.pop()
			curlist.append(newlist)
			level=level-1
		elif x in string.whitespace:
			if accum:
				curlist.append(accum)
				accum=""
		else:
			accum=accum+x
	if accum:
		curlist.append(accum)
	if (level!=0):
		print "!!! tokenizer: Exiting with unterminated parenthesis in:\n'"+mystring+"'"
		return None
	return newtokens


#######################################################################

def evaluate(tokens,mydefines,allon=0):
	"""Removes tokens based on whether conditional definitions exist or not.
	Recognizes !

	>>> evaluate(['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']], {})
	['sys-apps/linux-headers']

	Negate the flag:

	>>> evaluate(['sys-apps/linux-headers', '!nls?', ['sys-devel/gettext']], {})
	['sys-apps/linux-headers', ['sys-devel/gettext']]

	Define 'nls':

	>>> evaluate(['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']], {"nls":1})
	['sys-apps/linux-headers', ['sys-devel/gettext']]

	Turn allon on:

	>>> evaluate(['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']], {}, True)
	['sys-apps/linux-headers', ['sys-devel/gettext']]
	"""

	if tokens == None:
		return None
	mytokens = tokens + []		# this copies the list
	pos = 0
	while pos < len(mytokens):
		if type(mytokens[pos]) == types.ListType:
			evaluate(mytokens[pos], mydefines)
			if not len(mytokens[pos]):
				del mytokens[pos]
				continue
		elif mytokens[pos][-1] == "?":
			cur = mytokens[pos][:-1]
			del mytokens[pos]
			if allon:
				if cur[0] == "!":
					del mytokens[pos]
			else:
				if cur[0] == "!":
					if (cur[1:] in mydefines) and (pos < len(mytokens)):
						del mytokens[pos]
						continue
				elif (cur not in mydefines) and (pos < len(mytokens)):
					del mytokens[pos]
					continue
		pos = pos + 1
	return mytokens


#######################################################################

def flatten(mytokens):
	"""Converts nested arrays into a flat arrays:

	>>> flatten([1,[2,3]])
	[1, 2, 3]
	>>> flatten(['sys-apps/linux-headers', ['sys-devel/gettext']])
	['sys-apps/linux-headers', 'sys-devel/gettext']
	"""

	newlist=[]
	for x in mytokens:
		if type(x)==types.ListType:
			newlist.extend(flatten(x))
		else:
			newlist.append(x)
	return newlist


#######################################################################

_package_weights_ = {"pre":-2,"p":0,"alpha":-4,"beta":-3,"rc":-1}	# dicts are unordered
_package_ends_    = ["pre", "p", "alpha", "beta", "rc"]			# so we need ordered list

def relparse(myver):
	"""Parses the last elements of a version number into a triplet, that can
	later be compared:

	>>> relparse('1.2_pre3')
	[1.2, -2, 3.0]
	>>> relparse('1.2b')
	[1.2, 98, 0]
	>>> relparse('1.2')
	[1.2, 0, 0]
	"""

	number   = 0
	p1       = 0
	p2       = 0
	mynewver = string.split(myver,"_")
	if len(mynewver)==2:
		# an _package_weights_
		number = string.atof(mynewver[0])
		match = 0
		for x in _package_ends_:
			elen = len(x)
			if mynewver[1][:elen] == x:
				match = 1
				p1 = _package_weights_[x]
				try:
					p2 = string.atof(mynewver[1][elen:])
				except:
					p2 = 0
				break
		if not match:	
			# normal number or number with letter at end
			divider = len(myver)-1
			if myver[divider:] not in "1234567890":
				# letter at end
				p1 = ord(myver[divider:])
				number = string.atof(myver[0:divider])
			else:
				number = string.atof(myver)		
	else:
		# normal number or number with letter at end
		divider = len(myver)-1
		if myver[divider:] not in "1234567890":
			#letter at end
			p1     = ord(myver[divider:])
			number = string.atof(myver[0:divider])
		else:
			number = string.atof(myver)  
	return [number,p1,p2]


#######################################################################

__ververify_cache__ = {}

def ververify(myorigval,silent=1):
	"""Returns 1 if given a valid version string, els 0. Valid versions are in the format

	<v1>.<v2>...<vx>[a-z,_{_package_weights_}[vy]]

	>>> ververify('2.4.20')
	1
	>>> ververify('2.4..20')		# two dots
	0
	>>> ververify('2.x.20')			# 'x' is not numeric
	0
	>>> ververify('2.4.20a')
	1
	>>> ververify('2.4.20cvs')		# only one trailing letter
	0
	>>> ververify('1a')
	1
	>>> ververify('test_a')			# no version at all
	0
	>>> ververify('2.4.20_beta1')
	1
	>>> ververify('2.4.20_beta')
	1
	>>> ververify('2.4.20_wrongext')	# _wrongext is no valid trailer
	0
	"""

	# Lookup the cache first
	try:
		return __ververify_cache__[myorigval]
	except KeyError:
		pass

	if len(myorigval) == 0:
		if not silent:
			error("package version is empty")
		__ververify_cache__[myorigval] = 0
		return 0
	myval = string.split(myorigval,'.')
	if len(myval)==0:
		if not silent:
			error("package name has empty version string")
		__ververify_cache__[myorigval] = 0
		return 0
	# all but the last version must be a numeric
	for x in myval[:-1]:
		if not len(x):
			if not silent:
				error("package version has two points in a row")
			__ververify_cache__[myorigval] = 0
			return 0
		try:
			foo = string.atoi(x)
		except:
			if not silent:
				error("package version contains non-numeric '"+x+"'")
			__ververify_cache__[myorigval] = 0
			return 0
	if not len(myval[-1]):
			if not silent:
				error("package version has trailing dot")
			__ververify_cache__[myorigval] = 0
			return 0
	try:
		foo = string.atoi(myval[-1])
		__ververify_cache__[myorigval] = 1
		return 1
	except:
		pass

	# ok, our last component is not a plain number or blank, let's continue
	if myval[-1][-1] in string.lowercase:
		try:
			foo = string.atoi(myval[-1][:-1])
			return 1
			__ververify_cache__[myorigval] = 1
			# 1a, 2.0b, etc.
		except:
			pass
	# ok, maybe we have a 1_alpha or 1_beta2; let's see
	ep=string.split(myval[-1],"_")
	if len(ep)!= 2:
		if not silent:
			error("package version has more than one letter at then end")
		__ververify_cache__[myorigval] = 0
		return 0
	try:
		foo = string.atoi(ep[0])
	except:
		# this needs to be numeric, i.e. the "1" in "1_alpha"
		if not silent:
			error("package version must have numeric part before the '_'")
		__ververify_cache__[myorigval] = 0
		return 0

	for mye in _package_ends_:
		if ep[1][0:len(mye)] == mye:
			if len(mye) == len(ep[1]):
				# no trailing numeric is ok
				__ververify_cache__[myorigval] = 1
				return 1
			else:
				try:
					foo = string.atoi(ep[1][len(mye):])
					__ververify_cache__[myorigval] = 1
					return 1
				except:
					# if no _package_weights_ work, *then* we return 0
					pass	
	if not silent:
		error("package version extension after '_' is invalid")
	__ververify_cache__[myorigval] = 0
	return 0


def isjustname(mypkg):
	myparts = string.split(mypkg,'-')
	for x in myparts:
		if ververify(x):
			return 0
	return 1


_isspecific_cache_={}

def isspecific(mypkg):
	"now supports packages with no category"
	try:
		return __isspecific_cache__[mypkg]
	except:
		pass

	mysplit = string.split(mypkg,"/")
	if not isjustname(mysplit[-1]):
			__isspecific_cache__[mypkg] = 1
			return 1
	__isspecific_cache__[mypkg] = 0
	return 0


#######################################################################

__pkgsplit_cache__={}

def pkgsplit(mypkg, silent=1):

	"""This function can be used as a package verification function. If
	it is a valid name, pkgsplit will return a list containing:
	[pkgname, pkgversion(norev), pkgrev ].

	>>> pkgsplit('')
	>>> pkgsplit('x')
	>>> pkgsplit('x-')
	>>> pkgsplit('-1')
	>>> pkgsplit('glibc-1.2-8.9-r7')
	>>> pkgsplit('glibc-2.2.5-r7')
	['glibc', '2.2.5', 'r7']
	>>> pkgsplit('foo-1.2-1')
	>>> pkgsplit('Mesa-3.0')
	['Mesa', '3.0', 'r0']
	"""

	try:
		return __pkgsplit_cache__[mypkg]
	except KeyError:
		pass

	myparts = string.split(mypkg,'-')
	if len(myparts) < 2:
		if not silent:
			error("package name without name or version part")
		__pkgsplit_cache__[mypkg] = None
		return None
	for x in myparts:
		if len(x) == 0:
			if not silent:
				error("package name with empty name or version part")
			__pkgsplit_cache__[mypkg] = None
			return None
	# verify rev
	revok = 0
	myrev = myparts[-1]
	if len(myrev) and myrev[0] == "r":
		try:
			string.atoi(myrev[1:])
			revok = 1
		except: 
			pass
	if revok:
		if ververify(myparts[-2]):
			if len(myparts) == 2:
				__pkgsplit_cache__[mypkg] = None
				return None
			else:
				for x in myparts[:-2]:
					if ververify(x):
						__pkgsplit_cache__[mypkg]=None
						return None
						# names can't have versiony looking parts
				myval=[string.join(myparts[:-2],"-"),myparts[-2],myparts[-1]]
				__pkgsplit_cache__[mypkg]=myval
				return myval
		else:
			__pkgsplit_cache__[mypkg] = None
			return None

	elif ververify(myparts[-1],silent):
		if len(myparts)==1:
			if not silent:
				print "!!! Name error in",mypkg+": missing name part."
			__pkgsplit_cache__[mypkg]=None
			return None
		else:
			for x in myparts[:-1]:
				if ververify(x):
					if not silent: error("package name has multiple version parts")
					__pkgsplit_cache__[mypkg] = None
					return None
			myval = [string.join(myparts[:-1],"-"), myparts[-1],"r0"]
			__pkgsplit_cache__[mypkg] = myval
			return myval
	else:
		__pkgsplit_cache__[mypkg] = None
		return None


#######################################################################

__catpkgsplit_cache__ = {}

def catpkgsplit(mydata,silent=1):
	"""returns [cat, pkgname, version, rev ]

	>>> catpkgsplit('sys-libs/glibc-1.2-r7')
	['sys-libs', 'glibc', '1.2', 'r7']
	>>> catpkgsplit('glibc-1.2-r7')
	['null', 'glibc', '1.2', 'r7']
	"""

	try:
		return __catpkgsplit_cache__[mydata]
	except KeyError:
		pass

	if mydata[:len(projectdir)] == projectdir:
		mydata = mydata[len(projectdir)+1:]
	if mydata[-3:] == '.oe':
		mydata = mydata[:-3]

	mysplit = mydata.split("/")
	p_split = None
	splitlen = len(mysplit)
	if splitlen == 1:
		retval = ["null"]
		p_split = pkgsplit(mydata,silent)
	else:
		retval = [mysplit[splitlen - 2]]
		p_split = pkgsplit(mysplit[splitlen - 1],silent)
	if not p_split:
		__catpkgsplit_cache__[mydata] = None
		return None
	retval.extend(p_split)
	__catpkgsplit_cache__[mydata] = retval
	return retval


#######################################################################

__vercmp_cache__ = {}

def vercmp(val1,val2):
	"""This takes two version strings and returns an integer to tell you whether
	the versions are the same, val1>val2 or val2>val1.
	
	>>> vercmp('1', '2')
	-1.0
	>>> vercmp('2', '1')
	1.0
	>>> vercmp('1', '1.0')
	0
	>>> vercmp('1', '1.1')
	-1.0
	>>> vercmp('1.1', '1_p2')
	1.0
	"""

	# quick short-circuit
	if val1 == val2:
		return 0
	valkey = val1+" "+val2

	# cache lookup
	try:
		return __vercmp_cache__[valkey]
		try:
			return - __vercmp_cache__[val2+" "+val1]
		except KeyError:
			pass
	except KeyError:
		pass
	
	# consider 1_p2 vc 1.1
	# after expansion will become (1_p2,0) vc (1,1)
	# then 1_p2 is compared with 1 before 0 is compared with 1
	# to solve the bug we need to convert it to (1,0_p2)
	# by splitting _prepart part and adding it back _after_expansion

	val1_prepart = val2_prepart = ''
	if val1.count('_'):
		val1, val1_prepart = val1.split('_', 1)
	if val2.count('_'):
		val2, val2_prepart = val2.split('_', 1)

	# replace '-' by '.'
	# FIXME: Is it needed? can val1/2 contain '-'?

	val1 = string.split(val1,'-')
	if len(val1) == 2:
		val1[0] = val1[0] +"."+ val1[1]
	val2 = string.split(val2,'-')
	if len(val2) == 2:
		val2[0] = val2[0] +"."+ val2[1]

	val1 = string.split(val1[0],'.')
	val2 = string.split(val2[0],'.')

	# add back decimal point so that .03 does not become "3" !
	for x in range(1,len(val1)):
		if val1[x][0] == '0' :
			val1[x] = '.' + val1[x]
	for x in range(1,len(val2)):
		if val2[x][0] == '0' :
			val2[x] = '.' + val2[x]

	# extend varion numbers
	if len(val2) < len(val1):
		val2.extend(["0"]*(len(val1)-len(val2)))
	elif len(val1) < len(val2):
		val1.extend(["0"]*(len(val2)-len(val1)))

	# add back _prepart tails
	if val1_prepart:
		val1[-1] += '_' + val1_prepart
	if val2_prepart:
		val2[-1] += '_' + val2_prepart
	# The above code will extend version numbers out so they
	# have the same number of digits.
	for x in range(0,len(val1)):
		cmp1 = relparse(val1[x])
		cmp2 = relparse(val2[x])
		for y in range(0,3):
			myret = cmp1[y] - cmp2[y]
			if myret != 0:
				__vercmp_cache__[valkey] = myret
				return myret
	__vercmp_cache__[valkey] = 0
	return 0


#######################################################################

def pkgcmp(pkg1,pkg2):
	""" Compares two packages, which should have been split via
	pkgsplit(). if the return value val is less than zero, then pkg2 is
	newer than pkg1, zero if equal and positive if older.

	>>> pkgcmp(['glibc', '2.2.5', 'r7'], ['glibc', '2.2.5', 'r7'])
	0
	>>> pkgcmp(['glibc', '2.2.5', 'r4'], ['glibc', '2.2.5', 'r7'])
	-1
	>>> pkgcmp(['glibc', '2.2.5', 'r7'], ['glibc', '2.2.5', 'r2'])
	1
	"""
	
	mycmp = vercmp(pkg1[1],pkg2[1])
	if mycmp > 0:
		return 1
	if mycmp < 0:
		return -1
	r1=string.atoi(pkg1[2][1:])
	r2=string.atoi(pkg2[2][1:])
	if r1 > r2:
		return 1
	if r2 > r1:
		return -1
	return 0


#######################################################################

def dep_parenreduce(mysplit, mypos=0):
	"""Accepts a list of strings, and converts '(' and ')' surrounded items to sub-lists:

	>>> dep_parenreduce([''])
	['']
	>>> dep_parenreduce(['1', '2', '3'])
	['1', '2', '3']
	>>> dep_parenreduce(['1', '(', '2', '3', ')', '4'])
	['1', ['2', '3'], '4']
	"""

	while mypos < len(mysplit): 
		if mysplit[mypos] == "(":
			firstpos = mypos
			mypos = mypos + 1
			while mypos < len(mysplit):
				if mysplit[mypos] == ")":
					mysplit[firstpos:mypos+1] = [mysplit[firstpos+1:mypos]]
					mypos = firstpos
					break
				elif mysplit[mypos] == "(":
					# recurse
					mysplit = dep_parenreduce(mysplit,mypos)
				mypos = mypos + 1
		mypos = mypos + 1
	return mysplit


def dep_opconvert(mysplit, myuse):
	"Does dependency operator conversion"
	
	mypos   = 0
	newsplit = []
	while mypos < len(mysplit):
		if type(mysplit[mypos]) == types.ListType:
			newsplit.append(dep_opconvert(mysplit[mypos],myuse))
			mypos += 1
		elif mysplit[mypos] == ")":
			# mismatched paren, error
			return None
		elif mysplit[mypos]=="||":
			if ((mypos+1)>=len(mysplit)) or (type(mysplit[mypos+1])!=types.ListType):
				# || must be followed by paren'd list
				return None
			try:
				mynew = dep_opconvert(mysplit[mypos+1],myuse)
			except Exception, e:
				error("unable to satisfy OR dependancy: " + string.join(mysplit," || "))
				raise e
			mynew[0:0] = ["||"]
			newsplit.append(mynew)
			mypos += 2
		elif mysplit[mypos][-1] == "?":
			# use clause, i.e "gnome? ( foo bar )"
			# this is a quick and dirty hack so that repoman can enable all USE vars:
			if (len(myuse) == 1) and (myuse[0] == "*"):
				# enable it even if it's ! (for repoman) but kill it if it's
				# an arch variable that isn't for this arch. XXX Sparc64?
				if (mysplit[mypos][:-1] not in settings.usemask) or \
						(mysplit[mypos][:-1]==settings["ARCH"]):
					enabled=1
				else:
					enabled=0
			else:
				if mysplit[mypos][0] == "!":
					myusevar = mysplit[mypos][1:-1]
					enabled = not myusevar in myuse
					#if myusevar in myuse:
					#	enabled = 0
					#else:
					#	enabled = 1
				else:
					myusevar=mysplit[mypos][:-1]
					enabled = myusevar in myuse
					#if myusevar in myuse:
					#	enabled=1
					#else:
					#	enabled=0
			if (mypos +2 < len(mysplit)) and (mysplit[mypos+2] == ":"):
				# colon mode
				if enabled:
					# choose the first option
					if type(mysplit[mypos+1]) == types.ListType:
						newsplit.append(dep_opconvert(mysplit[mypos+1],myuse))
					else:
						newsplit.append(mysplit[mypos+1])
				else:
					# choose the alternate option
					if type(mysplit[mypos+1]) == types.ListType:
						newsplit.append(dep_opconvert(mysplit[mypos+3],myuse))
					else:
						newsplit.append(mysplit[mypos+3])
				mypos += 4
			else:
				# normal use mode
				if enabled:
					if type(mysplit[mypos+1]) == types.ListType:
						newsplit.append(dep_opconvert(mysplit[mypos+1],myuse))
					else:
						newsplit.append(mysplit[mypos+1])
				# otherwise, continue
				mypos += 2
		else:
			# normal item
			newsplit.append(mysplit[mypos])
			mypos += 1
	return newsplit

class digraph:
	"""beautiful directed graph object"""

	def __init__(self):
		self.dict={}
		#okeys = keys, in order they were added (to optimize firstzero() ordering)
		self.okeys=[]
	
	def addnode(self,mykey,myparent):
		if not self.dict.has_key(mykey):
			self.okeys.append(mykey)
			if myparent==None:
				self.dict[mykey]=[0,[]]
			else:
				self.dict[mykey]=[0,[myparent]]
				self.dict[myparent][0]=self.dict[myparent][0]+1
			return
		if myparent and (not myparent in self.dict[mykey][1]):
			self.dict[mykey][1].append(myparent)
			self.dict[myparent][0]=self.dict[myparent][0]+1
	
	def delnode(self,mykey):
		if not self.dict.has_key(mykey):
			return
		for x in self.dict[mykey][1]:
			self.dict[x][0]=self.dict[x][0]-1
		del self.dict[mykey]
		while 1:
			try:
				self.okeys.remove(mykey)	
			except ValueError:
				break
	
	def allnodes(self):
		"returns all nodes in the dictionary"
		return self.dict.keys()
	
	def firstzero(self):
		"returns first node with zero references, or NULL if no such node exists"
		for x in self.okeys:
			if self.dict[x][0]==0:
				return x
		return None 

	def allzeros(self):
		"returns all nodes with zero references, or NULL if no such node exists"
		zerolist = []
		for x in self.dict.keys():
			if self.dict[x][0]==0:
				zerolist.append(x)
		return zerolist

	def hasallzeros(self):
		"returns 0/1, Are all nodes zeros? 1 : 0"
		zerolist = []
		for x in self.dict.keys():
			if self.dict[x][0]!=0:
				return 0
		return 1

	def empty(self):
		if len(self.dict)==0:
			return 1
		return 0

	def hasnode(self,mynode):
		return self.dict.has_key(mynode)

	def copy(self):
		mygraph=digraph()
		for x in self.dict.keys():
			mygraph.dict[x]=self.dict[x][:]
			mygraph.okeys=self.okeys[:]
		return mygraph

#######################################################################
#######################################################################
#
# SECTION: Config
#
# PURPOSE: Reading and handling of system/target-specific/local configuration
#	   reading of package configuration
#
#######################################################################
#######################################################################

def reader(cfgfile, feeder):
	"""Generic configuration file reader that opens a file, reads the lines,
	handles continuation lines, comments, empty lines and feed all read lines
	into the function feeder(lineno, line).
	"""
	
	f = open(cfgfile,'r')
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
		feeder(lineno, s)




# matches "VAR = VALUE"
__config_regexp__  = re.compile( r"(?P<exp>export\s*)?(?P<var>\w+)\s*(?P<colon>:)?=\s*(?P<apo>['\"]?)(?P<value>.*)(?P=apo)$")

# matches "include FILE"
__include_regexp__ = re.compile( r"include\s+(.+)" )

__read_config_visit_cache__ = {}

def __read_config__(cfgfile, level):
	"""Reads a configuration file"""
	visit = 1

	def process_config(lineno, s):
		m = __config_regexp__.match(s)
		if m:
			groupd = m.groupdict()
			key = groupd["var"]
			if groupd.has_key("exp") and groupd["exp"] is not None:
				if not envflags.has_key(key):
					envflags[key] = {}
				envflags[key]["export"] = 1
			if groupd.has_key("colon") and groupd["colon"] is not None:
				setenv(key, groupd["value"])
			else:
				env[key] = groupd["value"]
#			print key,groupd["value"]
			return

		m = __include_regexp__.match(s)
		if m:
			if not visit: return
			s = expand(m.group(1))
			if os.access(s, os.R_OK):
				if level==0:
					inherit_os_env(2)
				__read_config__(s, level+1)
			else:
				debug(1, "%s:%d: could not import %s" % (cfgfile, lineno, s))
			return

		print lineno, s

	cfgfile = os.path.abspath(cfgfile)
	if __read_config_visit_cache__.has_key(cfgfile): visit = 0
	__read_config_visit_cache__[cfgfile] = 1
	debug(2, "read " + cfgfile)
	reader(cfgfile, process_config)

def read_config(cfgfile):
	__read_config__(cfgfile, 0)

	for s in ['BUILD_ARCH','BUILD_OS', 'ARCH', 'OS', 'MACHINE','ARCH']:
		if not env.has_key(s):
			print "FATAL: %s" % envflags[s]['warn']
			fatal('read ${OEDIR}/oe.conf to learn about local configuration')


__func_start_regexp__    = re.compile( r"(\w+)\s*\(\s*\)\s*{$" )
__include_regexp__       = re.compile( r"include\s+(.+)" )
__inherit_regexp__       = re.compile( r"inherit\s+(.+)" )
__export_func_regexp__   = re.compile( r"EXPORT_FUNCTIONS\s+(.+)" )

__read_oe_infunc__ = ""
__read_oe_body__   = []
__read_oe_classname__ = "" # our python equiv to OECLASS
__oepath_found_it__ = 0

def read_oe(oefile, inherit = False, classname = None):
	"""Reads a build file"""
	"""When inherit flag is set to False(default), EXPORT_FUNCTIONS is ignored."""

	def process_oe(lineno, s):
		global __read_oe_infunc__, __read_oe_body__, __read_oe_classname__, __oepath_found_it__
		if __read_oe_infunc__:
			if s == '}':
				__read_oe_body__.append('')
				env[__read_oe_infunc__] = string.join(__read_oe_body__, '\n')
				__read_oe_infunc__ = ""
				__read_oe_body__ = []
			else:
				__read_oe_body__.append(s)
			return
			
			
		m = __config_regexp__.match(s)
		if m:
			key = m.group("var")
			var = m.group("value")
			if var and (var[0]=='"' or var[0]=="'"):
				fatal("Mismatch in \" or ' characters for %s=" % key)
			if m.group("colon"):
				setenv(key, var)
			else:
				env[key] = var
			#print "%s=%s" % (key,var)
			return

		m = __func_start_regexp__.match(s)
		if m:
			__read_oe_infunc__ = m.group(1)
			return

		m = __include_regexp__.match(s)
		if m:
			file = expand(m.group(1))
			try:
				read_oe(file)
			except IOError:
				fatal("error accessing build file %s" % file)
			return

		m = __inherit_regexp__.match(s)
		if m:
			__word__ = re.compile(r"\S+")
			files = m.group(1)
			n = __word__.findall(files)
			for f in n:
				file = expand(f)
				if file[0] != "/":
					if env.has_key('OEPATH'):
						__oepath_found_it__ = 0
						for dir in expand(env['OEPATH']).split(":"):
#							print "attempting to access %s" % os.path.join(dir, "classes",file + ".oeclass")
							if os.access(os.path.join(dir, "classes", file + ".oeclass"), os.R_OK):
								file = os.path.join(dir, "classes",file + ".oeclass")
								__oepath_found_it__ = 1
					if __oepath_found_it__ == 0:
						fatal("unable to locate %s in OEPATH"  % file)
					__read_oe_classname__ = file

				o = re.match(r".*/([^/\.]+)",file)
				if o:
					__read_oe_classname__ = o.group(1)

#				print "read_oe: inherit: loading %s" % file
				try:
					read_oe(file, True, __read_oe_classname__)
					__read_oe_classname__ = classname
				except IOError:
					fatal("error accessing build file %s" % file)
			return

		m = __export_func_regexp__.match(s)
		if m:
			if inherit == True:
				__word__ = re.compile(r"\S+")
				fns = m.group(1)
				n = __word__.findall(fns)
				for f in n:
					setenv(f, "\t%s_%s\n" % (__read_oe_classname__,f))
			return

		error("Unknown syntax in %s" % oefile)
		print s
		sys.exit(1)


	debug(2,"read_oe('%s')" % oefile)
	reader(oefile, process_oe)




#######################################################################
#######################################################################
#
# SECTION: Environment
#
# PURPOSE: store, modify and emit environment variables. Enforce need
#          variables, calculate missing ones.
#
#######################################################################
#######################################################################

__expand_var_regexp__ = re.compile(r"\${[^{}]+}")
__expand_python_regexp__ = re.compile(r"\${@.+?}")

def expand(s, env = globals()["env"]):
	"""Can expand variables with their values from env[]

	>>> env['MID'] = 'drin'
	>>> print expand('vorher ${MID} dahinter')
	vorher drin dahinter

	Unset variables are kept as is:

	>>> print expand('vorher ${MID} dahinter ${UNKNOWN}')
	vorher drin dahinter ${UNKNOWN}

	A syntax error just returns the string:

	>>> print expand('${UNKNOWN')
	${UNKNOWN

	We can evaluate python code:

	>>> print expand('${@ "Test"*3}')
	TestTestTest
	>>> env['START'] = '0x4000'
	>>> print expand('${@ hex(0x1000000+${START}) }')
	0x1004000

	We are able to handle recursive definitions:

	>>> env['ARCH'] = 'arm'
	>>> env['OS'] = 'linux'
	>>> env['SYS'] = '${ARCH}-${OS}'
	>>> print expand('${SYS}')
	arm-linux
	"""

	def var_sub(match):
		key = match.group()[2:-1]
		#print "got key:", key
		if env.has_key(key):
			return env[key]
		else:
			return match.group()

	def python_sub(match):
		code = match.group()[3:-1]
		s = eval(code)
		if type(s) == types.IntType: s = str(s)
		return s

	while s.find('$') != -1:
		olds = s
		s = __expand_var_regexp__.sub(var_sub, s)
		s = __expand_python_regexp__.sub(python_sub, s)
		if len(s)>2048:
			fatal("expanded string too long")
		if s == olds: break
	return s


#######################################################################

def setenv(var, value, env = globals()["env"]):
	"""Simple set an environment in the global oe.env[] variable, but
	with expanding variables beforehand.
	"""

	env[var] = expand(value)


#######################################################################

def getenv(var, env = globals()["env"]):
	"""Returns an expanded environment var"""
	return expand('${%s}' % var, env)


#######################################################################

def inherit_os_env(position, env = globals()["env"]):
	"""This reads the the os-environment and imports variables marked as
	such in envflags into our environment. This happens at various places
	during package definition read time, see comments near envflags[] for
	more.
	"""
	
	debug(2,"inherit_os_env(%d)" % position)

	position = str(position)
	for s in os.environ.keys():
		try:
			d = envflags[s]
			if d.has_key('inherit') and d['inherit'] == position:
				env[s] = os.environ[s]
				debug(2, 'inherit %s from os environment' % s)
		except KeyError:
			pass


#######################################################################

def set_automatic_vars(file):
	"""Deduce per-package environment variables"""

	debug(2,"setting automatic vars")
	pkg = catpkgsplit(file)
	if pkg == None:
		fatal("package file not in valid format")
	setenv('CATEGORY',	pkg[0])
	setenv('PN',		pkg[1])
	setenv('PV',		pkg[2])
	setenv('PR',		pkg[3])
	setenv('P',		'${PN}-${PV}')
	setenv('PF',		'${P}-${PR}')

	for s in ['${TOPDIR}/${CATEGORY}/${PF}', 
		  '${TOPDIR}/${CATEGORY}/${PN}-${PV}',
		  '${TOPDIR}/${CATEGORY}/files',
		  '${TOPDIR}/${CATEGORY}']:
		s = expand(s)
		if os.access(s, os.R_OK):
			setenv('FILESDIR', s)
			break
	setenv('WORKDIR',	'${TMPDIR}/${CATEGORY}/${PF}')
	setenv('T',		'${WORKDIR}/temp')
	setenv('D',		'${WORKDIR}/image')
	setenv('S',		'${WORKDIR}/${P}')
	setenv('SLOT',		'0')
	inherit_os_env(3)


#######################################################################

def set_additional_vars():
	"""Deduce rest of variables, e.g. ${A} out of ${SRC_URI}"""

	debug(2,"set_additional_vars")

	inherit_os_env(4)
	if env.has_key('SRC_URI'):
		# Do we already have something in A?
		if env.has_key('A'):
			a = env['A'].split()
		else:
			a = []

		for loc in env['SRC_URI'].split():
			(type, host, path, user, pswd, parm) = decodeurl(expand(loc))
			if type in ['http','https','ftp']:
				a.append(os.path.basename(path))

		env['A'] = string.join(a)

	for s in ['S','STAGING_DIR','STAGING_BINLIB', 'STAGING_LIBDIR']:
		if env.has_key(s):
			env[s] = getenv(s)


#######################################################################

def update_env(env = globals()["env"]):
	"""Modifies the environment vars according to local overrides

	For the example we do some preparations:

	>>> setenv('TEST_arm', 'target')
	>>> setenv('TEST_ramses', 'machine')
	>>> setenv('TEST_local', 'local')
        >>> setenv('OVERRIDES', 'arm')

	and then we set some TEST environment variable and let it update:

	>>> setenv('TEST', 'original')
	>>> update_env()
	>>> print env['TEST']
	target

	You can set OVERRIDES to another value, yielding another result:

        >>> setenv('OVERRIDES', 'arm:ramses:local')
	>>> setenv('TEST', 'original')
	>>> update_env()
	>>> print env['TEST']
	local

	Besides normal updates, we are able to append text:

	>>> setenv('TEST_append', ' foo')
	>>> update_env()
	>>> print env['TEST']
	local foo

	And we can prepend text:

	>>> setenv('TEST_prepend', 'more ')
	>>> update_env()
	>>> print env['TEST']
	more local foo

	Deleting stuff is more fun with multiline environment variables, but
	it works with normal ones, too. The TEST_delete='foo' construct
	deletes any line in TEST that matches 'foo':

	>>> setenv('TEST_delete', 'foo ')
	>>> update_env()
	>>> print "'%s'" % env['TEST']
	''
	"""

	debug(2, "update_env()")

	# can't do delete env[...] while iterating over the dictionary, so remember them
	dodel = []
	# preprocess overrides
	override = expand(env['OVERRIDES']).split(':')

	for s in env:
		for o in override:
			name = s + '_' + o
			if env.has_key(name):
				env[s] = env[name]
				dodel.append(name)

		# Handle line appends:
		name = s+'_append'
		if env.has_key(name):
			env[s] = env[s]+env[name]
			dodel.append(name)

		# Handle line prepends
		name = s+'_prepend'
		if env.has_key(name):
			env[s] = env[name]+env[s]
			dodel.append(name)

		# Handle line deletions
		name = s+'_delete'
		if env.has_key(name):
			new = ''
			pattern = string.replace(env[name],"\n","").strip()
			for line in string.split(env[s],"\n"):
				if line.find(pattern) == -1:
					new = new + '\n' + line
			env[s] = new
			dodel.append(name)

	# delete all environment vars no longer needed
	for s in dodel:
		del env[s]

	inherit_os_env(5)


#######################################################################

def emit_env(o=sys.__stdout__, env = globals()["env"]):
	"""This prints the contents of env[] so that it can later be sourced by a shell
	Normally, it prints to stdout, but this it can be redirectory to some open file handle

	It is used by exec_shell_func().
	"""

	o.write('\nPATH="' + os.path.join(projectdir, 'bin/build') + ':${PATH}"\n')


	for s in env:
		if s == s.lower(): continue

		o.write('\n')
		if envflags.has_key(s):
			if envflags[s].has_key('export'):
				 o.write('export ')

		o.write(s+'="'+getenv(s,env)+'"\n')

	for s in env:
		if s != s.lower(): continue

		o.write("\n" + s + '() {\n' + getenv(s,env) + '}\n')


#######################################################################

def print_orphan_env():
	"""Debug output: do we have any variables that are not mentioned in oe.envflags[] ?"""
	for s in env:
		if s == s.lower(): continue		# only care for env vars
		header = 0				# header shown?
		try:
			d = envflags[s]
		except KeyError:
			if not header:
				note("Nonstandard variables defined in your project:")
				header = 1
			print debug_prepend + s
		if header:
			print


#######################################################################

def print_missing_env():
	"""Debug output: warn about all missing variables

	Returns 1 on error, terminates on fatal error.
	"""

	err = 0
	for s in envflags:
		if not envflags[s].has_key('warnlevel'): continue
		if env.has_key(s): continue

		level = envflags[s]['warnlevel']
		try: warn = debug_prepend + envflags[s]['warn']
		except KeyError: warn = ''
		if level == 1:
			note('Variable %s is not defined' % s)
			if warn: print " -", warn
		elif level == 2:
			error('Important variable %s is not defined' % s)
			err = 1
			if warn: print " -", warn
		elif level == 3:
			error('Important variable %s is not defined' % s)
			if warn: print " -", warn
			sys.exit(1)
	return err


envflags = {

#
# desc:        descriptional text
#
# warnlevel 1: notify the user that this field is missing
# warnlevel 2: complain loudly if this field doesn't exist, but continue
# warnlevel 3: this field is absolutely mandatory, stop working if it isn't there
#
# warn:        text to display when showing a warning
#
# inherit 1:   get this var from the environment (if possible) before global config
# inherit 2:   between global and local config
# inherit 3:   between local config and package definition
# inherit 4:   before setting additional vars
# inherit 5:   after package definition
#              (this defines the precendency, because any var can be overriden by the next step)
#
# export:      when creating the package build script, do not only define this var, but export it
#


# Directories for the Build system

"OEDIR":		{ "warnlevel": 3,
			  "inherit": "1" },
"OEPATH":		{ "warnlevel": 3,
			  "inherit": "1" },
"TOPDIR":		{ "warnlevel": 3,
			  "desc":	"Toplevel directory of build area" },
"TMPDIR":		{ "warnlevel": 3 },
"DL_DIR":		{ "warnlevel": 3 },
"STAMP":		{ "warnlevel": 3 },
"STAGING_DIR":		{ "warnlevel": 3 },
"STAGING_BINDIR":	{ "warnlevel": 3 },
"STAGING_LIBDIR":	{ "warnlevel": 3 },

# Mirros and download:

"DEBIAN_MIRROR":	{ "warnlevel": 3 },
"SOURCEFORGE_MIRROR":	{ "warnlevel": 3 },
"FETCHCOMMAND":		{ "warnlevel": 3 },
"RESUMECOMMAND":	{ "warnlevel": 3 },

# Architecture / Board related:

"DISTRO":		{ "warnlevel": 0, },
"BUILD_ARCH":		{ "warnlevel": 3,
			  "warn":      "put something like BUILD_ARCH='i686' into ${OEDIR}/conf/local.conf" },
"BUILD_OS":		{ "warnlevel": 3,
			  "warn":      "put something like BUILD_OS='linux' into ${OEDIR}/conf/local.conf" },
"ARCH":			{ "warnlevel": 3,
			  "warn":      "put something like ARCH='arm' into ${OEDIR}/conf/local.conf" },
"OS":			{ "warnlevel": 3,
			  "warn":      "put something like OS='linux' into ${OEDIR}/conf/local.conf" },
"MACHINE":		{ "warnlevel": 3,
			  "warn":      "put something like MACHINE='ramses' into ${OEDIR}/conf/local.conf" },
"USE":			{ "warnlevel": 2,
			  "warn":      "put USE= with a list of features into ${OEDIR}/conf/local.conf" },
"SYS":			{ "warnlevel": 3 },
"BUILD_SYS":		{ "warnlevel": 3 },
"CROSS":		{ "warnlevel": 3 },
"OVERRIDES":     	{ "warnlevel": 2 },
"ALLOWED_FLAGS":	{ "warnlevel": 2 },

"FULL_OPTIMIZATION":	{ "warnlevel": 2 },
"OPTIMIZATION":		{ "warnlevel": 2 },

"CPPFLAGS":		{ "warnlevel": 3 },
"CFLAGS":		{ "warnlevel": 3 },
"CXXFLAGS":		{ "warnlevel": 3 },
"LDFLAGS":		{ "warnlevel": 3 },
"CPP":			{ "warnlevel": 3 },
"CC":			{ "warnlevel": 3 },
"CXX":			{ "warnlevel": 3 },
"LD":			{ "warnlevel": 3 },
"STRIP":		{ "warnlevel": 3 },
"AR":			{ "warnlevel": 3 },
"RANLIB":		{ "warnlevel": 3 },
"MAKE":			{ "warnlevel": 3 },

"BUILD_CPPFLAGS":	{ "warnlevel": 3 },
"BUILD_CFLAGS":		{ "warnlevel": 3 },
"BUILD_CXXFLAGS":	{ "warnlevel": 3 },
"BUILD_LDFLAGS":	{ "warnlevel": 3 },
"BUILD_CPP":		{ "warnlevel": 3 },
"BUILD_CC":		{ "warnlevel": 3 },
"BUILD_CXX":		{ "warnlevel": 3 },
"BUILD_LD":		{ "warnlevel": 3 },

"PKG_CONFIG_PATH":	{ "warnlevel": 3 },



# Mandatory fields in build files

"DESCRIPTION":		{ "warnlevel": 3 },
"DEPEND":		{ "warnlevel": 1 },
"RDEPEND":		{ "warnlevel": 1 },
"PROVIDES":		{ "warnlevel": 0 },
"SRC_URI":		{ "warnlevel": 1 },
"LICENSE":		{ "warnlevel": 1 },
"HOMEPAGE":		{ "warnlevel": 1 },

# Use when needed

"PROVIDE":		{ "warnlevel": 0 },
"RECOMMEND":		{ "warnlevel": 0 },
"FOR_TARGET":		{ "warnlevel": 0 },
"SLOT":			{ "warnlevel": 0 },
"GET_URI":		{ "warnlevel": 0 },
"MAINTAINER":		{ "warnlevel": 0 },
"EXTRA_OECONF":		{ "warnlevel": 0 },
"EXTRA_OEMAKE":		{ "warnlevel": 0 },



#"OEBUILD":		{ "warnlevel": 3 },
"P":			{ "warnlevel": 3 },
"CATEGORY":		{ "warnlevel": 2 },
"PN":			{ "warnlevel": 3 },
"PV":			{ "warnlevel": 3 },
"PR":			{ "warnlevel": 2 },
"PF":			{ "warnlevel": 3 },
"WORKDIR":		{ "warnlevel": 3 },
"FILESDIR":		{ "warnlevel": 3 },
"S":			{ "warnlevel": 3 },
"T":			{ "warnlevel": 3 },
"D":			{ "warnlevel": 3 },
"A":			{ "warnlevel": 1 },

# Package creation functions:

"pkg_setup":		{ "warnlevel": 0 },
"pkg_nofetch":		{ "warnlevel": 0 },
"pkg_fetch":		{ "warnlevel": 0 },
"src_compile":		{ "warnlevel": 1 },
"src_install":		{ "warnlevel": 1 },
"src_stage":		{ "warnlevel": 0 },
"pkg_preinst":		{ "warnlevel": 0 },
"pkg_postint":		{ "warnlevel": 0 },
"pkg_prerm":		{ "warnlevel": 0 },
"pkg_postrm":		{ "warnlevel": 0 },

# Automatically generated, but overrideable:

"do_unpack":		{ "warnlevel": 1 },
"do_compile":		{ "warnlevel": 1 },

"OEDEBUG":		{ "inherit":  "1" },

}

# defaults for vars needed to access oe.conf
env['TOPDIR'] = projectdir
env['OEDIR'] = os.path.join(sys.prefix, "share/oe")
env['OEPATH'] = "${OEDIR}/bin:${OEDIR}:${TOPDIR}/bin:${TOPDIR}"
inherit_os_env(1)

if __name__ == "__main__":
	import doctest, oe
	doctest.testmod(oe)
