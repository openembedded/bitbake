#! /usr/bin/env python3
#
# Copyright (C) 2023 Garmin Ltd.
#
# SPDX-License-Identifier: GPL-2.0-only
#

import logging
from datetime import datetime

from sqlalchemy.ext.asyncio import create_async_engine
from sqlalchemy.pool import NullPool
from sqlalchemy import (
    MetaData,
    Column,
    Table,
    Text,
    Integer,
    UniqueConstraint,
    DateTime,
    Index,
    select,
    insert,
    exists,
    literal,
    and_,
    delete,
)
import sqlalchemy.engine
from sqlalchemy.orm import declarative_base
from sqlalchemy.exc import IntegrityError

logger = logging.getLogger("hashserv.sqlalchemy")

Base = declarative_base()


class UnihashesV2(Base):
    __tablename__ = "unihashes_v2"
    id = Column(Integer, primary_key=True, autoincrement=True)
    method = Column(Text, nullable=False)
    taskhash = Column(Text, nullable=False)
    unihash = Column(Text, nullable=False)

    __table_args__ = (
        UniqueConstraint("method", "taskhash"),
        Index("taskhash_lookup_v3", "method", "taskhash"),
    )


class OuthashesV2(Base):
    __tablename__ = "outhashes_v2"
    id = Column(Integer, primary_key=True, autoincrement=True)
    method = Column(Text, nullable=False)
    taskhash = Column(Text, nullable=False)
    outhash = Column(Text, nullable=False)
    created = Column(DateTime)
    owner = Column(Text)
    PN = Column(Text)
    PV = Column(Text)
    PR = Column(Text)
    task = Column(Text)
    outhash_siginfo = Column(Text)

    __table_args__ = (
        UniqueConstraint("method", "taskhash", "outhash"),
        Index("outhash_lookup_v3", "method", "outhash"),
    )


class DatabaseEngine(object):
    def __init__(self, url, username=None, password=None):
        self.logger = logger
        self.url = sqlalchemy.engine.make_url(url)

        if username is not None:
            self.url = self.url.set(username=username)

        if password is not None:
            self.url = self.url.set(password=password)

    async def create(self):
        self.logger.info("Using database %s", self.url)
        self.engine = create_async_engine(self.url, poolclass=NullPool)

        async with self.engine.begin() as conn:
            # Create tables
            logger.info("Creating tables...")
            await conn.run_sync(Base.metadata.create_all)

    def connect(self, logger):
        return Database(self.engine, logger)


def map_row(row):
    if row is None:
        return None
    return dict(**row._mapping)


