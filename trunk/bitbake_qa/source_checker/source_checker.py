# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
#
#
# Copyright (C)       2005 Holger Hans Peter Freyther
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions are met:
#
#   Redistributions of source code must retain the above copyright notice,
#   this list of conditions and the following disclaimer.
#
#   Redistributions in binary form must reproduce the above copyright
#   notice, this list of conditions and the following disclaimer in the
#   documentation and/or other materials provided with the distribution.
#
#   Neither the name Holger Hans Peter Freyther nor the names of its
#   contributors may be used to endorse or promote products derived
#   from this software without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE COPYRIGHT HOLDERS AND CONTRIBUTORS
# "AS IS" AND ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT
# LIMITED TO, THE IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS
# FOR A PARTICULAR PURPOSE ARE DISCLAIMED. IN NO EVENT SHALL THE
# COPYRIGHT OWNER OR CONTRIBUTORS BE LIABLE FOR ANY DIRECT, INDIRECT,
# INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL DAMAGES
# (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS OR
# SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT,
# STRICT LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING
# IN ANY WAY OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE
# POSSIBILITY OF SUCH DAMAGE.

from bittest import TestItem
import bb
import os, sys

class TestCase:
    def __init__(self):
        pass

    def test_name(self):
        return "Source Checker"

    def generate_error(file, error):
        (type,value,traceback) = sys.exc_info()
        return TestItem(file,False,error % (value,type,traceback))
    generate_error = staticmethod(generate_error)

    def test(self,file, data):
        # we run the tests

        src_uri = bb.data.getVar('SRC_URI', data, 1)

        if not src_uri:
            return TestItem(file,True,"NO SRC_URI")

        try:
            bb.fetch.init(src_uri.split(), data)
        except bb.fetch.NoMethodError:
            return TestCase.generate_error(file,"""No Method Exception %s
Type: %s
Traceback: %s
""")
        try:
            bb.fetch.go(data)
        except bb.fetch.MissingParameterError:
            return TestCase.generate_error(file,"""Missing Parameter Error %s
Type: %s
Traceback: %s
""")
        except bb.fetch.FetchError:
            return TestCase.generate_error(file,"""Fetch Error %s
Type: %s
Traceback: %s
""")

        return TestItem(file,True,"")

