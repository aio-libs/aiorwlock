import asyncio
import pytest
import gc
import os
import sys


def pytest_generate_tests(metafunc):
    if 'loop_type' in metafunc.fixturenames:
        loop_type = ['asyncio']
        if os.environ.get('TOKIO') == 'y':
            loop_type.append('tokio')
            loop_type.append('uvloop')
        metafunc.parametrize("loop_type", loop_type)


@pytest.fixture(scope="session", params=[True, False],
                ids=['debug:true', 'debug:false'])
def debug(request):
    return request.param


@pytest.yield_fixture
def loop(request, loop_type, debug):
    # old_loop = asyncio.get_event_loop()
    asyncio.set_event_loop(None)
    if loop_type == 'uvloop':
        import uvloop
        loop = uvloop.new_event_loop()
    elif loop_type == 'tokio':
        import tokio
        policy = tokio.TokioLoopPolicy()
        asyncio.set_event_loop_policy(policy)
        loop = tokio.new_event_loop()
    else:
        loop = asyncio.new_event_loop()

    loop.set_debug(debug)
    asyncio.set_event_loop(loop)
    yield loop

    loop.close()
    asyncio.set_event_loop(None)
    gc.collect()


@pytest.mark.tryfirst
def pytest_pycollect_makeitem(collector, name, obj):
    if collector.funcnamefilter(name):
        item = pytest.Function(name, parent=collector)
        if 'run_loop' in item.keywords:
            return list(collector._genfunctions(name, obj))


@pytest.mark.tryfirst
def pytest_pyfunc_call(pyfuncitem):
    """
    Run asyncio marked test functions in an event loop instead of a normal
    function call.
    """
    if 'run_loop' in pyfuncitem.keywords:
        funcargs = pyfuncitem.funcargs
        loop = funcargs['loop']
        testargs = {arg: funcargs[arg]
                    for arg in pyfuncitem._fixtureinfo.argnames}
        loop.run_until_complete(pyfuncitem.obj(**testargs))
        return True


def pytest_runtest_setup(item):
    if 'run_loop' in item.keywords and 'loop' not in item.fixturenames:
        # inject an event loop fixture for all async tests
        item.fixturenames.append('loop')


def pytest_ignore_collect(path, config):
    if 'pep492' in str(path):
        if sys.version_info < (3, 5, 0):
            return True
