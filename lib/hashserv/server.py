# Copyright (C) 2019 Garmin Ltd.
#
# SPDX-License-Identifier: GPL-2.0-only
#

from datetime import datetime, timedelta
import asyncio
import logging
import math
import time
from . import create_async_client
import bb.asyncrpc


logger = logging.getLogger("hashserv.server")


class Measurement(object):
    def __init__(self, sample):
        self.sample = sample

    def start(self):
        self.start_time = time.perf_counter()

    def end(self):
        self.sample.add(time.perf_counter() - self.start_time)

    def __enter__(self):
        self.start()
        return self

    def __exit__(self, *args, **kwargs):
        self.end()


class Sample(object):
    def __init__(self, stats):
        self.stats = stats
        self.num_samples = 0
        self.elapsed = 0

    def measure(self):
        return Measurement(self)

    def __enter__(self):
        return self

    def __exit__(self, *args, **kwargs):
        self.end()

    def add(self, elapsed):
        self.num_samples += 1
        self.elapsed += elapsed

    def end(self):
        if self.num_samples:
            self.stats.add(self.elapsed)
            self.num_samples = 0
            self.elapsed = 0


class Stats(object):
    def __init__(self):
        self.reset()

    def reset(self):
        self.num = 0
        self.total_time = 0
        self.max_time = 0
        self.m = 0
        self.s = 0
        self.current_elapsed = None

    def add(self, elapsed):
        self.num += 1
        if self.num == 1:
            self.m = elapsed
            self.s = 0
        else:
            last_m = self.m
            self.m = last_m + (elapsed - last_m) / self.num
            self.s = self.s + (elapsed - last_m) * (elapsed - self.m)

        self.total_time += elapsed

        if self.max_time < elapsed:
            self.max_time = elapsed

    def start_sample(self):
        return Sample(self)

    @property
    def average(self):
        if self.num == 0:
            return 0
        return self.total_time / self.num

    @property
    def stdev(self):
        if self.num <= 1:
            return 0
        return math.sqrt(self.s / (self.num - 1))

    def todict(self):
        return {
            k: getattr(self, k)
            for k in ("num", "total_time", "max_time", "average", "stdev")
        }


