from collections.abc import Iterator

import pytest
from fastapi.testclient import TestClient

from app.config import Settings
from app.main import create_app
from tests.conftest import TEST_DATABASE_URL


@pytest.fixture
def api_client(database_name: str) -> Iterator[TestClient]:
    """App completa (lifespan incluido) contra una base de MongoDB aislada."""
    settings = Settings(
        _env_file=None, database_url=TEST_DATABASE_URL, database_name=database_name
    )
    with TestClient(create_app(settings)) as client:
        yield client
