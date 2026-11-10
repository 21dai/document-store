"""Cache de documentos en Redis: guarda, recupera, invalida y tolera que Redis falle."""

from datetime import UTC, datetime

import fakeredis
import pytest
from redis.exceptions import ConnectionError as RedisConnectionError

from app.cache.document_cache import (
    NullDocumentCache,
    RedisDocumentCache,
    build_document_cache,
)
from app.config import Settings
from app.models.document import Document

CREATED_AT = datetime(2026, 11, 10, 12, 0, 0, 123000, tzinfo=UTC)


def make_document(document_id: int = 7, name: str = "informe") -> Document:
    return Document(
        id=document_id,
        name=name,
        original_filename="informe.pdf",
        checksum="a" * 64,
        file_size=1024,
        page_count=3,
        extracted_text="# Informe\n\nTexto con tildes: áéí ñ",
        is_processed=True,
        created_at=CREATED_AT,
        updated_at=CREATED_AT,
    )


@pytest.fixture
def redis() -> fakeredis.FakeAsyncRedis:
    return fakeredis.FakeAsyncRedis()


async def test_guarda_y_recupera_el_documento_igual(
    redis: fakeredis.FakeAsyncRedis,
) -> None:
    cache = RedisDocumentCache(redis, ttl_seconds=300)
    document = make_document()

    await cache.set(document)

    assert await cache.get(7) == document


async def test_cada_entrada_vence_a_los_ttl_segundos(
    redis: fakeredis.FakeAsyncRedis,
) -> None:
    cache = RedisDocumentCache(redis, ttl_seconds=300)

    await cache.set(make_document())

    # Si una invalidación se pierde, el dato viejo dura como mucho el TTL.
    assert 0 < await redis.ttl("documento:7") <= 300


async def test_un_documento_que_no_esta_en_cache_devuelve_none(
    redis: fakeredis.FakeAsyncRedis,
) -> None:
    assert await RedisDocumentCache(redis, ttl_seconds=300).get(99) is None


async def test_delete_invalida_la_entrada(redis: fakeredis.FakeAsyncRedis) -> None:
    cache = RedisDocumentCache(redis, ttl_seconds=300)
    await cache.set(make_document())

    await cache.delete(7)

    assert await cache.get(7) is None


async def test_un_valor_ilegible_se_trata_como_ausente(
    redis: fakeredis.FakeAsyncRedis,
) -> None:
    await redis.set("documento:7", b"esto no es json")

    assert await RedisDocumentCache(redis, ttl_seconds=300).get(7) is None


async def test_un_documento_sin_id_no_se_guarda(
    redis: fakeredis.FakeAsyncRedis,
) -> None:
    cache = RedisDocumentCache(redis, ttl_seconds=300)

    await cache.set(make_document(document_id=None))  # type: ignore[arg-type]

    assert await redis.keys("*") == []


class RedisCaido:
    """Doble de un cliente de Redis que no responde."""

    def __init__(self) -> None:
        self.closed = False

    async def get(self, key: str) -> bytes:
        raise RedisConnectionError("redis no responde")

    async def set(self, key: str, value: str, ex: int) -> None:
        raise RedisConnectionError("redis no responde")

    async def delete(self, key: str) -> None:
        raise RedisConnectionError("redis no responde")

    async def aclose(self) -> None:
        self.closed = True


async def test_si_redis_no_responde_el_cache_no_falla(
    caplog: pytest.LogCaptureFixture,
) -> None:
    # El cache nunca es un punto de falla: sin Redis, se lee de MongoDB.
    cache = RedisDocumentCache(RedisCaido(), ttl_seconds=300)  # type: ignore[arg-type]

    assert await cache.get(7) is None
    await cache.set(make_document())
    await cache.delete(7)

    assert "Redis" in caplog.text


async def test_aclose_cierra_el_cliente_de_redis() -> None:
    client = RedisCaido()

    await RedisDocumentCache(client, ttl_seconds=300).aclose()  # type: ignore[arg-type]

    assert client.closed


async def test_el_cache_nulo_no_guarda_nada() -> None:
    cache = NullDocumentCache()

    await cache.set(make_document())

    assert await cache.get(7) is None
    await cache.delete(7)
    await cache.aclose()


def test_sin_redis_url_el_cache_queda_desactivado() -> None:
    assert isinstance(build_document_cache(Settings(_env_file=None)), NullDocumentCache)


async def test_con_redis_url_usa_redis_con_el_ttl_configurado() -> None:
    settings = Settings(
        _env_file=None, redis_url="redis://redis:6379/0", cache_ttl_seconds=60
    )

    cache = build_document_cache(settings)

    assert isinstance(cache, RedisDocumentCache)
    assert cache.ttl_seconds == 60
    await cache.aclose()
