# Short Drama AI Video Backend — Implementation Plan

> **For agentic workers:** REQUIRED SUB-SKILL: Use superpowers:subagent-driven-development (recommended) or superpowers:executing-plans to implement this plan task-by-task. Steps use checkbox (`- [ ]`) syntax for tracking.

**Goal:** Backend FastAPI + frontend React para generar historias en video por episodios (Proyecto → Episodios → Fragmentos de 10-12 s) con cola de trabajos en Redis, plug-ins de IA (Ollama, Edge-TTS, mock de video) y ensamblaje de episodio con TTS + subtítulos.

**Architecture:** Monolito modular: API FastAPI y workers arq comparten el mismo código de dominio (`backend/app`). Redis solo para colas; SQLite (SQLAlchemy async) para datos; ffmpeg para ensamblaje; plug-ins por dominio (llm/image/video/tts) con contratos abstractos. Frontend Vite+React (Tailwind/shadcn, tema oscuro) consumiendo `/api/v1`.

**Tech Stack:** Python 3.11+, FastAPI, SQLAlchemy 2 (aiosqlite), Pydantic v2, arq, Redis, httpx, edge-tts, ffmpeg; React 18+, TypeScript, Vite, Tailwind, shadcn/ui.

**Spec:** `docs/superpowers/specs/2026-10-02-short-drama-video-backend-design.md`

## Global Constraints

- Python ≥ 3.11; entorno virtual en `backend/.venv` (Windows/PowerShell).
- Backend deps: fastapi, uvicorn[standard], sqlalchemy>=2.0, aiosqlite, pydantic>=2, pydantic-settings, arq, redis, httpx, edge-tts, python-multipart; dev: pytest, pytest-asyncio, fakeredis, ruff.
- `ffmpeg`/`ffprobe` en PATH (override con `FFMPEG_PATH`/`FFPROBE_PATH`).
- Almacenamiento: `storage/<project_id>/{images,videos,audio,episodes,uploads}/` relativo a `backend/` (override `STORAGE_DIR`).
- Fragmentos: duración objetivo 10 s (rango 10-12); `planned_fragments(90) == 9`.
- Estados de Job: `queued|running|succeeded|failed|cancelled`; reintentos de parseo LLM máx. 3; poll de video cada 1 s.
- Sin auth; CORS permitir `http://localhost:5173`.
- Todos los endpoints bajo `/api/v1`; OpenAPI en `/docs`.
- Frontend: Vite + React + TS, Tailwind, shadcn/ui tema oscuro, react-router-dom, proxy dev `/api` → `http://localhost:8000`.

## Review Focus

1. **JSON de LLM malformado** (code fences, truncado, campos extra) → bucle parse/reparar y `ScriptValidationError` legible en `Job.error` tras 3 reintentos. *(Test en Task 10, unidad en Task 5.)*
2. **Redis caído** → los endpoints CRUD siguen funcionando; los endpoints que encolan devuelven 503 `queue_unavailable`. *(Test en Task 9.)*
3. **Assembly con fragmentos faltantes** (fallidos/cancelados) → el Job falla con error que nombra los números de plano `[N-M]` faltantes. *(Test en Task 12.)*
4. **Path traversal en assets** (`GET /api/v1/assets/../../data.db`) → 404; nunca sirve fuera de `STORAGE_DIR`. *(Test en Task 6.)*
5. **Upload no-imagen o >10 MB** → 400 con error de campo; no se escribe nada. *(Test en Task 6.)*

---

### Task 1: Backend scaffold (config, db, health)

**Files:**
- Create: `backend/pyproject.toml`, `backend/.env.example`, `backend/.gitignore`, `backend/app/__init__.py`, `backend/app/config.py`, `backend/app/db.py`, `backend/app/main.py`
- Test: `backend/tests/test_health.py`

**Interfaces:**
- Produces: `get_settings() -> Settings` (`config.py`); `engine`, `SessionLocal`, `Base`, `init_db()`, `get_session()` (`db.py`); `create_app() -> FastAPI` (`main.py`).
- `Settings` fields (defaults): `database_url="sqlite+aiosqlite:///./data.db"`, `redis_url="redis://localhost:6379"`, `ollama_url="http://localhost:11434"`, `ollama_model="qwen2.5:14b"`, `storage_dir=Path("./storage")`, `ffmpeg_path="ffmpeg"`, `ffprobe_path="ffprobe"`, `script_gen_retries=3`, `max_upload_mb=10`, `subtitle_burn_default=False`.

- [ ] **Step 1: Write the failing test**

`backend/tests/test_health.py`:
```python
def test_health(client):
    r = client.get("/health")
    assert r.status_code == 200 and r.json() == {"status": "ok"}
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_health.py -v`
Expected: FAIL (no `client` fixture, app missing).

- [ ] **Step 3: Implement scaffold**

