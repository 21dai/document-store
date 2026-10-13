# document-store

Microservicio responsable de persistir y administrar documentos procesados.

## Estado del proyecto

En desarrollo.

La arquitectura y el contrato HTTP fueron definidos, pero el microservicio
todavía está siendo implementado.

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

## Arquitectura prevista

```text
HTTP Router
    ↓
Service
    ↓
Repository
    ↓
MongoDB
```

## Estructura prevista

```text
app/
├── main.py
├── config.py
├── dependencies.py
├── routers/
├── services/
├── repositories/
├── models/
├── schemas/
└── utils/

tests/
├── unit/
└── integration/
```

## API prevista

La API se expondrá bajo el prefijo:

```text
/api/v1
```

Endpoints previstos:

| Método | Endpoint | Descripción |
|---|---|---|
| GET | `/health` | Verificar que el servicio está activo |
| POST | `/api/v1/documents` | Crear un documento |
| GET | `/api/v1/documents` | Listar documentos |
| GET | `/api/v1/documents/{document_id}` | Obtener un documento |
| PUT | `/api/v1/documents/{document_id}` | Actualizar un documento |
| DELETE | `/api/v1/documents/{document_id}` | Eliminar un documento |

El contrato HTTP definitivo se encuentra documentado en el Issue #1.

## Persistencia

La información será almacenada en MongoDB.

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

Las variables de entorno se documentarán en:

```text
.env.example
```

No se deben commitear credenciales reales ni archivos `.env`.

## Desarrollo local

Los comandos definitivos de instalación y ejecución se agregarán cuando se
complete la inicialización del proyecto con `uv`.

La aplicación deberá poder ejecutarse posteriormente con FastAPI y Uvicorn.

## Tests

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