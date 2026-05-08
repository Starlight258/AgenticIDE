import pytest

from src import store


@pytest.fixture(autouse=True)
def clear_store() -> None:
    store.clear()
