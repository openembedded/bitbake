import os,sys,logging
import signal, time, atexit, threading
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import xmlrpclib

try:
    import sqlite3
except ImportError:
    from pysqlite2 import dbapi2 as sqlite3

import bb.server.xmlrpc
import prserv
import prserv.db

logger = logging.getLogger("BitBake.PRserv")

if sys.hexversion < 0x020600F0:
    print("Sorry, python 2.6 or later is required.")
    sys.exit(1)

class Handler(SimpleXMLRPCRequestHandler):
    def _dispatch(self,method,params):
        try:
            value=self.server.funcs[method](*params)
        except:
            import traceback
            traceback.print_exc()
            raise
        return value

PIDPREFIX = "/tmp/PRServer_%s_%s.pid"
singleton = None

class PRServer(SimpleXMLRPCServer):
    def __init__(self, dbfile, logfile, interface, daemon=True):
        ''' constructor '''
        SimpleXMLRPCServer.__init__(self, interface,
                                    requestHandler=SimpleXMLRPCRequestHandler,
                                    logRequests=False, allow_none=True)
        self.dbfile=dbfile
        self.daemon=daemon
        self.logfile=logfile
        self.working_thread=None
        self.host, self.port = self.socket.getsockname()
        self.db=prserv.db.PRData(dbfile)
        self.table=self.db["PRMAIN"]
        self.pidfile=PIDPREFIX % (self.host, self.port)

        self.register_function(self.getPR, "getPR")
        self.register_function(self.quit, "quit")
        self.register_function(self.ping, "ping")
        self.register_function(self.export, "export")
        self.register_function(self.importone, "importone")
        self.register_introspection_functions()

    def export(self, version=None, pkgarch=None, checksum=None, colinfo=True):
        try:
            return self.table.export(version, pkgarch, checksum, colinfo)
        except sqlite3.Error as exc:
            logger.error(str(exc))
            return None

    def importone(self, version, pkgarch, checksum, value):
        return self.table.importone(version, pkgarch, checksum, value)

    def ping(self):
        return not self.quit

    def getinfo(self):
        return (self.host, self.port)

    def getPR(self, version, pkgarch, checksum):
        try:
            return self.table.getValue(version, pkgarch, checksum)
        except prserv.NotFoundError:
            logger.error("can not find value for (%s, %s)",version, checksum)
            return None
        except sqlite3.Error as exc:
            logger.error(str(exc))
            return None

    def quit(self):
        self.quit=True
        return

    def work_forever(self,):
        self.quit = False
        self.timeout = 0.5
        logger.info("PRServer: started! DBfile: %s, IP: %s, PORT: %s, PID: %s" %
                     (self.dbfile, self.host, self.port, str(os.getpid())))

        while not self.quit:
            self.handle_request()

        logger.info("PRServer: stopping...")
        self.server_close()
        return

    def start(self):
        if self.daemon is True:
            logger.info("PRServer: try to start daemon...")
            self.daemonize()
        else:
            atexit.register(self.delpid)
            pid = str(os.getpid()) 
            pf = file(self.pidfile, 'w+')
            pf.write("%s\n" % pid)
            pf.close()
            self.work_forever()

    def delpid(self):
        os.remove(self.pidfile)

    def daemonize(self):
        """
        See Advanced Programming in the UNIX, Sec 13.3
        """
        try:
            pid = os.fork()
            if pid > 0:
                #parent return instead of exit to give control 
                return
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        os.setsid()
        """
        fork again to make sure the daemon is not session leader, 
        which prevents it from acquiring controlling terminal
        """
        try:
            pid = os.fork()
            if pid > 0: #parent
                sys.exit(0)
        except OSError as e:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

        os.umask(0)
        os.chdir("/")

        sys.stdout.flush()
        sys.stderr.flush()
        si = file('/dev/null', 'r')
        so = file(self.logfile, 'a+')
        se = so
        os.dup2(si.fileno(),sys.stdin.fileno())
        os.dup2(so.fileno(),sys.stdout.fileno())
        os.dup2(se.fileno(),sys.stderr.fileno())

        # write pidfile
        atexit.register(self.delpid)
        pid = str(os.getpid()) 
        pf = file(self.pidfile, 'w')
        pf.write("%s\n" % pid)
        pf.close()

        self.work_forever()
        sys.exit(0)

