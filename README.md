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

## Arranque del backend

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

1. **Esquema del guion** — Ollama genera sinopsis, personajes, escenas, utilería y el guion por episodio con desglose de planos `[N-M]` (tiempo/lugar, cast, diálogos). Regenerable.
2. **Biblioteca de recursos** — personajes/escenas/utilería con **variantes** (apariencias alternativas), imágenes de referencia (subidas; generación por IA preparada como plug-in) y voz por personaje.
3. **Videos por episodio** — cada fragmento se genera vía el proveedor de video configurado; al completarse, el ensamblaje une fragmentos + TTS (Edge-TTS) + subtítulos SRT (opcional: quemados) → `final.mp4`.

## Proveedores (plug-ins)

| Dominio | Implementado | Previstos |
|---|---|---|
| Guion (LLM) | **Ollama** | Gemini, OpenAI |
| Imágenes | Subida manual | GPT Image, Seedream, ComfyUI |
| Video | **Mock** (clips de prueba con ffmpeg) | Seedance 2.0/2.5 (Volcengine Ark), Veo 3 (Vertex), Omni 1.1 |
| Voz (TTS) | **Edge-TTS** | OpenAI TTS, ElevenLabs |

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

## Tests

```powershell
cd backend
.\.venv\Scripts\python -m pytest        # 35 tests (unitarios + E2E del pipeline)

cd frontend
npm test                                # vitest
npm run build                           # typecheck + build
```

## Notas

- Almacenamiento local: `backend/storage/<project_id>/{images,videos,audio,episodes,uploads}/`.
- Los trabajos (Jobs) se cancelan, muestran progreso y se reencolan si el worker se cae (`reclaim` a los 5 min).
- Redis en Windows: `choco install redis-64` o Docker `docker run -d -p 6379:6379 redis`.
