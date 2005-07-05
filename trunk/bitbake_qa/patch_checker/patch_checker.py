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

from   bittest import TestItem
import bb, sys


class TestCase:
    def __init__(self):
        pass

    def test_name(self):
        return "Patch Checker"

    def test(self,file, data):
        """
        Run the Test now... some duplication of the base.bbclass
        """

        error = None

        try:
            bb.build.exec_func('do_unpack', data)
            bb.build.exec_func('do_patch',  data)

            try:
                bb.build.exec_func('do_clean', data)
            except:
                pass
        except bb.build.FuncFailed:
            error = """Function failed
Distro: %s
Machine: %s
OS: %s
ARCH: %s
FPU: %s
""" % (bb.data.getVar('DISTRO',data),bb.data.getVar('MACHINE',data),bb.data.getVar('TARGET_OS',data, True),bb.data.getVar('TARGET_ARCH',data, True),bb.data.getVar('TARGET_FPU',data, True))
        except bb.build.EventException:
            (type,value,traceback) = sys.exc_info()
            e = value.event
            error = """EventException %s
Distro: %s
Machine: %s
OS: %s
ARCH: %s
FPU: %s
""" % (bb.event.getName(e),bb.data.getVar('DISTRO',data),bb.data.getVar('MACHINE',data),bb.data.getVar('TARGET_OS',data, True),bb.data.getVar('TARGET_ARCH',data, True),bb.data.getVar('TARGET_FPU',data))



        return TestItem(file,error == None, error)
