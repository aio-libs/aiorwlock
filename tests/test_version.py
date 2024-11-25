import aiorwlock


def test_version() -> None:
    ver = aiorwlock.__version__
    assert isinstance(ver, str)
