import os,shlex,string

class OEPackage:
	"OpenEmbedded package"

	data = {}
	
	def __init__(self):
		self.data["name"] = "generic package"
		self.data["version"] = "1.0"
		self.data["depends"] = ["libc6"]
		self.data["provides"] = [""]
		self.data["conflicts"] = [""]
		self.data["description"] = ""
		self.data["build"] = ""

	def build(self):
		print "Building %s..." % self.data["name"]
		os.system(self.data["build"])

	def ipk(self, tempdir = ""):
		print "Packaging (ipk) %s..." % self.data["name"]
		os.system("ipkg-build %s" % tempdir)

def parse_oe(filename, datadict):
	"""Parse .oe format file from filename, playing parsed key/value
	pairs into the dictionary passed as datadict"""
	f = open(filename,'r')
	lex = shlex.shlex(f)
	while 1:
		val=""
		line=""
		lex.wordchars = string.digits+string.letters+"~!@#$%*_\:;?,./-+()"
		lex.whitespace = " \t\r\n"
		lex.quotes = "\"'"
		key=lex.get_token()
		if (key==''):
			#normal end of file
			return
		equ=lex.get_token()
		if (equ==''):
			print lex.error_leader(filename, lex.lineno) + "unexpected end of file"
			return
		elif (equ=='='):
			# standard shell key/value pair .. this="that"
			val=lex.get_token()
			if (val==''):
				print lex.error_leader(filename, lex.lineno) + "unexpected end of file"
				return
		elif (equ=='()'):
			# found 'function' style key/value pair, parse accordingly
			lqt=lex.get_token()
			if (lqt != '{'):
				print lex.error_leader(filename, lex.lineno) + "error: %s unexpected, expected '{'" % lqt
				return
			lex.wordchars = string.printable
			lex.whitespace = "\n"
			while 1:
				line=lex.get_token()
				if(line == '}'):
					break
				if(line == ''):
					print lex.error_leader(filename, lex.lineno) + "unexpected end of file"
					return
				val+=line+"\n"
		else:
			print lex.error_leader(filename, lex.lineno) + "invalid token: " + equ
			return
	
#		print "%s = %s" % (key, val)
		datadict[key] = val
