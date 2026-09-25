# Sannia POC — Backend de digitalización de formularios

Backend FastAPI de la POC:

```text
PDF/foto
  ↓
import
  ↓
worker persistente
  ↓
OpenAI
  ↓
draft_json
  ↓
revisión humana
  ↓
plantilla versionada
  ↓
respuesta + evidencia
  ↓
submit
  ↓
reporte
```

## Arquitectura

Se conserva el patrón del proyecto:

```text
Route
  ↓
Service
  ↓
Repository / Provider
  ↓
PostgreSQL / S3 / OpenAI
```

- `routes/`: HTTP, parámetros y códigos.
- `services/`: reglas y orquestación.
- `repositories/`: SQLAlchemy y persistencia.
- `interfaces/`: contratos que desacoplan infraestructura.
- `cloud/`: implementaciones externas S3/OpenAI.
- `workers/`: procesamiento durable sobre `worker_tasks`.
- `dto/`: contratos de entrada/salida y validación.

## Preparación

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
pip install -r requirements.txt
copy .env.example .env
```

Completa `.env` con PostgreSQL, S3 y `OPENAI_API_KEY`.

### AWS

Las credenciales estáticas son opcionales.

En local puedes usar:

```env
AWS_ACCESS_KEY_ID=...
AWS_SECRET_ACCESS_KEY=...
```

En AWS puedes dejarlas vacías y usar IAM Role / default credential chain de boto3.

## Base de datos

```powershell
alembic upgrade head
```

## Levantar API + worker

El worker vive dentro del proceso FastAPI y arranca cuando:

```env
WORKER_ENABLED=true
```

Ejecutar:

```powershell
python -m uvicorn app.main:app --reload --host 0.0.0.0 --port 8000
```

Swagger:

```text
http://127.0.0.1:8000/docs
```

Detener API + worker:

```text
Ctrl + C
```

## Flujo de importación

```text
POST /poc/imports
GET  /poc/imports/{id}
```

Estados:

```text
received
  ↓
processing
  ↓
requires_review
```

o:

```text
received
  ↓
processing
  ↓
failed
```

La IA nunca crea una plantilla. Solo produce `draft_json`.

## Confirmación del draft y métricas

Si `POST /poc/templates` recibe `source_import_id`, ese import debe estar en `requires_review` y tener `draft_json`. Un import en `received`, `processing` o `failed` no puede confirmarse como plantilla y devuelve `source_import_not_ready`.

Al confirmar, `TemplateService` compara el `draft_json` original con la definición revisada y actualiza `form_imports.corrections_count`. Sin cambios queda en `0`; si el usuario modifica título, sección o campo, aumenta según los cambios lógicos.

## Tipos de campo

`select` es un `FieldType` oficial del backend. Solo los campos `select` aceptan `options`; deben tener entre 2 y 30 opciones y valores únicos. Las respuestas a `select` se validan contra esos valores.

## Retry de IA

Los errores transitorios (`timeout`, `rate limit`, conexión o 5xx) se propagan al worker.

Mientras quedan intentos:

```text
form_import = processing
worker_task = pending para retry
```

Cuando se agotan:

```text
form_import = failed
worker_task = error
```

Los errores permanentes (por ejemplo key inválida / request inválido) terminan el import sin retry durable.

## OpenAI PDF

Responses API recibe PDF como `input_file`.

El payload usa:

```json
{
  "type": "input_file",
  "filename": "formulario.pdf",
  "file_data": "data:application/pdf;base64,...",
  "detail": "high"
}
```

`detail` en `input_file` para PDF es válido en la API actual. Se conserva y está cubierto por test.

Para imagen se usa:

```json
{
  "type": "input_image",
  "image_url": "data:image/jpeg;base64,...",
  "detail": "high"
}
```

## Responses ligadas a versión exacta

Para crear una respuesta:

```http
POST /poc/responses
```

Body:

```json
{
  "template_version_id": "UUID_DE_LA_VERSION",
  "name": "Visita 001",
  "job_demo_id": "opcional"
}
```

Ya no se selecciona implícitamente la última versión. Así la versión que vio el usuario queda congelada aunque aparezca otra versión entre render y creación.

## Tests

```powershell
pip install -r requirements-dev.txt
pytest -q
```

La prueba real contra OpenAI está deshabilitada por default.

Para ejecutarla:

```powershell
$env:RUN_OPENAI_INTEGRATION="1"
pytest -q tests/integration/test_openai_pdf_integration.py
```

Requiere una `OPENAI_API_KEY` válida.

## Documentación de cierre

Ver:

```text
docs/BACKEND_CLOSURE.md
```
