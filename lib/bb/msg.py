# ex:ts=4:sw=4:sts=4:et
# -*- tab-width: 4; c-basic-offset: 4; indent-tabs-mode: nil -*-
"""
BitBake 'msg' implementation

Message handling infrastructure for bitbake

"""

# Copyright (C) 2006        Richard Purdie
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

import sys
import logging
import collections
from itertools import groupby
import warnings
import bb
import bb.event

class BBLogFormatter(logging.Formatter):
    """Formatter which ensures that our 'plain' messages (logging.INFO + 1) are used as is"""

    DEBUG3 = logging.DEBUG - 2
    DEBUG2 = logging.DEBUG - 1
    DEBUG = logging.DEBUG
    VERBOSE = logging.INFO - 1
    NOTE = logging.INFO
    PLAIN = logging.INFO + 1
    ERROR = logging.ERROR
    WARNING = logging.WARNING
    CRITICAL = logging.CRITICAL

    levelnames = {
        DEBUG3   : 'DEBUG',
        DEBUG2   : 'DEBUG',
        DEBUG   : 'DEBUG',
        VERBOSE: 'NOTE',
        NOTE    : 'NOTE',
        PLAIN  : '',
        WARNING : 'WARNING',
        ERROR   : 'ERROR',
        CRITICAL: 'ERROR',
    }

    def getLevelName(self, levelno):
        try:
            return self.levelnames[levelno]
        except KeyError:
            self.levelnames[levelno] = value = 'Level %d' % levelno
            return value

    def format(self, record):
        record.levelname = self.getLevelName(record.levelno)
        if record.levelno == self.PLAIN:
            msg = record.getMessage()
        else:
            msg = logging.Formatter.format(self, record)

        if hasattr(record, 'bb_exc_info'):
            etype, value, tb = record.bb_exc_info
            formatted = bb.exceptions.format_exception(etype, value, tb, limit=5)
            msg += '\n' + ''.join(formatted)
        return msg

class BBLogFilter(object):
    def __init__(self, handler, level, debug_domains):
        self.stdlevel = level
        self.debug_domains = debug_domains
        loglevel = level
        for domain in debug_domains:
            if debug_domains[domain] < loglevel:
                loglevel = debug_domains[domain]
        handler.setLevel(loglevel)
        handler.addFilter(self)

    def filter(self, record):
        if record.levelno >= self.stdlevel:
            return True
        if record.name in self.debug_domains and record.levelno >= self.debug_domains[record.name]:
            return True
        return False


class Loggers(dict):
    def __getitem__(self, key):
        if key in self:
            return dict.__getitem__(self, key)
        else:
            log = logging.getLogger("BitBake.%s" % domain._fields[key])
            dict.__setitem__(self, key, log)
            return log

def _NamedTuple(name, fields):
    Tuple = collections.namedtuple(name, " ".join(fields))
    return Tuple(*range(len(fields)))

domain = _NamedTuple("Domain", (
    "Default",
    "Build",
    "Cache",
    "Collection",
    "Data",
    "Depends",
    "Fetcher",
    "Parsing",
    "PersistData",
    "Provider",
    "RunQueue",
    "TaskData",
    "Util"))
logger = logging.getLogger("BitBake")
loggers = Loggers()

# Message control functions
#

loggerDefaultDebugLevel = 0
loggerDefaultVerbose = False
loggerDefaultDomains = []

def init_msgconfig(verbose, debug, debug_domains = []):
    """
    Set default verbosity and debug levels config the logger
    """
    bb.msg.loggerDebugLevel = debug
    bb.msg.loggerVerbose = verbose
    bb.msg.loggerDefaultDomains = debug_domains

def addDefaultlogFilter(handler):

    debug = loggerDefaultDebugLevel
    verbose = loggerDefaultVerbose
    domains = loggerDefaultDomains

    if debug:
        level = BBLogFormatter.DEBUG - debug + 1
    elif verbose:
        level = BBLogFormatter.VERBOSE
    else:
        level = BBLogFormatter.NOTE

    debug_domains = {}
    for (domainarg, iterator) in groupby(domains):
        dlevel = len(tuple(iterator))
        debug_domains["BitBake.%s" % domainarg] = logging.DEBUG - dlevel + 1
        for index, msgdomain in enumerate(domain._fields):
            if msgdomain == domainarg:
                break
        else:
            warn(None, "Logging domain %s is not valid, ignoring" % domainarg)

    BBLogFilter(handler, level, debug_domains)

#
# Message handling functions
#

def debug(level, msgdomain, msg):
    warnings.warn("bb.msg.debug is deprecated in favor of the python 'logging' module",
                  DeprecationWarning, stacklevel=2)
    level = logging.DEBUG - (level - 1)
    if not msgdomain:
        logger.debug(level, msg)
    else:
        loggers[msgdomain].debug(level, msg)

def plain(msg):
    warnings.warn("bb.msg.plain is deprecated in favor of the python 'logging' module",
                  DeprecationWarning, stacklevel=2)
    logger.plain(msg)

def note(level, msgdomain, msg):
    warnings.warn("bb.msg.note is deprecated in favor of the python 'logging' module",
                  DeprecationWarning, stacklevel=2)
    if level > 1:
        if msgdomain:
            logger.verbose(msg)
        else:
            loggers[msgdomain].verbose(msg)
    else:
        if msgdomain:
            logger.info(msg)
        else:
            loggers[msgdomain].info(msg)

def warn(msgdomain, msg):
    warnings.warn("bb.msg.warn is deprecated in favor of the python 'logging' module",
                  DeprecationWarning, stacklevel=2)
    if not msgdomain:
        logger.warn(msg)
    else:
        loggers[msgdomain].warn(msg)

def error(msgdomain, msg):
    warnings.warn("bb.msg.error is deprecated in favor of the python 'logging' module",
                  DeprecationWarning, stacklevel=2)
    if not msgdomain:
        logger.error(msg)
    else:
        loggers[msgdomain].error(msg)

def fatal(msgdomain, msg):
    if not msgdomain:
        logger.critical(msg)
    else:
        loggers[msgdomain].critical(msg)
    sys.exit(1)
