import asyncio
import collections

__version__ = '0.2.0'
__all__ = ['RWLock']


class _ContextManager:
    """Context manager.

    This enables the following idiom for acquiring and releasing a
    lock around a block:

        with (yield from lock):
            <block>

    while failing loudly when accidentally using:

        with lock:
            <block>
    """

    def __init__(self, lock):
        self._lock = lock

    def __enter__(self):
        # We have no use for the "as ..."  clause in the with
        # statement for locks.
        return None

    def __exit__(self, *args):
        try:
            self._lock.release()
        finally:
            self._lock = None  # Crudely prevent reuse.


# implementation based on:
# http://bugs.python.org/issue8800

# The internal lock object managing the RWLock state.
class _RWLockCore:

    def __init__(self, fast, loop):
        self._do_yield = not fast
        self._loop = loop or asyncio.get_event_loop()

        self._read_waiters = collections.deque()
        self._write_waiters = collections.deque()
        self._state = 0  # positive is shared count, negative exclusive count
        self._owning = []  # tasks will be few, so a list is not inefficient

    # Acquire the lock in read mode.
    @asyncio.coroutine
    def acquire_read(self):
        me = asyncio.Task.current_task(loop=self._loop)

        if me in self._owning:
            self._state += 1
            self._owning.append(me)
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True

        if not self._write_waiters and self._state >= 0:
            self._state += 1
            self._owning.append(me)
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True

        fut = asyncio.Future(loop=self._loop)
        self._read_waiters.append(fut)
        try:
            yield from fut
            self._state += 1
            self._owning.append(me)
            return True
        finally:
            self._read_waiters.remove(fut)

    # Acquire the lock in write mode.  A 'waiting' count is maintain ed,
    # ensurring that 'readers' will yield to writers.
    @asyncio.coroutine
    def acquire_write(self):
        me = asyncio.Task.current_task(loop=self._loop)

        if me in self._owning:
            if self._state > 0:
                raise RuntimeError("cannot upgrade RWLock from read to write")
            self._state -= 1
            self._owning.append(me)
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True

        if self._state == 0:
            self._state -= 1
            self._owning.append(me)
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True

        fut = asyncio.Future(loop=self._loop)
        self._write_waiters.append(fut)
        try:
            yield from fut
            self._state -= 1
            self._owning.append(me)
            return True
        finally:
            self._write_waiters.remove(fut)

    def release(self):
        me = asyncio.Task.current_task(loop=self._loop)
        try:
            self._owning.remove(me)
        except ValueError:
            raise RuntimeError("cannot release an un-acquired lock")
        if self._state > 0:
            self._state -= 1
        else:
            self._state += 1
        if self._state == 0:
            if self._write_waiters:
                self._write_waiters[0].set_result(None)
            elif self._read_waiters:
                self._read_waiters[0].set_result(None)


# Lock objects to access the _RWLockCore in reader or writer mode
class _ReaderLock:

    def __init__(self, lock):
        self._lock = lock

    @asyncio.coroutine
    def acquire(self):
        yield from self._lock.acquire_read()

    def release(self):
        self._lock.release()

    def __repr__(self):
        status = 'locked' if self._lock._state > 0 else 'unlocked'
        return "<ReaderLock: [{}]>".format(status)

    def __enter__(self):
        raise RuntimeError(
            '"yield from" should be used as context manager expression')

    def __exit__(self, *args):
        # This must exist because __enter__ exists, even though that
        # always raises; that's how the with-statement works.
        pass  # pragma: no cover

    def __iter__(self):
        # This is not a coroutine.  It is meant to enable the idiom:
        #
        #     with (yield from lock):
        #         <block>
        #
        # as an alternative to:
        #
        #     yield from lock.acquire()
        #     try:
        #         <block>
        #     finally:
        #         lock.release()
        yield from self.acquire()
        return _ContextManager(self)


class _WriterLock:

    def __init__(self, lock):
        self._lock = lock

    @asyncio.coroutine
    def acquire(self):
        yield from self._lock.acquire_write()

    def release(self):
        self._lock.release()

    def __repr__(self):
        status = 'locked' if self._lock._state < 0 else 'unlocked'
        return "<WriterLock: [{}]>".format(status)

    def __enter__(self):
        raise RuntimeError(
            '"yield from" should be used as context manager expression')

    def __exit__(self, *args):
        # This must exist because __enter__ exists, even though that
        # always raises; that's how the with-statement works.
        pass  # pragma: no cover

    def __iter__(self):
        # This is not a coroutine.  It is meant to enable the idiom:
        #
        #     with (yield from lock):
        #         <block>
        #
        # as an alternative to:
        #
        #     yield from lock.acquire()
        #     try:
        #         <block>
        #     finally:
        #         lock.release()
        yield from self.acquire()
        return _ContextManager(self)


class RWLock:
    # Doc shamelessly ripped off from Java
    """A RWLock maintains a pair of associated locks, one for read-only
    operations and one for writing. The read lock may be held simultaneously
    by multiple reader tasks, so long as there are no writers. The write
    lock is exclusive.
    """

    core = _RWLockCore

    def __init__(self, *, fast=False, loop=None):
        self._loop = loop or asyncio.get_event_loop()
        core = self.core(fast, self._loop)
        self._reader_lock = _ReaderLock(core)
        self._writer_lock = _WriterLock(core)

    @property
    def reader_lock(self):
        """The lock used for read, or shared, access"""
        return self._reader_lock

    @property
    def writer_lock(self):
        """The lock used for write, or exclusive, access"""
        return self._writer_lock

    def __repr__(self):
        return '<RWLock: {} {}>'.format(self.reader_lock.__repr__(),
                                        self.writer_lock.__repr__())
