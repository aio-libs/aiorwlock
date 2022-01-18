import pytest


@pytest.fixture(scope='module', params=[True, False], ids=['fast', 'slow'])
def fast_track(request):
    return request.param


@pytest.fixture
def loop(event_loop):
    return event_loop
