# Fases 1–3: Guion confirmable, recursos por lotes y storyboards

Fecha: 2026-10-04
Estado: aprobado en conversación (diseño); implementación pendiente.

## Objetivo

Reestructurar el pipeline para que el guion generado se **revise y confirme**
antes de pasar a recursos; que al confirmar se **creen cards limpias** de
personajes/escenas/utilería (nombre + descripción) y la estructura de capítulos;
que las imágenes de los recursos se **generen por lotes** con el modelo elegido;
y que cada fragmento tenga un **storyboard de varios paneles con rango de
segundos**, generado por IA bajo demanda.

## Decisiones aprobadas

1. La revisión/confirmación vive **dentro del paso 1** (borrador → confirmado).
2. La revisión es **solo lectura** + confirmar/regenerar (sin edición del guion).
3. Al confirmar se crean **cards limpias** (nombre + descripción), **sin variante
   ni imagen**; las imágenes se generan luego por lotes.
4. El storyboard de un fragmento tiene **varios paneles con rango de segundos**.
5. Los storyboards se generan **bajo demanda** en el paso 3.
6. El guion debe ser de género **DRAMA** (conflicto, arcos emocionales, diálogos).

## Restricciones técnicas

- La BD es SQLite y se inicializa con `create_all` (sin Alembic): las **tablas
  nuevas** se crean solas, pero las **columnas nuevas en tablas existentes no**.
  Por eso los datos nuevos del proyecto van en `Project.settings` (JSON) o en
  **tablas nuevas**.
- Cola Redis + arq; sin Redis los endpoints de jobs devuelven 503
  `queue_unavailable` (comportamiento actual, se mantiene).
- TDD obligatorio.

## Modelo de datos

- `Project.settings["script_draft"]`: JSON del `ScriptDraft` generado (sinopsis,
  characters, scenes, props, episodes con shots y dialogues). Guion pendiente.
- `Project.settings["script_confirmed"]`: bool.
- **Tabla nueva `storyboard_panels`**: `id`, `fragment_id` (FK cascade),
  `order`, `title`, `start_seconds`, `end_seconds`, `prompt`.
- **Nuevos `JobType`**: `resource_image_gen`, `storyboard_gen`.

## Flujo backend

1. `run_script_gen` (modificado): genera el draft y lo guarda en
   `settings["script_draft"]`; `script_confirmed=false`; **no** crea
   recursos/episodios.
2. `GET /projects/{id}/script-draft`: devuelve el draft pendiente.
3. `POST /projects/{id}/confirm-script`: materializa desde el draft →
   recursos (nombre + descripción en `profile`, sin variantes) + episodios +
   fragmentos + diálogos; marca la fase 1 completada y `script_confirmed=true`.
   Idempotente: elimina los recursos/episodios materializados previamente antes
   de recrear.
4. `POST /projects/{id}/resources/generate-images`
   `{resource_ids: number[], provider?: string, model?: string}` → job
   `resource_image_gen`. El task, por recurso, crea la variante "Principal" si no
   existe y guarda la imagen generada; `progress = hechos/total*100`. Los fallos
   individuales no detienen el lote (se reportan en el resultado).
5. `POST /projects/{id}/storyboards` `{episode_ids?: number[]}` → job
   `storyboard_gen`. El task, por cada fragmento, pide al LLM paneles con rango
   de segundos (0–12 s) y prompts visuales optimizados; los persiste.
6. `GET /episodes/{id}/fragments` incluye `storyboard` (lista de paneles).

## Frontend

- **ScriptStep**: vista de guion de solo lectura desde el draft (sinopsis,
  personajes, escenas, utilería, capítulos con planos y diálogos) + botón
  "Confirmar guion"; estado "Guion confirmado".
- **ResourcesStep**: checkbox por card, "Seleccionar todo", `ProviderSelector`
  (imagen) y "Generar imágenes" con `JobProgress`.
- **VideosStep**: por fragmento, editor de paneles (título, rango s, prompt) y
  botón "Generar storyboards" (por capítulo / todo).
- **ProjectView**: el paso 2 se desbloquea con `script_confirmed`.

## Errores y casos límite

- Confirmar sin draft → 400.
- Regenerar tras confirmar → `script_confirmed=false`; al reconfirmar se
  reemplazan recursos/episodios previos.
- Redis caído → 503 `queue_unavailable`; el draft sigue visible.
- Fallo de un recurso en el lote → el job continúa y reporta fallidos.

## Testing

- Backend: store-draft, confirm-script (materializa y limpia), batch image job,
  storyboard job (paneles con rangos), endpoints.
- Frontend: vista de guion + confirmar, selección por lotes, editor de paneles.

## Fuera de alcance

Fases 4–5: referencias `@` con pestañas (personajes/escenas/utilería) y
generación de video desde imagen de referencia por fragmento.
