import logging
import signal
import subprocess

logger = logging.getLogger('BitBake.Process')

def subprocess_setup():
    # Python installs a SIGPIPE handler by default. This is usually not what
    # non-Python subprocesses expect.
    signal.signal(signal.SIGPIPE, signal.SIG_DFL)

class CmdError(RuntimeError):
    def __init__(self, command):
        self.command = command

    def __str__(self):
        if not isinstance(self.command, basestring):
            cmd = subprocess.list2cmdline(self.command)
        else:
            cmd = self.command

        return "Execution of '%s' failed" % cmd

class NotFoundError(CmdError):
    def __str__(self):
        return CmdError.__str__(self) + ": command not found"

class ExecutionError(CmdError):
    def __init__(self, command, exitcode, stdout = None, stderr = None):
        CmdError.__init__(self, command)
        self.exitcode = exitcode
        self.stdout = stdout
        self.stderr = stderr

    def __str__(self):
        message = ""
        if self.stderr:
            message += self.stderr
        if self.stdout:
            message += self.stdout
        if message:
            message = ":\n" + message
        return (CmdError.__str__(self) +
                " with exit code %s" % self.exitcode + message)

class Popen(subprocess.Popen):
    defaults = {
        "close_fds": True,
        "preexec_fn": subprocess_setup,
        "stdout": subprocess.PIPE,
        "stderr": subprocess.STDOUT,
        "stdin": subprocess.PIPE,
        "shell": False,
    }

    def __init__(self, *args, **kwargs):
        options = dict(self.defaults)
        options.update(kwargs)
        subprocess.Popen.__init__(self, *args, **options)

def _logged_communicate(pipe, log, input):
    bufsize = 512
    hasoutput = pipe.stdout is not None or pipe.stderr is not None
    if hasoutput:
        outdata, errdata = [], []
        while pipe.poll() is None:
            if pipe.stdout is not None:
                data = pipe.stdout.read(bufsize)
                if data is not None:
                    outdata.append(data)
                    log.write(data)

            if pipe.stderr is not None:
                data = pipe.stderr.read(bufsize)
                if data is not None:
                    errdata.append(data)
                    log.write(data)
        return ''.join(outdata), ''.join(errdata)

def run(cmd, input=None, **options):
    """Convenience function to run a command and return its output, raising an
    exception when the command fails"""

    if isinstance(cmd, basestring) and not "shell" in options:
        options["shell"] = True

    log = options.get('log')
    if log:
        del options['log']

    try:
        pipe = Popen(cmd, **options)
    except OSError, exc:
        if exc.errno == 2:
            raise NotFoundError(cmd)
        else:
            raise

    if log:
        stdout, stderr = _logged_communicate(pipe, log, input)
    else:
        stdout, stderr = pipe.communicate(input)

    if pipe.returncode != 0:
        raise ExecutionError(cmd, pipe.returncode, stdout, stderr)
    return stdout, stderr
