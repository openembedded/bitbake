"""
OpenEmbedded Parsers

File parsers for the OpenEmbedded 
(http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""
__version__ = '1.0'

__all__ = [ 'handlers', 'supports', 'handle', 'init', 'ConfHandler', 'OEHandler', 'SRPMHandler', 'ParseError' ]
handlers = []

class ParseError(Exception):
	"""Exception raised when parsing fails"""

class SkipPackage(Exception):
	"""Exception raised to skip this package"""

import ConfHandler
ConfHandler.ParseError = ParseError
import OEHandler
OEHandler.ParseError = ParseError
import SRPMHandler
SRPMHandler.ParseError = ParseError

def supports(fn, data):
	"""Returns true if we have a handler for this file, false otherwise"""
	for h in handlers:
		if h['supports'](fn, data):
			return 1
	return 0

def handle(fn, data, include = 0):
	"""Call the handler that is appropriate for this file"""
	for h in handlers:
		if h['supports'](fn, data):
			return h['handle'](fn, data, include)
	return None

def init(fn, data):
	for h in handlers:
		if h['supports'](fn):
			return h['init'](data)
