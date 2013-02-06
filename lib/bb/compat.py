"""Code pulled from future python versions, here for compatibility"""

from collections import MutableMapping, KeysView, ValuesView, ItemsView
try:
    from thread import get_ident as _get_ident
except ImportError:
    from dummy_thread import get_ident as _get_ident

def total_ordering(cls):
    """Class decorator that fills in missing ordering methods"""
    convert = {
        '__lt__': [('__gt__', lambda self, other: other < self),
                   ('__le__', lambda self, other: not other < self),
                   ('__ge__', lambda self, other: not self < other)],
        '__le__': [('__ge__', lambda self, other: other <= self),
                   ('__lt__', lambda self, other: not other <= self),
                   ('__gt__', lambda self, other: not self <= other)],
        '__gt__': [('__lt__', lambda self, other: other > self),
                   ('__ge__', lambda self, other: not other > self),
                   ('__le__', lambda self, other: not self > other)],
        '__ge__': [('__le__', lambda self, other: other >= self),
                   ('__gt__', lambda self, other: not other >= self),
                   ('__lt__', lambda self, other: not self >= other)]
    }
    roots = set(dir(cls)) & set(convert)
    if not roots:
        raise ValueError('must define at least one ordering operation: < > <= >=')
    root = max(roots)       # prefer __lt__ to __le__ to __gt__ to __ge__
    for opname, opfunc in convert[root]:
        if opname not in roots:
            opfunc.__name__ = opname
            opfunc.__doc__ = getattr(int, opname).__doc__
            setattr(cls, opname, opfunc)
    return cls

