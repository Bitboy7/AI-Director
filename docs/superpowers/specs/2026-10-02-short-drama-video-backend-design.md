# Diseño: Backend de generación de videos cortos con IA (Short Drama)

- Fecha: 2026-10-02
- Estado: Aprobado (en revisión)
- Stack: Python 3.11+ / FastAPI / arq / Redis / SQLite / ffmpeg + React (Vite, TypeScript, Tailwind, shadcn/ui)

## 1. Contexto y objetivo

Plataforma personal estilo "Short Drama" que genera videos narrativos por episodios usando IA.
Una historia se organiza como **Proyecto → Episodios → Fragmentos (planos de 10-12 s)**.
Un episodio de 1:30 minutos consta de ~9 fragmentos.

Pipeline de contenido en 3 pasos (wizard):

1. **Esquema del guion**: un LLM genera sinopsis, perfiles de personajes y el guion por episodio con desglose de planos `[N-M]` (tiempo/lugar, cast, diálogos).
2. **Biblioteca de recursos**: personajes, escenas y utilería del proyecto, cada uno con **variantes** (apariencias alternativas), imágenes de referencia (generadas por IA o subidas manualmente) y voz para personajes.
3. **Videos por episodio**: cada fragmento se convierte en un video de 10-12 s vía un proveedor externo; después se ensambla el episodio final con TTS, subtítulos y mezcla de audio.

Los videos, imágenes y audios se almacenan **localmente**.

## 2. Alcance y no-alcance

**En alcance:**

- CRUD de proyectos, episodios, recursos, variantes, imágenes de referencia y fragmentos.
- Generación de guion con LLM (primer proveedor funcional: Ollama).
- Cola de trabajos asíncrona con Redis + workers separados (arq).
- Capa de plug-ins para: LLM (guion), generación de imágenes, generación de video y TTS.
- Subida manual de imágenes de referencia.
- TTS por personaje/variante (primer proveedor: Edge-TTS).
- Subtítulos SRT sincronizados con el audio TTS, opción de quemarlos en el video.
- Ensamblaje por episodio: unión de fragmentos + pista de diálogos (ffmpeg) → `final.mp4`.
- Frontend de administración en React con estilo moderno (tema oscuro, Tailwind + shadcn/ui).
- Almacenamiento local de assets.

**Fuera de alcance (por ahora):**

- Autenticación y multi-usuario.
- Integración real con proveedores de video (Seedance 2.0/2.5, Veo 3, Omni 1.1) e imágenes (GPT Image, Seedream, ComfyUI): solo se define el contrato de plug-in. Se incluye un `MockVideoProvider` para validar el pipeline end-to-end.
- Música de fondo, ASR, doblaje automático, efectos de sonido.
- Procesamiento con GPU local.

## 3. Decisiones de arquitectura

- **Monolito modular**: API FastAPI y workers arq comparten el mismo código de dominio; Redis solo para colas; SQLite como base de datos; ffmpeg para ensamblaje.
- **arq** como gestor de cola (nativo asyncio, encaja con FastAPI async y SDKs HTTP de proveedores).
- **SQLAlchemy 2.x** con SQLite (`aiosqlite`).
- **Pydantic v2** para contratos de payloads de proveedores y API.
- Escala: personal (1 usuario). Sin auth.
- Estructura sugerida:

```
backend/
  app/
    main.py            # FastAPI app
    config.py          # settings (.env)
    db.py              # engine/session
    models/            # ORM
    schemas/           # pydantic
    api/               # routers
    services/          # lógica de dominio (scripting, assembly...)
    providers/         # llm/ image/ video/ tts/ (plug-ins)
    jobs/              # definiciones de tareas arq + worker runner
  storage/             # assets locales (por proyecto)
  tests/
frontend/              # Vite + React + TS (ver sección 9)
```

## 4. Modelo de datos

