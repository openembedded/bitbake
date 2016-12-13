"""
BitBake 'remotedata' module

Provides support for using a datastore from the bitbake client
"""

# Copyright (C) 2016  Intel Corporation
#
# This program is free software; you can redistribute it and/or modify
# it under the terms of the GNU General Public License version 2 as
# published by the Free Software Foundation.
#
# This program is distributed in the hope that it will be useful,
# but WITHOUT ANY WARRANTY; without even the implied warranty of
# MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
# GNU General Public License for more details.
#
# You should have received a copy of the GNU General Public License along
# with this program; if not, write to the Free Software Foundation, Inc.,
# 51 Franklin Street, Fifth Floor, Boston, MA 02110-1301 USA.

import bb.data

class RemoteDatastores:
    """Used on the server side to manage references to server-side datastores"""
    def __init__(self, cooker):
        self.cooker = cooker
        self.datastores = {}
        self.locked = []
        self.nextindex = 1

    def __len__(self):
        return len(self.datastores)

    def __getitem__(self, key):
        if key is None:
            return self.cooker.data
        else:
            return self.datastores[key]

    def items(self):
        return self.datastores.items()

    def store(self, d, locked=False):
        """
        Put a datastore into the collection. If locked=True then the datastore
        is understood to be managed externally and cannot be released by calling
        release().
        """
        idx = self.nextindex
        self.datastores[idx] = d
        if locked:
            self.locked.append(idx)
        self.nextindex += 1
        return idx

    def check_store(self, d, locked=False):
        """
        Put a datastore into the collection if it's not already in there;
        in either case return the index
        """
        for key, val in self.datastores.items():
            if val is d:
                idx = key
                break
        else:
            idx = self.store(d, locked)
        return idx

    def release(self, idx):
        """Discard a datastore in the collection"""
        if idx in self.locked:
            raise Exception('Tried to release locked datastore %d' % idx)
        del self.datastores[idx]
