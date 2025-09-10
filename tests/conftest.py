import asyncio

import pytest
import pytest_asyncio


@pytest.fixture(scope="module", params=[True, False], ids=["fast", "slow"])
def fast_track(request: pytest.FixtureRequest) -> bool:
    return request.param
