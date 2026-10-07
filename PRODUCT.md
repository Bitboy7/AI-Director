# Product

<!-- impeccable:product-schema 1 -->

## Platform

web

## Users

Un equipo o estudio pequeño que produce contenido "short drama" en serie. Su
trabajo principal es convertir una idea de historia en una serie de episodios en
video terminados (guion → recursos → videos por episodio → ensamblaje), operando
la plataforma de forma local con sus propias claves de IA.

## Product Purpose

AI Director genera historias de short drama por episodios usando IA. El éxito se
mide en una serie completa y publicable: episodios ensamblados (video + voz por
personaje + subtítulos) con personajes, escenas y utilería consistentes entre
episodios. Es una plataforma auto-hospedada de despliegue único, sin cuentas
multi-usuario en su estado actual.

## Positioning

Automatización de la serie, no de un video suelto. Un proyecto es una historia
serializada (episodios → fragmentos de planos de 10-12 s) y el pipeline mantiene
consistencia de personajes/escenas/utilería con variantes y voz por personaje.
El usuario conserva la propiedad de sus claves y elige el proveedor y el modelo
por dominio (LLM, imagen, video, voz) en cada paso del flujo.

## Operating Context

- Auto-hospedado, local-first: SQLite + almacenamiento local por proyecto
  (`backend/storage/<project_id>/{images,videos,audio,episodes,uploads}/`).
- Cola de trabajos asíncrona vía Redis + arq (3 workers: default/video/assembly);
  los jobs muestran progreso, se cancelan y se reencolan si el worker se cae
  (reclaim a los 5 min). Sin Redis, los jobs no se encolan.
- El operador configura sus propias claves de IA en la UI de Configuración o por
  variables de entorno; solo se ofrecen los proveedores configurados.
- Ensamblaje de video con ffmpeg/ffprobe; TTS con Edge-TTS; subtítulos SRT
  opcionales (quemados o no).

## Capabilities and Constraints

- Wizard de 3 pasos por proyecto: (1) esquema de guion con LLM, (2) biblioteca de
  recursos con variantes, imágenes de referencia (subidas o generadas) y voz por
  personaje, (3) videos por episodio + ensamblaje.
- Arquitectura de proveedores plug-in (`register_provider(kind, name, factory)`):
  LLM: Ollama/Gemini/OpenAI; imagen: Gemini (Nano Banana)/fal.ai; video:
  Mock/Gemini Omni/fal.ai; voz: Edge-TTS. Selector por paso de proveedor y modelo
  con listado dinámico de modelos (`GET /api/v1/providers/{kind}/{provider}/models`).
- El guion y los recursos se regeneran; el progreso de jobs LLM se estima por uso
  de CPU y el de video por tiempo transcurrido.
- Restricción técnica: requiere Redis para la cola y ffmpeg en PATH para el
  ensamblaje. Plataforma web sobre Vite/React/TypeScript + FastAPI.
- Indeciso aún: coexistencia multi-usuario real (autenticación) si el estudio
  crece; no está decidido ni implementado.

## Brand Commitments

- Nombre: "AI Director".
- Género: plataforma de short drama; el flujo producto es el pipeline de serie
  descrito arriba.
- El frontend es un admin web en tema oscuro (shadcn/ui) — hecho de estado actual,
  no una directiva de diseño.

## Evidence on Hand

- README.md documenta el flujo, proveedores y variables de entorno.
- Tests del pipeline: backend (pytest) y frontend (vitest).
- Sin testimonios, clientes, métricas ni material de marketing real; no
  fabricar ninguno.

## Product Principles

1. Serie primero: un proyecto es una historia serializada; la consistencia de
   personajes, escenas y utilería entre episodios es el núcleo.
2. Independencia de proveedores: el usuario es dueño de sus claves y elige
   proveedor/modelo por dominio y por paso, sin atarse a un solo servicio.
3. Control visible: cada paso del pipeline es observable, regenerable y
   editable; el usuario entiende qué generó cada pieza.
4. Auto-hospedado y local-first: datos y activos locales; la automatización debe
   funcionar sin lock-in de un proveedor concreto.