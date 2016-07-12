from aiorwlock import RWLock

import pytest


@pytest.mark.run_loop
async def test_read_context_manager(loop):
    rwlock = RWLock(loop=loop)
    reader = rwlock.reader_lock
    assert not reader.locked
    async with reader:
        assert reader.locked


@pytest.mark.run_loop
async def test_write_context_manager(loop):
    rwlock = RWLock(loop=loop)
    writer = rwlock.writer_lock
    assert not writer.locked
    async with writer:
        assert writer.locked


@pytest.mark.run_loop
async def test_await_read_lock(loop):
    rwlock = RWLock(loop=loop)
    reader = rwlock.reader_lock
    assert not reader.locked
    with await reader:
        assert reader.locked


@pytest.mark.run_loop
async def test_await_write_lock(loop):
    rwlock = RWLock(loop=loop)
    writer = rwlock.writer_lock
    assert not writer.locked
    with await writer:
        assert writer.locked