class ServerClient(bb.asyncrpc.AsyncServerConnection):
    def __init__(
        self,
        socket,
        db_engine,
        request_stats,
        backfill_queue,
        upstream,
        read_only,
    ):
        super().__init__(socket, "OEHASHEQUIV", logger)
        self.db_engine = db_engine
        self.request_stats = request_stats
        self.max_chunk = bb.asyncrpc.DEFAULT_MAX_CHUNK
        self.backfill_queue = backfill_queue
        self.upstream = upstream
        self.read_only = read_only

        self.handlers.update(
            {
                "get": self.handle_get,
                "get-outhash": self.handle_get_outhash,
                "get-stream": self.handle_get_stream,
                "get-stats": self.handle_get_stats,
                # Not always read-only, but internally checks if the server is
                # read-only
                "report": self.handle_report,
            }
        )

        if not read_only:
            self.handlers.update(
                {
                    "report-equiv": self.handle_equivreport,
                    "reset-stats": self.handle_reset_stats,
                    "backfill-wait": self.handle_backfill_wait,
                    "remove": self.handle_remove,
                    "clean-unused": self.handle_clean_unused,
                }
            )

    def validate_proto_version(self):
        return self.proto_version > (1, 0) and self.proto_version <= (1, 1)

    async def process_requests(self):
        async with self.db_engine.connect(self.logger) as db:
            self.db = db
            if self.upstream is not None:
                self.upstream_client = await create_async_client(self.upstream)
            else:
                self.upstream_client = None

            try:
                await super().process_requests()
            finally:
                if self.upstream_client is not None:
                    await self.upstream_client.close()

    async def dispatch_message(self, msg):
        for k in self.handlers.keys():
            if k in msg:
                self.logger.debug("Handling %s" % k)
                if "stream" in k:
                    return await self.handlers[k](msg[k])
                else:
                    with self.request_stats.start_sample() as self.request_sample, self.request_sample.measure():
                        return await self.handlers[k](msg[k])

        raise bb.asyncrpc.ClientError("Unrecognized command %r" % msg)

    async def handle_get(self, request):
        method = request["method"]
        taskhash = request["taskhash"]
        fetch_all = request.get("all", False)

        return await self.get_unihash(method, taskhash, fetch_all)

    async def get_unihash(self, method, taskhash, fetch_all=False):
        d = None

        if fetch_all:
            row = await self.db.get_unihash_by_taskhash_full(method, taskhash)
            if row is not None:
                d = {k: row[k] for k in row.keys()}
            elif self.upstream_client is not None:
                d = await self.upstream_client.get_taskhash(method, taskhash, True)
                await self.update_unified(d)
        else:
            row = await self.db.get_equivalent(method, taskhash)

            if row is not None:
                d = {k: row[k] for k in row.keys()}
            elif self.upstream_client is not None:
                d = await self.upstream_client.get_taskhash(method, taskhash)
                await self.db.insert_unihash(d["method"], d["taskhash"], d["unihash"])

        return d

    async def handle_get_outhash(self, request):
        method = request["method"]
        outhash = request["outhash"]
        taskhash = request["taskhash"]
        with_unihash = request.get("with_unihash", True)

        return await self.get_outhash(method, outhash, taskhash, with_unihash)

    async def get_outhash(self, method, outhash, taskhash, with_unihash=True):
        d = None
        if with_unihash:
            row = await self.db.get_unihash_by_outhash(method, outhash)
        else:
            row = await self.db.get_outhash(method, outhash)

        if row is not None:
            d = {k: row[k] for k in row.keys()}
        elif self.upstream_client is not None:
            d = await self.upstream_client.get_outhash(method, outhash, taskhash)
            await self.update_unified(d)

        return d

    async def update_unified(self, data):
        if data is None:
            return

        await self.db.insert_unihash(data["method"], data["taskhash"], data["unihash"])
        await self.db.insert_outhash(data)

    async def handle_get_stream(self, request):
        await self.socket.send_message("ok")

        while True:
            upstream = None

            l = await self.socket.recv()
            if not l:
                break

            try:
                # This inner loop is very sensitive and must be as fast as
                # possible (which is why the request sample is handled manually
                # instead of using 'with', and also why logging statements are
                # commented out.
                self.request_sample = self.request_stats.start_sample()
                request_measure = self.request_sample.measure()
                request_measure.start()

                if l == "END":
                    break

                (method, taskhash) = l.split()
                # self.logger.debug('Looking up %s %s' % (method, taskhash))
                row = await self.db.get_equivalent(method, taskhash)

                if row is not None:
                    msg = row["unihash"]
                    # self.logger.debug('Found equivalent task %s -> %s', (row['taskhash'], row['unihash']))
                elif self.upstream_client is not None:
                    upstream = await self.upstream_client.get_unihash(method, taskhash)
                    if upstream:
                        msg = upstream
                    else:
                        msg = ""
                else:
                    msg = ""

                await self.socket.send(msg)
            finally:
                request_measure.end()
                self.request_sample.end()

            # Post to the backfill queue after writing the result to minimize
            # the turn around time on a request
            if upstream is not None:
                await self.backfill_queue.put((method, taskhash))

        await self.socket.send("ok")
        return self.NO_RESPONSE

    async def report_readonly(self, data):
        method = data["method"]
        outhash = data["outhash"]
        taskhash = data["taskhash"]

        info = await self.get_outhash(method, outhash, taskhash)
        if info:
            unihash = info["unihash"]
        else:
            unihash = data["unihash"]

        return {
            "taskhash": taskhash,
            "method": method,
            "unihash": unihash,
        }

    async def handle_report(self, data):
        if self.read_only:
            return await self.report_readonly(data)

        outhash_data = {
            "method": data["method"],
            "outhash": data["outhash"],
            "taskhash": data["taskhash"],
            "created": datetime.now(),
        }

        for k in ("owner", "PN", "PV", "PR", "task", "outhash_siginfo"):
            if k in data:
                outhash_data[k] = data[k]

        # Insert the new entry, unless it already exists
        if await self.db.insert_outhash(outhash_data):
            # If this row is new, check if it is equivalent to another
            # output hash
            row = await self.db.get_equivalent_for_outhash(
                data["method"], data["outhash"], data["taskhash"]
            )

            if row is not None:
                # A matching output hash was found. Set our taskhash to the
                # same unihash since they are equivalent
                unihash = row["unihash"]
            else:
                # No matching output hash was found. This is probably the
                # first outhash to be added.
                unihash = data["unihash"]

                # Query upstream to see if it has a unihash we can use
                if self.upstream_client is not None:
                    upstream_data = await self.upstream_client.get_outhash(
                        data["method"], data["outhash"], data["taskhash"]
                    )
                    if upstream_data is not None:
                        unihash = upstream_data["unihash"]

            await self.db.insert_unihash(data["method"], data["taskhash"], unihash)

        unihash_data = await self.get_unihash(data["method"], data["taskhash"])
        if unihash_data is not None:
            unihash = unihash_data["unihash"]
        else:
            unihash = data["unihash"]

        return {
            "taskhash": data["taskhash"],
            "method": data["method"],
            "unihash": unihash,
        }

    async def handle_equivreport(self, data):
        await self.db.insert_unihash(data["method"], data["taskhash"], data["unihash"])

        # Fetch the unihash that will be reported for the taskhash. If the
        # unihash matches, it means this row was inserted (or the mapping
        # was already valid)
        row = await self.db.get_equivalent(data["method"], data["taskhash"])

        if row["unihash"] == data["unihash"]:
            self.logger.info(
                "Adding taskhash equivalence for %s with unihash %s",
                data["taskhash"],
                row["unihash"],
            )

        return {k: row[k] for k in ("taskhash", "method", "unihash")}

    async def handle_get_stats(self, request):
        return {
            "requests": self.request_stats.todict(),
        }

    async def handle_reset_stats(self, request):
        d = {
            "requests": self.request_stats.todict(),
        }

        self.request_stats.reset()
        return d

    async def handle_backfill_wait(self, request):
        d = {
            "tasks": self.backfill_queue.qsize(),
        }
        await self.backfill_queue.join()
        return d

    async def handle_remove(self, request):
        condition = request["where"]
        if not isinstance(condition, dict):
            raise TypeError("Bad condition type %s" % type(condition))

        return {"count": await self.db.remove(condition)}

    async def handle_clean_unused(self, request):
        max_age = request["max_age_seconds"]
        oldest = datetime.now() - timedelta(seconds=-max_age)
        return {"count": await self.db.clean_unused(oldest)}


