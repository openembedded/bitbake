"""BitBake Persistent Data Store

Used to store data in a central location such that other threads/tasks can
access them at some future date.  Acts as a convenience wrapper around sqlite,
currently, providing a key/value store accessed by 'domain'.
"""

# Copyright (C) 2007        Richard Purdie
# Copyright (C) 2010        Chris Larson <chris_larson@mentor.com>
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

import collections
import logging
import os.path
import sys
import warnings
import bb.msg, bb.data, bb.utils

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

sqlversion = sqlite3.sqlite_version_info
if sqlversion[0] < 3 or (sqlversion[0] == 3 and sqlversion[1] < 3):
    raise Exception("sqlite3 version 3.3.0 or later is required.")


logger = logging.getLogger("BitBake.PersistData")
sqlite3.enable_shared_cache(True)


class SQLTable(collections.MutableMapping):
    """Object representing a table/domain in the database"""
    def __init__(self, cursor, table):
        self.cursor = cursor
        self.table = table

        self._execute("CREATE TABLE IF NOT EXISTS %s(key TEXT, value TEXT);"
                      % table)

    def _execute(self, *query):
        return self.cursor.execute(*query)

    def __getitem__(self, key):
        data = self._execute("SELECT * from %s where key=?;" %
                             self.table, [key])
        for row in data:
            return row[1]

    def __delitem__(self, key):
        self._execute("DELETE from %s where key=?;" % self.table, [key])

    def __setitem__(self, key, value):
        data = self._execute("SELECT * from %s where key=?;" %
                                   self.table, [key])
        exists = len(list(data))
        if exists:
            self._execute("UPDATE %s SET value=? WHERE key=?;" % self.table,
                          [value, key])
        else:
            self._execute("INSERT into %s(key, value) values (?, ?);" %
                          self.table, [key, value])

    def __contains__(self, key):
        return key in set(self)

    def __len__(self):
        data = self._execute("SELECT COUNT(key) FROM %s;" % self.table)
        for row in data:
            return row[0]

    def __iter__(self):
        data = self._execute("SELECT key FROM %s;" % self.table)
        return (row[0] for row in data)

    def values(self):
        return list(self.itervalues())

    def itervalues(self):
        data = self._execute("SELECT value FROM %s;" % self.table)
        return (row[0] for row in data)

    def items(self):
        return list(self.iteritems())

    def iteritems(self):
        return self._execute("SELECT * FROM %s;" % self.table)

    def clear(self):
        self._execute("DELETE FROM %s;" % self.table)


class PersistData(object):
    """Deprecated representation of the bitbake persistent data store"""
    def __init__(self, d):
        warnings.warn("Use of PersistData is deprecated.  Please use "
                      "persist(domain, d) instead.",
                      category=DeprecationWarning,
                      stacklevel=2)

        self.data = persist(d)
        logger.debug(1, "Using '%s' as the persistent data cache",
                     self.data.filename)

    def addDomain(self, domain):
        """
        Add a domain (pending deprecation)
        """
        return self.data[domain]

    def delDomain(self, domain):
        """
        Removes a domain and all the data it contains
        """
        del self.data[domain]

    def getKeyValues(self, domain):
        """
        Return a list of key + value pairs for a domain
        """
        return self.data[domain].items()

    def getValue(self, domain, key):
        """
        Return the value of a key for a domain
        """
        return self.data[domain][key]

    def setValue(self, domain, key, value):
        """
        Sets the value of a key for a domain
        """
        self.data[domain][key] = value

    def delValue(self, domain, key):
        """
        Deletes a key/value pair
        """
        del self.data[domain][key]

def connect(database):
    return sqlite3.connect(database, timeout=30, isolation_level=None)

def persist(domain, d):
    """Convenience factory for SQLTable objects based upon metadata"""
    cachedir = (bb.data.getVar("PERSISTENT_DIR", d, True) or
                bb.data.getVar("CACHE", d, True))
    if not cachedir:
        logger.critical("Please set the 'PERSISTENT_DIR' or 'CACHE' variable")
        sys.exit(1)

    bb.utils.mkdirhier(cachedir)
    cachefile = os.path.join(cachedir, "bb_persist_data.sqlite3")
    connection = connect(cachefile)
    return SQLTable(connection, domain)