`pyproject.toml` con `[project]` deps de Global Constraints + `[tool.pytest.ini_options]` (asyncio_mode="auto"); `config.py` con `Settings(BaseSettings)` y `get_settings()` cacheado; `db.py` con `create_async_engine`, `async_sessionmaker`, `Base(DeclarativeBase)`, `init_db()` (create_all) y `get_session()` dependency; `main.py` con `create_app()`: lifespan `init_db()`, CORS (`http://localhost:5173`), `GET /health`; fixture `client` en `tests/conftest.py` usando `httpx.AsyncClient(transport=ASGITransport(app))` con base de datos en memoria (`sqlite+aiosqlite:///:memory:`) por test. `.gitignore`: `.venv/`, `__pycache__/`, `storage/`, `*.db`, `node_modules/`.

- [ ] **Step 4: Run test to verify it passes**

Run: `.venv\Scripts\python -m pytest tests/test_health.py -v`
Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: backend scaffold with config, db and health endpoint"`

---

### Task 2: Modelos ORM + schemas Pydantic

**Files:**
- Create: `backend/app/models/__init__.py`, `base.py`, `project.py`, `resource.py`, `job.py`, `asset.py`
- Create: `backend/app/schemas/__init__.py`, `project.py`, `resource.py`, `job.py`, `script.py`
- Test: `backend/tests/test_models.py`, `backend/tests/test_script_schema.py`

**Interfaces:**
- Models (snake_case, `TimestampMixin` con `created_at`/`updated_at`): `Project(name, synopsis, video_style, aspect_ratio="16:9", status, settings JSON)`, `Episode(project_id, number, title, script JSON, status)`, `Fragment(episode_id, shot_number, time_place, cast JSON, prompt_video, duration=10, status, video_path)`, `DialogueLine(fragment_id, character_variant_id nullable, text, order)`, `Resource(project_id, type, name, profile JSON)`, `ResourceVariant(resource_id, name, description, episodes JSON, image_model, image_style, voice JSON)`, `ReferenceImage(variant_id, path, origin, kind)`, `Job(type, status, progress, payload JSON, result JSON, error, parent_id, project_id)`, `Asset(project_id, kind, path, metadata JSON)`.
- Enums: `JobType` (`script_gen|resource_gen|image_gen|video_gen|tts|episode_assembly`), `JobStatus` (`queued|running|succeeded|failed|cancelled`), `AssetKind` (`image|video|audio|episode|upload`), `ResourceType` (`character|scene|prop`), `ImageOrigin` (`uploaded|generated`).
- Schemas: `ProjectCreate/Read/Update`, `EpisodeRead/Update`, `ResourceCreate/Read`, `ResourceVariantCreate/Read`, `ReferenceImageRead`, `FragmentRead/Update`, `DialogueLineRead`, `JobRead`.
- `schemas/script.py`: `ScriptGenerationRequest` (`synopsis`, `video_style`, `aspect_ratio="16:9"`, `num_episodes`, `episode_duration_seconds=90`, `language="es"`), `ScriptDraft` (synopsis, characters[], scenes[], props[], episodes[]), `ScriptCharacter/Scene/Prop` (name, description, tags[]), `ScriptEpisode` (number, title, shots[]), `ScriptShot` (shot_number, time_place, cast[], action, dialogues[]), `ScriptDialogue` (character, text); función módulo `planned_fragments(duration_seconds: int, fragment_seconds: int = 10) -> int` (ceil).

- [ ] **Step 1: Write the failing tests**

```python
# test_models.py
def test_project_episode_fragment_dialogue_chain(db_session):
    p = Project(name="Neon Rebellion"); db_session.add(p); db_session.flush()
    e = Episode(project_id=p.id, number=1)
    f = Fragment(episode_id=e.id, shot_number=1, duration=10)
    d = DialogueLine(fragment_id=f.id, text="Hola", order=0)
    db_session.add_all([e, f, d]); db_session.commit()
    assert f in db_session.get(Episode, e.id).fragments

def test_delete_project_cascades(db_session):
    # crea proyecto + episodio + fragmento; borra proyecto;
    # los hijos desaparecen
```

```python
# test_script_schema.py
def test_script_draft_parses_minimal_json():
    # JSON mínimo válido con 1 personaje, 1 episodio, 1 shot, 1 diálogo
def test_planned_fragments():
    assert planned_fragments(90) == 9
    assert planned_fragments(100) == 10
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_models.py tests/test_script_schema.py -v`
Expected: FAIL (imports inexistentes).

- [ ] **Step 3: Implement models y schemas**

ORM con relaciones y `cascade="all, delete-orphan"`, `passive_deletes=True` donde corresponda; `db_session` fixture con SQLite en memoria en `tests/conftest.py` (reusa el engine de test). `planned_fragments` = `math.ceil(duration_seconds / fragment_seconds)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: ORM models and pydantic schemas"`

---

### Task 3: API CRUD (projects, episodes, resources, variants, fragments)

**Files:**
- Create: `backend/app/api/__init__.py`, `deps.py`, `projects.py`, `episodes.py`, `resources.py`, `fragments.py`
- Modify: `backend/app/main.py` (incluir routers)
- Test: `backend/tests/test_api_crud.py`

