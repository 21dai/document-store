# document-store

Microservicio responsable de persistir y administrar documentos procesados.

## Estado del proyecto

En desarrollo.

El contrato HTTP está definido en [`docs/api-contract.md`](docs/api-contract.md)
(Issue #1) y la arquitectura inicial del servicio ya está implementada
(Issue #2). Ya funcionan la persistencia en MongoDB (#3), el alta (#4), las
consultas con paginación (#5) y la actualización del nombre (#6). El borrado
queda pendiente para el Issue #7.

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
│       └── test_health.py
├── docs/
│   └── api-contract.md    # contrato HTTP (Issue #1)
├── main.py                # entrypoint de conveniencia para desarrollo
├── pyproject.toml
├── uv.lock
├── .python-version        # 3.14
├── .env.example
├── .gitignore
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
| DELETE | `/api/v1/documents/{document_id}` | Eliminar un documento (pendiente #7) |

### Crear un documento

```bash
curl -X POST http://localhost:8000/api/v1/documents \n  -H "Content-Type: application/json" \n  -d '{"name": "Filosofia Lean", "original_filename": "Filosofia Lean.pdf",
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
- MongoDB disponible en `DATABASE_URL` para los endpoints de documentos
  (el `/health` no lo requiere).

### Instalación

```bash
uv sync
```

### Ejecución

Con uvicorn (recomendado):

```bash
uv run uvicorn app.main:app --reload
```

O mediante el entrypoint de conveniencia:

```bash
uv run python main.py
```

Luego verificá el healthcheck:

```bash
curl http://localhost:8000/health
# {"status":"ok"}
```

### Docker

```bash
docker build -t document-store .
docker run --rm -p 8000:8000 --env-file .env document-store
```

La configuración completa de Docker, healthcheck y CI se aborda en el
issue #9.

## Tests

```bash
uv run pytest
```

Los tests de persistencia usan un MongoDB real: cada test crea una base con
nombre único y la borra al terminar. Por defecto se conectan a
`mongodb://localhost:27017`; se puede cambiar con `TEST_DATABASE_URL`. Si no
hay MongoDB, esos tests se saltean con un aviso (con `REQUIRE_MONGO=1`
fallan, para CI). Para levantar uno descartable:

```bash
docker run -d --rm --name document-store-test-mongo -p 27017:27017 mongo:7
```

El proyecto tendrá:

- tests unitarios para modelos, servicios y repositorios;
- tests de integración para los endpoints;
- tests relacionados con MongoDB;
- tests para documentos duplicados y documentos inexistentes.

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
