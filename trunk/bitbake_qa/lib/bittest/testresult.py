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

import types

__version__ = "0.0"


class TestItem:
    """
    A TestItem contains of the following:
    (
    tested_file  [String],
    test_result  [True,False],
    test_comment [String]
    )
    """
    def __init__(self,tested_file,test_result,test_comment):
        self._tested_file  = tested_file
        self._test_result  = test_result
        self._test_comment = test_comment

    def tested_file(self):
        return self._tested_file

    def test_result(self):
        return self._test_result

    def test_comment(self):
        return self._test_comment

class TestResult:
    """
    This class holds the testresults
    """

    def __init__(self, name):
        """
        name is the test name
        """
        self._test_name = name
        self._results   = []

    def test_name(self):
        return self._test_name

    def insert_result(self, item):
        """
        Insert item into the list of results. We will not
        enter item if item is None.
        If item is of type list we will add every element in the
        list to the list of test results
        """
        if item == None:
            return

        if type(item) == types.ListType:
            self._results.extend(item)
        else:
            self._results.append(item)

    def __iter__(self):
        return self._results.__iter__()

    def __getitem__(self,index):
        return self._results[index]

    def count(self):
        return self._results.count()

    def __len__(self):
        return self._results.__len__()


def _test():
    """
    Test the quite simple Test Data Types
    """
    import doctest


if __name__ == "__main__":
    _test()