class OrderedDict(dict):
    'Dictionary that remembers insertion order'
    # An inherited dict maps keys to values.
    # The inherited dict provides __getitem__, __len__, __contains__, and get.
    # The remaining methods are order-aware.
    # Big-O running times for all methods are the same as regular dictionaries.

    # The internal self.__map dict maps keys to links in a doubly linked list.
    # The circular doubly linked list starts and ends with a sentinel element.
    # The sentinel element never gets deleted (this simplifies the algorithm).
    # Each link is stored as a list of length three:  [PREV, NEXT, KEY].

    def __init__(self, *args, **kwds):
        '''Initialize an ordered dictionary.  The signature is the same as
        regular dictionaries, but keyword arguments are not recommended because
        their insertion order is arbitrary.

        '''
        if len(args) > 1:
            raise TypeError('expected at most 1 arguments, got %d' % len(args))
        try:
            self.__root
        except AttributeError:
            self.__root = root = []                     # sentinel node
            root[:] = [root, root, None]
            self.__map = {}
        self.__update(*args, **kwds)

    def __setitem__(self, key, value, PREV=0, NEXT=1, dict_setitem=dict.__setitem__):
        'od.__setitem__(i, y) <==> od[i]=y'
        # Setting a new item creates a new link at the end of the linked list,
        # and the inherited dictionary is updated with the new key/value pair.
        if key not in self:
            root = self.__root
            last = root[PREV]
            last[NEXT] = root[PREV] = self.__map[key] = [last, root, key]
        dict_setitem(self, key, value)

    def __delitem__(self, key, PREV=0, NEXT=1, dict_delitem=dict.__delitem__):
        'od.__delitem__(y) <==> del od[y]'
        # Deleting an existing item uses self.__map to find the link which gets
        # removed by updating the links in the predecessor and successor nodes.
        dict_delitem(self, key)
        link_prev, link_next, key = self.__map.pop(key)
        link_prev[NEXT] = link_next
        link_next[PREV] = link_prev

    def __iter__(self):
        'od.__iter__() <==> iter(od)'
        # Traverse the linked list in order.
        NEXT, KEY = 1, 2
        root = self.__root
        curr = root[NEXT]
        while curr is not root:
            yield curr[KEY]
            curr = curr[NEXT]

    def __reversed__(self):
        'od.__reversed__() <==> reversed(od)'
        # Traverse the linked list in reverse order.
        PREV, KEY = 0, 2
        root = self.__root
        curr = root[PREV]
        while curr is not root:
            yield curr[KEY]
            curr = curr[PREV]

    def clear(self):
        'od.clear() -> None.  Remove all items from od.'
        for node in self.__map.itervalues():
            del node[:]
        root = self.__root
        root[:] = [root, root, None]
        self.__map.clear()
        dict.clear(self)

    # -- the following methods do not depend on the internal structure --

    def keys(self):
        'od.keys() -> list of keys in od'
        return list(self)

    def values(self):
        'od.values() -> list of values in od'
        return [self[key] for key in self]

    def items(self):
        'od.items() -> list of (key, value) pairs in od'
        return [(key, self[key]) for key in self]

    def iterkeys(self):
        'od.iterkeys() -> an iterator over the keys in od'
        return iter(self)

    def itervalues(self):
        'od.itervalues -> an iterator over the values in od'
        for k in self:
            yield self[k]

    def iteritems(self):
        'od.iteritems -> an iterator over the (key, value) pairs in od'
        for k in self:
            yield (k, self[k])

    update = MutableMapping.update

    __update = update # let subclasses override update without breaking __init__

    __marker = object()

    def pop(self, key, default=__marker):
        '''od.pop(k[,d]) -> v, remove specified key and return the corresponding
        value.  If key is not found, d is returned if given, otherwise KeyError
        is raised.

        '''
        if key in self:
            result = self[key]
            del self[key]
            return result
        if default is self.__marker:
            raise KeyError(key)
        return default

    def setdefault(self, key, default=None):
        'od.setdefault(k[,d]) -> od.get(k,d), also set od[k]=d if k not in od'
        if key in self:
            return self[key]
        self[key] = default
        return default

    def popitem(self, last=True):
        '''od.popitem() -> (k, v), return and remove a (key, value) pair.
        Pairs are returned in LIFO order if last is true or FIFO order if false.

        '''
        if not self:
            raise KeyError('dictionary is empty')
        key = next(reversed(self) if last else iter(self))
        value = self.pop(key)
        return key, value

    def __repr__(self, _repr_running={}):
        'od.__repr__() <==> repr(od)'
        call_key = id(self), _get_ident()
        if call_key in _repr_running:
            return '...'
        _repr_running[call_key] = 1
        try:
            if not self:
                return '%s()' % (self.__class__.__name__,)
            return '%s(%r)' % (self.__class__.__name__, self.items())
        finally:
            del _repr_running[call_key]

    def __reduce__(self):
        'Return state information for pickling'
        items = [[k, self[k]] for k in self]
        inst_dict = vars(self).copy()
        for k in vars(OrderedDict()):
            inst_dict.pop(k, None)
        if inst_dict:
            return (self.__class__, (items,), inst_dict)
        return self.__class__, (items,)

    def copy(self):
        'od.copy() -> a shallow copy of od'
        return self.__class__(self)

    @classmethod
    def fromkeys(cls, iterable, value=None):
        '''OD.fromkeys(S[, v]) -> New ordered dictionary with keys from S.
        If not specified, the value defaults to None.

        '''
        self = cls()
        for key in iterable:
            self[key] = value
        return self

    def __eq__(self, other):
        '''od.__eq__(y) <==> od==y.  Comparison to another OD is order-sensitive
        while comparison to a regular mapping is order-insensitive.

        '''
        if isinstance(other, OrderedDict):
            return len(self)==len(other) and self.items() == other.items()
        return dict.__eq__(self, other)

    def __ne__(self, other):
        'od.__ne__(y) <==> od!=y'
        return not self == other

    # -- the following methods support python 3.x style dictionary views --

    def viewkeys(self):
        "od.viewkeys() -> a set-like object providing a view on od's keys"
        return KeysView(self)

    def viewvalues(self):
        "od.viewvalues() -> an object providing a view on od's values"
        return ValuesView(self)

    def viewitems(self):
        "od.viewitems() -> a set-like object providing a view on od's items"
        return ItemsView(self)

