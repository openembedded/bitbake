#######################################################################
#
#  OpenEmbedded Python Library
#
#  Part of this code has been shamelessly stolen from Gentoo's portage.py.
#  In the source code was GPL-2 as License, so the same goes for this file.
#
#  Functions that have comments with lots of ###### have been tested in the
#  OE environment, all other stuff has been taken (more or less) 1:1 from
#  Portage and may or may not apply.
#
#  Please visit http://www.openembedded.org/phpwiki/ for more info.
#

import sys,posixpath,string,types
projectdir = posixpath.dirname(posixpath.dirname(posixpath.abspath(sys.argv[0])))


class VarExpandError(Exception):
	pass



#######################################################################
#
# tokenize()
#
# Put in a string like
#
#	'sys-apps/linux-headers nls? (sys-devel/gettext)'
#
# and get back
#
#	['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']]
#

def tokenize(mystring):
	"""breaks a string like 'foo? (bar) oni? (blah (blah))'
	into embedded lists; returns None on paren mismatch"""
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
#
# evaluate(tokens, defines)
#
#
# Assume you have this list of dependencies:
#
#	['sys-apps/linux-headers', 'nls?', ['sys-devel/gettext']]
#
# and you do a normal build (no defines are set), then you will get:
#
#	['sys-apps/linux-headers']
#
# as dependency. Now, assume you want to have NLS on your OE target, then put
# 'nls' into the defines list. Now you will get
#
#	['sys-apps/linux-headers', ['sys-devel/gettext']]
#
# Just put that throught flatten() and you have a list of dependencies.
#
#
# The tokens can also have negative flags, e.g.
#
#	['gdbm?', ['gdbm'], '!gdbm?', ['flatfile'] ]
#

def evaluate(tokens,mydefines,allon=0):
	"""removes tokens based on whether conditional definitions exist or not.
	Recognizes !"""
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
#
#  flatten()
#
#  [1,[2,3]] -> [1,2,3]
#
#  Usually used after tokenize() and evaluate()
#

def flatten(mytokens):
	"""this function now turns a [1,[2,3]] list into
	a [1,2,3] list and returns it."""
	newlist=[]
	for x in mytokens:
		if type(x)==types.ListType:
			newlist.extend(flatten(x))
		else:
			newlist.append(x)
	return newlist


#beautiful directed graph object
class digraph:
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

# valid end of version components; integers specify offset from release version
# pre=prerelease, p=patchlevel (should always be followed by an int), rc=release candidate
# all but _p (where it is required) can be followed by an optional trailing integer

def grabfile(myfilename):
	"""This function grabs the lines in a file, normalizes whitespace and returns lines in a list; if a line
	begins with a #, it is ignored, as are empty lines"""

	try:
		myfile=open(myfilename,"r")
	except IOError:
		return []
	mylines=myfile.readlines()
	myfile.close()
	newlines=[]
	for x in mylines:
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		myline=string.join(string.split(x))
		if not len(myline):
			continue
		if myline[0]=="#":
			continue
		newlines.append(myline)
	return newlines

def grabdict(myfilename,juststrings=0):
	"""This function grabs the lines in a file, normalizes whitespace and returns lines in a dictionary"""
	newdict={}
	try:
		myfile=open(myfilename,"r")
	except IOError:
		return newdict 
	mylines=myfile.readlines()
	myfile.close()
	for x in mylines:
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		myline=string.split(x)
		if len(myline)<2:
			continue
		if juststrings:
			newdict[myline[0]]=string.join(myline[1:])
		else:
			newdict[myline[0]]=myline[1:]
	return newdict

def grabints(myfilename):
	newdict={}
	try:
		myfile=open(myfilename,"r")
	except IOError:
		return newdict 
	mylines=myfile.readlines()
	myfile.close()
	for x in mylines:
		#the split/join thing removes leading and trailing whitespace, and converts any whitespace in the line
		#into single spaces.
		myline=string.split(x)
		if len(myline)!=2:
			continue
		newdict[myline[0]]=string.atoi(myline[1])
	return newdict

