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

        self.register_function(self.getPR, "getPR")
        self.register_function(self.quit, "quit")
        self.register_function(self.ping, "ping")
        self.register_introspection_functions()

    def ping(self):
        return not self.quit
 
    def getPR(self, version, checksum):
        try:
            return self.table.getValue(version,checksum)
        except prserv.NotFoundError:
            logging.error("can not find value for (%s, %s)",version,checksum)
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
            logging.info("PRServer: starting daemon...")
            self.daemonize()
        else:
            logging.info("PRServer: starting...")
            self._serve_forever()

    def delpid(self):
        os.remove(PRServer.pidfile)

    def daemonize(self):
        """
        See Advanced Programming in the UNIX, Sec 13.3
        """
        os.umask(0)

        try:
            pid = os.fork()
            if pid > 0: 
                sys.exit(0)
        except OSError as e:
            sys.stderr.write("1st fork failed: %d %s\n" % (e.errno, e.strerror))
            sys.exit(1)

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
            sys.stderr.write("2nd fork failed: %d %s\n" % (e.errno, e.strerror))
            sys.exit(1)

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
        pf = file(PRServer.pidfile, 'w+')
        pf.write("%s\n" % pid)
        pf.write("%s\n" % self.host)
        pf.write("%s\n" % self.port)
        pf.close()

        self._serve_forever()

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
        except:
            pass

    def getPR(self, version, checksum):
        return self.connection.getPR(version, checksum)

    def ping(self):
        return self.connection.ping()

def start_daemon(options):
    try:
        pf = file(PRServer.pidfile,'r')
        pid = int(pf.readline().strip())
        pf.close()
    except IOError:
        pid = None

    if pid:
        sys.stderr.write("pidfile %s already exist. Daemon already running?\n"
                            % PRServer.pidfile)
        sys.exit(1)

    server = PRServer(options.dbfile, interface=(options.host, options.port),
                      logfile=os.path.abspath(options.logfile))
    server.start()

def stop_daemon():
    try:
        pf = file(PRServer.pidfile,'r')
        pid = int(pf.readline().strip())
        host = pf.readline().strip()
        port = int(pf.readline().strip())
        pf.close()
    except IOError:
        pid = None

    if not pid:
        sys.stderr.write("pidfile %s does not exist. Daemon not running?\n"
                        % PRServer.pidfile)
        sys.exit(1)

    PRServerConnection(host,port).terminate()
    time.sleep(0.5)

    try:
        while 1:
            os.kill(pid,signal.SIGTERM)
            time.sleep(0.1)
    except OSError as err:
        err = str(err)
        if err.find("No such process") > 0:
            if os.path.exists(PRServer.pidfile):
                os.remove(PRServer.pidfile)
        else:
            print err
            sys.exit(1)

