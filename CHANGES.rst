Changes
-------

0.5.0 (2017-12-03)
^^^^^^^^^^^^^^^^^^

* Fix corner cases and deadlock when we upgrade lock from write to
  read #39

* Use loop.create_future instead asyncio.Future if possible

0.4.0 (2015-09-20)
^^^^^^^^^^^^^^^^^^

* Support Python 3.5 and `async with` statement

* rename `.reader_lock` -> `.reader`, `.writer_lock` ->
  `.writer`. Backward compatibility is preserved.

0.3.0 (2014-02-11)
^^^^^^^^^^^^^^^^^^

* Add `.locked` property

0.2.0 (2014-02-09)
^^^^^^^^^^^^^^^^^^

* Make `.release()` non-coroutine


0.1.0 (2014-12-22)
^^^^^^^^^^^^^^^^^^

* Initial release