**Interfaces:**
- Consumes: modelos/schemas de Task 2, `get_session` de Task 1.
- Produces: routers montados en `create_app()` bajo `/api/v1`: `POST/GET /projects`, `GET/PATCH/DELETE /projects/{id}`, `GET /projects/{id}/episodes`, `PATCH /episodes/{id}`, `GET /episodes/{id}/script`, `GET/POST /projects/{id}/resources`, `PATCH/DELETE /resources/{id}`, `POST/PATCH/DELETE /resources/{id}/variants`, `GET/PATCH /episodes/{id}/fragments`, `PATCH /fragments/{id}` (acepta actualizar `prompt_video`, `duration`, `cast`, diálogos).

- [ ] **Step 1: Write the failing test**

```python
# test_api_crud.py
def test_full_crud_flow(client):
    r = client.post("/api/v1/projects", json={"name": "Neon Rebellion",
        "synopsis": "Ciudad futurista", "video_style": "cyberpunk",
        "aspect_ratio": "16:9"})
    assert r.status_code == 200 and r.json()["id"] == 1
    # episodio, recurso, variante, fragmento, diálogos; PATCH fragmento;
    # GET anidados; DELETE recurso; DELETE proyecto y verificar 404
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_api_crud.py -v`
Expected: FAIL (404, routers no montados).

- [ ] **Step 3: Implement routers**

Routers FastAPI con `APIRouter(prefix="/api/v1")`; CRUD con `get_session`; validación de pertenencia (recurso/episodio del proyecto correcto → 404 si no); `Fragment` expone diálogos anidados en `FragmentRead` (crear/reemplazar diálogos en PATCH).

- [ ] **Step 4: Run test to verify it passes**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: REST CRUD for projects, episodes, resources, fragments"`

---

### Task 4: Contratos de proveedores + registro

**Files:**
- Create: `backend/app/providers/__init__.py`, `base.py`
- Test: `backend/tests/test_provider_registry.py`

**Interfaces:**
- `base.py`: excepciones `ProviderError(Exception)`, `ProviderAuthError`, `ProviderRateLimitError`, `ProviderTimeoutError`, `ProviderUnavailableError`.
- ABCs: `LLMProvider.complete(system: str, user: str, json_mode: bool = False) -> str`; `ImageProvider.generate(prompt: str, model: str | None, style: str | None, aspect: str, count: int) -> list[Path]`; `VideoProvider.submit(payload: VideoSubmitPayload) -> str` (task_id), `poll(task_id: str) -> VideoTaskStatus`, `download(url: str, dest: Path) -> Path`; `TTSProvider.synthesize(text: str, voice: str) -> TTSResult`.
- Tipos: `VideoSubmitPayload(prompt, duration_seconds, aspect_ratio, style, reference_images: list[Path])`; `VideoTaskStatus(state: Literal["queued","processing","succeeded","failed"], video_url: str | None, error: str | None)`; `TTSResult(path: Path, duration_seconds: float)`.
- `providers/__init__.py`: `register_provider(kind: str, name: str, factory)`, `get_provider(kind: str, name: str) -> Any` (por defecto nombre de settings: `llm→"ollama"`, `image→"upload"`, `video→"mock"`, `tts→"edge"`), `list_providers(kind)`.

- [ ] **Step 1: Write the failing tests**

```python
def test_register_and_get_provider():
    class Fake: pass
    register_provider("llm", "fake", lambda: Fake())
    assert isinstance(get_provider("llm", "fake"), Fake)

def test_unknown_provider_raises():
    with pytest.raises(ProviderUnavailableError):
        get_provider("video", "noexiste")

def test_error_hierarchy():
    assert issubclass(ProviderRateLimitError, ProviderError)
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_provider_registry.py -v`
Expected: FAIL (imports inexistentes).

- [ ] **Step 3: Implement base + registry**

Diccionario global `_REGISTRY: dict[tuple[str, str], Callable]`; `get_provider` instancia (o devuelve cached si el factory es singleton).

- [ ] **Step 4: Run test to verify it passes**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: provider contracts and registry"`

---

### Task 5: Proveedor Ollama + servicio de scripting

**Files:**
- Create: `backend/app/providers/llm/__init__.py`, `ollama.py`
- Create: `backend/app/services/__init__.py`, `scripting.py`
- Test: `backend/tests/test_scripting.py`

**Interfaces:**
- Consumes: `LLMProvider`, `ScriptDraft`, `ScriptGenerationRequest` (Task 2/4), `settings`.
- `scripting.py`: `build_system_prompt() -> str` (incluye el JSON Schema como string), `build_user_prompt(req: ScriptGenerationRequest) -> str`, `parse_script_json(text: str) -> ScriptDraft` (quita code fences, `json.loads`, valida), `repair_prompt(bad_json: str, error: str) -> str`, `async generate_script_draft(provider: LLMProvider, req: ScriptGenerationRequest, retries: int) -> ScriptDraft`, excepción `ScriptValidationError(ValueError)`.
- `OllamaLLM.complete(...)`: POST `{ollama_url}/api/chat`, body `{"model": settings.ollama_model, "messages": [...], "stream": False, "format": "json" si json_mode}`.

- [ ] **Step 1: Write the failing tests**

