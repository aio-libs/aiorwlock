import asyncio

import pytest

from aiorwlock import RWLock


class Bunch:
    """A bunch of Tasks. Port python threading tests"""

    def __init__(self, f, n, wait_before_exit=False):
        """
        Construct a bunch of `n` tasks running the same function `f`.
        If `wait_before_exit` is True, the tasks won't terminate until
        do_finish() is called.
        """
        self._loop = asyncio.get_event_loop()
        self.f = f
        self.n = n
        self.started = []
        self.finished = []
        self._can_exit = not wait_before_exit

        self._futures = []

        async def task():
            tid = asyncio.current_task()
            self.started.append(tid)
            try:
                await f()
            finally:
                self.finished.append(tid)
                while not self._can_exit:
                    await asyncio.sleep(0.01)

        for _ in range(n):
            t = asyncio.Task(task())
            self._futures.append(t)

    async def wait_for_finished(self):
        await asyncio.gather(*self._futures)

    def do_finish(self):
        self._can_exit = True


async def _wait():
    await asyncio.sleep(0.01)


@pytest.mark.asyncio
async def test_ctor_loop_reader(loop):
    rwlock = RWLock().reader_lock
    assert rwlock._lock._get_loop() is loop


@pytest.mark.asyncio
async def test_ctor_noloop_reader(loop):
    asyncio.set_event_loop(loop)
    rwlock = RWLock().reader_lock
    assert rwlock._lock._get_loop() is loop


@pytest.mark.asyncio
async def test_ctor_loop_writer(loop):
    rwlock = RWLock().writer_lock
    assert rwlock._lock._get_loop() is loop


@pytest.mark.asyncio
async def test_ctor_noloop_writer(loop):
    asyncio.set_event_loop(loop)
    rwlock = RWLock().writer_lock
    assert rwlock._lock._get_loop() is loop


@pytest.mark.asyncio
async def test_repr(loop):
    rwlock = RWLock()
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


@pytest.mark.asyncio
async def test_release_unlocked(loop):
    rwlock = RWLock()
    with pytest.raises(RuntimeError):
        rwlock.reader_lock.release()


