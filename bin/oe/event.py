#!/usr/bin/python
"""
OpenEmbedded 'Event' implementation

Classes and functions for manipulating 'events' in the
OpenEmbedded (http://openembedded.org) build infrastructure.

Copyright: (c) 2003 Chris Larson
"""

import os, re
class Event:
	"""Base class for events"""

NotHandled = 0
Handled = 1
handlers = []

def tmpHandler(event):
	"""Default handler for code events"""
	return NotHandled

def defaultTmpHandler():
	tmp = "def tmpHandler(e):\n\t\"\"\"heh\"\"\"\n\treturn 0" 
	comp = compile(tmp, "tmpHandler(e)", "exec")
	return comp

def fire(event):
	"""Fire off an Event"""
	for h in handlers:
		if type(h).__name__ == "code":
			exec(h)
			if tmpHandler(event) == Handled:
				return Handled
		else:
			if h(event) == Handled:
				return Handled
	return NotHandled

def register(handler):
	"""Register an Event handler"""
	if handler is not None:
		if type(handler).__name__ == "str":
			return registerCode(handler)
		handlers.append(handler)

def registerCode(handlerStr):
	"""Register a 'code' Event.
	   Deprecated interface; call register instead.

	   Expects to be passed python code as a string, which will
	   be passed in turn to compile() and then exec().  Note that
	   the code will be within a function, so should have had
	   appropriate tabbing put in place."""
	tmp = "def tmpHandler(e):\n%s" % handlerStr
	comp = compile(tmp, "tmpHandler(e)", "exec")
	handlers.append(comp)

def remove(handler):
	"""Remove an Event handler"""
	for h in handlers:
		if type(handler).__name__ == "str":
			return removeCode(handler)

		if handler is h:
			handlers.remove(handler)

def removeCode(handlerStr):
	"""Remove a 'code' Event handler
	   Deprecated interface; call remove instead."""
	tmp = "def tmpHandler(e):\n%s" % handlerStr
	comp = compile(tmp, "tmpHandler(e)", "exec")
	handlers.remove(comp)