```python
# con provider fake que devuelve JSON con code fences
def test_parse_script_json_with_fences():
    draft = parse_script_json('```json\n{"synopsis": "x", ...}\n```')
    assert draft.synopsis == "x"

def test_generate_script_draft_success(fake_provider):
    # 1º intento devuelve JSON inválido, 2º válido → draft correcto

def test_generate_script_draft_exhausts_retries(fake_provider):
    # siempre inválido → pytest.raises(ScriptValidationError)
    # y fake_provider.calls == retries + 1 (original + reparos)

def test_ollama_payload(httpx_mock):
    # assert body enviado: model, format="json", stream=False
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_scripting.py -v`
Expected: FAIL (imports inexistentes).

- [ ] **Step 3: Implement**

`parse_script_json` con `json.loads` + `ScriptDraft.model_validate`; loop en `generate_script_draft`: complete → parse; al fallar, `complete` con `repair_prompt`; excepción tras `retries`. Test de payload con `httpx.MockTransport` inyectado al cliente httpx del provider.

- [ ] **Step 4: Run tests to verify they pass**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: Ollama provider and script generation service"`

---

### Task 6: Storage, upload de imágenes y API de assets

**Files:**
- Create: `backend/app/services/storage.py`, `backend/app/providers/image/__init__.py`, `upload.py`
- Create: `backend/app/api/assets.py`; Modify: `backend/app/api/resources.py` (endpoints de imágenes), `backend/app/main.py`
- Test: `backend/tests/test_storage_and_assets.py`

**Interfaces:**
- `storage.py`: `project_dir(project_id: int) -> Path`, `asset_dir(project_id: int, kind: AssetKind) -> Path`, `save_upload(project_id: int, kind: AssetKind, filename: str, stream) -> Path` (nombre seguro `uuid4+sufijo`, valida extensión imagen `{png,jpg,jpeg,webp}` y tamaño ≤ `max_upload_mb`, crea `Asset`), `resolve_asset(relative_path: str) -> Path | None` (rechaza `..`, rutas absolutas; resuelve y verifica dentro de `storage_dir`).
- API: `POST /api/v1/variants/{id}/images` (multipart `file` → `ReferenceImage(origin="uploaded")`); `POST /api/v1/variants/{id}/images/generate` → 501 `image_provider_not_configured`; `GET /api/v1/assets/{path:path}` → `FileResponse` o 404.

- [ ] **Step 1: Write the failing tests**

```python
def test_upload_image_creates_reference_image(client):
    # multipart con PNG 1x1 → 200, ReferenceImage origin="uploaded"

def test_upload_rejects_non_image(client):
    # text/plain → 400, mensaje con el campo

def test_upload_rejects_oversize(client, settings_override_max_upload_mb=1):
    # 2 MB → 400

def test_asset_path_traversal_blocked(client):
    r = client.get("/api/v1/assets/../../data.db")
    assert r.status_code in (400, 404)

def test_asset_serves_uploaded_file(client):
    # subir imagen y luego GET /api/v1/assets/<ruta> → 200
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_storage_and_assets.py -v`
Expected: FAIL (rutas inexistentes).

- [ ] **Step 3: Implement**

`save_upload` lee el stream en trozos contando bytes (aborta si excede); `resolve_asset` con `Path.resolve()` y chequeo `is_relative_to(storage_dir)`. Los tests usan `tmp_path` como `STORAGE_DIR` (override en settings vía fixture).

- [ ] **Step 4: Run tests to verify they pass**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: local storage, image upload and assets API"`

---

### Task 7: Proveedor TTS Edge-TTS

**Files:**
- Create: `backend/app/providers/tts/__init__.py`, `edge.py`
- Test: `backend/tests/test_edge_tts.py`

**Interfaces:**
- Consumes: `TTSProvider`, `TTSResult` (Task 4), `settings.ffprobe_path`.
- `EdgeTTS.synthesize(text: str, voice: str) -> TTSResult`: guarda con `edge_tts.Communicate(text, voice).save(str(tmp))` y calcula `duration_seconds` con `ffprobe -v error -show_entries format=duration -of csv=p=0 <file>`; registra `register_provider("tts", "edge", EdgeTTS)`.

- [ ] **Step 1: Write the failing test**

```python
# monkeypatch de edge_tts.Communicate que escribe un wav de 2 s
# (generado en el test con ffmpeg); assert duration_seconds ≈ 2.0 ± 0.3
def test_edge_tts_returns_path_and_duration(monkeypatch, tmp_path):
    result = asyncio.run(EdgeTTS().synthesize("Hola mundo", "es-ES-AlvaroNeural"))
    assert result.path.exists() and 1.5 < result.duration_seconds < 2.5
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_edge_tts.py -v`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Implement**

Subprocess `ffprobe` vía `asyncio.create_subprocess_exec(settings.ffprobe_path, ...)`; error de ffprobe → `ProviderError`.

- [ ] **Step 4: Run test to verify it passes**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: Edge-TTS provider"`

---

### Task 8: Mock video provider

**Files:**
- Create: `backend/app/providers/video/__init__.py`, `mock.py`
- Test: `backend/tests/test_mock_video.py`

