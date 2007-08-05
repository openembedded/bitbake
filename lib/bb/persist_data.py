# BitBake Persistent Data Store
#
# Copyright (C) 2007        Richard Purdie
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

import bb, os

try:
    import sqlite3
except ImportError:
    try:
        from pysqlite2 import dbapi2 as sqlite3
    except ImportError:
        bb.msg.fatal(bb.msg.domain.PersistData, "Importing sqlite3 and pysqlite2 failed, please install one of them. A 'python-pysqlite2' like package is likely to be what you need.")

class PersistData:
    """
    BitBake Persistent Data Store

    Used to store data in a central location such that other threads/tasks can 
    access them at some future date.

    The "domain" is used as a key to isolate each data pool and in this 
    implementation corresponds to an SQL table. The SQL table consists of a 
    simple key and value pair.

    Why sqlite? It handles all the locking issues for us.
    """
    def __init__(self, d):
        self.cachedir = bb.data.getVar("CACHE", d, True)
        if self.cachedir in [None, '']:
            bb.msg.fatal(bb.msg.domain.PersistData, "Please set the 'CACHE' variable.")
        try:
            os.stat(self.cachedir)
        except OSError:
            bb.mkdirhier(self.cachedir)

        self.cachefile = os.path.join(self.cachedir,"bb_persist_data.sqlite3")
        bb.msg.debug(1, bb.msg.domain.PersistData, "Using '%s' as the persistent data cache" % self.cachefile)

        self.connection = sqlite3.connect(self.cachefile, timeout=5, isolation_level=None)

    def addDomain(self, domain):
        """
        Should be called before any domain is used
        Creates it if it doesn't exist.
        """
        self.connection.execute("CREATE TABLE IF NOT EXISTS %s(key TEXT, value TEXT);" % domain)

    def delDomain(self, domain):
        """
        Removes a domain and all the data it contains
        """
        self.connection.execute("DROP TABLE IF EXISTS %s;" % domain)

    def getValue(self, domain, key):
        """
        Return the value of a key for a domain
        """
        data = self.connection.execute("SELECT * from %s where key=?;" % domain, [key])
        for row in data:
            return row[1]

    def setValue(self, domain, key, value):
        """
        Sets the value of a key for a domain
        """
        data = self.connection.execute("SELECT * from %s where key=?;" % domain, [key])
        rows = 0
        for row in data:
            rows = rows + 1
        if rows:
            self._execute("UPDATE %s SET value=? WHERE key=?;" % domain, [value, key])
        else:
            self._execute("INSERT into %s(key, value) values (?, ?);" % domain, [key, value])

    def delValue(self, domain, key):
        """
        Deletes a key/value pair
        """
        self._execute("DELETE from %s where key=?;" % domain, [key])

    def _execute(self, *query):
        while True:	
            try:
                self.connection.execute(*query)
                return
            except sqlite3.OperationalError, e:
                if 'database is locked' in str(e):
                    continue
                raise
        
        

