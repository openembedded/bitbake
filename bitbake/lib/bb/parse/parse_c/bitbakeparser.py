"""

BitBake C Parser Python Code

Copyright (C) 2005 Holger Hans Peter Freyther

Permission is hereby granted, free of charge, to any person obtaining a copy
of this software and associated documentation files (the "Software"), to deal
in the Software without restriction, including without limitation the rights
to use, copy, modify, merge, publish, distribute, sublicense, and/or sell
copies of the Software, and to permit persons to whom the Software is
furnished to do so, subject to the following conditions:

The above copyright notice and this permission notice shall be included in all
copies or substantial portions of the Software.

THE SOFTWARE IS PROVIDED "AS IS", WITHOUT WARRANTY OF ANY KIND, EXPRESS OR
IMPLIED, INCLUDING BUT NOT LIMITED TO THE WARRANTIES OF MERCHANTABILITY,
FITNESS FOR A PARTICULAR PURPOSE AND NONINFRINGEMENT. IN NO EVENT
SHALL THE AUTHORS OR COPYRIGHT HOLDERS BE LIABLE FOR ANY CLAIM,
DAMAGES OR OTHER LIABILITY, WHETHER IN AN ACTION OF CONTRACT, TORT OR
OTHERWISE, ARISING FROM, OUT OF OR IN CONNECTION WITH THE SOFTWARE OR
THE USE OR OTHER DEALINGS IN THE SOFTWARE.
"""

__version__ = "0xdeadbeef"

class CParser:
    """
    The C-based Parser for Bitbake
    """
    def __init__(self, data, type):
        """
        Constructor
        """
        self._data = data

    def _syntax_error(self, file, line):
        """
        lemon/flex reports an syntax error to us and we will
        raise an exception
        """
        pass

    def _export(self, data):
        """
        EXPORT VAR = "MOO"
        we will now export VAR
        """
        pass

    def _assign(self, key, value):
        """
        VAR = "MOO"
        we will assign moo to VAR
        """
        pass

    def _assign(self, key, value):
        """
        """
        pass

    def _append(self, key, value):
        """
        VAR += "MOO"
        we will append " MOO" to var
        """
        pass

    def _prepend(self, key, value):
        """
        VAR =+ "MOO"
        we will prepend "MOO " to var
        """
        pass

    def _immediate(self, key, value):
        """
        VAR := "MOO ${CVSDATE}"
        we will assign immediately and expand vars
        """
        pass

    def _conditional(self, key, value):
        """
        """
        pass

    def _add_task(self, task, before = None, after = None):
        """
        """
        pass

    def _include(self, file):
        """
        """
        pass

    def _inherit(self, file):
        """
        """
        pass

    def _shell_procedure(self, name, body):
        """
        """
        pass

    def _python_procedure(self, name, body):
        """
        """
        pass

    def _fakeroot_procedure(self, name, body):
        """
        """
        pass

    def _def_procedure(self, a, b, c):
        """
        """
        pass

    def _export_func(self, name):
        """
        """
        pass

    def _add_handler(self, handler):
        """
        """
        pass
