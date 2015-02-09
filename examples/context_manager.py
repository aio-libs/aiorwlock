import asyncio
import aiorwlock


loop = asyncio.get_event_loop()


@asyncio.coroutine
def go():
    rwlock = aiorwlock.RWLock(loop=loop)

    # acquire reader lock
    with (yield from rwlock.reader_lock):
        print("inside reader lock")

        yield from asyncio.sleep(0.1, loop=loop)

    # acquire writer lock
    with (yield from rwlock.writer_lock):
        print("inside writer lock")

        yield from asyncio.sleep(0.1, loop=loop)


loop.run_until_complete(go())