@pytest.mark.asyncio
async def test_many_readers(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.reader_lock.acquire()
        try:
            locked.append(1)
            await _wait()
            nlocked.append(len(locked))
            await _wait()
            locked.pop(-1)
        finally:
            rwlock.reader_lock.release()

    await Bunch(f, N).wait_for_finished()
    assert max(nlocked) > 1


@pytest.mark.asyncio
async def test_read_upgrade_write_release(loop):
    rwlock = RWLock()
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


@pytest.mark.asyncio
async def test_reader_recursion(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.reader_lock.acquire()
        try:
            await rwlock.reader_lock.acquire()
            try:
                locked.append(1)
                await _wait()
                nlocked.append(len(locked))
                await _wait()
                locked.pop(-1)
            finally:
                rwlock.reader_lock.release()
        finally:
            rwlock.reader_lock.release()

    await Bunch(f, N).wait_for_finished()
    assert max(nlocked) > 1


@pytest.mark.asyncio
async def test_writer_recursion(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.writer_lock.acquire()
        try:
            await rwlock.writer_lock.acquire()
            try:
                locked.append(1)
                await _wait()
                nlocked.append(len(locked))
                await _wait()
                locked.pop(-1)
            finally:
                rwlock.writer_lock.release()
        finally:
            rwlock.writer_lock.release()

    await Bunch(f, N).wait_for_finished()
    assert max(nlocked) == 1


@pytest.mark.asyncio
async def test_writer_then_reader_recursion(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    N = 5
    locked = []
    nlocked = []

    async def f():
        await rwlock.writer_lock.acquire()
        try:
            await rwlock.reader_lock.acquire()
            try:
                locked.append(1)
                await _wait()
                nlocked.append(len(locked))
                await _wait()
                locked.pop(-1)
            finally:
                rwlock.reader_lock.release()
        finally:
            rwlock.writer_lock.release()

    await Bunch(f, N).wait_for_finished()
    assert max(nlocked) == 1


@pytest.mark.asyncio
async def test_writer_recursion_fail(loop):
    rwlock = RWLock()
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

    await Bunch(f, N).wait_for_finished()
    assert len(locked) == N


@pytest.mark.asyncio
async def test_readers_writers(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    N = 5
    rlocked = []
    wlocked = []
    nlocked = []

    async def r():
        await rwlock.reader_lock.acquire()
        try:
            rlocked.append(1)
            await _wait()
            nlocked.append((len(rlocked), len(wlocked)))
            await _wait()
            rlocked.pop(-1)
        finally:
            rwlock.reader_lock.release()

    async def w():
        await rwlock.writer_lock.acquire()
        try:
            wlocked.append(1)
            await _wait()
            nlocked.append((len(rlocked), len(wlocked)))
            await _wait()
            wlocked.pop(-1)
        finally:
            rwlock.writer_lock.release()

    b1 = Bunch(r, N)
    b2 = Bunch(w, N)

    await asyncio.sleep(0.0001)

    await b1.wait_for_finished()
    await b2.wait_for_finished()

    (
        r,
        w,
    ) = zip(*nlocked)

    assert max(r) > 1
    assert max(w) == 1

    for r, w in nlocked:
        if w:
            assert r == 0
        if r:
            assert w == 0


@pytest.mark.asyncio
async def test_writer_success(loop):
    # Verify that a writer can get access
    rwlock = RWLock()
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
            await _wait()

        for _ in range(2):
            await _wait()

            # print("current pre-writes", reads)
            await rwlock.writer_lock.acquire()
            try:
                writes += 1
                # print("current writes", reads)
            finally:
                rwlock.writer_lock.release()

    b1 = Bunch(r, N)
    b2 = Bunch(w, 1)

    await b1.wait_for_finished()
    await b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


@pytest.mark.asyncio
async def test_writer_success_fast(loop):
    # Verify that a writer can get access
    rwlock = RWLock(fast=True)
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
                await asyncio.sleep(0)
            finally:
                rwlock.reader_lock.release()

    async def w():
        nonlocal reads, writes
        while reads == 0:
            await _wait()

        for _ in range(2):
            await _wait()

            # print("current pre-writes", reads)
            await rwlock.writer_lock.acquire()
            try:
                writes += 1
                # print("current writes", reads)
            finally:
                rwlock.writer_lock.release()

    b1 = Bunch(r, N)
    b2 = Bunch(w, 1)

    await b1.wait_for_finished()
    await b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


@pytest.mark.asyncio
async def test_writer_success_with_statement(loop):
    # Verify that a writer can get access
    rwlock = RWLock()
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
            await _wait()

        for _ in range(2):
            await _wait()

            # print("current pre-writes", reads)
            async with rwlock.writer_lock:
                writes += 1

    b1 = Bunch(r, N)
    b2 = Bunch(w, 1)

    await b1.wait_for_finished()
    await b2.wait_for_finished()
    assert writes == 2
    # uncomment this to view performance
    # print('>>>>>>>>>>>', writes, reads)


@pytest.mark.asyncio
async def test_raise_error_on_with_for_reader_lock(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    with pytest.raises(RuntimeError):
        with rwlock.reader_lock:
            pass


@pytest.mark.asyncio
async def test_raise_error_on_with_for_writer_lock(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    with pytest.raises(RuntimeError):
        with rwlock.writer_lock:
            pass


@pytest.mark.asyncio
async def test_read_locked(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    assert not rwlock.reader_lock.locked
    async with rwlock.reader_lock:
        assert rwlock.reader_lock.locked


@pytest.mark.asyncio
async def test_write_locked(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    assert not rwlock.writer_lock.locked
    async with rwlock.writer_lock:
        assert rwlock.writer_lock.locked


@pytest.mark.asyncio
async def test_write_read_lock_multiple_tasks(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
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
        task = asyncio.Task(coro())
        await asyncio.sleep(0.1, loop)
    await task
    assert not rl.locked
    assert not wl.locked


@pytest.mark.asyncio
async def test_read_context_manager(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    reader = rwlock.reader_lock
    assert not reader.locked
    async with reader:
        assert reader.locked


@pytest.mark.asyncio
async def test_write_context_manager(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    writer = rwlock.writer_lock
    assert not writer.locked
    async with writer:
        assert writer.locked


@pytest.mark.asyncio
async def test_await_read_lock(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    reader = rwlock.reader_lock
    assert not reader.locked
    async with reader:
        assert reader.locked


@pytest.mark.asyncio
async def test_await_write_lock(loop, fast_track):
    rwlock = RWLock(fast=fast_track)
    writer = rwlock.writer_lock
    assert not writer.locked
    async with writer:
        assert writer.locked


@pytest.mark.asyncio
async def test_writer_ambiguous_loops(fast_track):
    loop = asyncio.new_event_loop()

    try:
        lock = RWLock(fast=fast_track)
        lock._writer_lock._lock._loop = loop

        with pytest.raises(
            RuntimeError, match='is bound to a different event loop'
        ):
            async with lock.writer_lock:
                pass
    finally:
        loop.close()


@pytest.mark.asyncio
async def test_reader_ambiguous_loops(fast_track):
    loop = asyncio.new_event_loop()

    try:
        lock = RWLock(fast=fast_track)
        lock._reader_lock._lock._loop = loop

        with pytest.raises(
            RuntimeError, match='is bound to a different event loop'
        ):
            async with lock.reader_lock:
                pass
    finally:
        loop.close()


def test_created_outside_of_coroutine(event_loop, fast_track):
    async def main():
        async with lock.reader_lock:
            pass
        async with lock.writer_lock:
            pass

    lock = RWLock(fast=fast_track)
    event_loop.run_until_complete(main())


@pytest.mark.asyncio
async def test_cross_event_loop_reader_race_condition():
    """
    Test for race condition where RWLock is shared across event loops.

    This reproduces a bug scenario where:
    1. RWLock is created and reader lock acquired on Event Loop A
    2. RWLock is shared with Event Loop B which also acquires reader lock
    3. One loop releases successfully, the other may fail due to internal state loop mismatch
    4. This can leave the lock in an inconsistent and locked state

    Expected behavior if bug is FIXED:
    - acquire() should fail on other event loops (good)
    - original release() should succeed (good)

    Expected behavior if bug EXISTS:
    - acquire() might succeed on other event loops (bad)
    - release() might fail due to loop mismatch (bad)
    """
    import concurrent.futures

    lock = RWLock()
    acquire_results = {}
    acquire_errors = {}
    release_results = {}
    release_errors = {}

    def run_on_new_loop(loop_name):
        """Run RWLock operations on a new event loop"""
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        async def acquire_and_release():
            acquired = False
            try:
                # Try to acquire reader lock - should fail if bug is fixed
                await lock.reader_lock.acquire()
                acquired = True
                acquire_results[loop_name] = "acquired successfully (unexpected!)"

                # Small delay to ensure timing
                await asyncio.sleep(0.01)

            except RuntimeError as e:
                acquire_errors[loop_name] = str(e)
                # This is expected if bug is fixed - acquire should fail

            # Only try to release if we actually acquired
            if acquired:
                try:
                    lock.reader_lock.release()
                    # If we reach here, then some other thread managed to acquire a lock, which is bad
                    # because when any other thread attempts to release, it will raise a RuntimeError
                    # and leave the lock in a locked state.
                    release_results[loop_name] = "released successfully"
                except RuntimeError as e:
                    release_errors[loop_name] = str(e)
                    # This indicates the race condition bug

        try:
            new_loop.run_until_complete(acquire_and_release())
        finally:
            new_loop.close()

    # First acquire reader lock on current event loop
    await lock.reader_lock.acquire()
    original_release_success = False
    original_release_error = None

    try:
        # Start operations on two separate event loops concurrently
        with concurrent.futures.ThreadPoolExecutor(max_workers=2) as executor:
            future1 = executor.submit(run_on_new_loop, "loop_b")
            future2 = executor.submit(run_on_new_loop, "loop_c")

            # Wait for both to complete
            future1.result(timeout=5)
            future2.result(timeout=5)

    finally:
        # Release the original lock - this should always work if no race condition
        try:
            lock.reader_lock.release()
            original_release_success = True
        except Exception as e:
            original_release_error = str(e)

    # Analyze the behavior:
    unexpected_acquires = len(acquire_results) > 0  # Should be 0 if bug is fixed
    acquire_loop_errors = any("different event loop" in str(error) for error in acquire_errors.values())
    release_loop_errors = any("different event loop" in str(error) for error in release_errors.values())
    original_release_failed = not original_release_success

    if unexpected_acquires or release_loop_errors or original_release_failed:
        # Race condition detected
        pytest.fail(
            f"Cross-event-loop race condition detected:\n"
            f"- Unexpected successful acquires: {unexpected_acquires} (should be False)\n"
            f"- Release errors on wrong loops: {release_loop_errors} (should be False)\n"
            f"- Original release failed: {original_release_failed} (should be False)\n"
            f"Details: acquire_results={acquire_results}, release_errors={release_errors}, "
            f"original_error={original_release_error}"
        )

    # If we get here, the behavior is correct:
    # - All acquire attempts on other loops should have failed (acquire_errors should have 2 entries)
    # - No releases should have failed due to loop errors
    # - Original release should have succeeded
    assert len(acquire_errors) == 2, f"Expected 2 acquire errors, got {len(acquire_errors)}"
    assert acquire_loop_errors, "Expected acquire errors to be about event loop binding"
    assert len(release_errors) == 0, f"Expected no release errors, got {release_errors}"
    assert original_release_success, f"Expected original release to succeed, got error: {original_release_error}"


@pytest.mark.asyncio
async def test_cross_event_loop_writer_race_condition():
    """
    Test writer lock race condition across event loops.

    Scenario: Writer lock acquired/released on thread A (pins lock to that loop),
    then thread B attempts acquire - should fail but currently succeeds and
    gets stuck on release.
    """
    import concurrent.futures

    lock = RWLock()

    # Pin the lock to current event loop by acquiring/releasing writer lock
    await lock.writer_lock.acquire()
    lock.writer_lock.release()

    acquire_success = False
    release_error = None

    def run_on_new_loop():
        new_loop = asyncio.new_event_loop()
        asyncio.set_event_loop(new_loop)

        async def acquire_and_release():
            nonlocal acquire_success, release_error
            try:
                await lock.writer_lock.acquire()
                acquire_success = True  # Should not reach here if bug is fixed
                lock.writer_lock.release()
            except RuntimeError as e:
                if acquire_success:
                    # Failed on release - indicates race condition
                    release_error = str(e)
                # If failed on acquire, that's expected behavior

        try:
            new_loop.run_until_complete(acquire_and_release())
        finally:
            new_loop.close()

    with concurrent.futures.ThreadPoolExecutor(max_workers=1) as executor:
        executor.submit(run_on_new_loop).result(timeout=5)

    if acquire_success or release_error:
        pytest.fail(
            f"Writer cross-event-loop race condition detected: "
            f"acquire_success={acquire_success}, release_error={release_error}"
        )

    # If we get here, acquire properly failed (expected behavior)
