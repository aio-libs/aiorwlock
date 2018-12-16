import asyncio
import sys

from collections import deque
from asyncio import Task, Future  # noqa
from typing import Any, List, Tuple, Optional, Callable  # noqa

try:
    from typing import Deque
except ImportError:
    Deque = deque  # type: ignore


Loop = asyncio.AbstractEventLoop
OptLoop = Optional[Loop]


__version__ = '0.6.0'
__all__ = ['RWLock']

PY_35 = sys.version_info >= (3, 5, 3)


def current_task(loop: OptLoop = None) -> 'Task[Any]':
    _loop = loop or asyncio.get_event_loop()  # type: Loop
    if hasattr(asyncio, 'current_task'):
        t = asyncio.current_task(loop=_loop)
    else:
        t = asyncio.Task.current_task(loop=_loop)
    if t is None:
        raise RuntimeError('Loop is not running')
    return t


# implementation based on:
# http://bugs.python.org/issue8800

# The internal lock object managing the RWLock state.
class _RWLockCore:
    _RL = 1
    _WL = 2

    def __init__(self, fast: bool, loop: OptLoop):
        self._do_yield = not fast
        self._loop = loop or asyncio.get_event_loop()  # type: Loop
        self._read_waiters = deque()  # type: Deque[Future[None]]
        self._write_waiters = deque()  # type: Deque[Future[None]]
        self._r_state = 0  # type: int
        self._w_state = 0  # type: int
        # tasks will be few, so a list is not inefficient
        self._owning = []  # type: List[Tuple[Task[Any], int]]

    @property
    def read_locked(self) -> bool:
        return self._r_state > 0

    @property
    def write_locked(self) -> bool:
        return self._w_state > 0

    # Acquire the lock in read mode.
    async def acquire_read(self) -> bool:
        me = current_task(loop=self._loop)

        if (me, self._RL) in self._owning or (me, self._WL) in self._owning:
            self._r_state += 1
            self._owning.append((me, self._RL))
            if self._do_yield:
                await asyncio.sleep(0.0, loop=self._loop)
            return True

        if (not self._write_waiters and
                self._r_state >= 0 and self._w_state == 0):
            self._r_state += 1
            self._owning.append((me, self._RL))
            if self._do_yield:
                await asyncio.sleep(0.0, loop=self._loop)
            return True

        fut = self._loop.create_future()
        self._read_waiters.append(fut)
        try:
            await fut
            self._r_state += 1
            self._owning.append((me, self._RL))
            return True

        except asyncio.CancelledError:
            self._wake_up()
            raise

        finally:
            self._read_waiters.remove(fut)

    # Acquire the lock in write mode.  A 'waiting' count is maintained,
    # ensuring that 'readers' will yield to writers.
    async def acquire_write(self) -> bool:
        me = current_task(loop=self._loop)

        if (me, self._WL) in self._owning:
            self._w_state += 1
            self._owning.append((me, self._WL))
            if self._do_yield:
                await asyncio.sleep(0.0, loop=self._loop)
            return True
        elif (me, self._RL) in self._owning:
            if self._r_state > 0:
                raise RuntimeError('Cannot upgrade RWLock from read to write')

        if self._r_state == 0 and self._w_state == 0:
            self._w_state += 1
            self._owning.append((me, self._WL))
            if self._do_yield:
                await asyncio.sleep(0.0, loop=self._loop)
            return True

        fut = self._loop.create_future()
        self._write_waiters.append(fut)
        try:
            await fut
            self._w_state += 1
            self._owning.append((me, self._WL))
            return True

        except asyncio.CancelledError:
            self._wake_up()
            raise

        finally:
            self._write_waiters.remove(fut)

    def release_read(self) -> None:
        self._release(self._RL)

    def release_write(self) -> None:
        self._release(self._WL)

    def _release(self, lock_type: int) -> None:
        # assert lock_type in (self._RL, self._WL)
        me = current_task(loop=self._loop)
        try:
            self._owning.remove((me, lock_type))
        except ValueError:
            raise RuntimeError('Cannot release an un-acquired lock')
        if lock_type == self._RL:
            self._r_state -= 1
        else:
            self._w_state -= 1
        self._wake_up()

    def _wake_up(self) -> None:
        # If no one is reading or writing, wake up write waiters
        # first, only one write waiter should be waken up, if no
        # write waiters and have read waiters, wake up all read
        # waiters.
        if self._r_state == 0 and self._w_state == 0:
            if self._write_waiters:
                self._wake_up_first(self._write_waiters)
            elif self._read_waiters:
                self._wake_up_all(self._read_waiters)

    def _wake_up_first(self, waiters: 'Deque[Future[None]]') -> None:
        # Wake up the first waiter who isn't cancelled.
        for fut in waiters:
            if not fut.done():
                fut.set_result(None)
                break

    def _wake_up_all(self, waiters: 'Deque[Future[None]]') -> None:
        # Wake up all not cancelled waiters.
        for fut in waiters:
            if not fut.done():
                fut.set_result(None)