**Interfaces:**
- Consumes: `VideoProvider`, `VideoSubmitPayload`, `VideoTaskStatus` (Task 4), `settings.ffmpeg_path`.
- `MockVideoProvider`: `submit(payload) -> task_id` (genera en `asyncio.create_task`, estado `queued→processing→succeeded`), `poll(task_id) -> VideoTaskStatus` (`video_url` = ruta local), `download(url, dest) -> Path` (copia). Video de prueba: ffmpeg `-f lavfi -i color=c=0x3355aa:s=<res>:d=<duration>` h264, resoluciones según aspect (16:9→1280x720, 9:16→720x1280). Registra `register_provider("video", "mock", MockVideoProvider)`.

- [ ] **Step 1: Write the failing test**

```python
def test_mock_provider_lifecycle(tmp_path):
    provider = MockVideoProvider()
    tid = asyncio.run(provider.submit(VideoSubmitPayload(
        prompt="prueba", duration_seconds=3, aspect_ratio="16:9",
        style="cyberpunk", reference_images=[])))
    # poll hasta succeeded (max 10 s); video_url existe
    dest = asyncio.run(provider.download(status.video_url, tmp_path / "out.mp4"))
    assert dest.exists() and dest.stat().st_size > 1000
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_mock_video.py -v`
Expected: FAIL (módulo inexistente).

- [ ] **Step 3: Implement**

ffmpeg con `asyncio.create_subprocess_exec`; estado en dict interno `_tasks`; `poll` fallido si el proceso termina con error.

- [ ] **Step 4: Run test to verify it passes**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: mock video provider with ffmpeg test clips"`

---

### Task 9: Cola arq + Job API (estado, cancel, SSE, reclaim)

**Files:**
- Create: `backend/app/jobs/__init__.py`, `queue.py`, `state.py`, `settings.py`, `run.py`
- Create: `backend/app/api/jobs.py`; Modify: `backend/app/main.py`
- Test: `backend/tests/test_jobs_api.py`

**Interfaces:**
- `queue.py`: `async get_redis() -> ArqRedis` (create_pool con `settings.redis_url`), `async enqueue(queue: str, func_name: str, job_id: int) -> Job` (guarda el arq job id en `Job.result["arq_job_id"]`; si Redis no disponible → `QueueUnavailableError`).
- `state.py`: `async mark_running(job_id)`, `mark_succeeded(job_id, result: dict)`, `mark_failed(job_id, error: str)`, `mark_cancelled(job_id)`, `async is_cancelled(job_id) -> bool`.
- `settings.py`: `WorkerSettings` de arq con `functions=[run_ping]`, `on_startup=reclaim_stale`, `redis_settings=RedisSettings.from_dsn(settings.redis_url)`. `reclaim_stale(ctx)`: `UPDATE jobs SET status='queued' WHERE status='running' AND updated_at < now-5min`.
- `run.py`: `python -m app.jobs.run` → `arq.worker.Worker(...).run()`.
- `run_ping(ctx, job_id)`: sleep 0.1, `mark_succeeded(job_id, {"pong": True})`.
- API `/api/v1/jobs`: `GET /jobs/{id}`, `GET /jobs?project_id=`, `POST /jobs/{id}/cancel` (solo `queued|running`; arq `abort_job` + `mark_failed` con "cancelled"? No: estado `cancelled`), `GET /jobs/{id}/events` (SSE: poll DB 1 s hasta estado terminal).

- [ ] **Step 1: Write the failing tests**

```python
def test_enqueue_and_run_ping(fake_redis):
    # enqueue en fake redis, ejecutar arq worker inline (o llamar
    # run_ping con ctx={"redis": pool}); Job termina succeeded

def test_cancel_job(client):
    # job queued → POST cancel → estado cancelled

def test_enqueue_redis_down_returns_503(client, monkeypatch):
    # get_redis lanza → endpoint encola con 503 queue_unavailable
    # y GET /projects sigue funcionando (200)

def test_reclaim_stale_running(fake_redis, db_session):
    # job running con updated_at viejo → reclaim → queued
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_jobs_api.py -v`
Expected: FAIL (módulos inexistentes).

- [ ] **Step 3: Implement**

Fixture `fake_redis` con `fakeredis.aioredis.FakeRedis` + `arq.create_pool`; ejecutar tareas llamándolas directamente con `ctx={"redis": pool}`. SSE con `StreamingResponse(media_type="text/event-stream")`.

- [ ] **Step 4: Run tests to verify they pass**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: arq queue integration and jobs API"`

---

### Task 10: Job de generación de guion end-to-end

**Files:**
- Create: `backend/app/jobs/tasks.py` (run_script_gen, run_video_gen, run_episode_assembly como stubs NotImplemented — se completan aquí y en Task 12)
- Create: `backend/app/services/persist.py`
- Modify: `backend/app/api/projects.py` (endpoint generate-script), `backend/app/jobs/settings.py`
- Test: `backend/tests/test_script_gen_job.py`

