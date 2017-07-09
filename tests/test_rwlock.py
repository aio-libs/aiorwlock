import asyncio

from aiorwlock import RWLock
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

        @asyncio.coroutine
        def task():
            tid = asyncio.Task.current_task(loop=self._loop)
            self.started.append(tid)
            try:
                yield from f()
            finally:
                self.finished.append(tid)
                while not self._can_exit:
                    yield from asyncio.sleep(0.01, loop=self._loop)

        for i in range(n):
            t = asyncio.Task(task(), loop=self._loop)
            self._futures.append(t)

    @asyncio.coroutine
    def wait_for_finished(self):
        yield from asyncio.gather(*self._futures, loop=self._loop)

    def do_finish(self):
        self._can_exit = True


def _wait(loop=None):
    _loop = loop or asyncio.get_event_loop()
    yield from asyncio.sleep(0.01, loop=_loop)


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
def test_repr(loop):
    rwlock = RWLock(loop=loop)
    assert 'RWLock' in rwlock.__repr__()
    assert 'WriterLock: [unlocked' in rwlock.__repr__()
    assert 'ReaderLock: [unlocked' in rwlock.__repr__()

    # reader lock __repr__
    yield from rwlock.reader_lock.acquire()
    assert 'ReaderLock: [locked]' in rwlock.__repr__()
    rwlock.reader_lock.release()
    assert 'ReaderLock: [unlocked]' in rwlock.__repr__()

    # writer lock __repr__
    yield from rwlock.writer_lock.acquire()
    assert 'WriterLock: [locked]' in rwlock.__repr__()
    rwlock.writer_lock.release()
    assert 'WriterLock: [unlocked]' in rwlock.__repr__()


def test_release_unlocked(loop):
    rwlock = RWLock(loop=loop)
    with pytest.raises(RuntimeError):
        rwlock.reader_lock.release()


@pytest.mark.run_loop
def test_many_readers(loop):
    rwlock = RWLock(loop=loop)
    N = 5
    locked = []
    nlocked = []

    @asyncio.coroutine
    def f():
        yield from rwlock.reader_lock.acquire()
        try:
            locked.append(1)
            yield from _wait(loop=loop)
            nlocked.append(len(locked))
            yield from _wait(loop=loop)
            locked.pop(-1)
        finally:
            rwlock.reader_lock.release()

    yield from Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) > 1


@pytest.mark.run_loop
def test_read_upgrade_write_release(loop):
    rwlock = RWLock(loop=loop)
    yield from rwlock.writer_lock.acquire()
    yield from rwlock.reader_lock.acquire()
    yield from rwlock.reader_lock.acquire()

    yield from rwlock.reader_lock.acquire()
    rwlock.reader_lock.release()

    assert rwlock.writer_lock.locked

    rwlock.writer_lock.release()
    assert not rwlock.writer_lock.locked

    assert rwlock.reader.locked

    with pytest.raises(RuntimeError):
        yield from rwlock.writer_lock.acquire()

    rwlock.reader_lock.release()
    rwlock.reader_lock.release()


@pytest.mark.run_loop
def test_reader_recursion(loop):

    rwlock = RWLock(loop=loop)
    N = 5
    locked = []
    nlocked = []

    @asyncio.coroutine
    def f():
        yield from rwlock.reader_lock.acquire()
        try:
            yield from rwlock.reader_lock.acquire()
            try:
                locked.append(1)
                yield from _wait(loop=loop)
                nlocked.append(len(locked))
                yield from _wait(loop=loop)
                locked.pop(-1)
            finally:
                rwlock.reader_lock.release()
        finally:
            rwlock.reader_lock.release()

    yield from Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) > 1


@pytest.mark.run_loop
def test_writer_recursion(loop):
    rwlock = RWLock(loop=loop)
    N = 5
    locked = []
    nlocked = []

    @asyncio.coroutine
    def f():
        yield from rwlock.writer_lock.acquire()
        try:
            yield from rwlock.writer_lock.acquire()
            try:
                locked.append(1)
                yield from _wait(loop=loop)
                nlocked.append(len(locked))
                yield from _wait(loop=loop)
                locked.pop(-1)
            finally:
                rwlock.writer_lock.release()
        finally:
            rwlock.writer_lock.release()

    yield from Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) == 1


@pytest.mark.run_loop
def test_writer_then_reader_recursion(loop):
    rwlock = RWLock(loop=loop)
    N = 5
    locked = []
    nlocked = []

    @asyncio.coroutine
    def f():
        yield from rwlock.writer_lock.acquire()
        try:
            yield from rwlock.reader_lock.acquire()
            try:
                locked.append(1)
                yield from _wait(loop=loop)
                nlocked.append(len(locked))
                yield from _wait(loop=loop)
                locked.pop(-1)
            finally:
                rwlock.reader_lock.release()
        finally:
            rwlock.writer_lock.release()

    yield from Bunch(f, N, loop=loop).wait_for_finished()
    assert max(nlocked) == 1


@pytest.mark.run_loop
def test_writer_recursion_fail(loop):
    rwlock = RWLock(loop=loop)
    N = 5
    locked = []

    @asyncio.coroutine
    def f():
        yield from rwlock.reader_lock.acquire()
        try:
            with pytest.raises(RuntimeError):
                yield from rwlock.writer_lock.acquire()
            locked.append(1)
        finally:
            rwlock.reader_lock.release()

    yield from Bunch(f, N, loop=loop).wait_for_finished()
    assert len(locked) == N


