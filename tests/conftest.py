import asyncio

import pytest


@pytest.fixture(scope='module', params=[True, False], ids=['fast', 'slow'])
def fast_track(request):
    return request.param


@pytest.fixture
def loop():
    """Return an event loop for testing."""
    loop = asyncio.new_event_loop()
    yield loop
    loop.close()
