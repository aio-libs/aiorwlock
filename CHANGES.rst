Changes
-------

1.3.0 (2022-1-18)
^^^^^^^^^^^^^^^^^^

* Dropped Python 3.6 support
* Python 3.10 is officially supported
* Drop deprecated `loop` parameter from `RWLock` constructor


1.2.0 (2021-11-09)
^^^^^^^^^^^^^^^^^^

* Fix a bug that makes concurrent writes possible under some (rare) conjunctions (#235)

1.1.0 (2021-09-27)
^^^^^^^^^^^^^^^^^^

* Remove explicit loop usage in `asyncio.sleep()` call, make the library forward
  compatible with Python 3.10

1.0.0 (2020-12-32)
^^^^^^^^^^^^^^^^^^

* Fix a bug with cancelation during acquire #170 (thanks @romasku)

* Deprecate passing explicit `loop` argument to `RWLock` constructor

* Deprecate creation of `RWLock` instance outside of async function context

* Minimal supported version is Python 3.6

* The library works with Python 3.8 and Python 3.9 seamlessly


0.6.0 (2018-12-18)
^^^^^^^^^^^^^^^^^^
* Wake up all readers after writer releases lock #60 (thanks @ranyixu)

* Fixed Python 3.7 compatibility

* Removed old `yield from` syntax

* Minimal supported version is Python 3.5.3

* Removed support for none async context managers

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
