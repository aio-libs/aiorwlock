import pytest
import asyncio
import contextlib

from aiorwlock import RWLock, current_task


ensure_future = asyncio.ensure_future


@contextlib.contextmanager
def should_fail(timeout, loop):
    task = current_task(loop)

    handle = loop.call_later(timeout, task.cancel)
    try:
        yield
    except asyncio.CancelledError:
        handle.cancel()
        return
    else:
        assert False, ('Inner task expected to be cancelled', task)


@pytest.mark.run_loop
async def test_get_write_then_read(loop):
    rwlock = RWLock(loop=loop)

    rl = rwlock.reader
    wl = rwlock.writer
    async with wl:
        assert wl.locked
        assert not rl.locked

        async with rl:
            assert wl.locked
            assert rl.locked


@pytest.mark.run_loop
async def test_get_write_then_read_and_write_again(loop):
    rwlock = RWLock(loop=loop)
    rl = rwlock.reader
    wl = rwlock.writer

    f = loop.create_future()
    writes = []

    async def get_write_lock():
        await f
        with should_fail(.1, loop):
            async with wl:
                assert wl.locked
                writes.append('should not be here')

    ensure_future(get_write_lock(), loop=loop)

    async with wl:
        assert wl.locked

        async with rl:
            f.set_result(None)
            await asyncio.sleep(0.12, loop=loop)
            # second task can not append to writes
            assert writes == []
            assert rl.locked


@pytest.mark.run_loop
async def test_writers_deadlock(loop):
    rwlock = RWLock(loop=loop)
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
            await asyncio.sleep(.2, loop)

    async with rl:
        assert rl.locked
        task_b = ensure_future(coro(), loop=loop)
        task_c = ensure_future(coro(), loop=loop)
        await asyncio.sleep(0.1, loop)
    # cancel lock waiter right after release
    task_b.cancel()
    assert not rl.locked

    # wait task_c to complete
    await asyncio.sleep(0.3, loop)
    assert task_c.done()
    assert not rl.locked
    assert not wl.locked


@pytest.mark.run_loop
async def test_readers_cancel(loop):
    rwlock = RWLock(loop=loop)
    rl = rwlock.reader
    wl = rwlock.writer

    async def coro(lock):
        async with lock:
            assert lock.locked
            await asyncio.sleep(0.2, loop)

    async with wl:
        assert wl.locked
        task_b = ensure_future(coro(rl), loop=loop)
        task_c = ensure_future(coro(rl), loop=loop)
        await asyncio.sleep(0.1, loop)

    task_b.cancel()
    assert not wl.locked

    await task_c
    assert task_c.done()
    assert not rl.locked
    assert not wl.locked