# Multiprocessing pool code imported from python 2.7.3. Previous versions of 
# python have issues in this code which hang pool usage

#
# Module providing the `Pool` class for managing a process pool
#
# multiprocessing/pool.py
#
# Copyright (c) 2006-2008, R Oudkerk
# All rights reserved.
#
# Redistribution and use in source and binary forms, with or without
# modification, are permitted provided that the following conditions
# are met:
#
# 1. Redistributions of source code must retain the above copyright
#    notice, this list of conditions and the following disclaimer.
# 2. Redistributions in binary form must reproduce the above copyright
#    notice, this list of conditions and the following disclaimer in the
#    documentation and/or other materials provided with the distribution.
# 3. Neither the name of author nor the names of any contributors may be
#    used to endorse or promote products derived from this software
#    without specific prior written permission.
#
# THIS SOFTWARE IS PROVIDED BY THE AUTHOR AND CONTRIBUTORS "AS IS" AND
# ANY EXPRESS OR IMPLIED WARRANTIES, INCLUDING, BUT NOT LIMITED TO, THE
# IMPLIED WARRANTIES OF MERCHANTABILITY AND FITNESS FOR A PARTICULAR PURPOSE
# ARE DISCLAIMED.  IN NO EVENT SHALL THE AUTHOR OR CONTRIBUTORS BE LIABLE
# FOR ANY DIRECT, INDIRECT, INCIDENTAL, SPECIAL, EXEMPLARY, OR CONSEQUENTIAL
# DAMAGES (INCLUDING, BUT NOT LIMITED TO, PROCUREMENT OF SUBSTITUTE GOODS
# OR SERVICES; LOSS OF USE, DATA, OR PROFITS; OR BUSINESS INTERRUPTION)
# HOWEVER CAUSED AND ON ANY THEORY OF LIABILITY, WHETHER IN CONTRACT, STRICT
# LIABILITY, OR TORT (INCLUDING NEGLIGENCE OR OTHERWISE) ARISING IN ANY WAY
# OUT OF THE USE OF THIS SOFTWARE, EVEN IF ADVISED OF THE POSSIBILITY OF
# SUCH DAMAGE.
#
import threading
import Queue
import itertools
import collections
import time

import multiprocessing
from multiprocessing import Process, cpu_count, TimeoutError, pool
from multiprocessing.util import Finalize, debug

#
# Constants representing the state of a pool
#

RUN = 0
CLOSE = 1
TERMINATE = 2

#
# Miscellaneous
#

def mapstar(args):
    return map(*args)

class MaybeEncodingError(Exception):
    """Wraps possible unpickleable errors, so they can be
    safely sent through the socket."""

    def __init__(self, exc, value):
        self.exc = repr(exc)
        self.value = repr(value)
        super(MaybeEncodingError, self).__init__(self.exc, self.value)

    def __str__(self):
        return "Error sending result: '%s'. Reason: '%s'" % (self.value,
                                                             self.exc)

    def __repr__(self):
        return "<MaybeEncodingError: %s>" % str(self)

def worker(inqueue, outqueue, initializer=None, initargs=(), maxtasks=None):
    assert maxtasks is None or (type(maxtasks) == int and maxtasks > 0)
    put = outqueue.put
    get = inqueue.get
    if hasattr(inqueue, '_writer'):
        inqueue._writer.close()
        outqueue._reader.close()

    if initializer is not None:
        initializer(*initargs)

    completed = 0
    while maxtasks is None or (maxtasks and completed < maxtasks):
        try:
            task = get()
        except (EOFError, IOError):
            debug('worker got EOFError or IOError -- exiting')
            break

        if task is None:
            debug('worker got sentinel -- exiting')
            break

        job, i, func, args, kwds = task
        try:
            result = (True, func(*args, **kwds))
        except Exception, e:
            result = (False, e)
        try:
            put((job, i, result))
        except Exception as e:
            wrapped = MaybeEncodingError(e, result[1])
            debug("Possible encoding error while sending result: %s" % (
                wrapped))
            put((job, i, (False, wrapped)))
        completed += 1
    debug('worker exiting after %d tasks' % completed)


