import logging
import os.path
import errno
import sys
import warnings
import sqlite3

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

sqlversion = sqlite3.sqlite_version_info
if sqlversion[0] < 3 or (sqlversion[0] == 3 and sqlversion[1] < 3):
    raise Exception("sqlite3 version 3.3.0 or later is required.")

class NotFoundError(StandardError):
    pass

class PRTable():
    def __init__(self,cursor,table):
        self.cursor = cursor
        self.table = table

        #create the table
        self._execute("CREATE TABLE IF NOT EXISTS %s \
                    (version TEXT NOT NULL, \
                    checksum TEXT NOT NULL, \
                    value INTEGER, \
                    PRIMARY KEY (version,checksum));"
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
            except sqlite3.IntegrityError as exc:
                print "Integrity error %s" % str(exc)
                break

    def getValue(self, version, checksum):
        data=self._execute("SELECT value FROM %s WHERE version=? AND checksum=?;" % self.table,
                           (version,checksum))
        row=data.fetchone()
        if row != None:
            return row[0]
        else:
            #no value found, try to insert
            self._execute("INSERT INTO %s VALUES (?, ?, (select ifnull(max(value)+1,0) from %s where version=?));" 
                           % (self.table,self.table),
                           (version,checksum,version))
            data=self._execute("SELECT value FROM %s WHERE version=? AND checksum=?;" % self.table,
                               (version,checksum))
            row=data.fetchone()
            if row != None:
                return row[0]
            else:
                raise NotFoundError

class PRData(object):
    """Object representing the PR database"""
    def __init__(self, filename):
        self.filename=os.path.abspath(filename)
        #build directory hierarchy
        try:
            os.makedirs(os.path.dirname(self.filename))
        except OSError as e:
            if e.errno != errno.EEXIST:
                raise e
        self.connection=sqlite3.connect(self.filename, timeout=5,
                                          isolation_level=None)
        self.cursor=self.connection.cursor()
        self._tables={}

    def __del__(self):
        print "PRData: closing DB %s" % self.filename
        self.connection.close()

    def __getitem__(self,tblname):
        if not isinstance(tblname, basestring):
            raise TypeError("tblname argument must be a string, not '%s'" %
                            type(tblname))
        if tblname in self._tables:
            return self._tables[tblname]
        else:
            tableobj = self._tables[tblname] = PRTable(self.cursor, tblname)
            return tableobj

    def __delitem__(self, tblname):
        if tblname in self._tables:
            del self._tables[tblname]
        logging.info("drop table %s" % (tblname))
        self.cursor.execute("DROP TABLE IF EXISTS %s;" % tblname) 