- **Project** (historia): `id`, `name`, `synopsis`, `video_style`, `aspect_ratio` (16:9), `status`, `settings` (JSON: modelo LLM, modelos por defecto de imagen/TTS), timestamps.
- **Episode**: `id`, `project_id`, `number`, `title`, `script` (JSON con desglose de planos y diálogos), `status`.
- **Resource**: `id`, `project_id`, `type` (`character` | `scene` | `prop`), `name`, `profile` (JSON estructurado: tipo, perfil visual, tags, identidad, arco, personalidad, relaciones, crecimiento). Reutilizable en todo el proyecto.
- **ResourceVariant**: `id`, `resource_id`, `name` (ej. "Base Appearance", "Transcendent Guardian"), `description` (prompt de imagen/video), `episodes` (a qué episodios aplica), `image_model`, `image_style`, `voice` (para personajes: proveedor TTS, voz, timbre).
- **ReferenceImage**: `id`, `variant_id`, `path` (relativo), `origin` (`uploaded` | `generated`), `kind` (frontal, turnaround 3 vistas, extra).
- **Fragment** (plano `[N-M]`): `id`, `episode_id`, `shot_number`, `time_place`, `cast` (ids de variantes usadas), `prompt_video`, `duration` (10-12 s), `status`, `video_path`.
- **DialogueLine**: `id`, `fragment_id`, `character_variant_id`, `text`, `order`. Fuente única para TTS y subtítulos.
- **Job**: `id`, `type` (`script_gen` | `resource_gen` | `image_gen` | `video_gen` | `tts` | `episode_assembly`), `status` (`queued` | `running` | `succeeded` | `failed` | `cancelled`), `progress` (0-100), `payload` (JSON), `result` (JSON), `error`, `parent_id`, `project_id`, timestamps.
- **Asset**: `id`, `project_id`, `kind` (`image` | `video` | `audio` | `episode` | `upload`), `path` relativo, `metadata` (JSON).

Relaciones: Project 1-N Episode; Project 1-N Resource; Resource 1-N Variant; Variant 1-N ReferenceImage; Episode 1-N Fragment; Fragment 1-N DialogueLine.

## 5. Pipeline de contenido

### Paso 1 — Esquema del guion
- Entrada: sinopsis, estilo de video, relación de aspecto, nº de episodios, duración objetivo.
- Ollama (modelo configurable, ej. `qwen2.5:14b` / `llama3.1`) genera JSON estructurado: perfiles de personajes, escenas/utilería detectadas, y por episodio: planos `[N-M]` con tiempo/lugar, cast, acción y diálogos.
- El JSON se valida contra un schema pydantic; si no cumple, se reintenta con prompt de corrección (hasta N intentos).
- Se persisten Project, Episodes, Fragments, DialogueLines y borradores de Resources.
- Job `script_gen` (padre) → jobs hijos por episodio si procede. Regenerable por episodio o completo, preservando ediciones marcadas como bloqueadas (campo `locked` en futuras iteraciones).

### Paso 2 — Biblioteca de recursos
- El usuario crea variantes manualmente o pide a Ollama generarlas desde el guion (`resource_gen`).
- Por variante: descripción/prompt, episodios aplicables, modelo y estilo de imagen, voz (personajes).
- Imágenes de referencia: subida multipart (hoy) o generación vía plug-in `ImageProvider` (futuro). Mínimo recomendado: 1 frontal + turnaround para personajes.

### Paso 3 — Videos por episodio
- Por fragmento: `video_gen` → el `VideoProvider` recibe prompt + imágenes de referencia del cast + duración + aspecto + estilo.
- Al completar todos los fragmentos (o bajo demanda) → `episode_assembly`.

## 6. Cola de trabajos

- Colas arq: `default` (script, recursos, imágenes, TTS), `video` (lenta; permite workers dedicados), `assembly`.
- Estados y progreso en `Job`; el frontend hace polling o SSE.
- Concurrencia limitada por proveedor (semáforo por worker); reintentos con backoff exponencial para errores transitorios (429/5xx/timeout), máx. 3.
- Reclaim al arrancar: jobs `running` huérfanos → `queued`.
- Cancelación cooperativa: el worker comprueba el estado entre pasos.
- Generación de video diferida: submit → `task_id` → poll → download a disco local; el Job permanece `running` durante todo el ciclo.

## 7. Capa de proveedores (plug-ins)

Contratos (clases abstractas, Pydantic in/out, errores tipados `ProviderAuthError`, `ProviderRateLimitError`, `ProviderTimeoutError`):

- **LLMProvider** (`providers/llm/`): `generate_script(synopsis, style, episodes, ...)`, `generate_resources(script)`, `generate_variants(resource)`. Implementado: **Ollama** (URL configurable). Previstos: Gemini, OpenAI.
- **ImageProvider** (`providers/image/`): `generate_image(prompt, model, style, aspect, n) -> [paths]`. Implementado: **UploadOnly** (solo subida manual). Previstos: GPT Image, Seedream, ComfyUI.
- **VideoProvider** (`providers/video/`): `submit(prompt, refs, duration, aspect, style) -> task_id`, `poll(task_id) -> status`, `download(url) -> path`. Implementado: **MockVideoProvider** (video de prueba con ffmpeg para validar el pipeline). Previstos: Seedance 2.0/2.5 (Volcengine Ark), Veo 3 (Vertex AI), Omni 1.1.
- **TTSProvider** (`providers/tts/`): `synthesize(text, voice, timbre) -> path`. Implementado: **Edge-TTS**. Previstos: OpenAI TTS, ElevenLabs.