**Interfaces:**
- `persist.py`: `apply_script_draft(session, project: Project, draft: ScriptDraft) -> dict` — actualiza proyecto (synopsis/style/aspect), crea `Resource` por personaje/escena/prop del draft con una variante por defecto `"Base Appearance"` (description del draft), crea `Episode`+`Fragment`+`DialogueLine` (cast por nombre → variant_id si el personaje existe); devuelve resumen (nº episodios/fragmentos/recursos).
- `run_script_gen(ctx, job_id)`: payload `{project_id, request}` → `mark_running` → `get_provider("llm", "ollama")` → `generate_script_draft(...)` → `apply_script_draft` → `mark_succeeded`; `ScriptValidationError` → `mark_failed(job_id, str(e))`.
- API: `POST /api/v1/projects/{id}/generate-script` (body `ScriptGenerationRequest`) → crea `Job(type=script_gen, queued)` y `enqueue` → 202 con `JobRead`.

- [ ] **Step 1: Write the failing test**

```python
def test_generate_script_job_end_to_end(client, fake_redis, db_session):
    # POST /projects → POST generate-script con request de 1 episodio 90 s
    # (provider LLM monkeypatcheado con draft fijo)
    # → ejecutar run_script_gen(ctx) → job succeeded
    # → GET episodes: 1 episodio, planned_fragments(90)=9 fragmentos
    # → recursos: personajes del draft con variante "Base Appearance"
    # → diálogos anidados en fragmentos

def test_generate_script_job_invalid_json_fails(client, fake_redis):
    # provider siempre inválido, retries=0 en settings de test
    # → job failed y "ScriptValidationError" en Job.error
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_script_gen_job.py -v`
Expected: FAIL (endpoint inexistente).

- [ ] **Step 3: Implement**

`apply_script_draft` idempotente por llamada (crea; no borra lo existente). Test inyecta draft vía `monkeypatch.setattr(scripting, "generate_script_draft", ...)`.

- [ ] **Step 4: Run tests to verify they pass**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: script generation job end-to-end"`

---

### Task 11: Job de generación de recursos (variantes desde el guion)

**Files:**
- Modify: `backend/app/schemas/script.py` (añadir `ResourcesDraft`), `backend/app/services/scripting.py`, `backend/app/jobs/tasks.py` (completar `run_resource_gen`), `backend/app/api/projects.py` (endpoint generate-resources)
- Test: `backend/tests/test_resource_gen_job.py`

**Interfaces:**
- `schemas/script.py`: `ResourcesDraft(resources: list[ResourceDraft])` con `ResourceDraft(type: ResourceType, name, description, variants: list[VariantDraft])`, `VariantDraft(name, description)`.
- `scripting.py`: `parse_resources_json(text: str) -> ResourcesDraft`, `async generate_resources_draft(provider: LLMProvider, script_context: dict, retries: int) -> ResourcesDraft` (mismo bucle parse/repair que Task 5).
- `run_resource_gen(ctx, job_id)`: payload `{project_id}` → `mark_running` → contexto (sinopsis + recursos existentes del proyecto) → `generate_resources_draft` → persiste: crea recursos faltantes y/o variantes nuevas (nombres duplicados → se omiten con aviso en result) → `mark_succeeded` con resumen; `ScriptValidationError` → `mark_failed`.
- API: `POST /api/v1/projects/{id}/generate-resources` (body `{}` opcional) → Job `resource_gen` → 202 `JobRead`.

- [ ] **Step 1: Write the failing test**

```python
def test_resource_gen_job_end_to_end(client, fake_redis, db_session):
    # proyecto con guion ya generado (draft fijo); provider fake devuelve
    # ResourcesDraft con 1 personaje nuevo + 1 variante nueva de uno
    # existente → run_resource_gen → job succeeded
    # → GET resources: aparece el nuevo y el existente tiene 2 variantes

def test_resource_gen_job_duplicate_variant_skipped(client, fake_redis):
    # draft con variante ya existente → job succeeded, sin duplicar,
    # y result menciona el nombre omitido
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_resource_gen_job.py -v`
Expected: FAIL (endpoint inexistente).

- [ ] **Step 3: Implement**

Reusa `build_system_prompt`/parse de Task 5; persistencia inline en `run_resource_gen` (buscar por `(type, name)`).

- [ ] **Step 4: Run tests to verify they pass**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: resource variants generation job"`

---

### Task 12: Job de video (mock) + ensamblaje de episodio (TTS + SRT + concat)

**Files:**
- Create: `backend/app/services/srt.py`, `assembly.py`
- Modify: `backend/app/jobs/tasks.py` (completar run_video_gen, run_episode_assembly), `backend/app/api/episodes.py` (generate), `backend/app/api/fragments.py` (generate)
- Test: `backend/tests/test_assembly.py`, `backend/tests/test_video_jobs.py`

