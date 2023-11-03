# Copyright (C) 2018-2019 Garmin Ltd.
#
# SPDX-License-Identifier: GPL-2.0-only
#

import asyncio
from contextlib import closing
import re
import itertools
import json
from urllib.parse import urlparse

UNIX_PREFIX = "unix://"
WS_PREFIX = "ws://"
WSS_PREFIX = "wss://"

ADDR_TYPE_UNIX = 0
ADDR_TYPE_TCP = 1
ADDR_TYPE_WS = 2


def parse_address(addr):
    if addr.startswith(UNIX_PREFIX):
        return (ADDR_TYPE_UNIX, (addr[len(UNIX_PREFIX) :],))
    elif addr.startswith(WS_PREFIX) or addr.startswith(WSS_PREFIX):
        return (ADDR_TYPE_WS, (addr,))
    else:
        m = re.match(r"\[(?P<host>[^\]]*)\]:(?P<port>\d+)$", addr)
        if m is not None:
            host = m.group("host")
            port = m.group("port")
        else:
            host, port = addr.split(":")

        return (ADDR_TYPE_TCP, (host, int(port)))


def create_server(addr, dbname, *, sync=True, upstream=None, read_only=False):
    def sqlite_engine():
        from .sqlite import DatabaseEngine

        return DatabaseEngine(dbname, sync)

    from . import server

    db_engine = sqlite_engine()

    s = server.Server(db_engine, upstream=upstream, read_only=read_only)

    (typ, a) = parse_address(addr)
    if typ == ADDR_TYPE_UNIX:
        s.start_unix_server(*a)
    elif typ == ADDR_TYPE_WS:
        url = urlparse(a[0])
        s.start_websocket_server(url.hostname, url.port)
    else:
        s.start_tcp_server(*a)

    return s


def create_client(addr):
    from . import client

    c = client.Client()

    (typ, a) = parse_address(addr)
    if typ == ADDR_TYPE_UNIX:
        c.connect_unix(*a)
    elif typ == ADDR_TYPE_WS:
        c.connect_websocket(*a)
    else:
        c.connect_tcp(*a)

    return c


async def create_async_client(addr):
    from . import client

    c = client.AsyncClient()

    (typ, a) = parse_address(addr)
    if typ == ADDR_TYPE_UNIX:
        await c.connect_unix(*a)
    elif typ == ADDR_TYPE_WS:
        await c.connect_websocket(*a)
    else:
        await c.connect_tcp(*a)

    return c
