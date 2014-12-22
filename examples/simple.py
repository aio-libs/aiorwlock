import asyncio
import aiorwlock


loop = asyncio.get_event_loop()


@asyncio.coroutine
def go():
    rwlock = aiorwlock.RWLock(loop=loop)

    # acquire reader lock
    yield from rwlock.reader_lock.acquire()
    try:
        print("inside reader lock")

        yield from asyncio.sleep(0.1, loop=loop)
    finally:
        yield from rwlock.reader_lock.release()

    # acquire writer lock
    yield from rwlock.writer_lock.acquire()
    try:
        print("inside writer lock")

        yield from asyncio.sleep(0.1, loop=loop)
    finally:
        yield from rwlock.writer_lock.release()


loop.run_until_complete(go())
