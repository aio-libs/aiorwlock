import asyncio
import threading
from collections import deque
from typing import Any, Deque, List, Optional, Tuple

Loop = asyncio.AbstractEventLoop
OptLoop = Optional[Loop]

# silence LGTM service alerts
Future = asyncio.Future
Task = asyncio.Task

__version__ = '1.3.0'
__all__ = ('RWLock',)


# implementation based on:
# http://bugs.python.org/issue8800

_global_lock = threading.Lock()


class _LoopBoundMixin:
    _loop = None

    def _get_loop(self) -> Loop:
        loop = asyncio.get_event_loop()

        if self._loop is None:
            with _global_lock:
                if self._loop is None:
                    self._loop = loop
        if loop is not self._loop:
            raise RuntimeError(f'{self!r} is bound to a different event loop')
        return loop


# The internal lock object managing the RWLock state.
class _RWLockCore(_LoopBoundMixin):
    _RL = 1
    _WL = 2

    def __init__(self, fast: bool):
        self._do_yield = not fast
        self._read_waiters: Deque[Future[None]] = deque()
        self._write_waiters: Deque[Future[None]] = deque()
        self._r_state: int = 0
        self._w_state: int = 0
        # tasks will be few, so a list is not inefficient
        self._owning: List[Tuple[Task[Any], int]] = []

    @property
    def read_locked(self) -> bool:
        return self._r_state > 0

    @property
    def write_locked(self) -> bool:
        return self._w_state > 0

    async def _yield_after_acquire(self, lock_type: int) -> None:
        if self._do_yield:
            try:
                await asyncio.sleep(0.0)
            except asyncio.CancelledError:
                self._release(lock_type)
                self._wake_up()
                raise

    # Acquire the lock in read mode.
    async def acquire_read(self) -> bool:
        me = asyncio.current_task()
        assert me is not None  # nosec

        if (me, self._RL) in self._owning or (me, self._WL) in self._owning:
            self._r_state += 1
            self._owning.append((me, self._RL))
            await self._yield_after_acquire(self._RL)
            return True

        if (
            not self._write_waiters
            and self._r_state >= 0
            and self._w_state == 0
        ):
            self._r_state += 1
            self._owning.append((me, self._RL))
            await self._yield_after_acquire(self._RL)
            return True

        fut = self._get_loop().create_future()
        self._read_waiters.append(fut)
        try:
            await fut
            self._owning.append((me, self._RL))
            return True

        except asyncio.CancelledError:
            self._r_state -= 1
            self._wake_up()
            raise

        finally:
            self._read_waiters.remove(fut)

    # Acquire the lock in write mode.  A 'waiting' count is maintained,
    # ensuring that 'readers' will yield to writers.
    async def acquire_write(self) -> bool:
        me = asyncio.current_task()
        assert me is not None  # nosec

        if (me, self._WL) in self._owning:
            self._w_state += 1
            self._owning.append((me, self._WL))
            await self._yield_after_acquire(self._WL)
            return True
        elif (me, self._RL) in self._owning:
            if self._r_state > 0:
                raise RuntimeError('Cannot upgrade RWLock from read to write')

        if self._r_state == 0 and self._w_state == 0:
            self._w_state += 1
            self._owning.append((me, self._WL))
            await self._yield_after_acquire(self._WL)
            return True

        fut = self._get_loop().create_future()
        self._write_waiters.append(fut)
        try:
            await fut
            self._owning.append((me, self._WL))
            return True

        except asyncio.CancelledError:
            self._w_state -= 1
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
        me = asyncio.current_task(loop=self._get_loop())
        assert me is not None  # nosec

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
                # Wake up the first waiter which isn't cancelled.
                for fut in self._write_waiters:
                    if not fut.done():
                        fut.set_result(None)
                        self._w_state += 1
                        return

            # Wake up all not cancelled waiters.
            for fut in self._read_waiters:
                if not fut.done():
                    fut.set_result(None)
                    self._r_state += 1


class _ContextManagerMixin:
    def __enter__(self) -> None:
        raise RuntimeError(
            '"await" should be used as context manager expression'
        )

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
        return f'<ReaderLock: [{status}]>'


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
        return f'<WriterLock: [{status}]>'


class RWLock:
    """A RWLock maintains a pair of associated locks, one for read-only
    operations and one for writing. The read lock may be held simultaneously
    by multiple reader tasks, so long as there are no writers. The write
    lock is exclusive.
    """

    core = _RWLockCore

    def __init__(self, *, fast: bool = False) -> None:
        core = self.core(fast)
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
        return f'<RWLock: {rl} {wl}>'