def writeints(mydict,myfilename):
	try:
		myfile=open(myfilename,"w")
	except IOError:
		return 0
	for x in mydict.keys():
		myfile.write(x+" "+`mydict[x]`+"\n")
	myfile.close()
	return 1

def writedict(mydict,myfilename,writekey=1):
	"""Writes out a dict to a file; writekey=0 mode doesn't write out
	the key and assumes all values are strings, not lists."""
	try:
		myfile=open(myfilename,"w")
	except IOError:
		print "Failed to open file for writedict():",myfilename
		return 0
	if not writekey:
		for x in mydict.values():
			myfile.write(x+"\n")
	else:
		for x in mydict.keys():
			myfile.write(x+" ")
			for y in mydict[x]:
				myfile.write(y+" ")
			myfile.write("\n")
	myfile.close()
	return 1


#######################################################################
#
# varexpand()
#
# Expands variables of the form ${VARNAME} via keys
# Expands variables of the form ${@python-code} via eval()
# Expands shell escapes like \n
#

# cache expansions of constant strings
_varexpand_cache_ = {}
def varexpand(mystring,mydict = {}, stripnl=0):
	"""
	Removes quotes, handles \n, etc.
	This code is used by the configfile code, as well as others (parser)
	This would be a good bunch of code to port to C.
	"""

	try:
		return _varexpand_cache_[" "+mystring]
	except KeyError:
		pass

	numvars   = 0
	mystring  = " "+mystring
	insing    = 0	# in single quotes?
	indoub    = 0	# in double quotes?
	pos       = 1
	newstring = " "
	while pos<len(mystring):
		if (mystring[pos] == "'") and (mystring[pos-1] != "\\"):
			if indoub:
				newstring = newstring + "'"
			else:
				insing = not insing
			pos = pos+1
			continue
		elif (mystring[pos] == '"') and (mystring[pos-1] != "\\"):
			if insing:
				newstring = newstring + '"'
			else:
				indoub = not indoub
			pos = pos + 1
			continue
		if not insing: 
			# expansion time
			if stripnl and (mystring[pos] == "\n"):
				#print "stripped: ",newstring
				# convert newlines to spaces
				newstring = newstring + " "
				pos = pos + 1
			elif mystring[pos] == "\\":
				# backslash expansion time
				if pos +1 >= len(mystring):
					newstring = newstring + mystring[pos]
					break
				else:
					a = mystring[pos+1]
					pos = pos + 2
					if a == 'a':
						newstring = newstring + chr(007)
					elif a == 'b':
						newstring = newstring + chr(010)
					elif a == 'e':
						newstring = newstring + chr(033)
					elif (a == 'f') or (a == 'n'):
						newstring = newstring + chr(012)
					elif a == 'r':
						newstring = newstring + chr(015)
					elif a == 't':
						newstring = newstring + chr(011)
					elif a == 'v':
						newstring = newstring + chr(013)
					else:
						# remove backslash only, as bash does: this takes care of \\ and \' and \" as well
						newstring = newstring + mystring[pos-1:pos]
						continue
			elif (mystring[pos] == "$") and (mystring[pos-1] != "\\"):
				pos = pos + 1
				if pos+1 >= len(mystring):
					_varexpand_cache_[mystring] = ""
					return ""
				if mystring[pos] == "{":
					pos = pos + 1
					terminus = "}"
				else:
					terminus = string.whitespace
				myvstart = pos
				while mystring[pos] not in terminus:
					if pos+1 >= len(mystring):
						_varexpand_cache_[mystring] = ""
						return ""
					pos = pos + 1
				myvarname = mystring[myvstart:pos]
				pos = pos + 1
				if len(myvarname) == 0:
					_varexpand_cache_[mystring] = ""
					return ""
				numvars = numvars + 1

				# keep vars that are not all in UPPERCASE
				if myvarname[0] == '@':
					newstring = newstring + eval(myvarname[1:])
				elif myvarname != myvarname.upper():
					newstring = newstring + '${' + myvarname + '}'
				elif mydict.has_key(myvarname):
					newstring = newstring + mydict[myvarname]
				else:
					raise VarExpandError, "'" + myvarname + "' missing"
			else:
				newstring = newstring + mystring[pos]
				pos = pos + 1
		else:
			newstring = newstring + mystring[pos]
			pos = pos + 1
	if numvars == 0:
		_varexpand_cache_[mystring] = newstring[1:]
	return newstring[1:]	