Selección por configuración (`providers` en `.env`/settings) y por proyecto/recurso en la UI. El job runner interpreta los errores tipados para reintentar o fallar.

## 8. API REST (`/api/v1`)

- Proyectos: `POST/GET /projects`, `GET/PATCH/DELETE /projects/{id}`, `POST /projects/{id}/generate-script`, `POST /projects/{id}/generate-resources`.
- Episodios: `GET /projects/{id}/episodes`, `PATCH /episodes/{id}`, `GET /episodes/{id}/script`.
- Recursos: `GET/POST /projects/{id}/resources`, `PATCH/DELETE /resources/{id}`.
- Variantes: `POST/PATCH/DELETE /resources/{id}/variants`.
- Imágenes: `POST /variants/{id}/images` (multipart) y `POST /variants/{id}/images/generate` (Job, futuro).
- Fragmentos: `GET/PATCH /episodes/{id}/fragments`, `PATCH /fragments/{id}`.
- Generación: `POST /episodes/{id}/generate` (video_gen por fragmento + assembly), `POST /fragments/{id}/generate`.
- Jobs: `GET /jobs/{id}`, `GET /jobs?project_id=`, `POST /jobs/{id}/cancel`, `GET /jobs/{id}/events` (SSE).
- Assets: `GET /assets/{path}`; `GET /episodes/{id}/final` (video final).

## 9. Ensamblaje de episodio (`episode_assembly`, ffmpeg)

1. TTS por `DialogueLine` con la voz de su variante → `audio/` (duración real registrada).
2. Subtítulos SRT generados del guion, sincronizados a la duración de cada línea TTS (determinista; sin ASR). Opción `subtitle_burn` para quemarlos en el video.
3. Mezcla: diálogos sobre la pista de cada fragmento; unión de fragmentos en orden → `episodes/{id}/final.mp4`.
4. Progreso por fragmento (ej. 5/9). Si un fragmento falta o falló, el assembly se detiene con error claro.

## 10. Frontend (Vite + React + TypeScript)

Estilo moderno: tema oscuro, Tailwind CSS, componentes shadcn/ui, tarjetas limpias, indicadores de progreso, toasts.

- **Dashboard**: lista de proyectos (crear/abrir/eliminar).
- **Wizard por proyecto (3 pasos)**:
  1. *Esquema del guion*: sinopsis/estilo/aspecto; botón "Generar guion" (Job); vista y edición del guion y desglose de planos.
  2. *Biblioteca de recursos*: tabs personajes/escenas/utilería; editor de variantes; subida de imágenes de referencia; selector de voz y episodios.
  3. *Videos por episodio*: lista de fragmentos; generar por episodio o fragmento; progreso del Job; vista previa del video final.
- Componentes compartidos: `JobProgress` (reintentar/cancelar), `AssetPicker`, reproductor de video contra `/api/v1/assets`.
- Cliente `fetch` tipado (contratos generados manualmente desde schemas Pydantic; OpenAPI disponible en `/docs`).

## 11. Almacenamiento y configuración

- `storage/<project_id>/{images, videos, audio, episodes, uploads}/`; rutas relativas en `Asset`.
- Configuración en `.env`: `DATABASE_URL`, `REDIS_URL`, `OLLAMA_URL`, `STORAGE_DIR`, `FFMPEG_PATH`, y credenciales de proveedores cuando existan.
- Comando de mantenimiento para limpiar archivos huérfanos de jobs fallidos/cancelados.

## 12. Errores y observabilidad

- Errores tipados de proveedores → mensajes legibles en la UI + acción reintentar Job.
- Logs estructurados por job (`job_id`, `project_id`, `provider`, `stage`).
- Tests unitarios de proveedores con respuestas simuladas; test end-to-end del pipeline con `MockVideoProvider` + Edge-TTS.

## 13. Futuras extensiones (fuera de esta iteración)

- Plug-ins reales: Seedance (Volcengine Ark), Veo 3 (Vertex), Omni 1.1; imágenes: GPT Image/Seedream/ComfyUI.
- Música de fondo y mezcla avanzada; ASR para verificación de subtítulos.
- Bloqueo de ediciones (`locked`) para preservar cambios manuales al regenerar.
- Autenticación si algún día es multi-usuario.