class Pool(object):
    '''
    Class which supports an async version of the `apply()` builtin
    '''
    Process = Process

    def __init__(self, processes=None, initializer=None, initargs=(),
                 maxtasksperchild=None):
        self._setup_queues()
        self._taskqueue = Queue.Queue()
        self._cache = {}
        self._state = RUN
        self._maxtasksperchild = maxtasksperchild
        self._initializer = initializer
        self._initargs = initargs

        if processes is None:
            try:
                processes = cpu_count()
            except NotImplementedError:
                processes = 1
        if processes < 1:
            raise ValueError("Number of processes must be at least 1")

        if initializer is not None and not hasattr(initializer, '__call__'):
            raise TypeError('initializer must be a callable')

        self._processes = processes
        self._pool = []
        self._repopulate_pool()

        self._worker_handler = threading.Thread(
            target=Pool._handle_workers,
            args=(self, )
            )
        self._worker_handler.daemon = True
        self._worker_handler._state = RUN
        self._worker_handler.start()


        self._task_handler = threading.Thread(
            target=Pool._handle_tasks,
            args=(self._taskqueue, self._quick_put, self._outqueue, self._pool)
            )
        self._task_handler.daemon = True
        self._task_handler._state = RUN
        self._task_handler.start()

        self._result_handler = threading.Thread(
            target=Pool._handle_results,
            args=(self._outqueue, self._quick_get, self._cache)
            )
        self._result_handler.daemon = True
        self._result_handler._state = RUN
        self._result_handler.start()

        self._terminate = Finalize(
            self, self._terminate_pool,
            args=(self._taskqueue, self._inqueue, self._outqueue, self._pool,
                  self._worker_handler, self._task_handler,
                  self._result_handler, self._cache),
            exitpriority=15
            )

    def _join_exited_workers(self):
        """Cleanup after any worker processes which have exited due to reaching
        their specified lifetime.  Returns True if any workers were cleaned up.
        """
        cleaned = False
        for i in reversed(range(len(self._pool))):
            worker = self._pool[i]
            if worker.exitcode is not None:
                # worker exited
                debug('cleaning up worker %d' % i)
                worker.join()
                cleaned = True
                del self._pool[i]
        return cleaned

    def _repopulate_pool(self):
        """Bring the number of pool processes up to the specified number,
        for use after reaping workers which have exited.
        """
        for i in range(self._processes - len(self._pool)):
            w = self.Process(target=worker,
                             args=(self._inqueue, self._outqueue,
                                   self._initializer,
                                   self._initargs, self._maxtasksperchild)
                            )
            self._pool.append(w)
            w.name = w.name.replace('Process', 'PoolWorker')
            w.daemon = True
            w.start()
            debug('added worker')

    def _maintain_pool(self):
        """Clean up any exited workers and start replacements for them.
        """
        if self._join_exited_workers():
            self._repopulate_pool()

    def _setup_queues(self):
        from multiprocessing.queues import SimpleQueue
        self._inqueue = SimpleQueue()
        self._outqueue = SimpleQueue()
        self._quick_put = self._inqueue._writer.send
        self._quick_get = self._outqueue._reader.recv

    def apply(self, func, args=(), kwds={}):
        '''
        Equivalent of `apply()` builtin
        '''
        assert self._state == RUN
        return self.apply_async(func, args, kwds).get()

    def map(self, func, iterable, chunksize=None):
        '''
        Equivalent of `map()` builtin
        '''
        assert self._state == RUN
        return self.map_async(func, iterable, chunksize).get()

    def imap(self, func, iterable, chunksize=1):
        '''
        Equivalent of `itertools.imap()` -- can be MUCH slower than `Pool.map()`
        '''
        assert self._state == RUN
        if chunksize == 1:
            result = IMapIterator(self._cache)
            self._taskqueue.put((((result._job, i, func, (x,), {})
                         for i, x in enumerate(iterable)), result._set_length))
            return result
        else:
            assert chunksize > 1
            task_batches = Pool._get_tasks(func, iterable, chunksize)
            result = IMapIterator(self._cache)
            self._taskqueue.put((((result._job, i, mapstar, (x,), {})
                     for i, x in enumerate(task_batches)), result._set_length))
            return (item for chunk in result for item in chunk)

    def imap_unordered(self, func, iterable, chunksize=1):
        '''
        Like `imap()` method but ordering of results is arbitrary
        '''
        assert self._state == RUN
        if chunksize == 1:
            result = IMapUnorderedIterator(self._cache)
            self._taskqueue.put((((result._job, i, func, (x,), {})
                         for i, x in enumerate(iterable)), result._set_length))
            return result
        else:
            assert chunksize > 1
            task_batches = Pool._get_tasks(func, iterable, chunksize)
            result = IMapUnorderedIterator(self._cache)
            self._taskqueue.put((((result._job, i, mapstar, (x,), {})
                     for i, x in enumerate(task_batches)), result._set_length))
            return (item for chunk in result for item in chunk)

    def apply_async(self, func, args=(), kwds={}, callback=None):
        '''
        Asynchronous equivalent of `apply()` builtin
        '''
        assert self._state == RUN
        result = ApplyResult(self._cache, callback)
        self._taskqueue.put(([(result._job, None, func, args, kwds)], None))
        return result

    def map_async(self, func, iterable, chunksize=None, callback=None):
        '''
        Asynchronous equivalent of `map()` builtin
        '''
        assert self._state == RUN
        if not hasattr(iterable, '__len__'):
            iterable = list(iterable)

        if chunksize is None:
            chunksize, extra = divmod(len(iterable), len(self._pool) * 4)
            if extra:
                chunksize += 1
        if len(iterable) == 0:
            chunksize = 0

        task_batches = Pool._get_tasks(func, iterable, chunksize)
        result = MapResult(self._cache, chunksize, len(iterable), callback)
        self._taskqueue.put((((result._job, i, mapstar, (x,), {})
                              for i, x in enumerate(task_batches)), None))
        return result

    @staticmethod
    def _handle_workers(pool):
        thread = threading.current_thread()

        # Keep maintaining workers until the cache gets drained, unless the pool
        # is terminated.
        while thread._state == RUN or (pool._cache and thread._state != TERMINATE):
            pool._maintain_pool()
            time.sleep(0.1)
        # send sentinel to stop workers
        pool._taskqueue.put(None)
        debug('worker handler exiting')

    @staticmethod
    def _handle_tasks(taskqueue, put, outqueue, pool):
        thread = threading.current_thread()

        for taskseq, set_length in iter(taskqueue.get, None):
            i = -1
            for i, task in enumerate(taskseq):
                if thread._state:
                    debug('task handler found thread._state != RUN')
                    break
                try:
                    put(task)
                except IOError:
                    debug('could not put task on queue')
                    break
            else:
                if set_length:
                    debug('doing set_length()')
                    set_length(i+1)
                continue
            break
        else:
            debug('task handler got sentinel')


        try:
            # tell result handler to finish when cache is empty
            debug('task handler sending sentinel to result handler')
            outqueue.put(None)

            # tell workers there is no more work
            debug('task handler sending sentinel to workers')
            for p in pool:
                put(None)
        except IOError:
            debug('task handler got IOError when sending sentinels')

        debug('task handler exiting')

    @staticmethod
    def _handle_results(outqueue, get, cache):
        thread = threading.current_thread()

        while 1:
            try:
                task = get()
            except (IOError, EOFError):
                debug('result handler got EOFError/IOError -- exiting')
                return

            if thread._state:
                assert thread._state == TERMINATE
                debug('result handler found thread._state=TERMINATE')
                break

            if task is None:
                debug('result handler got sentinel')
                break

            job, i, obj = task
            try:
                cache[job]._set(i, obj)
            except KeyError:
                pass

        while cache and thread._state != TERMINATE:
            try:
                task = get()
            except (IOError, EOFError):
                debug('result handler got EOFError/IOError -- exiting')
                return

            if task is None:
                debug('result handler ignoring extra sentinel')
                continue
            job, i, obj = task
            try:
                cache[job]._set(i, obj)
            except KeyError:
                pass

        if hasattr(outqueue, '_reader'):
            debug('ensuring that outqueue is not full')
            # If we don't make room available in outqueue then
            # attempts to add the sentinel (None) to outqueue may
            # block.  There is guaranteed to be no more than 2 sentinels.
            try:
                for i in range(10):
                    if not outqueue._reader.poll():
                        break
                    get()
            except (IOError, EOFError):
                pass

        debug('result handler exiting: len(cache)=%s, thread._state=%s',
              len(cache), thread._state)

    @staticmethod
    def _get_tasks(func, it, size):
        it = iter(it)
        while 1:
            x = tuple(itertools.islice(it, size))
            if not x:
                return
            yield (func, x)

    def __reduce__(self):
        raise NotImplementedError(
              'pool objects cannot be passed between processes or pickled'
              )

    def close(self):
        debug('closing pool')
        if self._state == RUN:
            self._state = CLOSE
            self._worker_handler._state = CLOSE

    def terminate(self):
        debug('terminating pool')
        self._state = TERMINATE
        self._worker_handler._state = TERMINATE
        self._terminate()

    def join(self):
        debug('joining pool')
        assert self._state in (CLOSE, TERMINATE)
        self._worker_handler.join()
        self._task_handler.join()
        self._result_handler.join()
        for p in self._pool:
            p.join()

    @staticmethod
    def _help_stuff_finish(inqueue, task_handler, size):
        # task_handler may be blocked trying to put items on inqueue
        debug('removing tasks from inqueue until task handler finished')
        inqueue._rlock.acquire()
        while task_handler.is_alive() and inqueue._reader.poll():
            inqueue._reader.recv()
            time.sleep(0)

    @classmethod
    def _terminate_pool(cls, taskqueue, inqueue, outqueue, pool,
                        worker_handler, task_handler, result_handler, cache):
        # this is guaranteed to only be called once
        debug('finalizing pool')

        worker_handler._state = TERMINATE
        task_handler._state = TERMINATE

        debug('helping task handler/workers to finish')
        cls._help_stuff_finish(inqueue, task_handler, len(pool))

        assert result_handler.is_alive() or len(cache) == 0

        result_handler._state = TERMINATE
        outqueue.put(None)                  # sentinel

        # We must wait for the worker handler to exit before terminating
        # workers because we don't want workers to be restarted behind our back.
        debug('joining worker handler')
        if threading.current_thread() is not worker_handler:
            worker_handler.join(1e100)

        # Terminate workers which haven't already finished.
        if pool and hasattr(pool[0], 'terminate'):
            debug('terminating workers')
            for p in pool:
                if p.exitcode is None:
                    p.terminate()

        debug('joining task handler')
        if threading.current_thread() is not task_handler:
            task_handler.join(1e100)

        debug('joining result handler')
        if threading.current_thread() is not result_handler:
            result_handler.join(1e100)

        if pool and hasattr(pool[0], 'terminate'):
            debug('joining pool workers')
            for p in pool:
                if p.is_alive():
                    # worker has not yet exited
                    debug('cleaning up worker %d' % p.pid)
                    p.join()

