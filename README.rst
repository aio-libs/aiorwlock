aiorwlock
=========

Read write lock for asyncio_ A ``RWLock`` maintains a pair of associated locks,
one for read-only operations and one for writing. The read lock may be
held simultaneously by multiple reader threads, so long as there are
no writers. The write lock is exclusive.


.. _asyncio: http://docs.python.org/3.4/library/asyncio.html
