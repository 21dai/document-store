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
MongoDB (implementación con PyMongo async)
```

- **Router** (`app/routers/`): adapta HTTP, valida requests con schemas
  Pydantic y delega en la capa de servicio.
- **Service** (`app/services/`): contiene la lógica de negocio y depende solo
  de la abstracción `DocumentRepository` (principio de inversión de
  dependencias).
- **Repository** (`app/repositories/`): define el puerto
  `DocumentRepository` (ABC) y su implementación `MongoDocumentRepository`
  con PyMongo asíncrono.
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
├── main.py                # entrypoint: uvicorn con HOST y PORT de la config
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
| GET | `/health` | Verificar que el servicio está activo |
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
`503` si MongoDB no está disponible; `/health` no depende de la base.

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
| `APP_VERSION` | `0.1.0` | Versión expuesta en OpenAPI |
| `DEBUG` | `false` | Modo debug / recarga automática |
| `HOST` | `0.0.0.0` | Host del servidor |
| `PORT` | `8000` | Puerto del servidor |
| `API_V1_PREFIX` | `/api/v1` | Prefijo de la API |
| `DATABASE_URL` | `mongodb://localhost:27017` | URI de conexión a MongoDB |
| `DATABASE_NAME` | `document_store` | Nombre de la base de datos |
| `DATABASE_TIMEOUT_MS` | `3000` | Timeout de conexión y de selección del servidor (ms) |

## Desarrollo local

### Requisitos

- [uv](https://docs.astral.sh/uv/) instalado (`uv` gestiona automáticamente
  Python 3.14, definido en `.python-version`).
- MongoDB 7 disponible en `DATABASE_URL` para los endpoints de documentos
  (el `/health` no lo requiere).
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

O mediante el entrypoint, que toma `HOST`, `PORT` y `DEBUG` de la
configuración (es lo que ejecuta la imagen Docker):

```bash
uv run python main.py
```

## Healthcheck

El servicio escucha en el puerto **8000** (configurable con `PORT`) y expone:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

`/health` es un chequeo de **liveness**: responde `200` mientras el proceso
de la API esté vivo y **no depende de MongoDB**. Si la base no responde, la app
arranca igual, `/health` sigue en `200`, los endpoints de documentos responden
`503` y los índices se crean apenas MongoDB esté disponible. Por ahora no hay
un endpoint de readiness que verifique la base.

La imagen Docker define un `HEALTHCHECK` que consulta `/health` cada 30 s
(timeout 3 s, 3 reintentos); el estado se ve con `docker ps` o
`docker inspect --format '{{.State.Health.Status}}' <contenedor>`.

## Docker

La imagen se construye en dos etapas: instala las dependencias de producción
con `uv` desde `uv.lock` y la imagen final (Python 3.14 slim) solo lleva el
entorno virtual y el código de `app/`, sin `uv`, tests ni dependencias de
extracción de PDF. Corre con un usuario sin privilegios y expone el puerto
`8000`. Toda la configuración llega por variables de entorno.

```bash
docker build -t document-store .
docker run --rm -p 8000:8000 --env-file .env document-store
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
arranque de la app y `/health`).

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
   MongoDB y verifica que `/health` responda `200`, que el `HEALTHCHECK` de
   la imagen llegue a `healthy` y que se pueda crear y consultar un
   documento.

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