class ApplyResult(object):

    def __init__(self, cache, callback):
        self._cond = threading.Condition(threading.Lock())
        self._job = multiprocessing.pool.job_counter.next()
        self._cache = cache
        self._ready = False
        self._callback = callback
        cache[self._job] = self

    def ready(self):
        return self._ready

    def successful(self):
        assert self._ready
        return self._success

    def wait(self, timeout=None):
        self._cond.acquire()
        try:
            if not self._ready:
                self._cond.wait(timeout)
        finally:
            self._cond.release()

    def get(self, timeout=None):
        self.wait(timeout)
        if not self._ready:
            raise TimeoutError
        if self._success:
            return self._value
        else:
            raise self._value

    def _set(self, i, obj):
        self._success, self._value = obj
        if self._callback and self._success:
            self._callback(self._value)
        self._cond.acquire()
        try:
            self._ready = True
            self._cond.notify()
        finally:
            self._cond.release()
        del self._cache[self._job]

#
# Class whose instances are returned by `Pool.map_async()`
#

class MapResult(ApplyResult):

    def __init__(self, cache, chunksize, length, callback):
        ApplyResult.__init__(self, cache, callback)
        self._success = True
        self._value = [None] * length
        self._chunksize = chunksize
        if chunksize <= 0:
            self._number_left = 0
            self._ready = True
            del cache[self._job]
        else:
            self._number_left = length//chunksize + bool(length % chunksize)

    def _set(self, i, success_result):
        success, result = success_result
        if success:
            self._value[i*self._chunksize:(i+1)*self._chunksize] = result
            self._number_left -= 1
            if self._number_left == 0:
                if self._callback:
                    self._callback(self._value)
                del self._cache[self._job]
                self._cond.acquire()
                try:
                    self._ready = True
                    self._cond.notify()
                finally:
                    self._cond.release()

        else:
            self._success = False
            self._value = result
            del self._cache[self._job]
            self._cond.acquire()
            try:
                self._ready = True
                self._cond.notify()
            finally:
                self._cond.release()

