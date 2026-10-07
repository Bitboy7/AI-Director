# AI Director

Plataforma personal estilo "Short Drama" que genera historias en video por episodios usando IA.

**Flujo:** Proyecto (historia) → Episodios → Fragmentos (planos de 10-12 s). Un episodio de 1:30 ≈ 9 fragmentos.

## Estructura

```
backend/    API FastAPI + workers arq (cola Redis)
frontend/   Admin web (Vite + React + TypeScript + Tailwind + shadcn/ui, tema oscuro)
```

## Requisitos

- Python 3.11+
- Redis (para la cola de trabajos)
- ffmpeg + ffprobe en PATH (ensamblaje de video)
- Node.js 20+ (solo frontend)
- Ollama (opcional pero recomendado: genera los guiones con un modelo local)

## Arranque rápido (todo en uno)

```powershell
python start.py                 # API + workers + frontend (+ Redis via Docker si falta)
python start.py --no-frontend   # solo backend
python start.py --check         # verifica el entorno sin arrancar nada
python start.py --skip-install  # no reinstala dependencias
```

Crea el venv e instala dependencias si faltan, levanta Redis con Docker si no está
corriendo, arranca la API (8000), los 3 workers arq y Vite (5173), y detiene todo
con Ctrl+C. Logs: `logs/start.log` y `logs/<servicio>.log`.

## Arranque manual del backend

```powershell
cd backend
python -m venv .venv
.\.venv\Scripts\python -m pip install -e ".[dev]"
copy .env.example .env        # ajusta variables si hace falta

# Terminal 1: API
.\.venv\Scripts\python -m uvicorn app.main:app --reload --port 8000

# Terminal 2: worker de cola (default; también: video, assembly)
.\.venv\Scripts\python -m app.jobs.run default
.\.venv\Scripts\python -m app.jobs.run video
.\.venv\Scripts\python -m app.jobs.run assembly
```

OpenAPI: <http://localhost:8000/docs>

## Arranque del frontend

```powershell
cd frontend
npm install
npm run dev     # http://localhost:5173 (proxy /api -> :8000)
```

## Pipeline (wizard de 3 pasos)

1. **Esquema del guion** — el LLM configurado (por defecto Ollama) genera sinopsis, personajes, escenas, utilería y el guion por episodio con desglose de planos `[N-M]` (tiempo/lugar, cast, diálogos). Regenerable.
2. **Biblioteca de recursos** — personajes/escenas/utilería con **variantes** (apariencias alternativas), imágenes de referencia (subidas o generadas con Nano Banana/Gemini) y voz por personaje.
3. **Videos por episodio** — cada fragmento se genera vía el proveedor de video configurado (Mock o Gemini Omni); al completarse, el ensamblaje une fragmentos + TTS (Edge-TTS) + subtítulos SRT (opcional: quemados) → `final.mp4`.

El proveedor **y el modelo** se eligen en cada paso desde la propia UI (selector por
paso) y se guardan en `project.settings` (`llm_provider`/`llm_model`,
`image_provider`/`image_model`, `video_provider`/`video_model`). Al elegir un
proveedor, la app descarga dinámicamente sus modelos disponibles
(`GET /api/v1/providers/{kind}/{provider}/models`): fal (catálogo completo por
categoría), Gemini (modelos de imagen/video), Ollama (`/api/tags`).

## Proveedores (plug-ins)

| Dominio | Implementado | Previstos |
|---|---|---|
| Guion (LLM) | **Ollama**, **Gemini** (`gemini-3.8-flash`), **OpenAI** (`gpt-4o-mini`) | — |
| Imágenes | **Gemini (Nano Banana)**, **fal.ai** (FLUX, Nano Banana 2, etc.) | GPT Image, Seedream, ComfyUI |
| Video | **Mock** (clips de prueba con ffmpeg), **Gemini Omni** (`gemini-omni-1.1-flash`), **fal.ai** (Kling, Wan, etc. vía cola) | Seedance 2.0/2.5 (Volcengine Ark), Veo 3 (Vertex) |
| Voz (TTS) | **Edge-TTS** | OpenAI TTS, ElevenLabs |