**Interfaces:**
- `srt.py`: `SrtEntry(start_seconds: float, end_seconds: float, text: str)`, `build_srt(entries: list[SrtEntry]) -> str` (formato `HH:MM:SS,mmm`).
- `assembly.py`: `async assemble_episode(session, episode_id: int, subtitle_burn: bool) -> dict` — si falta `video_path` en algún fragmento → `AssemblyMissingFragmentsError` con lista `shot_number` faltantes; si no: por fragmento TTS por línea (voz de la variante del personaje) → mezclar líneas sobre el video (`adelay`+`amix`) → fragmento temporal con audio; acumular entradas SRT; concat demuxer → `storage/<pid>/episodes/<episode_id>/final.mp4` + `final.srt`; `subtitle_burn` → `final_burn.mp4` (filtro subtitles). Devuelve rutas. `episode.status="assembled"`.
- `run_video_gen(ctx, job_id)`: payload `{fragment_id}` → construir `VideoSubmitPayload` (prompt del fragmento + imágenes del cast + estilo/aspect del proyecto) → submit/poll loop (1 s, `is_cancelled` en cada iteración) → download a `storage/<pid>/videos/<fragment_id>.mp4` → `fragment.video_path`, `status="generated"` → si todos los fragmentos del episodio generados: enqueue `episode_assembly`.
- `run_episode_assembly(ctx, job_id)`: payload `{episode_id, subtitle_burn}` → si fragmentos pendientes: re-enqueue en 5 s (`mark queued`); si no: `assemble_episode`; `AssemblyMissingFragmentsError` → `mark_failed` con mensaje nombrando planos.
- API: `POST /api/v1/episodes/{id}/generate` (body `{subtitle_burn?}`) → encola video_gen por fragmento + assembly; `POST /api/v1/fragments/{id}/generate`.

- [ ] **Step 1: Write the failing tests**

```python
# test_assembly.py
def test_build_srt_format():
    assert build_srt([SrtEntry(0.0, 2.0, "Hola")]) == \
        "1\n00:00:00,000 --> 00:00:02,000\nHola\n\n"

def test_assemble_two_fragments(client, fake_redis, db_session):
    # 2 fragmentos con video de mock ya generado (fixture 3 s)
    # TTS monkeypatcheado (audio 1 s por línea); assemble_episode(...)
    # → final.mp4 existe, final.srt con 2 entradas, status assembled

def test_assemble_missing_fragment_raises(client, fake_redis):
    # 1 fragmento sin video_path → pytest.raises(AssemblyMissingFragmentsError)
    # y mensaje contiene "[N-2]"

def test_video_job_cancel_stops_polling(fake_redis):
    # cancel durante poll → job cancelled, sin video_path en fragmento
```

```python
# test_video_jobs.py
def test_episode_generate_creates_jobs(client):
    # episodio con 3 fragmentos → 3 video_gen jobs + 1 assembly job queued
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `.venv\Scripts\python -m pytest tests/test_assembly.py tests/test_video_jobs.py -v`
Expected: FAIL (módulos inexistentes).

- [ ] **Step 3: Implement**

Comandos ffmpeg: mezcla de audio por fragmento con `filter_complex` (adelay por línea, amix, `-shortest`); concat con archivo `list.txt` + `-f concat -safe 0`; burn con filtro `subtitles=final.srt` escapando ruta (Windows: `\:` en filtro). `run_episode_assembly` usa `ctx["redis"]` para re-enqueue.

- [ ] **Step 4: Run tests to verify they pass**

Run: igual que Step 2. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: video generation job and episode assembly"`

---

### Task 13: Scaffold del frontend (Vite + Tailwind + shadcn, tema oscuro)

**Files:**
- Create: `frontend/` vía `npm create vite@latest frontend -- --template react-ts` + deps: tailwindcss `@tailwindcss/vite`, shadcn init (base color `slate`, css variables, dark), componentes: `button card input textarea select tabs progress dialog badge label`; `lucide-react`, `react-router-dom`; vitest + @testing-library/react + jsdom; proxy `/api` → `http://localhost:8000` en `vite.config.ts`.
- Test: `frontend/src/App.test.tsx`

**Interfaces:**
- Produces: estructura estándar shadcn (`src/components/ui/*`, `src/lib/utils.ts`), tema oscuro por defecto (clase `dark` en `<html>`), rutas vacías `Dashboard` y `ProjectView` (placeholders).

- [ ] **Step 1: Write the failing test**

```tsx
// App.test.tsx
import { render, screen } from "@testing-library/react";
import App from "./App";
test("renders dashboard title", () => {
  render(<App />);
  expect(screen.getByText(/AI Director/i)).toBeInTheDocument();
});
```

- [ ] **Step 2: Run test to verify it fails**

Run: `npm test` (vitest run)
Expected: FAIL (App no existe).

- [ ] **Step 3: Implement scaffold**

Configurar Tailwind v4 (`@tailwindcss/vite` + `@import "tailwindcss"` en CSS), shadcn con variables dark, App con router y un layout con header "AI Director".

- [ ] **Step 4: Run test to verify it passes**

Run: `npm test`. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: frontend scaffold with Vite, Tailwind, shadcn dark theme"`

---

### Task 14: Frontend app (cliente API, Dashboard, wizard de 3 pasos, JobProgress)

