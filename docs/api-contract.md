# Contrato HTTP — document-store

Documento que define el contrato HTTP inicial de `document-store`, el
microservicio responsable de persistir y administrar documentos procesados en
MongoDB.

> Referencia: Issue #1 — Definir contrato HTTP para la persistencia de
> documentos.

## Alcance

`document-store` **no** extrae texto de PDFs ni recibe archivos PDF. Recibe
datos ya procesados por `pdf-extractext` y enviados por `orchestrator-service`.

Responsabilidades:

- Persistir documentos procesados en MongoDB.
- Detectar documentos duplicados mediante un checksum SHA-256 único.
- Consultar documentos por ID.
- Listar documentos con paginación.
- Actualizar campos editables.
- Eliminar documentos.
- Devolver errores HTTP consistentes en formato RFC 9457 (Problem Details).

## Convenciones generales

- URL base: `/api/v1`
- Content-Type de requests y responses: `application/json`
- Los errores siguen el formato **RFC 9457 Problem Details**
  (`application/problem+json`):

```json
{
  "type": "about:blank",
  "title": "Document not found",
  "status": 404,
  "detail": "No existe un documento con id 42.",
  "instance": "/api/v1/documents/42"
}
```

### Formato del checksum

- SHA-256 en representación hexadecimal.
- Exactamente **64 caracteres**, minúsculas.
- Expresión regular de validación: `^[a-f0-9]{64}$`
- El checksum lo calcula `orchestrator-service` a partir de los bytes del PDF;
  `document-store` solo lo valida, lo persiste y garantiza su unicidad.

### Identificador de documento

- `document_id` es un **entero positivo secuencial** (1, 2, 3, …) que
  genera `document-store` al crear el documento (decisión del equipo, issue #3).
- La secuencia se lleva en la colección `counters` con un incremento atómico,
  así que dos altas simultáneas nunca reciben el mismo id. Un alta rechazada
  (por ejemplo, checksum duplicado) puede dejar un hueco en la numeración.

## Endpoints

### Healthcheck

```
GET /health
```

Verifica que el servicio está activo. No requiere conexión a MongoDB.

**Respuesta `200 OK`:**

```json
{
  "status": "ok"
}
```

---

### Crear documento

```
POST /api/v1/documents
```

**Request** (`application/json`):

```json
{
  "name": "Filosofia Lean",
  "original_filename": "Filosofia Lean.pdf",
  "checksum": "\u003csha256 hexadecimal de 64 caracteres\u003e",
  "file_size": 734000,
  "page_count": 42,
  "extracted_text": "Texto extraído del PDF...",
  "is_processed": true
}
```

| Campo | Tipo | Reglas |
|---|---|---|
| `name` | string | Requerido, 1–255 caracteres |
| `original_filename` | string | Requerido, 1–255 caracteres |
| `checksum` | string | Requerido, formato `^[a-f0-9]{64}$`, único |
| `file_size` | integer | Requerido, `>= 0` (bytes) |
| `page_count` | integer | Requerido, `>= 0` |
| `extracted_text` | string | Requerido (puede ser string vacío) |
| `is_processed` | boolean | Requerido |

La validación es **estricta**: cada campo debe llegar con su tipo JSON (un número
como texto, `"734000"`, o un booleano como `"true"` o `1` se rechazan con 400).
Los espacios al principio y al final de `name` y `original_filename` se quitan
antes de validar, así que un nombre solo con espacios es inválido.

**Respuesta `201 Created`:**

```json
{
  "id": 1,
  "name": "Filosofia Lean",
  "original_filename": "Filosofia Lean.pdf",
  "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
  "file_size": 734000,
  "page_count": 42,
  "extracted_text": "Texto extraído del PDF...",
  "is_processed": true,
  "created_at": "2026-10-14T12:00:00Z",
  "updated_at": "2026-10-14T12:00:00Z"
}
```

**Errores:**

| Código | Situación |
|---|---|
| `400 Bad Request` | Datos inválidos (faltan campos, tipos incorrectos, checksum con formato inválido) |
| `409 Conflict` | Ya existe un documento con el mismo checksum |

---

### Consultar documento por ID

```
GET /api/v1/documents/{document_id}
```

**Respuesta `200 OK`:** el documento completo (mismo formato que la respuesta
de creación).

**Errores:**

| Código | Situación |
|---|---|
| `404 Not Found` | No existe un documento con ese ID |

---

### Listar documentos (paginado)

```
GET /api/v1/documents?skip=0&limit=10
```

| Parámetro | Tipo | Default | Reglas |
|---|---|---|---|
| `skip` | integer (query) | `0` | `>= 0` |
| `limit` | integer (query) | `10` | entre `1` y `100` |

**Respuesta `200 OK`:**

```json
[
  {
    "id": 1,
    "name": "Filosofia Lean",
    "original_filename": "Filosofia Lean.pdf",
    "checksum": "e3b0c44298fc1c149afbf4c8996fb92427ae41e4649b934ca495991b7852b855",
    "file_size": 734000,
    "page_count": 42,
    "extracted_text": "Texto extraído del PDF...",
    "is_processed": true,
    "created_at": "2026-10-14T12:00:00Z",
    "updated_at": "2026-10-14T12:00:00Z"
  }
]
```

---

### Actualizar documento

```
PUT /api/v1/documents/{document_id}
```

En la primera versión **solo se puede actualizar el nombre**. Los demás campos
(incluido el `checksum`) son inmutables.

**Request** (`application/json`):

```json
{
  "name": "Nuevo nombre"
}
```

**Respuesta `200 OK`:** el documento actualizado completo.

**Errores:**

| Código | Situación |
|---|---|
| `400 Bad Request` | Datos inválidos (nombre vacío o ausente) |
| `404 Not Found` | No existe un documento con ese ID |

---

### Eliminar documento

```
DELETE /api/v1/documents/{document_id}
```

**Respuesta `204 No Content`:** sin cuerpo.

**Errores:**

| Código | Situación |
|---|---|
| `404 Not Found` | No existe un documento con ese ID |

## Modelo de persistencia

El documento almacenado en MongoDB incluye, como mínimo:

| Campo | Descripción |
|---|---|
| `id` | Entero secuencial, identificador público del documento (**índice único**) |
| `name` | Nombre editable del documento |
| `original_filename` | Nombre original del archivo PDF |
| `checksum` | SHA-256 hexadecimal, **único** (índice único en MongoDB) |
| `file_size` | Tamaño del archivo en bytes |
| `page_count` | Cantidad de páginas |
| `extracted_text` | Texto extraído del PDF |
| `is_processed` | Estado de procesamiento |
| `created_at` | Fecha de creación (UTC, precisión de milisegundos) |
| `updated_at` | Fecha de última actualización (UTC, precisión de milisegundos) |

Colecciones: `documents` (los documentos, con índices únicos `id_unico` y
`checksum_unico`) y `counters` (la secuencia de ids). Los índices se crean al
arrancar el servicio; si MongoDB no está disponible en ese momento, se crean
en segundo plano apenas responda.

## Decisiones

- `document-store` no extrae texto de PDFs.
- `document-store` no recibe el archivo PDF en la creación.
- `orchestrator-service` calcula el checksum a partir de los bytes del PDF.
- `document-store` valida, persiste y garantiza la unicidad del checksum.
- MongoDB es responsabilidad de `document-store`.
- Los errores utilizan el formato RFC 9457 Problem Details.
- El contrato queda reflejado automáticamente en la documentación OpenAPI que
  FastAPI expone en `/docs` y `/openapi.json`.
