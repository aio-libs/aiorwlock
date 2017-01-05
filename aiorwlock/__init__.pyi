import asyncio

from typing import Generic, Optional, Generator, Any


class _ContextManager:

    def __init__(self, lock: asyncio.Lock) -> None: ...

    def __enter__(self) -> None: ...

    def __exit__(self, *args: Any) -> None: ...


class _ContextManagerMixin:

    def __iter__(self) -> Generator[Any, None, _ContextManager]: ...

    def __enter__(self) -> None: ...

    def __exit__(self, *args: Any) -> None: ...


class _ReaderLock(_ContextManagerMixin):

    def __init__(self, lock: asyncio.Lock) ->None: ...

    @property
    def locked(self) -> bool: ...

    @asyncio.coroutine
    def acquire(self) -> Generator[Any, None, None]: ...

    def release(self) -> None: ...


class _WriterLock(_ContextManagerMixin):

    def __init__(self, lock: asyncio.Lock) -> None: ...

    @property
    def locked(self) -> bool: ...

    @asyncio.coroutine
    def acquire(self) -> Generator[Any, None, None]: ...

    def release(self) -> None: ...


class RWLock:

    def __init__(self, *, fast: bool=False,
                 loop: Optional[asyncio.AbstractEventLoop]=None) -> None: ...

    @property
    def reader(self) -> _ReaderLock: ...

    @property
    def reader_lock(self) -> _ReaderLock: ...

    @property
    def writer(self) -> _WriterLock: ...

    @property
    def writer_lock(self) -> _WriterLock: ...