#######################################################################
#
# Reads some text file and returns a dictionary that is mykeys + all found definitions
# Definitions have the form:
#
# VAR=value
# VAR     =    value				whitespace is ok
# VAR = " value"				using double quotes
# VAR = 'value '				using single quotes
# VAR() {					use this for multi-line values
#    value
#    value
# }
#
# When myexpand is true, all lines go throught varexpand(), see above.
#

def getconfig(mycfg, mykeys={}, myexpand=0):
	import shlex
	f = open(mycfg,'r')
	lex = shlex.shlex(f)
	lex.wordchars = string.digits + string.letters + "~!@#%*_\:;?,./-+{}"
	lex.quotes = "\"'"
	while 1:
		key = lex.get_token()
		if key == '':
			# Normal end of file
			break;
		equ = lex.get_token()
		val = ''
		if equ == '':
			# Unexpected end of file
			print lex.error_leader(mycfg, lex.lineno), \
				"enexpected end of config file: variable", key
			return None
		elif equ == '(':
			equ = lex.get_token()
			if equ != ')':
				print lex.error_leader(mycfg, lex.lineno), \
					"expected ')', got '"+ equ + "'"
				return None
			equ = lex.get_token()
			if equ != '{':
				print lex.error_leader(mycfg, lex.lineno), \
					"expected '{', got '"+ equ + "'"
				return None
			lex.lineno = lex.lineno - 1
			while 1:
				equ = lex.instream.readline()
				if equ == '':
					break
				equ = equ.rstrip()
				if equ == '}':
					break
				if myexpand:
					try:
						equ = varexpand(equ, mykeys, 0)
					except VarExpandError, detail:
						print lex.error_leader(mycfg, lex.lineno) + detail.args[0]
				lex.lineno = lex.lineno + 1
				val = val + equ + "\n"
			lex.lineno = lex.lineno + 2
		elif equ != '=':
			print lex.error_leader(mycfg, lex.lineno), \
				"expected '=', got '" + equ + "'"
			return None
		if val == '':
			val = lex.get_token()
			#stripnl = 1
			stripnl = 0
		else:
			stripnl = 0
		if val == '':
			print lex.error_leader(mycfg, lex.lineno), \
				"end of file in variable definition"
			return None
		if myexpand:
			try:
				val = varexpand(val,mykeys,stripnl)
			except VarExpandError, detail:
				print lex.error_leader(mycfg, lex.lineno) + detail.args[0]
		mykeys[key] = val
			
	return mykeys