class PRServSingleton():
    def __init__(self, dbfile, logfile, interface):
        self.dbfile = dbfile
        self.logfile = logfile
        self.interface = interface
        self.host = None
        self.port = None
        self.event = threading.Event()

    def _work(self):
        self.prserv = PRServer(self.dbfile, self.logfile, self.interface, False)
        self.host, self.port = self.prserv.getinfo()
        self.event.set()
        self.prserv.work_forever()
        del self.prserv.db

    def start(self):
        self.working_thread = threading.Thread(target=self._work)
        self.working_thread.start()

    def getinfo(self):
        self.event.wait()
        return (self.host, self.port)

class PRServerConnection():
    def __init__(self, host, port):
        if is_local_special(host, port):
            host, port = singleton.getinfo()
        self.host = host
        self.port = port
        self.connection = bb.server.xmlrpc._create_server(self.host, self.port)

    def terminate(self):
        # Don't wait for server indefinitely
        import socket
        socket.setdefaulttimeout(2)
        try:
            self.connection.quit()
        except Exception as exc:
            sys.stderr.write("%s\n" % str(exc))

    def getPR(self, version, pkgarch, checksum):
        return self.connection.getPR(version, pkgarch, checksum)

    def ping(self):
        return self.connection.ping()

    def export(self,version=None, pkgarch=None, checksum=None, colinfo=True):
        return self.connection.export(version, pkgarch, checksum, colinfo)

    def importone(self, version, pkgarch, checksum, value):
        return self.connection.importone(version, pkgarch, checksum, value)

def start_daemon(dbfile, host, port, logfile):
    pidfile = PIDPREFIX % (host, port)
    try:
        pf = file(pidfile,'r')
        pid = int(pf.readline().strip())
        pf.close()
    except IOError:
        pid = None

    if pid:
        sys.stderr.write("pidfile %s already exist. Daemon already running?\n"
                            % pidfile)
        return 1

    server = PRServer(os.path.abspath(dbfile), os.path.abspath(logfile), (host,port))
    server.start()
    return 0

def stop_daemon(host, port):
    pidfile = PIDPREFIX % (host, port)
    try:
        pf = file(pidfile,'r')
        pid = int(pf.readline().strip())
        pf.close()
    except IOError:
        pid = None

    if not pid:
        sys.stderr.write("pidfile %s does not exist. Daemon not running?\n"
                        % pidfile)

    try:
        PRServerConnection(host, port).terminate()
    except:
        logger.critical("Stop PRService %s:%d failed" % (host,port))
    time.sleep(0.5)

    try:
        if pid:
            if os.path.exists(pidfile):
                os.remove(pidfile)
            os.kill(pid,signal.SIGTERM)
            time.sleep(0.1)
    except OSError as e:
        err = str(e)
        if err.find("No such process") <= 0:
            raise e

    return 0

def is_local_special(host, port):
    if host.strip().upper() == 'localhost'.upper() and (not port):
        return True
    else:
        return False

def auto_start(d):
    global singleton
    if (not d.getVar('PRSERV_HOST', True)) or (not d.getVar('PRSERV_PORT', True)):
        return True

    if is_local_special(d.getVar('PRSERV_HOST', True), int(d.getVar('PRSERV_PORT', True))) and not singleton:
        import bb.utils
        cachedir = (d.getVar("PERSISTENT_DIR", True) or d.getVar("CACHE", True))
        if not cachedir:
            logger.critical("Please set the 'PERSISTENT_DIR' or 'CACHE' variable")
            sys.exit(1)
        bb.utils.mkdirhier(cachedir)
        dbfile = os.path.join(cachedir, "prserv.sqlite3")
        logfile = os.path.join(cachedir, "prserv.log")
        singleton = PRServSingleton(os.path.abspath(dbfile), os.path.abspath(logfile), ("localhost",0))
        singleton.start()
    if singleton:
        host, port = singleton.getinfo()
    else:
        host = d.getVar('PRSERV_HOST', True)
        port = int(d.getVar('PRSERV_PORT', True))

    try:
        return PRServerConnection(host,port).ping()
    except Exception:
        logger.critical("PRservice %s:%d not available" % (host, port))
    return False

def auto_shutdown(d=None):
    global singleton
    if singleton:
        host, port = singleton.getinfo()
        try:
            PRServerConnection(host, port).terminate()
        except:
            logger.critical("Stop PRService %s:%d failed" % (host,port))
        singleton = None

def ping(host, port):
    conn=PRServerConnection(host, port)
    return conn.ping()
