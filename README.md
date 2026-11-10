# document-store

Microservicio responsable de persistir y administrar documentos procesados.

## Estado del proyecto

En desarrollo.

El contrato HTTP está definido en [`docs/api-contract.md`](docs/api-contract.md)
(Issue #1) y la arquitectura inicial del servicio ya está implementada
(Issue #2). Ya funcionan la persistencia en MongoDB (#3), el alta (#4), las
consultas con paginación (#5), la actualización del nombre (#6), el borrado
(#7) y el manejo de errores (#8). La imagen Docker, el healthcheck y el CI
están configurados (#9).

## Responsabilidad

`document-store` se encarga de:

- recibir los datos de documentos ya procesados;
- persistirlos en MongoDB;
- detectar documentos duplicados mediante checksum;
- consultar documentos;
- actualizar los campos permitidos;
- eliminar documentos;
- exponer una API HTTP para que otros servicios lo consuman.

## Fuera del alcance

`document-store` no debe:

- recibir ni procesar archivos PDF;
- extraer texto;
- depender de `pypdf` o `pypdfium2`;
- reemplazar a `pdf-extractext`;
- coordinar el flujo completo de procesamiento;
- contener una base de datos propia dentro de `orchestrator-service`.

La extracción de texto es responsabilidad de `pdf-extractext` y la coordinación
del flujo es responsabilidad de `orchestrator-service`.

## Arquitectura

El servicio sigue una arquitectura de tres capas con inyección de
dependencias:

```text
HTTP Router
    ↓
Service
    ↓
Repository (interfaz ABC)
    ↓
CachedDocumentRepository (decorador: cache-aside en Redis)
    ↓
MongoDocumentRepository (PyMongo async) → MongoDB
```

- **Router** (`app/routers/`): adapta HTTP, valida requests con schemas
  Pydantic y delega en la capa de servicio.
- **Service** (`app/services/`): contiene la lógica de negocio y depende solo
  de la abstracción `DocumentRepository` (principio de inversión de
  dependencias).
- **Repository** (`app/repositories/`): define el puerto
  `DocumentRepository` (ABC) y su implementación `MongoDocumentRepository`
  con PyMongo asíncrono, envuelta por `CachedDocumentRepository`, que agrega
  el cache en Redis (ver [Cache de documentos](#cache-de-documentos-redis)).
- Las dependencias se arman en `app/dependencies.py` mediante `Depends` de
  FastAPI.

## Estructura del proyecto

```text
document-store/
├── app/
│   ├── main.py            # app FastAPI, lifespan de MongoDB, routers
│   ├── config.py          # Settings con pydantic-settings (.env)
│   ├── dependencies.py    # inyección: Settings → DB → Repository → Service
│   ├── routers/
│   │   ├── health.py
│   │   └── documents.py
│   ├── services/
│   │   └── document_service.py
│   ├── repositories/
│   │   ├── document_repository.py        # interfaz (ABC)
│   │   └── mongo_document_repository.py  # implementación MongoDB
│   ├── models/
│   │   └── document.py                   # entidad de dominio
│   ├── schemas/
│   │   ├── document.py                   # DTOs Pydantic (Create/Update/Response)
│   │   └── error.py                      # ProblemDetail (RFC 9457)
│   └── utils/
├── tests/
│   ├── unit/
│   └── integration/
├── docs/
│   └── api-contract.md    # contrato HTTP (Issue #1)
├── .github/workflows/
│   └── ci.yml             # lint, tests, build Docker y smoke test (Issue #9)
├── main.py                # entrypoint: uvicorn con HOST, PORT, DEBUG y GRACEFUL_SHUTDOWN_SECONDS de la config
├── pyproject.toml
├── uv.lock
├── .python-version        # 3.14
├── .env.example
├── .gitignore
├── .dockerignore
├── Dockerfile
└── README.md
```

## API

La API se expone bajo el prefijo:

```text
/api/v1
```

Endpoints:

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Liveness: el proceso está vivo (no toca MongoDB) |
| GET | `/ready` | Readiness: MongoDB responde (`503` si no) |
| POST | `/api/v1/documents` | Crear un documento (implementado) |
| GET | `/api/v1/documents` | Listar documentos (implementado) |
| GET | `/api/v1/documents/{document_id}` | Obtener un documento (implementado) |
| PUT | `/api/v1/documents/{document_id}` | Actualizar el nombre (implementado) |
| DELETE | `/api/v1/documents/{document_id}` | Eliminar un documento (implementado) |

### Crear un documento

```bash
curl -X POST http://localhost:8000/api/v1/documents \
  -H "Content-Type: application/json" \
  -d '{"name": "Filosofia Lean", "original_filename": "Filosofia Lean.pdf",
       "checksum": "<sha256 de 64 caracteres hex en minúsculas>",
       "file_size": 734000, "page_count": 42,
       "extracted_text": "Texto extraído...", "is_processed": true}'
```

| Respuesta | Cuándo |
|---|---|
| `201 Created` | Se guardó; el cuerpo es el documento con su `id` entero y las fechas en UTC |
| `400 Bad Request` | Falta un campo, un tipo es incorrecto (validación estricta), el checksum no es SHA-256 o el JSON está mal formado |
| `409 Conflict` | Ya existe un documento con el mismo `checksum` |

Los errores usan **RFC 9457 Problem Details** (`application/problem+json`).

### Consultar documentos

```bash
curl http://localhost:8000/api/v1/documents/1
curl "http://localhost:8000/api/v1/documents?skip=0&limit=10"
```

| Respuesta | Cuándo |
|---|---|
| `200 OK` | El documento, o la página de documentos **en orden de `id` ascendente** (lista vacía si no hay) |
| `400 Bad Request` | El id no es un entero positivo, o `skip`/`limit` están fuera de rango (`skip >= 0`, `1 <= limit <= 100`) |
| `404 Not Found` | No existe un documento con ese id |

### Actualizar un documento

Solo `name` es editable. Debe ser un string de hasta 255 caracteres después
de quitar los espacios de los extremos; un nombre vacío o compuesto solo por
espacios se rechaza. El body no admite campos adicionales, incluidos los campos
protegidos del documento.

```bash
curl -X PUT http://localhost:8000/api/v1/documents/1 \
  -H "Content-Type: application/json" \
  -d '{"name": "  Nuevo nombre  "}'
```

Respuesta `200 OK`:

```json
{
  "id": 1,
  "name": "Nuevo nombre",
  "original_filename": "Filosofia Lean.pdf",
  "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "file_size": 734000,
  "page_count": 42,
  "extracted_text": "Texto extraído...",
  "is_processed": true,
  "created_at": "2026-10-14T12:00:00Z",
  "updated_at": "2026-10-21T15:30:00Z"
}
```

`id`, `checksum`, `original_filename`, `file_size`, `page_count`,
`extracted_text`, `is_processed` y `created_at` se conservan. El servidor
asigna `updated_at` en UTC con precisión de milisegundos.

| Respuesta | Cuándo |
|---|---|
| `200 OK` | Se actualizó el nombre y el cuerpo contiene el documento completo |
| `400 Bad Request` | El id no es un entero positivo, el JSON o el nombre son inválidos, o hay campos adicionales |
| `404 Not Found` | No existe un documento con ese id |

### Eliminar un documento

```bash
curl -i -X DELETE http://localhost:8000/api/v1/documents/1
```

La respuesta `204 No Content` no contiene cuerpo cuando el documento se
elimina correctamente. El `document_id` debe ser un entero positivo.

| Respuesta | Cuándo |
|---|---|
| `204 No Content` | El documento existía y fue eliminado |
| `400 Bad Request` | El id no es un entero positivo |
| `404 Not Found` | No existe un documento con ese id |

### Errores

Todas las respuestas de error, incluidas las que arma FastAPI y las no
previstas, usan **RFC 9457 Problem Details** (`application/problem+json`):

```json
{
  "type": "about:blank",
  "title": "Not Found",
  "status": 404,
  "detail": "No existe un documento con id 42.",
  "instance": "http://localhost:8000/api/v1/documents/42"
}
```

| Código | Cuándo |
|---|---|
| `400 Bad Request` | Datos inválidos en el body, el id de la ruta o los parámetros de consulta (validación estricta) |
| `404 Not Found` | No existe un documento con ese id, o la ruta no existe |
| `405 Method Not Allowed` | El método no está permitido en esa ruta (incluye el header `Allow`) |
| `409 Conflict` | Ya existe un documento con el mismo `checksum` |
| `500 Internal Server Error` | Error no previsto; el detalle es genérico y no expone mensajes internos |
| `503 Service Unavailable` | MongoDB no responde (sin `Retry-After`: es una caída, no una carga pasajera) |

El servicio **nunca responde `422`**: la validación es estricta y los datos
inválidos salen como `400`, por eso el `422` que FastAPI agrega por defecto
tampoco aparece en `/docs`. Cualquier endpoint de documentos puede responder
`503` si MongoDB no está disponible, igual que `/ready`; `/health` no depende
de la base.

El contrato HTTP completo (requests, responses, errores y reglas de negocio)
está documentado en [`docs/api-contract.md`](docs/api-contract.md) (Issue #1).

Con la aplicación en ejecución, la documentación interactiva generada por
FastAPI está disponible en `/docs` (Swagger UI) y `/openapi.json`.

## Persistencia

La información se almacena en MongoDB, en dos colecciones:

- `documents`: un documento por PDF procesado, con **índices únicos** sobre
  `id` y `checksum` (la base garantiza que no haya duplicados aunque lleguen
  dos altas a la vez).
- `counters`: la secuencia de ids, incrementada de forma atómica.

Las fechas se guardan en UTC con precisión de milisegundos.

El documento deberá incluir, como mínimo:

- identificador;
- nombre;
- nombre original del archivo;
- checksum;
- tamaño del archivo;
- cantidad de páginas;
- texto extraído;
- estado de procesamiento;
- fecha de creación;
- fecha de actualización.

El `checksum` deberá ser único para evitar guardar el mismo documento más de una
vez.

## Configuración

Las variables de entorno están documentadas en `.env.example`. Para correr el
proyecto localmente, copiá el archivo y ajustá los valores según tu entorno:

```bash
cp .env.example .env
```

No se deben commitear credenciales reales ni archivos `.env` (el `.gitignore`
ya los excluye).

Variables disponibles:

| Variable | Default | Descripción |
|---|---|---|
| `APP_NAME` | `document-store` | Nombre de la aplicación |
| `APP_VERSION` | `0.3.0` | Versión expuesta en OpenAPI |
| `DEBUG` | `false` | Modo debug / recarga automática |
| `HOST` | `0.0.0.0` | Host del servidor |
| `PORT` | `8000` | Puerto del servidor. En Docker también lo usa el `HEALTHCHECK`: se cambia sin reconstruir la imagen |
| `GRACEFUL_SHUTDOWN_SECONDS` | `10` | Segundos que uvicorn espera las requests en curso al recibir `SIGTERM` (12-Factor IX). Tiene que ser menor que el `stop_grace_period` del compose (15 s): si no, Docker mata el proceso antes de que cierre |
| `API_V1_PREFIX` | `/api/v1` | Prefijo de la API |
| `DATABASE_URL` | `mongodb://localhost:27017` | URI de conexión a MongoDB |
| `DATABASE_NAME` | `document_store` | Nombre de la base de datos |
| `DATABASE_TIMEOUT_MS` | `3000` | Timeout de conexión y de selección del servidor (ms) |
| `REDIS_URL` | *(vacío)* | URL de Redis para el cache de documentos. Vacío = sin cache. En el stack: `redis://:<clave>@redis:6379/0` |
| `CACHE_TTL_SECONDS` | `300` | Segundos que dura cada documento en el cache |
| `REDIS_TIMEOUT_MS` | `500` | Timeout de Redis (ms): si no responde, se lee de MongoDB |

## Cache de documentos (Redis)

Patrón **Cache-Aside** con Redis como *backing service* (12-Factor IV): se
activa con `REDIS_URL`, sin tocar el código. MongoDB sigue siendo la fuente de
verdad; Redis solo guarda copias.

| Operación | Qué hace con el cache |
|---|---|
| `GET /api/v1/documents/{id}` | Primero Redis (`documento:{id}`). Si no está, MongoDB y lo guarda con TTL |
| `POST /api/v1/documents` | Guarda el documento creado (write-through): el primer `GET` ya sale del cache |
| `PUT /api/v1/documents/{id}` | Guarda el documento renombrado; si el id no existe, invalida la entrada |
| `DELETE /api/v1/documents/{id}` | Invalida la entrada, aunque el borrado falle |
| `GET /api/v1/documents` (listar) | No usa cache: cada alta o borrado cambia las páginas |

Diseño:

- **Decorador del repositorio** (`CachedDocumentRepository`): envuelve al de
  MongoDB con la misma interfaz, así que el service no sabe que el cache
  existe (OCP y DIP de SOLID). Sin `REDIS_URL`, el decorador usa un cache nulo.
- **Nunca es un punto de falla:** si Redis no responde, se registra un warning
  y se lee de MongoDB, con un timeout corto (`REDIS_TIMEOUT_MS`).
- **TTL** (`CACHE_TTL_SECONDS`): si una invalidación se pierde (Redis caído
  justo en ese momento), el dato viejo dura como mucho ese tiempo.

Para verlo funcionar en el stack de `infrastructure`:

```bash
docker exec redis sh -c 'redis-cli --no-auth-warning -a "$REDIS_PASSWORD" keys "documento:*"'
docker exec redis sh -c 'redis-cli --no-auth-warning -a "$REDIS_PASSWORD" ttl documento:1'
```

## Desarrollo local

### Requisitos

- [uv](https://docs.astral.sh/uv/) instalado (`uv` gestiona automáticamente
  Python 3.14, definido en `.python-version`).
- MongoDB 7 disponible en `DATABASE_URL` para los endpoints de documentos y
  `/ready` (el `/health` no lo requiere).
- Docker, solo para construir y correr la imagen.

### Instalación

```bash
uv sync
```

### Ejecución

Con uvicorn y recarga automática:

```bash
uv run uvicorn app.main:app --reload
```

O mediante el entrypoint, que toma `HOST`, `PORT`, `DEBUG` y
`GRACEFUL_SHUTDOWN_SECONDS` de la configuración (es lo que ejecuta la imagen
Docker):

```bash
uv run python main.py
```

## Healthcheck: `/health` y `/ready`

El servicio expone dos chequeos, en el puerto `PORT` (8000 por defecto):

| Endpoint | Pregunta | MongoDB caído | Quién lo usa |
|---|---|---|---|
| `/health` | **Liveness**: ¿el proceso está vivo? | `200 {"status":"ok"}`: no toca la base | Diagnóstico; un orquestador que reinicia procesos colgados |
| `/ready` | **Readiness**: ¿puede atender? Hace `ping` a MongoDB | `503` Problem Details | El `HEALTHCHECK` de la imagen, y con él el compose y Traefik |

```bash
curl http://localhost:8000/health
# {"status":"ok"}
curl http://localhost:8000/ready
# {"status":"ready"}            con MongoDB arriba
# 503 application/problem+json  con MongoDB caído:
# {"type":"about:blank","title":"Service Unavailable","status":503,
#  "detail":"La base de datos no está disponible; reintentar más tarde.","instance":".../ready"}
```

Si la base no responde, la app arranca igual: `/health` sigue en `200`, `/ready`
y los endpoints de documentos responden `503`, y los índices se crean apenas
MongoDB esté disponible. `/ready` usa la misma conexión de la app (no abre otra)
y tarda como mucho `DATABASE_TIMEOUT_MS` (3 s) en darse cuenta.

La imagen Docker define un `HEALTHCHECK` contra `/ready` cada 30 s (timeout 5 s,
mayor que esos 3 s, para recibir el `503` en lugar de cortar antes; 3
reintentos). Con MongoDB caído el contenedor pasa a `unhealthy` y vuelve a
`healthy` cuando la base responde. El estado se ve con `docker ps` o
`docker inspect --format '{{.State.Health.Status}}' <contenedor>`.

## Docker

La imagen se construye en dos etapas: instala las dependencias de producción
con `uv` desde `uv.lock` y la imagen final (Python 3.14 slim) solo lleva el
entorno virtual y el código de `app/`, sin `uv`, tests ni dependencias de
extracción de PDF. Corre con un usuario sin privilegios y arranca con
`python main.py`. Toda la configuración llega por variables de entorno: el
puerto es `ENV PORT=8000` por defecto (`EXPOSE ${PORT}` es solo
documentación) y el `HEALTHCHECK` usa ese mismo `PORT`.

```bash
docker build -t document-store .
docker run --rm -p 8000:8000 --env-file .env document-store
docker run --rm -p 9000:9000 -e PORT=9000 --env-file .env document-store   # otro puerto, misma imagen
```

**Apagado ordenado.** `python main.py` es el PID 1 y recibe el `SIGTERM` de
`docker stop`: uvicorn deja de aceptar conexiones, espera las requests en curso
hasta `GRACEFUL_SHUTDOWN_SECONDS` y el lifespan cierra el cliente de MongoDB.
En los logs se ve:

```text
INFO:     Shutting down
INFO:     Waiting for application shutdown.
INFO:     Application shutdown complete.
INFO:     Finished server process [1]
```

`DATABASE_URL` tiene que apuntar a un MongoDB alcanzable **desde el
contenedor**: `localhost` dentro del contenedor es el propio contenedor. Por
ejemplo, con MongoDB en otro contenedor de la misma red:

```bash
docker network create document-store
docker run -d --name mongo --network document-store mongo:7-jammy
docker run --rm -p 8000:8000 --network document-store \
  -e DATABASE_URL=mongodb://mongo:27017 document-store
```

## Tests

```bash
uv run pytest
```

Los tests de persistencia usan un MongoDB real: cada test crea una base con
nombre único y la borra al terminar. Por defecto se conectan a
`mongodb://localhost:27017`; se puede cambiar con `TEST_DATABASE_URL`. Si no
hay MongoDB, esos tests se saltean con un aviso (con `REQUIRE_MONGO=1`
fallan, como en CI). Para levantar uno descartable:

```bash
docker run -d --rm --name document-store-test-mongo -p 27017:27017 mongo:7-jammy
```

Hay tests unitarios (modelo, schemas, servicio, configuración) y de
integración (endpoints, repositorio contra MongoDB, manejo de errores,
arranque de la app, `/health` y `/ready` con y sin MongoDB).

## Calidad de código

El lint y el formato se verifican con [Ruff](https://docs.astral.sh/ruff/)
(reglas `E`, `F`, `I`, `UP`, `B` y `ASYNC`, configuradas en `pyproject.toml`):

```bash
uv run ruff check .
uv run ruff format --check .
```

Para corregir automáticamente:

```bash
uv run ruff check --fix .
uv run ruff format .
```

## Integración continua

El workflow [`.github/workflows/ci.yml`](.github/workflows/ci.yml) corre en
cada push a `main` y en cada Pull Request:

1. **Lint y tests**: instala Python y `uv`, las dependencias (`uv sync
   --locked`), verifica lint y formato con Ruff y corre `pytest` contra un
   MongoDB levantado como servicio (`REQUIRE_MONGO=1`, así que ningún test
   se saltea).
2. **Build Docker y smoke test**: construye la imagen, la levanta junto a un
   MongoDB y verifica que `/health` y `/ready` respondan `200`, que el
   `HEALTHCHECK` de la imagen llegue a `healthy` y que se pueda crear y
   consultar un documento. Después detiene MongoDB y verifica que `/ready`
   responda `503`, que `/health` siga en `200` y que el contenedor pase a
   `unhealthy`.

## Dependencias entre servicios

```text
pdf-extractext
        ↓
orchestrator-service
        ↓
document-store
        ↓
MongoDB
```

`orchestrator-service` coordina el flujo, `pdf-extractext` extrae el texto y
`document-store` persiste los datos.

## Issues relacionados

- Issue #1: Definir contrato HTTP
- Issue #2: Inicializar arquitectura
- Issue #3: Implementar modelo y persistencia
- Issue #4: Implementar creación de documentos
- Issue #5: Implementar consultas y paginación
- Issue #6: Implementar actualización
- Issue #7: Implementar eliminación
- Issue #8: Implementar manejo de errores y pruebas
- Issue #9: Configurar Docker, healthcheck y CI
