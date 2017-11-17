import pytest
import asyncio
import contextlib

from aiorwlock import RWLock, create_future


if hasattr(asyncio, 'ensure_future'):
    ensure_future = asyncio.ensure_future
else:
    ensure_future = asyncio.async  # Deprecated since 3.4.4


@contextlib.contextmanager
def should_fail(timeout, loop):
    task = asyncio.Task.current_task(loop)

    handle = loop.call_later(timeout, task.cancel)
    try:
        yield
    except asyncio.CancelledError:
        handle.cancel()
        return
    else:
        assert False, ("Inner task expected to be cancelled", task)


@pytest.mark.run_loop
def test_get_write_then_read(loop):
    rwlock = RWLock(loop=loop)

    rl = rwlock.reader
    wl = rwlock.writer
    with (yield from wl):
        assert wl.locked
        assert not rl.locked

        with (yield from rl):
            assert wl.locked
            assert rl.locked


@pytest.mark.run_loop
def test_get_write_then_read_and_write_again(loop):
    rwlock = RWLock(loop=loop)
    rl = rwlock.reader
    wl = rwlock.writer

    f = create_future(loop)
    writes = []

    @asyncio.coroutine
    def get_write_lock():
        yield from f
        with should_fail(.1, loop):
            with (yield from wl):
                assert wl.locked
                writes.append('should not be here')

    ensure_future(get_write_lock(), loop=loop)

    with (yield from wl):
        assert wl.locked

        with (yield from rl):
            f.set_result(None)
            yield from asyncio.sleep(0.12, loop=loop)
            # second task can not append to writes
            assert writes == []
            assert rl.locked


@pytest.mark.run_loop
def test_writers_deadlock(loop):
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

    @asyncio.coroutine
    def coro():
        with (yield from wl):
            assert wl.locked
            yield from asyncio.sleep(.2, loop)

    with (yield from rl):
        assert rl.locked
        task_b = ensure_future(coro(), loop=loop)
        task_c = ensure_future(coro(), loop=loop)
        yield from asyncio.sleep(0.1, loop)
    # cancel lock waiter right after release
    task_b.cancel()
    assert not rl.locked

    # wait task_c to complete
    yield from asyncio.sleep(0.3, loop)
    assert task_c.done()
    assert not rl.locked
    assert not wl.locked


@pytest.mark.run_loop
def test_readers_cancel(loop):
    rwlock = RWLock(loop=loop)
    rl = rwlock.reader
    wl = rwlock.writer

    @asyncio.coroutine
    def coro(lock):
        with (yield from lock):
            assert lock.locked
            yield from asyncio.sleep(0.2, loop)

    with (yield from wl):
        assert wl.locked
        task_b = ensure_future(coro(rl), loop=loop)
        task_c = ensure_future(coro(rl), loop=loop)
        yield from asyncio.sleep(0.1, loop)

    task_b.cancel()
    assert not wl.locked

    yield from task_c
    assert task_c.done()
    assert not rl.locked
    assert not wl.locked
