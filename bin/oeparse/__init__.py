"""
OpenEmbedded Parsers

File parsers for the OpenEmbedded 
(http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson

Based on functions from the base oe module, Copyright 2003 Holger Schurig
"""
__version__ = '1.0'

__all__ = [ 'handlers', 'supports', 'handle' ]
handlers = []

import ConfHandler
import OEHandler

def supports(fn):
	"""Returns true if we have a handler for this file, false otherwise"""
	for h in handlers:
		if h['supports'](fn):
			return True
	return False

def handle(fn, data = {}):
	"""Call the handler that is appropriate for this file"""
	for h in handlers:
		if h['supports'](fn):
			return h['handle'](fn, data)
	return None