def fetch(myuris, listonly=0):
	"fetch files.  Will use digest file if available."
	if ("mirror" in features) and ("nomirror" in settings["RESTRICT"].split()):
		print ">>> \"mirror\" mode and \"nomirror\" restriction enabled; skipping fetch."
		return 1
	global thirdpartymirrors
	mymirrors=settings["GENTOO_MIRRORS"].split()
	fetchcommand=settings["FETCHCOMMAND"]
	resumecommand=settings["RESUMECOMMAND"]
	fetchcommand=string.replace(fetchcommand,"${DISTDIR}",settings["DISTDIR"])
	resumecommand=string.replace(resumecommand,"${DISTDIR}",settings["DISTDIR"])
	mydigests=None
	digestfn=settings["FILESDIR"]+"/digest-"+settings["PF"]
	if os.path.exists(digestfn):
		myfile=open(digestfn,"r")
		mylines=myfile.readlines()
		mydigests={}
		for x in mylines:
			myline=string.split(x)
			if len(myline)<4:
				#invalid line
				print "!!! The digest",digestfn,"appears to be corrupt.  Aborting."
				return 0
			try:
				mydigests[myline[2]]={"md5":myline[1],"size":string.atol(myline[3])}
			except ValueError:
				print "!!! The digest",digestfn,"appears to be corrupt.  Aborting."
	if "fetch" in settings["RESTRICT"].split():
		# fetch is restricted.	Ensure all files have already been downloaded; otherwise,
		# print message and exit.
		gotit=1
		for myuri in myuris:
			myfile=os.path.basename(myuri)
			try:
				mystat=os.stat(settings["DISTDIR"]+"/"+myfile)
			except (OSError,IOError),e:
				# file does not exist
				print "!!!",myfile,"not found in",settings["DISTDIR"]+"."
				gotit=0
		if not gotit:
			print
			print "!!!",settings["CATEGORY"]+"/"+settings["PF"],"has fetch restriction turned on."
			print "!!! This probably means that this ebuild's files must be downloaded"
			print "!!! manually.  See the comments in the ebuild for more information."
			print
			spawn("/usr/sbin/ebuild.sh nofetch")
			return 0
		return 1
	locations=mymirrors[:]
	filedict={}
	for myuri in myuris:
		myfile=os.path.basename(myuri)
		if not filedict.has_key(myfile):
			filedict[myfile]=[]
			for y in range(0,len(locations)):
				filedict[myfile].append(locations[y]+"/distfiles/"+myfile)
		if myuri[:9]=="mirror://":
			eidx = myuri.find("/", 9)
			if eidx != -1:
				mirrorname = myuri[9:eidx]
				if thirdpartymirrors.has_key(mirrorname):
					for locmirr in thirdpartymirrors[mirrorname]:
						filedict[myfile].append(locmirr+"/"+myuri[eidx+1:])		
		else:
				filedict[myfile].append(myuri)
	for myfile in filedict.keys():
		if listonly:
			fetched=0
			print ""
		for loc in filedict[myfile]:
			if listonly:
				print loc+" ",
				continue
			try:
				mystat=os.stat(settings["DISTDIR"]+"/"+myfile)
				if mydigests!=None and mydigests.has_key(myfile):
					#if we have the digest file, we know the final size and can resume the download.
					if mystat[ST_SIZE]<mydigests[myfile]["size"]:
						fetched=1
					else:
						#we already have it downloaded, skip.
						#if our file is bigger than the recorded size, digestcheck should catch it.
						fetched=2
				else:
					#we don't have the digest file, but the file exists.  Assume it is fully downloaded.
					fetched=2
			except (OSError,IOError),e:
				fetched=0
			if fetched!=2:
				#we either need to resume or start the download
				#you can't use "continue" when you're inside a "try" block
				if fetched==1:
					#resume mode:
					print ">>> Resuming download..."
					locfetch=resumecommand
				else:
					#normal mode:
					locfetch=fetchcommand
				print ">>> Downloading",loc
				myfetch=string.replace(locfetch,"${URI}",loc)
				myfetch=string.replace(myfetch,"${FILE}",myfile)
				myret=spawn(myfetch,free=1)
				if mydigests!=None and mydigests.has_key(myfile):
					try:
						mystat=os.stat(settings["DISTDIR"]+"/"+myfile)
						# no exception?  file exists. let digestcheck() report
						# an appropriately for size or md5 errors
						if myret and (mystat[ST_SIZE]<mydigests[myfile]["size"]):
							# Fetch failed... Try the next one... Kill 404 files though.
							if (mystat[ST_SIZE]<100000) and (len(myfile)>4) and not ((myfile[-5:]==".html") or (myfile[-4:]==".htm")):
								html404=re.compile("<title>.*(not found|404).*</title>",re.I|re.M)
								try:
									if html404.search(open(settings["DISTDIR"]+"/"+myfile).read()):
										try:
											os.unlink(settings["DISTDIR"]+"/"+myfile)
											print ">>> Deleting invalid distfile. (Improper 404 redirect from server.)"
										except:
											pass
								except:
									pass
							continue
						fetched=2
						break
					except (OSError,IOError),e:
						fetched=0
				else:
					if not myret:
						fetched=2
						break
		if (fetched!=2) and not listonly:
			print '!!! Couldn\'t download',myfile+". Aborting."
			return 0
	return 1