En el selector de cada paso **solo se muestran los proveedores con su API configurada**
(con key en Configuración, variable de entorno, o que no la requieren como Ollama/Edge/Mock).

**Progreso de los trabajos:** los jobs LLM (guion y recursos) reportan un % estimado según el
consumo de CPU del proceso mientras generan (monitor de recursos, tope 90% hasta completar);
los jobs de video lo estiman por tiempo transcurrido. El frontend muestra la barra con ese % y
una nota "Progreso estimado según el uso de recursos del proceso".

**Credenciales de Google (Gemini/Nano Banana/Omni):** una sola API key de
[Google AI Studio](https://aistudio.google.com/) sirve para imágenes y video. Guárdala en la
UI de Configuración (provider `gemini` y/o `omni`) o define `GEMINI_API_KEY`/`GOOGLE_API_KEY`
en `backend/.env`. Nota: las claves nuevas de AI Studio son "auth keys" ligadas a un proyecto
de Google Cloud y Google rechaza claves sin restricciones.

**Credenciales de fal.ai:** genera una API key en <https://fal.ai/dashboard/keys> y guárdala
en Configuración (provider `fal`) o define `FAL_API_KEY` en `backend/.env`. El mismo provider
sirve para imágenes y video; al seleccionarlo en el paso correspondiente se listan sus
modelos (imagen: categoría `text-to-image`; video: `text-to-video` + `image-to-video`).

Los contratos están en `backend/app/providers/base.py`; registra nuevas implementaciones con `register_provider(kind, name, factory)` en el subpaquete correspondiente (`llm/`, `image/`, `video/`, `tts/`).

## Variables de entorno (`backend/.env`)

| Variable | Default | Descripción |
|---|---|---|
| `DATABASE_URL` | `sqlite+aiosqlite:///./data.db` | Base de datos |
| `REDIS_URL` | `redis://localhost:6379` | Cola de trabajos |
| `OLLAMA_URL` | `http://localhost:11434` | Endpoint de Ollama |
| `OLLAMA_MODEL` | `qwen2.5:14b` | Modelo para guiones |
| `STORAGE_DIR` | `./storage` | Videos/imágenes/audio locales |
| `FFMPEG_PATH` / `FFPROBE_PATH` | `ffmpeg` / `ffprobe` | Binarios de ffmpeg |
| `SCRIPT_GEN_RETRIES` | `3` | Reintentos de parseo del JSON del LLM |
| `MAX_UPLOAD_MB` | `10` | Límite de subida de imágenes |
| `SUBTITLE_BURN_DEFAULT` | `false` | Quemar subtítulos por defecto |
| `GEMINI_API_KEY` / `GOOGLE_API_KEY` / `OMNI_API_KEY` | — | API key de Google AI Studio (Gemini/Nano Banana/Omni); alternativa a la UI de Configuración |
| `GEMINI_ENDPOINT` | `https://generativelanguage.googleapis.com` | Endpoint de la Gemini API |
| `FAL_API_KEY` / `FAL_KEY` | — | API key de fal.ai (imágenes y video); alternativa a la UI de Configuración |
| `OPENAI_API_KEY` | — | API key de OpenAI (guiones); alternativa a la UI de Configuración |
| `SCRIPT_GEN_BUDGET_SECONDS` | `120` | Presupuesto para el % de progreso del guion (por uso de CPU) |
| `RESOURCE_GEN_BUDGET_SECONDS` | `60` | Presupuesto para el % de progreso de recursos |

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest        # tests unitarios + E2E del pipeline

cd frontend
npm test                                # vitest
npm run build                           # typecheck + build
```

## Notas

- Almacenamiento local: `backend/storage/<project_id>/{images,videos,audio,episodes,uploads}/`.
- Los trabajos (Jobs) se cancelan, muestran progreso y se reencolan si el worker se cae (`reclaim` a los 5 min).
- Redis en Windows: `choco install redis-64` o Docker `docker run -d -p 6379:6379 redis`.
