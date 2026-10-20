"""Fixtures compartidas: una base MongoDB real y aislada por test.

Los tests de persistencia necesitan un MongoDB al que conectarse. La URL se
toma de `TEST_DATABASE_URL` (por defecto `mongodb://localhost:27017`); cada
test usa una base con nombre único que se borra al terminar, así que no toca
datos existentes.

Si MongoDB no responde, esos tests se saltean con un aviso. Con
`REQUIRE_MONGO=1` (pensado para CI) fallan en lugar de saltearse.
"""

import os
import uuid
from collections.abc import AsyncIterator, Iterator

import pytest
from pymongo import AsyncMongoClient, MongoClient
from pymongo.asynchronous.database import AsyncDatabase
from pymongo.errors import PyMongoError

TEST_DATABASE_URL = os.environ.get("TEST_DATABASE_URL", "mongodb://localhost:27017")


def _require_mongo() -> None:
    try:
        with MongoClient(TEST_DATABASE_URL, serverSelectionTimeoutMS=1500) as client:
            client.admin.command("ping")
    except PyMongoError as exc:
        message = f"MongoDB no disponible en {TEST_DATABASE_URL}: {exc}"
        if os.environ.get("REQUIRE_MONGO") == "1":
            pytest.fail(message)
        pytest.skip(message)


@pytest.fixture
def database_name() -> Iterator[str]:
    """Nombre de una base nueva para el test; se borra al terminar."""
    _require_mongo()
    name = f"document_store_test_{uuid.uuid4().hex[:12]}"
    yield name
    with MongoClient(TEST_DATABASE_URL) as client:
        client.drop_database(name)


@pytest.fixture
async def mongo_database(database_name: str) -> AsyncIterator[AsyncDatabase]:
    client: AsyncMongoClient = AsyncMongoClient(TEST_DATABASE_URL, tz_aware=True)
    try:
        yield client[database_name]
    finally:
        await client.close()
