import asyncio
import contextlib
from typing import Any, Generator

import pytest

from aiorwlock import RWLock

ensure_future = asyncio.ensure_future


@contextlib.contextmanager
def should_fail(timeout: float) -> Generator[None, Any, None]:
    loop = asyncio.get_running_loop()
    task = asyncio.current_task(loop)

    handle = loop.call_later(timeout, task.cancel)
    try:
        yield
    except asyncio.CancelledError:
        handle.cancel()
        return
    else:
        msg = f"Inner task expected to be cancelled: {task}"
        pytest.fail(msg)


@pytest.mark.asyncio
async def test_get_write_then_read() -> None:
    rwlock = RWLock()

    rl = rwlock.reader
    wl = rwlock.writer
    async with wl:
        assert wl.locked
        assert not rl.locked

        async with rl:
            assert wl.locked
            assert rl.locked


@pytest.mark.asyncio
async def test_get_write_then_read_and_write_again() -> None:
    loop = asyncio.get_event_loop()
    rwlock = RWLock()
    rl = rwlock.reader
    wl = rwlock.writer
    f = loop.create_future()
    writes = []

    async def get_write_lock():
        await f
        with should_fail(0.1, loop):
            async with wl:
                assert wl.locked
                writes.append("should not be here")

    ensure_future(get_write_lock())

    async with wl:
        assert wl.locked

        async with rl:
            f.set_result(None)
            await asyncio.sleep(0.12)
            # second task can not append to writes
            assert writes == []
            assert rl.locked


@pytest.mark.asyncio
async def test_writers_deadlock() -> None:
    loop = asyncio.get_event_loop()
    rwlock = RWLock()
    rl = rwlock.reader
    wl = rwlock.writer

    # Scenario:
    # - task A (this) acquires read lock
    # - task B,C wait for write lock
    #
    # A releases the lock and, in the same loop interation,
    # task B gets cancelled (eg: by timeout);
    # B gets cancelled without waking up next waiter -- deadlock;
    #
    # See asyncio.Lock deadlock issue:
    #   https://github.com/python/cpython/pull/1031

    async def coro() -> None:
        async with wl:
            assert wl.locked
            await asyncio.sleep(0.2, loop)

    async with rl:
        assert rl.locked
        task_b = ensure_future(coro())
        task_c = ensure_future(coro())
        await asyncio.sleep(0.1, loop)
    # cancel lock waiter right after release
    task_b.cancel()
    assert not rl.locked

    # wait task_c to complete
    await asyncio.sleep(0.3, loop)
    assert task_c.done()
    assert not rl.locked
    assert not wl.locked


@pytest.mark.asyncio
async def test_readers_cancel() -> None:
    loop = asyncio.get_event_loop()
    rwlock = RWLock()
    rl = rwlock.reader
    wl = rwlock.writer

    async def coro(lock: RWLock):
        async with lock:
            assert lock.locked
            await asyncio.sleep(0.2, loop)

    async with wl:
        assert wl.locked
        task_b = ensure_future(coro(rl))
        task_c = ensure_future(coro(rl))
        await asyncio.sleep(0.1, loop)

    task_b.cancel()
    assert not wl.locked

    await task_c
    assert task_c.done()
    assert not rl.locked
    assert not wl.locked


@pytest.mark.asyncio
async def test_canceled_inside_acquire() -> None:
    rwlock = RWLock()
    rl = rwlock.reader

    async def coro(lock: RWLock):
        async with lock:
            pass

    task = ensure_future(coro(rl))
    await asyncio.sleep(0)
    task.cancel()

    try:
        await task
    except asyncio.CancelledError:
        pass

    assert not rl.locked


@pytest.mark.asyncio
async def test_race_multiple_writers() -> None:
    seq = []

    async def write_wait(lock: RWLock):
        async with lock.reader:
            await asyncio.sleep(0.1)
            seq.append("READ")
        async with lock.writer:
            seq.append("START1")
            await asyncio.sleep(0.1)
            seq.append("FIN1")

    async def write(lock: RWLock):
        async with lock.writer:
            seq.append("START2")
            await asyncio.sleep(0.1)
            seq.append("FIN2")

    lock = RWLock(fast=True)
    await asyncio.gather(write_wait(lock), write(lock))
    assert seq == ["READ", "START2", "FIN2", "START1", "FIN1"]