@pytest.mark.run_loop
def test_readers_writers(loop):
    rwlock = RWLock(loop=loop)
    N = 5
    rlocked = []
    wlocked = []
    nlocked = []

    @asyncio.coroutine
    def r():
        yield from rwlock.reader_lock.acquire()
        try:
            rlocked.append(1)
            yield from _wait(loop=loop)
            nlocked.append((len(rlocked), len(wlocked)))
            yield from _wait(loop=loop)
            rlocked.pop(-1)
        finally:
            rwlock.reader_lock.release()

    @asyncio.coroutine
    def w():
        yield from rwlock.writer_lock.acquire()
        try:
            wlocked.append(1)
            yield from _wait(loop=loop)
            nlocked.append((len(rlocked), len(wlocked)))
            yield from _wait(loop=loop)
            wlocked.pop(-1)
        finally:
            rwlock.writer_lock.release()

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, N, loop=loop)

    yield from asyncio.sleep(0.0001, loop=loop)

    yield from b1.wait_for_finished()
    yield from b2.wait_for_finished()

    r, w, = zip(*nlocked)

    assert max(r) > 1
    assert max(w) == 1

    for r, w in nlocked:
        if w:
            assert r == 0
        if r:
            assert w == 0


@pytest.mark.run_loop
def test_writer_success(loop):
    # Verify that a writer can get access
    rwlock = RWLock(loop=loop)
    N = 5
    reads = 0
    writes = 0

    @asyncio.coroutine
    def r():
        # read until we achive write successes
        nonlocal reads, writes
        while writes < 2:
            # print("current pre-reads", reads)
            yield from rwlock.reader_lock.acquire()
            try:
                reads += 1
                # print("current reads", reads)
            finally:
                rwlock.reader_lock.release()

    @asyncio.coroutine
    def w():
        nonlocal reads, writes
        while reads == 0:
            yield from _wait(loop=loop)

        for i in range(2):
            yield from _wait(loop=loop)

            # print("current pre-writes", reads)
            yield from rwlock.writer_lock.acquire()
            try:
                writes += 1
                # print("current writes", reads)
            finally:
                rwlock.writer_lock.release()

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, 1, loop=loop)

    yield from b1.wait_for_finished()
    yield from b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


@pytest.mark.run_loop
def test_writer_success_fast(loop):
    # Verify that a writer can get access
    rwlock = RWLock(loop=loop, fast=True)
    N = 5
    reads = 0
    writes = 0

    @asyncio.coroutine
    def r():
        # read until we achive write successes
        nonlocal reads, writes
        while writes < 2:
            # print("current pre-reads", reads)
            yield from rwlock.reader_lock.acquire()
            try:
                reads += 1
                # print("current reads", reads)
                yield from asyncio.sleep(0, loop=loop)
            finally:
                rwlock.reader_lock.release()

    @asyncio.coroutine
    def w():
        nonlocal reads, writes
        while reads == 0:
            yield from _wait(loop=loop)

        for i in range(2):
            yield from _wait(loop=loop)

            # print("current pre-writes", reads)
            yield from rwlock.writer_lock.acquire()
            try:
                writes += 1
                # print("current writes", reads)
            finally:
                rwlock.writer_lock.release()

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, 1, loop=loop)

    yield from b1.wait_for_finished()
    yield from b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


@pytest.mark.run_loop
def test_writer_success_with_statement(loop):
    # Verify that a writer can get access
    rwlock = RWLock(loop=loop)
    N = 5
    reads = 0
    writes = 0

    @asyncio.coroutine
    def r():
        # read until we achive write successes
        nonlocal reads, writes
        while writes < 2:
            # print("current pre-reads", reads)
            with (yield from rwlock.reader_lock):
                reads += 1
                # print("current reads", reads)

    @asyncio.coroutine
    def w():
        nonlocal reads, writes
        while reads == 0:
            yield from _wait(loop=loop)

        for i in range(2):
            yield from _wait(loop=loop)

            # print("current pre-writes", reads)
            with (yield from rwlock.writer_lock):
                writes += 1

    b1 = Bunch(r, N, loop=loop)
    b2 = Bunch(w, 1, loop=loop)

    yield from b1.wait_for_finished()
    yield from b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


def test_raise_error_on_with_for_reader_lock(loop):
    rwlock = RWLock(loop=loop)
    with pytest.raises(RuntimeError):
        with rwlock.reader_lock:
            pass


def test_raise_error_on_with_for_writer_lock(loop):
    rwlock = RWLock(loop=loop)
    with pytest.raises(RuntimeError):
        with rwlock.writer_lock:
            pass


@pytest.mark.run_loop
def test_read_locked(loop):
    rwlock = RWLock(loop=loop)
    assert not rwlock.reader_lock.locked
    with (yield from rwlock.reader_lock):
        assert rwlock.reader_lock.locked


@pytest.mark.run_loop
def test_write_locked(loop):
    rwlock = RWLock(loop=loop)
    assert not rwlock.writer_lock.locked
    with (yield from rwlock.writer_lock):
        assert rwlock.writer_lock.locked


@pytest.mark.run_loop
def test_write_read_lock_multiple_tasks(loop):
    rwlock = RWLock(loop=loop)
    rl = rwlock.reader
    wl = rwlock.writer

    @asyncio.coroutine
    def coro():
        with (yield from rl):
            assert not wl.locked
            assert rl.locked
            yield from asyncio.sleep(0.2, loop)

    with (yield from wl):
        assert wl.locked
        assert not rl.locked
        task = asyncio.Task(coro(), loop=loop)
        yield from asyncio.sleep(0.1, loop)
    yield from task
    assert not rl.locked
    assert not wl.locked