def digestgen(myarchives,overwrite=1):
	"""generates digest file if missing.  Assumes all files are available.	If
	overwrite=0, the digest will only be created if it doesn't already exist."""
	if not os.path.isdir(settings["FILESDIR"]):
		os.makedirs(settings["FILESDIR"])
		if "cvs" in features:
			print ">>> Auto-adding files/ dir to CVS..."
			spawn("cd "+settings["O"]+"; cvs add files",free=1)
	myoutfn=settings["FILESDIR"]+"/.digest-"+settings["PF"]
	myoutfn2=settings["FILESDIR"]+"/digest-"+settings["PF"]
	if (not overwrite) and os.path.exists(myoutfn2):
		return
	print ">>> Generating digest file..."

	try:
		outfile=open(myoutfn,"w")
	except IOError, e:
		print "!!! Filesystem error skipping generation. (Read-Only?)"
		print "!!! "+str(e)
		return
	
	for x in myarchives:
		myfile=settings["DISTDIR"]+"/"+x
		mymd5=perform_md5(myfile)
		mysize=os.stat(myfile)[ST_SIZE]
		#The [:-1] on the following line is to remove the trailing "L"
		outfile.write("MD5 "+mymd5+" "+x+" "+`mysize`[:-1]+"\n")	
	outfile.close()
	if not movefile(myoutfn,myoutfn2):
		print "!!! Failed to move digest."
		sys.exit(1)
	if "cvs" in features:
		print ">>> Auto-adding digest file to CVS..."
		spawn("cd "+settings["FILESDIR"]+"; cvs add digest-"+settings["PF"],free=1)
	print ">>> Computed message digests."
	
def digestcheck(myarchives):
	"Checks md5sums.  Assumes all files have been downloaded."
	if not myarchives:
		#No archives required; don't expect a digest
		return 1
	digestfn=settings["FILESDIR"]+"/digest-"+settings["PF"]
	if not os.path.exists(digestfn):
		if "digest" in features:
			print ">>> No message digest file found:",digestfn
			print ">>> \"digest\" mode enabled; auto-generating new digest..."
			digestgen(myarchives)
			return 1
		else:
			print "!!! No message digest file found:",digestfn
			print "!!! Type \"ebuild foo.ebuild digest\" to generate a digest."
			return 0
	myfile=open(digestfn,"r")
	mylines=myfile.readlines()
	mydigests={}
	for x in mylines:
		myline=string.split(x)
		if len(myline)<2:
			#invalid line
			continue
		mydigests[myline[2]]=[myline[1],myline[3]]
	for x in myarchives:
		if not mydigests.has_key(x):
			if "digest" in features:
				print ">>> No message digest entry found for archive \""+x+".\""
				print ">>> \"digest\" mode enabled; auto-generating new digest..."
				digestgen(myarchives)
				return 1
			else:
				print ">>> No message digest entry found for archive \""+x+".\""
				print "!!! Most likely a temporary problem. Try 'emerge rsync' again later."
				print "!!! If you are certain of the authenticity of the file then you may type"
				print "!!! the following to generate a new digest:"
				print "!!!   ebuild /usr/portage/category/package/package-version.ebuild digest" 
				return 0
		mymd5=perform_md5(settings["DISTDIR"]+"/"+x)
		if mymd5 != mydigests[x][0]:
			print
			print "!!!",x+": message digests do not match!"
			print "!!!",x,"is corrupt or incomplete."
			print ">>> our recorded digest:",mydigests[x][0]
			print ">>>  your file's digest:",mymd5
			print ">>> Please delete",settings["DISTDIR"]+"/"+x,"and refetch."
			print
			return 0
		else:
			print ">>> md5 ;-)",x
	return 1

