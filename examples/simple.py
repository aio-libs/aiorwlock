import asyncio
import aiorwlock


async def go():
    rwlock = aiorwlock.RWLock()

    # acquire reader lock
    await rwlock.reader_lock.acquire()
    try:
        print('inside reader lock')

        await asyncio.sleep(0.1)
    finally:
        rwlock.reader_lock.release()

    # acquire writer lock
    await rwlock.writer_lock.acquire()
    try:
        print('inside writer lock')

        await asyncio.sleep(0.1)
    finally:
        rwlock.writer_lock.release()


loop = asyncio.get_event_loop()
loop.run_until_complete(go())