class _ContextManagerMixin:

    def __enter__(self) -> None:
        raise RuntimeError(
            '"await" should be used as context manager expression')

    def __exit__(self, *args: Any) -> None:
        # This must exist because __enter__ exists, even though that
        # always raises; that's how the with-statement works.
        pass  # pragma: no cover

    async def __aenter__(self) -> None:
        await self.acquire()
        # We have no use for the "as ..."  clause in the with
        # statement for locks.
        return None

    async def __aexit__(self, *args: List[Any]) -> None:
        self.release()

    async def acquire(self) -> None:
        raise NotImplementedError  # pragma: no cover

    def release(self) -> None:
        raise NotImplementedError  # pragma: no cover


# Lock objects to access the _RWLockCore in reader or writer mode
class _ReaderLock(_ContextManagerMixin):

    def __init__(self, lock: _RWLockCore) -> None:
        self._lock = lock

    @property
    def locked(self) -> bool:
        return self._lock.read_locked

    async def acquire(self) -> None:
        await self._lock.acquire_read()

    def release(self) -> None:
        self._lock.release_read()

    def __repr__(self) -> str:
        status = 'locked' if self._lock._r_state > 0 else 'unlocked'
        return '<ReaderLock: [{}]>'.format(status)


class _WriterLock(_ContextManagerMixin):

    def __init__(self, lock: _RWLockCore):
        self._lock = lock

    @property
    def locked(self) -> bool:
        return self._lock.write_locked

    async def acquire(self) -> None:
        await self._lock.acquire_write()

    def release(self) -> None:
        self._lock.release_write()

    def __repr__(self) -> str:
        status = 'locked' if self._lock._w_state > 0 else 'unlocked'
        return '<WriterLock: [{}]>'.format(status)


class RWLock:
    """A RWLock maintains a pair of associated locks, one for read-only
    operations and one for writing. The read lock may be held simultaneously
    by multiple reader tasks, so long as there are no writers. The write
    lock is exclusive.
    """

    core = _RWLockCore

    def __init__(self, *, fast: bool = False, loop: OptLoop = None) -> None:
        self._loop = loop or asyncio.get_event_loop()  # type: Loop
        core = self.core(fast, self._loop)
        self._reader_lock = _ReaderLock(core)
        self._writer_lock = _WriterLock(core)

    @property
    def reader(self) -> _ReaderLock:
        """The lock used for read, or shared, access"""
        return self._reader_lock

    reader_lock = reader

    @property
    def writer(self) -> _WriterLock:
        """The lock used for write, or exclusive, access"""
        return self._writer_lock

    writer_lock = writer

    def __repr__(self) -> str:
        rl = self.reader_lock.__repr__()
        wl = self.writer_lock.__repr__()
        return '<RWLock: {} {}>'.format(rl, wl)