class Database(object):
    def __init__(self, engine, logger):
        self.engine = engine
        self.db = None
        self.logger = logger

    async def __aenter__(self):
        self.db = await self.engine.connect()
        return self

    async def __aexit__(self, exc_type, exc_value, traceback):
        await self.close()

    async def close(self):
        await self.db.close()
        self.db = None

    async def get_unihash_by_taskhash_full(self, method, taskhash):
        statement = (
            select(
                OuthashesV2,
                UnihashesV2.unihash.label("unihash"),
            )
            .join(
                UnihashesV2,
                and_(
                    UnihashesV2.method == OuthashesV2.method,
                    UnihashesV2.taskhash == OuthashesV2.taskhash,
                ),
            )
            .where(
                OuthashesV2.method == method,
                OuthashesV2.taskhash == taskhash,
            )
            .order_by(
                OuthashesV2.created.asc(),
            )
            .limit(1)
        )
        self.logger.debug("%s", statement)
        async with self.db.begin():
            result = await self.db.execute(statement)
            return map_row(result.first())

    async def get_unihash_by_outhash(self, method, outhash):
        statement = (
            select(OuthashesV2, UnihashesV2.unihash.label("unihash"))
            .join(
                UnihashesV2,
                and_(
                    UnihashesV2.method == OuthashesV2.method,
                    UnihashesV2.taskhash == OuthashesV2.taskhash,
                ),
            )
            .where(
                OuthashesV2.method == method,
                OuthashesV2.outhash == outhash,
            )
            .order_by(
                OuthashesV2.created.asc(),
            )
            .limit(1)
        )
        self.logger.debug("%s", statement)
        async with self.db.begin():
            result = await self.db.execute(statement)
            return map_row(result.first())

    async def get_outhash(self, method, outhash):
        statement = (
            select(OuthashesV2)
            .where(
                OuthashesV2.method == method,
                OuthashesV2.outhash == outhash,
            )
            .order_by(
                OuthashesV2.created.asc(),
            )
            .limit(1)
        )

        self.logger.debug("%s", statement)
        async with self.db.begin():
            result = await self.db.execute(statement)
            return map_row(result.first())

    async def get_equivalent_for_outhash(self, method, outhash, taskhash):
        statement = (
            select(
                OuthashesV2.taskhash.label("taskhash"),
                UnihashesV2.unihash.label("unihash"),
            )
            .join(
                UnihashesV2,
                and_(
                    UnihashesV2.method == OuthashesV2.method,
                    UnihashesV2.taskhash == OuthashesV2.taskhash,
                ),
            )
            .where(
                OuthashesV2.method == method,
                OuthashesV2.outhash == outhash,
                OuthashesV2.taskhash != taskhash,
            )
            .order_by(
                OuthashesV2.created.asc(),
            )
            .limit(1)
        )
        self.logger.debug("%s", statement)
        async with self.db.begin():
            result = await self.db.execute(statement)
            return map_row(result.first())

    async def get_equivalent(self, method, taskhash):
        statement = select(
            UnihashesV2.unihash,
            UnihashesV2.method,
            UnihashesV2.taskhash,
        ).where(
            UnihashesV2.method == method,
            UnihashesV2.taskhash == taskhash,
        )
        self.logger.debug("%s", statement)
        async with self.db.begin():
            result = await self.db.execute(statement)
            return map_row(result.first())

    async def remove(self, condition):
        async def do_remove(table):
            where = {}
            for c in table.__table__.columns:
                if c.key in condition and condition[c.key] is not None:
                    where[c] = condition[c.key]

            if where:
                statement = delete(table).where(*[(k == v) for k, v in where.items()])
                self.logger.debug("%s", statement)
                async with self.db.begin():
                    result = await self.db.execute(statement)
                return result.rowcount

            return 0

        count = 0
        count += await do_remove(UnihashesV2)
        count += await do_remove(OuthashesV2)

        return count

    async def clean_unused(self, oldest):
        statement = delete(OuthashesV2).where(
            OuthashesV2.created < oldest,
            ~(
                select(UnihashesV2.id)
                .where(
                    UnihashesV2.method == OuthashesV2.method,
                    UnihashesV2.taskhash == OuthashesV2.taskhash,
                )
                .limit(1)
                .exists()
            ),
        )
        self.logger.debug("%s", statement)
        async with self.db.begin():
            result = await self.db.execute(statement)
            return result.rowcount

    async def insert_unihash(self, method, taskhash, unihash):
        statement = insert(UnihashesV2).values(
            method=method,
            taskhash=taskhash,
            unihash=unihash,
        )
        self.logger.debug("%s", statement)
        try:
            async with self.db.begin():
                await self.db.execute(statement)
            return True
        except IntegrityError:
            logger.debug(
                "%s, %s, %s already in unihash database", method, taskhash, unihash
            )
            return False

    async def insert_outhash(self, data):
        outhash_columns = set(c.key for c in OuthashesV2.__table__.columns)

        data = {k: v for k, v in data.items() if k in outhash_columns}

        if "created" in data and not isinstance(data["created"], datetime):
            data["created"] = datetime.fromisoformat(data["created"])

        statement = insert(OuthashesV2).values(**data)
        self.logger.debug("%s", statement)
        try:
            async with self.db.begin():
                await self.db.execute(statement)
            return True
        except IntegrityError:
            logger.debug(
                "%s, %s already in outhash database", data["method"], data["outhash"]
            )
            return False
