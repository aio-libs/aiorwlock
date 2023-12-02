aiorwlock
=========
.. image:: https://github.com/aio-libs/aiorwlock/workflows/CI/badge.svg
   :target: https://github.com/aio-libs/aiorwlock/actions?query=workflow%3ACI
.. image:: https://codecov.io/gh/aio-libs/aiorwlock/branch/master/graph/badge.svg
   :target: https://codecov.io/gh/aio-libs/aiorwlock
.. image:: https://badges.gitter.im/Join%20Chat.svg
   :target: https://gitter.im/aio-libs/Lobby
   :alt: Chat on Gitter
.. image:: https://img.shields.io/pypi/dm/aiorwlock
   :target: https://pypistats.org/packages/aiorwlock
   :alt: Downloads count

Read write lock for asyncio_ . A ``RWLock`` maintains a pair of associated
locks, one for read-only operations and one for writing. The read lock may be
held simultaneously by multiple reader tasks, so long as there are
no writers. The write lock is exclusive.

Whether or not a read-write lock will improve performance over the use of
a mutual exclusion lock depends on the frequency that the data is *read*
compared to being *modified*. For example, a collection that is initially
populated with data and thereafter infrequently modified, while being
frequently searched is an ideal candidate for the use of a read-write lock.
However, if updates become frequent then the data spends most of its time
being exclusively locked and there is little, if any increase in concurrency.


Implementation is almost direct port from this patch_.


Example
-------

Requires Python 3.5.3+

.. code:: python

   import asyncio
   import aiorwlock

   rwlock = aiorwlock.RWLock()


   async def go():
       # acquire reader lock, multiple coroutines allowed to hold the lock
       async with rwlock.reader_lock:
           print('inside reader lock')
           await asyncio.sleep(0.1)

       # acquire writer lock, only one coroutine can hold the lock
       async with rwlock.writer_lock:
           print('inside writer lock')
           await asyncio.sleep(0.1)


   loop = asyncio.get_event_loop()
   loop.run_until_complete(go())


Fast path
---------

By default `RWLock` switches context on lock acquiring. That allows to
other waiting tasks get the lock even if task that holds the lock
doesn't contain context switches (`await fut` statements).

The default behavior can be switched off by `fast` argument:
`RWLock(fast=True)`.

Long story short:  lock is safe by  default, but if you  sure you have
context switches (`await`,  `async with`, `async for`  or `yield from`
statements) inside  locked code  you may want  to use  `fast=True` for
minor speedup.


TLA+ Specification
------------------

TLA+ specification of ``aiorwlock`` provided in this repository.


License
-------

``aiorwlock`` is offered under the Apache 2 license.


.. _asyncio: http://docs.python.org/3.8/library/asyncio.html
.. _patch: http://bugs.python.org/issue8800
