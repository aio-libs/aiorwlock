import asyncio
import aiorwlock


async def go():
    rwlock = aiorwlock.RWLock()

    # acquire reader lock
    async with rwlock.reader_lock:
        print('inside reader lock')
        await asyncio.sleep(0.1)

    # acquire writer lock
    async with rwlock.writer_lock:
        print('inside writer lock')
        await asyncio.sleep(0.1)


loop = asyncio.get_event_loop()
loop.run_until_complete(go())