def movefile(src,dest,newmtime=None,sstat=None):
	"""moves a file from src to dest, preserving all permissions and attributes; mtime will
	be preserved even when moving across filesystems.  Returns true on success and false on
	failure.  Move is atomic."""
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

def perform_md5(x, calc_prelink=0):
	return perform_checksum(x, calc_prelink)[0]


#######################################################################
#
# relparse()
#
# Parses the last elements of a version number into a triplet, that can
# later be compared:
#
#	'1.2_pre3'	-> [1.2, -2, 3.0]
#	'1.2b'		-> [1.2, 98, 0]
#	'1.2'		-> [1.2, 0, 0]
#

_package_weights_ = {"pre":-2,"p":0,"alpha":-4,"beta":-3,"rc":-1}	# dicts are unordered
_package_ends_    = ["pre", "p", "alpha", "beta", "rc"]			# so we need ordered list

def relparse(myver):
	"converts last version part into three components"
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
#
# ververify()
#
# Returns 1 if given a valid version string, else 0. Valid versions are in the format
#
#	<v1>.<v2>...<vx>[a-z,_{_package_weights_}[vy]]
#

_ververify_cache_={}

def ververify(myorigval,silent=1):
	# Lookup the cache first
	try:
		return _ververify_cache_[myorigval]
	except KeyError:
		pass

	if len(myorigval) == 0:
		if not silent:
			print "ERROR: package version is empty"
		_ververify_cache_[myorigval] = 0
		return 0
	myval = string.split(myorigval,'.')
	if len(myval)==0:
		if not silent:
			print "ERROR: package name has empty version string"
		_ververify_cache_[myorigval] = 0
		return 0
	# all but the last version must be a numeric
	for x in myval[:-1]:
		if not len(x):
			if not silent:
				print "ERROR: package version has two points in a row"
			_ververify_cache_[myorigval] = 0
			return 0
		try:
			foo = string.atoi(x)
		except:
			if not silent:
				print "ERROR: package version contains non-numeric '"+x+"'"
			_ververify_cache_[myorigval] = 0
			return 0
	if not len(myval[-1]):
			if not silent:
				print "ERROR: package version has trailing dot"
			_ververify_cache_[myorigval] = 0
			return 0
	try:
		foo = string.atoi(myval[-1])
		_ververify_cache_[myorigval] = 1
		return 1
	except:
		pass

	# ok, our last component is not a plain number or blank, let's continue
	if myval[-1][-1] in string.lowercase:
		try:
			foo = string.atoi(myval[-1][:-1])
			return 1
			_ververify_cache_[myorigval] = 1
			# 1a, 2.0b, etc.
		except:
			pass
	# ok, maybe we have a 1_alpha or 1_beta2; let's see
	ep=string.split(myval[-1],"_")
	if len(ep)!= 2:
		if not silent:
			print "ERROR: package version has more than one letter at then end"
		_ververify_cache_[myorigval] = 0
		return 0
	try:
		foo = string.atoi(ep[0])
	except:
		# this needs to be numeric, i.e. the "1" in "1_alpha"
		if not silent:
			print "ERROR: package version must have numeric part before the '_'"
		_ververify_cache_[myorigval] = 0
		return 0

	for mye in _package_ends_:
		if ep[1][0:len(mye)] == mye:
			if len(mye) == len(ep[1]):
				# no trailing numeric is ok
				_ververify_cache_[myorigval] = 1
				return 1
			else:
				try:
					foo = string.atoi(ep[1][len(mye):])
					_ververify_cache_[myorigval] = 1
					return 1
				except:
					# if no _package_weights_ work, *then* we return 0
					pass	
	if not silent:
		print "ERROR: package version extension after '_' is invalid"
	_ververify_cache_[myorigval] = 0
	return 0


def isjustname(mypkg):
	myparts = string.split(mypkg,'-')
	for x in myparts:
		if ververify(x):
			return 0
	return 1
