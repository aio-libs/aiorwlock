import asyncio

import pytest


@pytest.fixture(scope="module", params=[True, False], ids=["fast", "slow"])
def fast_track(request: pytest.FixtureRequest) -> bool:
    return request.param


@pytest.fixture
def loop(event_loop: asyncio.AbstractEventLoop):
    return event_loop