#
# Class whose instances are returned by `Pool.imap()`
#

class IMapIterator(object):

    def __init__(self, cache):
        self._cond = threading.Condition(threading.Lock())
        self._job = multiprocessing.pool.job_counter.next()
        self._cache = cache
        self._items = collections.deque()
        self._index = 0
        self._length = None
        self._unsorted = {}
        cache[self._job] = self

    def __iter__(self):
        return self

    def next(self, timeout=None):
        self._cond.acquire()
        try:
            try:
                item = self._items.popleft()
            except IndexError:
                if self._index == self._length:
                    raise StopIteration
                self._cond.wait(timeout)
                try:
                    item = self._items.popleft()
                except IndexError:
                    if self._index == self._length:
                        raise StopIteration
                    raise TimeoutError
        finally:
            self._cond.release()

        success, value = item
        if success:
            return value
        raise value

    __next__ = next                    # XXX

    def _set(self, i, obj):
        self._cond.acquire()
        try:
            if self._index == i:
                self._items.append(obj)
                self._index += 1
                while self._index in self._unsorted:
                    obj = self._unsorted.pop(self._index)
                    self._items.append(obj)
                    self._index += 1
                self._cond.notify()
            else:
                self._unsorted[i] = obj

            if self._index == self._length:
                del self._cache[self._job]
        finally:
            self._cond.release()

    def _set_length(self, length):
        self._cond.acquire()
        try:
            self._length = length
            if self._index == self._length:
                self._cond.notify()
                del self._cache[self._job]
        finally:
            self._cond.release()

#
# Class whose instances are returned by `Pool.imap_unordered()`
#

class IMapUnorderedIterator(IMapIterator):

    def _set(self, i, obj):
        self._cond.acquire()
        try:
            self._items.append(obj)
            self._index += 1
            self._cond.notify()
            if self._index == self._length:
                del self._cache[self._job]
        finally:
            self._cond.release()


