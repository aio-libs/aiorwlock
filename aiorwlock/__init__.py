import asyncio
import collections
import sys

__version__ = '0.5.0'
__all__ = ['RWLock']

PY_35 = sys.version_info >= (3, 5, 0)


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


def create_future(loop):
    """Compatibility wrapper for the loop.create_future() call introduced in
    3.5.2."""
    if hasattr(loop, 'create_future'):
        return loop.create_future()
    else:
        return asyncio.Future(loop=loop)


# implementation based on:
# http://bugs.python.org/issue8800

# The internal lock object managing the RWLock state.
class _RWLockCore:
    _RL = 1
    _WL = 2

    def __init__(self, fast, loop):
        self._do_yield = not fast
        self._loop = loop or asyncio.get_event_loop()

        self._read_waiters = collections.deque()
        self._write_waiters = collections.deque()
        self._r_state = 0
        self._w_state = 0
        self._owning = []  # tasks will be few, so a list is not inefficient

    @property
    def read_locked(self):
        return self._r_state > 0

    @property
    def write_locked(self):
        return self._w_state > 0

    # Acquire the lock in read mode.
    @asyncio.coroutine
    def acquire_read(self):
        me = asyncio.Task.current_task(loop=self._loop)

        if (me, self._RL) in self._owning or (me, self._WL) in self._owning:
            self._r_state += 1
            self._owning.append((me, self._RL))
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True

        if (not self._write_waiters and
                self._r_state >= 0 and self._w_state == 0):
            self._r_state += 1
            self._owning.append((me, self._RL))
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True

        fut = create_future(self._loop)
        self._read_waiters.append(fut)
        try:
            yield from fut
            self._r_state += 1
            self._owning.append((me, self._RL))
            return True

        except asyncio.CancelledError:
            self._wake_up()
            raise

        finally:
            self._read_waiters.remove(fut)

    # Acquire the lock in write mode.  A 'waiting' count is maintain ed,
    # ensurring that 'readers' will yield to writers.
    @asyncio.coroutine
    def acquire_write(self):
        me = asyncio.Task.current_task(loop=self._loop)

        if (me, self._WL) in self._owning:
            self._w_state += 1
            self._owning.append((me, self._WL))
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True
        elif (me, self._RL) in self._owning:
            if self._r_state > 0:
                raise RuntimeError("cannot upgrade RWLock from read to write")

        if self._r_state == 0 and self._w_state == 0:
            self._w_state += 1
            self._owning.append((me, self._WL))
            if self._do_yield:
                yield from asyncio.sleep(0.0, loop=self._loop)
            return True

        fut = create_future(self._loop)
        self._write_waiters.append(fut)
        try:
            yield from fut
            self._w_state += 1
            self._owning.append((me, self._WL))
            return True

        except asyncio.CancelledError:
            self._wake_up()
            raise

        finally:
            self._write_waiters.remove(fut)

    def release_read(self):
        self._release(self._RL)

    def release_write(self):
        self._release(self._WL)

    def _release(self, lock_type):
        me = asyncio.Task.current_task(loop=self._loop)
        try:
            self._owning.remove((me, lock_type))
        except ValueError:
            raise RuntimeError("cannot release an un-acquired lock")
        if lock_type == self._RL:
            self._r_state -= 1
        else:
            self._w_state -= 1
        self._wake_up()

    def _wake_up(self):
        '''If no one is reading or writing, wake up write waiters
        first, only one write waiter should be waken up, if no
        write waiters and have read waiters, wake up all read waiters.
        '''
        if self._r_state == 0 and self._w_state == 0:
            if self._write_waiters:
                # Only wake up one write writer
                self._wake_up_first(self._write_waiters)
            elif self._read_waiters:
                # Wake up all read waiters
                self._wake_up_all(self._read_waiters)

    def _wake_up_first(self, waiters):
        """Wake up the first waiter who isn't cancelled."""
        for fut in waiters:
            if not fut.done():
                fut.set_result(None)
                break
 
    def _wake_up_all(self, waiters):
        '''Wake up all waiters'''
        for fut in waiters:
            if not fut.done():
                fut.set_result(None)


class _ContextManagerMixin:

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

    if PY_35:

        def __await__(self):
            # To make "with await lock" work.
            yield from self.acquire()
            return _ContextManager(self)

        @asyncio.coroutine
        def __aenter__(self):
            yield from self.acquire()
            # We have no use for the "as ..."  clause in the with
            # statement for locks.
            return None

        @asyncio.coroutine
        def __aexit__(self, exc_type, exc, tb):
            self.release()


# Lock objects to access the _RWLockCore in reader or writer mode
class _ReaderLock(_ContextManagerMixin):

    def __init__(self, lock):
        self._lock = lock

    @property
    def locked(self):
        return self._lock.read_locked

    @asyncio.coroutine
    def acquire(self):
        yield from self._lock.acquire_read()

    def release(self):
        self._lock.release_read()

    def __repr__(self):
        status = 'locked' if self._lock._r_state > 0 else 'unlocked'
        return "<ReaderLock: [{}]>".format(status)


class _WriterLock(_ContextManagerMixin):

    def __init__(self, lock):
        self._lock = lock

    @property
    def locked(self):
        return self._lock.write_locked

    @asyncio.coroutine
    def acquire(self):
        yield from self._lock.acquire_write()

    def release(self):
        self._lock.release_write()

    def __repr__(self):
        status = 'locked' if self._lock._w_state > 0 else 'unlocked'
        return "<WriterLock: [{}]>".format(status)


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
    def reader(self):
        """The lock used for read, or shared, access"""
        return self._reader_lock

    reader_lock = reader

    @property
    def writer(self):
        """The lock used for write, or exclusive, access"""
        return self._writer_lock

    writer_lock = writer

    def __repr__(self):
        return '<RWLock: {} {}>'.format(self.reader_lock.__repr__(),
                                        self.writer_lock.__repr__())
