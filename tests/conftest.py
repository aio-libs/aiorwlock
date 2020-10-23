import asyncio
import gc

import pytest

try:
    import uvloop
except ImportError:
    uvloop = None


@pytest.fixture(scope='module', params=[True, False], ids=['fast', 'slow'])
def fast_track(request):
    return request.param


@pytest.fixture(
    scope='session', params=[True, False], ids=['debug:true', 'debug:false']
)
def debug(request):
    return request.param


@pytest.fixture(scope='module', params=['pyloop', 'uvloop'])
def loop_type(request):
    return request.param


@pytest.fixture
def event_loop(request, loop_type, debug):
    # old_loop = asyncio.get_event_loop()
    asyncio.set_event_loop(None)
    if loop_type == 'uvloop' and uvloop is not None:
        loop = uvloop.new_event_loop()
    else:
        loop = asyncio.new_event_loop()

    loop.set_debug(debug)
    asyncio.set_event_loop(loop)
    yield loop

    loop.close()
    asyncio.set_event_loop(None)
    gc.collect()


@pytest.fixture
def loop(event_loop):
    return event_loop
