---
version: 1
slug: "frontend-src-app-tsx"
primary_target: "frontend/src/App.tsx"
related_targets: []
---

# Surface brief — AI Director (admin)

Scope: entire admin web app (Dashboard, ProjectView con 3 fases, Settings).
Visitor mode: Operate. Audience: pequeño estudio de short drama serializado.

Job: convertir una idea en una serie de episodios ensamblados, manteniendo
consistencia de personajes/escenas/utilería y voz por personaje, con control
visible de cada paso (guion → recursos → video) y proveedores auto-configurados.

Constraints: contrato de API y comportamiento intactos; controles web estándar
(tabs, selects, inputs, dialogs); sin generar datos comerciales inventados;
respetar prefers-reduced-motion; tests de frontend deben seguir pasando.

## Direction contract

THESIS: El pipeline de la serie se lee como el tablero de storyboard de un
director: cada artefacto es un fotograma numerado sobre una hoja de contacto,
y el único trazo sobre el muro es el lápiz azul no-foto del director. Se
niega el admin oscuro genérico con tarjetas.

OWN-WORLD: Muro de sala de edición en azul-negro profundo; paneles de grafito
con keylines de 1px; lápiz azul no-foto (non-photo blue) como único acento
comprometido para lo activo/primario; rojo de lápiz para error, verde de ok
para completado; Geist para UI, Geist Mono para todo numeral de fotograma,
timecode y duración; slugs de plano en mono mayúsculas espaciado; las cards
son fotogramas con su contador.

STORY: El operador está en una sala a oscuras cubierta de su propio storyboard.
Ve la serie como una hoja de contacto; cada fase es una fila de fotogramas; el
trabajo actual está marcado en lápiz azul y el resto se atenuía a hairlines.
Entiende en segundos qué existe, qué corre y qué falló: cada estado es lápiz
azul activo o un sello.

FIRST VIEWPORT: Ground de muro oscuro; barra superior con la marca "AI
DIRECTOR" como claqueta y Configuración; cabecera de proyecto con una hoja de
contacto de 3 fotogramas (Guion / Recursos / Video), el fotograma actual
circulado en azul no-foto y los completados sellados con check. Los capítulos
son cards-fotograma numeradas con título y duración mono, expandibles para
revelar los planos; los recursos, cards con preview como fotogramas.

FORM: Mundo storyboard / lista de planos, mi candidato #1 (pick, IMPECCABLE'S
PICK), seed key f5d3a3ec. Movimiento firma: el lápiz azul del director —
seleccionar dibuja el círculo de lápiz sobre el fotograma mientras el resto
del muro baja a hairlines (disciplina de foco Ikeda).

FINISH: unreviewed and undocumented is unfinished; this build ends with the
finish review, the verdict, DESIGN.md, and every shipping raster carrying
its provenance
