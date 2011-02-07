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
            return record.getMessage()
        else:
            return logging.Formatter.format(self, record)

class Loggers(dict):
    def __getitem__(self, key):
        if key in self:
            return dict.__getitem__(self, key)
        else:
            log = logging.getLogger("BitBake.%s" % domain._fields[key])
            dict.__setitem__(self, key, log)
            return log

class DebugLevel(dict):
    def __getitem__(self, key):
        if key == "default":
            key = domain.Default
        return get_debug_level(key)

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
debug_level = DebugLevel()

# Message control functions
#

def set_debug_level(level):
    for log in loggers.itervalues():
        log.setLevel(logging.NOTSET)

    if level:
        logger.setLevel(logging.DEBUG - level + 1)
    else:
        logger.setLevel(logging.INFO)

def get_debug_level(msgdomain = domain.Default):
    if not msgdomain:
        level = logger.getEffectiveLevel()
    else:
        level = loggers[msgdomain].getEffectiveLevel()
    return max(0, logging.DEBUG - level + 1)

def set_verbose(level):
    if level:
        logger.setLevel(BBLogFormatter.VERBOSE)
    else:
        logger.setLevel(BBLogFormatter.INFO)

def set_debug_domains(domainargs):
    for (domainarg, iterator) in groupby(domainargs):
        for index, msgdomain in enumerate(domain._fields):
            if msgdomain == domainarg:
                level = len(tuple(iterator))
                if level:
                    loggers[index].setLevel(logging.DEBUG - level + 1)
                break
        else:
            warn(None, "Logging domain %s is not valid, ignoring" % domainarg)

#
# Message handling functions
#

def debug(level, msgdomain, msg):
    warnings.warn("bb.msg.debug will soon be deprecated in favor of the python 'logging' module",
                  PendingDeprecationWarning, stacklevel=2)
    level = logging.DEBUG - (level - 1)
    if not msgdomain:
        logger.debug(level, msg)
    else:
        loggers[msgdomain].debug(level, msg)

def plain(msg):
    warnings.warn("bb.msg.plain will soon be deprecated in favor of the python 'logging' module",
                  PendingDeprecationWarning, stacklevel=2)
    logger.plain(msg)

def note(level, msgdomain, msg):
    warnings.warn("bb.msg.note will soon be deprecated in favor of the python 'logging' module",
                  PendingDeprecationWarning, stacklevel=2)
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
    warnings.warn("bb.msg.warn will soon be deprecated in favor of the python 'logging' module",
                  PendingDeprecationWarning, stacklevel=2)
    if not msgdomain:
        logger.warn(msg)
    else:
        loggers[msgdomain].warn(msg)

def error(msgdomain, msg):
    warnings.warn("bb.msg.error will soon be deprecated in favor of the python 'logging' module",
                  PendingDeprecationWarning, stacklevel=2)
    if not msgdomain:
        logger.error(msg)
    else:
        loggers[msgdomain].error(msg)

def fatal(msgdomain, msg):
    warnings.warn("bb.msg.fatal will soon be deprecated in favor of raising appropriate exceptions",
                  PendingDeprecationWarning, stacklevel=2)
    if not msgdomain:
        logger.critical(msg)
    else:
        loggers[msgdomain].critical(msg)
    sys.exit(1)