**Files:**
- Create: `frontend/src/types.ts`, `frontend/src/lib/api.ts`, `frontend/src/pages/Dashboard.tsx`, `frontend/src/pages/ProjectView.tsx`, `frontend/src/pages/steps/ScriptStep.tsx`, `ResourcesStep.tsx`, `VideosStep.tsx`, `frontend/src/components/JobProgress.tsx`, `AssetPicker.tsx`, `VideoPlayer.tsx`
- Test: `frontend/src/lib/api.test.ts`, `frontend/src/components/JobProgress.test.tsx`, `frontend/src/pages/Dashboard.test.tsx`

**Interfaces:**
- `types.ts`: espejo TS de los schemas Pydantic (Project, Episode, Fragment, DialogueLine, Resource, ResourceVariant, Job, JobStatus...).
- `api.ts`: `listProjects(): Promise<Project[]>`, `createProject(name, synopsis, video_style, aspect_ratio)`, `deleteProject(id)`, `generateScript(projectId, request)`, `listEpisodes(projectId)`, `listFragments(episodeId)`, `updateFragment(id, patch)`, `listResources(projectId)`, `createVariant(resourceId, payload)`, `uploadReferenceImage(variantId, file)`, `generateEpisode(episodeId, subtitle_burn)`, `generateFragment(fragmentId)`, `getJob(jobId)`, `cancelJob(jobId)`, `subscribeJob(jobId, onEvent)` (SSE), `assetUrl(path)`.
- `Dashboard`: grid de tarjetas de proyecto (estilo moderno oscuro), dialog de creación.
- `ProjectView`: tabs *Esquema del guion* / *Biblioteca de recursos* / *Videos por episodio*.
  - `ScriptStep`: formulario sinopsis/estilo/aspecto + botón Generar (JobProgress) + editor de episodios/fragmentos/diálogos.
  - `ResourcesStep`: tabs personajes/escenas/utilería; editor de variantes (descripción, episodios, voz); `AssetPicker` para subir imágenes.
  - `VideosStep`: selector de episodio, tarjetas de fragmento con estado, botones Generar episodio/fragmento, `JobProgress`, `VideoPlayer` del final.
- `JobProgress`: polling 1 s (o SSE), barra de progreso, estados, botones reintentar/cancelar, error legible.

- [ ] **Step 1: Write the failing tests**

```tsx
// api.test.ts (fetch mockeado)
test("createProject posts payload", async () => {
  const fn = vi.fn().mockResolvedValue(ok({ id: 1 }));
  vi.stubGlobal("fetch", fn);
  await createProject("Neon Rebellion", "syn", "cyberpunk", "16:9");
  expect(fn.mock.calls[0][1].body).toContain("Neon Rebellion");
});

// JobProgress.test.tsx (fake timers)
test("polls until succeeded and shows progress", async () => {
  // getJob devuelve running 50% → luego succeeded 100%
  // avanza timers → se muestra "Completado"
});

// Dashboard.test.tsx (api mockeado)
test("renders project cards", async () => {
  // listProjects → 2 proyectos → aparecen ambos nombres
});
```

- [ ] **Step 2: Run tests to verify they fail**

Run: `npm test`
Expected: FAIL (módulos inexistentes).

- [ ] **Step 3: Implement**

Cliente fetch con base `/api/v1`; hooks de estado por página (useState/useEffect, sin TanStack Query); estilos con componentes shadcn + Tailwind dark.

- [ ] **Step 4: Run tests to verify they pass**

Run: `npm test`. Expected: PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: frontend dashboard, project wizard and job progress"`

---

### Task 15: E2E pipeline completo + documentación

**Files:**
- Create: `backend/tests/test_e2e_pipeline.py`, `README.md`, `.env.example` (revisar)
- Test: `backend/tests/test_e2e_pipeline.py`

**Interfaces:**
- Consumes: todo lo anterior. El E2E encadena: proyecto → generate-script (LLM fake) → generate de episodio (MockVideoProvider real con ffmpeg, TTS fake con audio fixture) → assembly → `final.mp4` + `final.srt` existentes con contenido.

- [ ] **Step 1: Write the failing test**

```python
def test_full_pipeline_e2e(client, fake_redis, db_session, tmp_path):
    # 1 episodio, 2 fragmentos, LLM fake con draft fijo, TTS fake
    # POST generate-script → run jobs → POST episodes/{id}/generate
    # → run video jobs (mock real) → run assembly
    # → final.mp4 y final.srt existen; srt contiene textos del draft
```

- [ ] **Step 2: Run test to verify it fails**

Run: `.venv\Scripts\python -m pytest tests/test_e2e_pipeline.py -v`
Expected: FAIL o errores de integración detectados (primer arranque del pipeline completo).

- [ ] **Step 3: Implement/fix hasta pasar + README**

Arreglar lo que el E2E destape. `README.md`: requisitos (Python, Redis, ffmpeg, Ollama, Node), arranque (venv + `uvicorn app.main:app --reload`; worker `python -m app.jobs.run`; frontend `npm run dev`), variables de `.env.example`.

- [ ] **Step 4: Run full test suites**

Run: `.venv\Scripts\python -m pytest tests/ -v` y `npm test` en frontend
Expected: todo PASS

- [ ] **Step 5: Commit**

`git commit -m "feat: end-to-end pipeline test and docs"`
