import os,sys,logging
import signal,time, atexit
from SimpleXMLRPCServer import SimpleXMLRPCServer, SimpleXMLRPCRequestHandler
import xmlrpclib,sqlite3

import bb.server.xmlrpc
import prserv
import prserv.db

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

class PRServer(SimpleXMLRPCServer):
    pidfile="/tmp/PRServer.pid"
    def __init__(self, dbfile, logfile, interface, daemon=True):
        ''' constructor '''
        SimpleXMLRPCServer.__init__(self, interface,
                                    requestHandler=SimpleXMLRPCRequestHandler,
                                    logRequests=False, allow_none=True)
        self.dbfile=dbfile
        self.daemon=daemon
        self.logfile=logfile
        self.host, self.port = self.socket.getsockname()
        self.db=prserv.db.PRData(dbfile)
        self.table=self.db["PRMAIN"]
        self.pidfile=PIDPREFIX % interface

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
            logging.error(str(exc))
            return None

    def importone(self, version, pkgarch, checksum, value):
        return self.table.importone(version, pkgarch, checksum, value)

    def ping(self):
        return not self.quit

    def getPR(self, version, pkgarch, checksum):
        try:
            return self.table.getValue(version, pkgarch, checksum)
        except prserv.NotFoundError:
            logging.error("can not find value for (%s, %s)",version, checksum)
            return None
        except sqlite3.Error as exc:
            logging.error(str(exc))
            return None

    def quit(self):
        self.quit=True
        return

    def _serve_forever(self):
        self.quit = False
        self.timeout = 0.5
        while not self.quit:
            self.handle_request()

        logging.info("PRServer: stopping...")
        self.server_close()
        return

    def start(self):
        if self.daemon is True:
            logging.info("PRServer: try to start daemon...")
            self.daemonize()
        else:
            atexit.register(self.delpid)
            pid = str(os.getpid()) 
            pf = file(self.pidfile, 'w+')
            pf.write("%s\n" % pid)
            pf.write("%s\n" % self.host)
            pf.write("%s\n" % self.port)
            pf.close()
            logging.info("PRServer: start success! DBfile: %s, IP: %s, PORT: %d" % 
                     (self.dbfile, self.host, self.port))
            self._serve_forever()

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

        logging.info("PRServer: starting daemon success! DBfile: %s, IP: %s, PORT: %s, PID: %s" % 
                     (self.dbfile, self.host, self.port, pid))

        self._serve_forever()
        exit(0)

class PRServerConnection():
    def __init__(self, host, port):
        self.connection = bb.server.xmlrpc._create_server(host, port)
        self.host = host
        self.port = port

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

def start_daemon(dbfile, logfile, interface):
    try:
        pf = file(PRServer.pidfile,'r')
        pid = int(pf.readline().strip())
        pf.close()
    except IOError:
        pid = None

    if pid:
        sys.stderr.write("pidfile %s already exist. Daemon already running?\n"
                            % PRServer.pidfile)
        return 1

    server = PRServer(os.path.abspath(dbfile), os.path.abspath(logfile), interface)
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
        return 1

    PRServerConnection(host, port).terminate()
    time.sleep(0.5)

    try:
        while 1:
            os.kill(pid,signal.SIGTERM)
            time.sleep(0.1)
    except OSError as e:
        err = str(e)
        if err.find("No such process") > 0:
            if os.path.exists(PRServer.pidfile):
                os.remove(PRServer.pidfile)
        else:
            raise Exception("%s [%d]" % (e.strerror, e.errno))

    return 0

def ping(host, port):
    print PRServerConnection(host,port).ping()
    return 0
