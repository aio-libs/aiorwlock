aiorwlock
=========
.. image:: https://travis-ci.org/jettify/aiorwlock.svg?branch=master
    :target: https://travis-ci.org/jettify/aiorwlock
.. image:: https://coveralls.io/repos/jettify/aiorwlock/badge.png?branch=master
    :target: https://coveralls.io/r/jettify/aiorwlock?branch=master

Read write lock for asyncio_ . A ``RWLock`` maintains a pair of associated
locks, one for read-only operations and one for writing. The read lock may be
held simultaneously by multiple reader tasks, so long as there are
no writers. The write lock is exclusive.

You have to use ``try/finally`` pattern, it is not possible to build
context manager for this lock since, ``yield from`` is necessary for
``release()`` method.


Example
-------

.. code:: python

    import asyncio
    import aiorwlock
    loop = asyncio.get_event_loop()


    @asyncio.coroutine
    def go():
        rwlock = aiorwlock.RWLock(loop=loop)
        try:
            yield from rwlock.writer_lock.acquire()
            # or same way you can acquire reader lock
            # yield from rwlock.reader_lock.acquire()
            yield from asyncio.sleep(0.1, loop=loop)
        finally:
            yield from rwlock.writer_lock.release()

    loop.run_until_complete(go())


.. _asyncio: http://docs.python.org/3.4/library/asyncio.html
