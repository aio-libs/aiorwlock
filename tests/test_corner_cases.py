import asyncio
import contextlib

import pytest

from aiorwlock import RWLock, _current_task

ensure_future = asyncio.ensure_future


@contextlib.contextmanager
def should_fail(timeout, loop):
    task = _current_task(loop)

    handle = loop.call_later(timeout, task.cancel)
    try:
        yield
    except asyncio.CancelledError:
        handle.cancel()
        return
    else:
        msg = 'Inner task expected to be cancelled: {}'.format(task)
        pytest.fail(msg)


@pytest.mark.asyncio
async def test_get_write_then_read(loop):
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
async def test_get_write_then_read_and_write_again(loop):
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
                writes.append('should not be here')

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
async def test_writers_deadlock(loop):
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

    async def coro():
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
async def test_readers_cancel(loop):
    rwlock = RWLock()
    rl = rwlock.reader
    wl = rwlock.writer

    async def coro(lock):
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
async def test_canceled_inside_acquire(loop):
    rwlock = RWLock()
    rl = rwlock.reader

    async def coro(lock):
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
