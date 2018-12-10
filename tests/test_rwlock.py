import asyncio

from aiorwlock import RWLock, current_task
import pytest


class Bunch(object):
    """A bunch of Tasks. Port python threading tests"""

    def __init__(self, f, n, wait_before_exit=False, loop=None):
        """
        Construct a bunch of `n` tasks running the same function `f`.
        If `wait_before_exit` is True, the tasks won't terminate until
        do_finish() is called.
        """
        self._loop = loop or asyncio.get_event_loop()
        self.f = f
        self.n = n
        self.started = []
        self.finished = []
        self._can_exit = not wait_before_exit

        self._futures = []

        async def task():
            tid = current_task(loop=self._loop)
            self.started.append(tid)
            try:
                await f()
            finally:
                self.finished.append(tid)
                while not self._can_exit:
                    await asyncio.sleep(0.01, loop=self._loop)

        for _ in range(n):
            t = asyncio.Task(task(), loop=self._loop)
            self._futures.append(t)

    async def wait_for_finished(self):
        await asyncio.gather(*self._futures, loop=self._loop)

    def do_finish(self):
        self._can_exit = True


async def _wait(loop=None):
    _loop = loop or asyncio.get_event_loop()
    await asyncio.sleep(0.01, loop=_loop)


def test_ctor_loop_reader(loop):
    rwlock = RWLock(loop=loop).reader_lock
    assert rwlock._lock._loop is loop


def test_ctor_noloop_reader(loop):
    asyncio.set_event_loop(loop)
    rwlock = RWLock().reader_lock
    assert rwlock._lock._loop is loop


def test_ctor_loop_writer(loop):
    rwlock = RWLock(loop=loop).writer_lock
    assert rwlock._lock._loop is loop


def test_ctor_noloop_writer(loop):
    asyncio.set_event_loop(loop)
    rwlock = RWLock().writer_lock
    assert rwlock._lock._loop is loop


@pytest.mark.run_loop
async def test_repr(loop):
    rwlock = RWLock(loop=loop)
    assert 'RWLock' in rwlock.__repr__()
    assert 'WriterLock: [unlocked' in rwlock.__repr__()
    assert 'ReaderLock: [unlocked' in rwlock.__repr__()

    # reader lock __repr__
    await rwlock.reader_lock.acquire()
    assert 'ReaderLock: [locked]' in rwlock.__repr__()
    rwlock.reader_lock.release()
    assert 'ReaderLock: [unlocked]' in rwlock.__repr__()

    # writer lock __repr__
    await rwlock.writer_lock.acquire()
    assert 'WriterLock: [locked]' in rwlock.__repr__()
    rwlock.writer_lock.release()
    assert 'WriterLock: [unlocked]' in rwlock.__repr__()


@pytest.mark.run_loop
async def test_release_unlocked(loop):
    rwlock = RWLock(loop=loop)
    with pytest.raises(RuntimeError):
        rwlock.reader_lock.release()


@pytest.mark.run_loop
async def test_many_readers(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.reader_lock.acquire()
        try:
            locked.append(1)
            await _wait(loop=loop)
            nlocked.append(len(locked))
            await _wait(loop=loop)
            locked.pop(-1)
        finally:
            rwlock.reader_lock.release()

    await Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) > 1


@pytest.mark.run_loop
async def test_read_upgrade_write_release(loop):
    rwlock = RWLock(loop=loop)
    await rwlock.writer_lock.acquire()
    await rwlock.reader_lock.acquire()
    await rwlock.reader_lock.acquire()

    await rwlock.reader_lock.acquire()
    rwlock.reader_lock.release()

    assert rwlock.writer_lock.locked

    rwlock.writer_lock.release()
    assert not rwlock.writer_lock.locked

    assert rwlock.reader.locked

    with pytest.raises(RuntimeError):
        await rwlock.writer_lock.acquire()

    rwlock.reader_lock.release()
    rwlock.reader_lock.release()


@pytest.mark.run_loop
async def test_reader_recursion(loop, fast_track):

    rwlock = RWLock(loop=loop, fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.reader_lock.acquire()
        try:
            await rwlock.reader_lock.acquire()
            try:
                locked.append(1)
                await _wait(loop=loop)
                nlocked.append(len(locked))
                await _wait(loop=loop)
                locked.pop(-1)
            finally:
                rwlock.reader_lock.release()
        finally:
            rwlock.reader_lock.release()

    await Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) > 1


@pytest.mark.run_loop
async def test_writer_recursion(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.writer_lock.acquire()
        try:
            await rwlock.writer_lock.acquire()
            try:
                locked.append(1)
                await _wait(loop=loop)
                nlocked.append(len(locked))
                await _wait(loop=loop)
                locked.pop(-1)
            finally:
                rwlock.writer_lock.release()
        finally:
            rwlock.writer_lock.release()

    await Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) == 1


@pytest.mark.run_loop
async def test_writer_then_reader_recursion(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.writer_lock.acquire()
        try:
            await rwlock.reader_lock.acquire()
            try:
                locked.append(1)
                await _wait(loop=loop)
                nlocked.append(len(locked))
                await _wait(loop=loop)
                locked.pop(-1)
            finally:
                rwlock.reader_lock.release()
        finally:
            rwlock.writer_lock.release()

    await Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) == 1


@pytest.mark.run_loop
async def test_writer_recursion_fail(loop):
    rwlock = RWLock(loop=loop)
    N = 5
    locked = []

    async def f():
        await rwlock.reader_lock.acquire()
        try:
            with pytest.raises(RuntimeError):
                await rwlock.writer_lock.acquire()
            locked.append(1)
        finally:
            rwlock.reader_lock.release()

    await Bunch(f, N, loop=loop).wait_for_finished()
    assert len(locked) == N