class Server(bb.asyncrpc.AsyncServer):
    def __init__(self, db_engine, upstream=None, read_only=False):
        if upstream and read_only:
            raise bb.asyncrpc.ServerError(
                "Read-only hashserv cannot pull from an upstream server"
            )

        super().__init__(logger)

        self.request_stats = Stats()
        self.db_engine = db_engine
        self.upstream = upstream
        self.read_only = read_only
        self.backfill_queue = None

    def accept_client(self, socket):
        return ServerClient(
            socket,
            self.db_engine,
            self.request_stats,
            self.backfill_queue,
            self.upstream,
            self.read_only,
        )

    async def backfill_worker_task(self):
        async with await create_async_client(
            self.upstream
        ) as client, self.db_engine.connect(logger) as db:
            while True:
                item = await self.backfill_queue.get()
                if item is None:
                    self.backfill_queue.task_done()
                    break

                method, taskhash = item
                d = await client.get_taskhash(method, taskhash)
                if d is not None:
                    await db.insert_unihash(d["method"], d["taskhash"], d["unihash"])
                self.backfill_queue.task_done()

    def start(self):
        tasks = super().start()
        if self.upstream:
            self.backfill_queue = asyncio.Queue()
            tasks += [self.backfill_worker_task()]

        self.loop.run_until_complete(self.db_engine.create())

        return tasks

    async def stop(self):
        if self.backfill_queue is not None:
            await self.backfill_queue.put(None)
        await super().stop()
