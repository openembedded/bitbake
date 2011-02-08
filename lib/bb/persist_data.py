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


class SQLTable(collections.MutableMapping):
    """Object representing a table/domain in the database"""
    def __init__(self, cursor, table):
        self.cursor = cursor
        self.table = table

        self._execute("CREATE TABLE IF NOT EXISTS %s(key TEXT, value TEXT);"
                      % table)

    def _execute(self, *query):
        """Execute a query, waiting to acquire a lock if necessary"""
        count = 0
        while True:
            try:
                return self.cursor.execute(*query)
            except sqlite3.OperationalError as exc:
                if 'database is locked' in str(exc) and count < 500:
                    count = count + 1
                    continue
                raise

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
        for row in data:
            yield row[0]

    def iteritems(self):
        data = self._execute("SELECT * FROM %s;" % self.table)
        for row in data:
            yield row[0], row[1]

    def itervalues(self):
        data = self._execute("SELECT value FROM %s;" % self.table)
        for row in data:
            yield row[0]


class SQLData(object):
    """Object representing the persistent data"""
    def __init__(self, filename):
        bb.utils.mkdirhier(os.path.dirname(filename))

        self.filename = filename
        self.connection = sqlite3.connect(filename, timeout=5,
                                          isolation_level=None)
        self.cursor = self.connection.cursor()
        self._tables = {}

    def __getitem__(self, table):
        if not isinstance(table, basestring):
            raise TypeError("table argument must be a string, not '%s'" %
                            type(table))

        if table in self._tables:
            return self._tables[table]
        else:
            tableobj = self._tables[table] = SQLTable(self.cursor, table)
            return tableobj

    def __delitem__(self, table):
        if table in self._tables:
            del self._tables[table]
        self.cursor.execute("DROP TABLE IF EXISTS %s;" % table)


class PersistData(object):
    """Deprecated representation of the bitbake persistent data store"""
    def __init__(self, d):
        warnings.warn("Use of PersistData will be deprecated in the future",
                      category=PendingDeprecationWarning,
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


def persist(d):
    """Convenience factory for construction of SQLData based upon metadata"""
    cachedir = (bb.data.getVar("PERSISTENT_DIR", d, True) or
                bb.data.getVar("CACHE", d, True))
    if not cachedir:
        logger.critical("Please set the 'PERSISTENT_DIR' or 'CACHE' variable")
        sys.exit(1)

    cachefile = os.path.join(cachedir, "bb_persist_data.sqlite3")
    return SQLData(cachefile)