@pytest.mark.run_loop
async def test_readers_writers(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    N = 5
    rlocked = []
    wlocked = []
    nlocked = []

    async def r():
        await rwlock.reader_lock.acquire()
        try:
            rlocked.append(1)
            await _wait(loop=loop)
            nlocked.append((len(rlocked), len(wlocked)))
            await _wait(loop=loop)
            rlocked.pop(-1)
        finally:
            rwlock.reader_lock.release()

    async def w():
        await rwlock.writer_lock.acquire()
        try:
            wlocked.append(1)
            await _wait(loop=loop)
            nlocked.append((len(rlocked), len(wlocked)))
            await _wait(loop=loop)
            wlocked.pop(-1)
        finally:
            rwlock.writer_lock.release()

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, N, loop=loop)

    await asyncio.sleep(0.0001, loop=loop)

    await b1.wait_for_finished()
    await b2.wait_for_finished()

    r, w, = zip(*nlocked)

    assert max(r) > 1
    assert max(w) == 1

    for r, w in nlocked:
        if w:
            assert r == 0
        if r:
            assert w == 0


@pytest.mark.run_loop
async def test_writer_success(loop):
    # Verify that a writer can get access
    rwlock = RWLock(loop=loop)
    N = 5
    reads = 0
    writes = 0

    async def r():
        # read until we achive write successes
        nonlocal reads, writes
        while writes < 2:
            # print("current pre-reads", reads)
            await rwlock.reader_lock.acquire()
            try:
                reads += 1
                # print("current reads", reads)
            finally:
                rwlock.reader_lock.release()

    async def w():
        nonlocal reads, writes
        while reads == 0:
            await _wait(loop=loop)

        for _ in range(2):
            await _wait(loop=loop)

            # print("current pre-writes", reads)
            await rwlock.writer_lock.acquire()
            try:
                writes += 1
                # print("current writes", reads)
            finally:
                rwlock.writer_lock.release()

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, 1, loop=loop)

    await b1.wait_for_finished()
    await b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


@pytest.mark.run_loop
async def test_writer_success_fast(loop):
    # Verify that a writer can get access
    rwlock = RWLock(loop=loop, fast=True)
    N = 5
    reads = 0
    writes = 0

    async def r():
        # read until we achive write successes
        nonlocal reads, writes
        while writes < 2:
            # print("current pre-reads", reads)
            await rwlock.reader_lock.acquire()
            try:
                reads += 1
                # print("current reads", reads)
                await asyncio.sleep(0, loop=loop)
            finally:
                rwlock.reader_lock.release()

    async def w():
        nonlocal reads, writes
        while reads == 0:
            await _wait(loop=loop)

        for _ in range(2):
            await _wait(loop=loop)

            # print("current pre-writes", reads)
            await rwlock.writer_lock.acquire()
            try:
                writes += 1
                # print("current writes", reads)
            finally:
                rwlock.writer_lock.release()

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, 1, loop=loop)

    await b1.wait_for_finished()
    await b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


@pytest.mark.run_loop
async def test_writer_success_with_statement(loop):
    # Verify that a writer can get access
    rwlock = RWLock(loop=loop)
    N = 5
    reads = 0
    writes = 0

    async def r():
        # read until we achive write successes
        nonlocal reads, writes
        while writes < 2:
            # print("current pre-reads", reads)
            async with rwlock.reader_lock:
                reads += 1
                # print("current reads", reads)

    async def w():
        nonlocal reads, writes
        while reads == 0:
            await _wait(loop=loop)

        for _ in range(2):
            await _wait(loop=loop)

            # print("current pre-writes", reads)
            async with rwlock.writer_lock:
                writes += 1

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, 1, loop=loop)

    await b1.wait_for_finished()
    await b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


def test_raise_error_on_with_for_reader_lock(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    with pytest.raises(RuntimeError):
        with rwlock.reader_lock:
            pass


def test_raise_error_on_with_for_writer_lock(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    with pytest.raises(RuntimeError):
        with rwlock.writer_lock:
            pass


@pytest.mark.run_loop
async def test_read_locked(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    assert not rwlock.reader_lock.locked
    async with rwlock.reader_lock:
        assert rwlock.reader_lock.locked


@pytest.mark.run_loop
async def test_write_locked(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    assert not rwlock.writer_lock.locked
    async with rwlock.writer_lock:
        assert rwlock.writer_lock.locked


@pytest.mark.run_loop
async def test_write_read_lock_multiple_tasks(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    rl = rwlock.reader
    wl = rwlock.writer

    async def coro():
        async with rl:
            assert not wl.locked
            assert rl.locked
            await asyncio.sleep(0.2, loop)

    async with wl:
        assert wl.locked
        assert not rl.locked
        task = asyncio.Task(coro(), loop=loop)
        await asyncio.sleep(0.1, loop)
    await task
    assert not rl.locked
    assert not wl.locked


def test_current_task(loop):
    with pytest.raises(RuntimeError):
        current_task(loop=loop)

    with pytest.raises(RuntimeError):
        current_task()


@pytest.mark.run_loop
async def test_read_context_manager(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    reader = rwlock.reader_lock
    assert not reader.locked
    async with reader:
        assert reader.locked


@pytest.mark.run_loop
async def test_write_context_manager(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    writer = rwlock.writer_lock
    assert not writer.locked
    async with writer:
        assert writer.locked


@pytest.mark.run_loop
async def test_await_read_lock(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    reader = rwlock.reader_lock
    assert not reader.locked
    async with reader:
        assert reader.locked


@pytest.mark.run_loop
async def test_await_write_lock(loop, fast_track):
    rwlock = RWLock(loop=loop, fast=fast_track)
    writer = rwlock.writer_lock
    assert not writer.locked
    async with writer:
        assert writer.locked
