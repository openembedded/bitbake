# Copyright (C) 2019 Garmin Ltd.
#
# SPDX-License-Identifier: GPL-2.0-only
#

import logging
import socket
import bb.asyncrpc
from . import create_async_client


logger = logging.getLogger("hashserv.client")


class AsyncClient(bb.asyncrpc.AsyncClient):
    MODE_NORMAL = 0
    MODE_GET_STREAM = 1

    def __init__(self):
        super().__init__('OEHASHEQUIV', '1.1', logger)
        self.mode = self.MODE_NORMAL

    async def setup_connection(self):
        await super().setup_connection()
        cur_mode = self.mode
        self.mode = self.MODE_NORMAL
        await self._set_mode(cur_mode)

    async def send_stream(self, msg):
        async def proc():
            await self.socket.send(msg)
            return await self.socket.recv()

        return await self._send_wrapper(proc)

    async def _set_mode(self, new_mode):
        async def stream_to_normal():
            await self.socket.send("END")
            return await self.socket.recv()

        if new_mode == self.MODE_NORMAL and self.mode == self.MODE_GET_STREAM:
            r = await self._send_wrapper(stream_to_normal)
            if r != "ok":
                raise ConnectionError("Unable to transition to normal mode: Bad response from server %r" % r)
        elif new_mode == self.MODE_GET_STREAM and self.mode == self.MODE_NORMAL:
            r = await self.invoke({"get-stream": None})
            if r != "ok":
                raise ConnectionError("Unable to transition to stream mode: Bad response from server %r" % r)
        elif new_mode != self.mode:
            raise Exception(
                "Undefined mode transition %r -> %r" % (self.mode, new_mode)
            )

        self.mode = new_mode

    async def get_unihash(self, method, taskhash):
        await self._set_mode(self.MODE_GET_STREAM)
        r = await self.send_stream("%s %s" % (method, taskhash))
        if not r:
            return None
        return r

    async def report_unihash(self, taskhash, method, outhash, unihash, extra={}):
        await self._set_mode(self.MODE_NORMAL)
        m = extra.copy()
        m["taskhash"] = taskhash
        m["method"] = method
        m["outhash"] = outhash
        m["unihash"] = unihash
        return await self.invoke({"report": m})

    async def report_unihash_equiv(self, taskhash, method, unihash, extra={}):
        await self._set_mode(self.MODE_NORMAL)
        m = extra.copy()
        m["taskhash"] = taskhash
        m["method"] = method
        m["unihash"] = unihash
        return await self.invoke({"report-equiv": m})

    async def get_taskhash(self, method, taskhash, all_properties=False):
        await self._set_mode(self.MODE_NORMAL)
        return await self.invoke(
            {"get": {"taskhash": taskhash, "method": method, "all": all_properties}}
        )

    async def get_outhash(self, method, outhash, taskhash, with_unihash=True):
        await self._set_mode(self.MODE_NORMAL)
        return await self.invoke(
            {"get-outhash": {"outhash": outhash, "taskhash": taskhash, "method": method, "with_unihash": with_unihash}}
        )

    async def get_stats(self):
        await self._set_mode(self.MODE_NORMAL)
        return await self.invoke({"get-stats": None})

    async def reset_stats(self):
        await self._set_mode(self.MODE_NORMAL)
        return await self.invoke({"reset-stats": None})

    async def backfill_wait(self):
        await self._set_mode(self.MODE_NORMAL)
        return (await self.invoke({"backfill-wait": None}))["tasks"]

    async def remove(self, where):
        await self._set_mode(self.MODE_NORMAL)
        return await self.invoke({"remove": {"where": where}})

    async def clean_unused(self, max_age):
        await self._set_mode(self.MODE_NORMAL)
        return await self.invoke({"clean-unused": {"max_age_seconds": max_age}})


class Client(bb.asyncrpc.Client):
    def __init__(self):
        super().__init__()
        self._add_methods(
            "connect_tcp",
            "get_unihash",
            "report_unihash",
            "report_unihash_equiv",
            "get_taskhash",
            "get_outhash",
            "get_stats",
            "reset_stats",
            "backfill_wait",
            "remove",
            "clean_unused",
        )

    def _get_async_client(self):
        return AsyncClient()
