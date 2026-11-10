# Fusión del editor (box 940b487) con el editor del PC (ee37702)

Rama: `feat/editor-merge-drag` (desde `ee37702`). No se empujó nada.

## Decisión
El editor del PC (servicio 0.3.4, pane `plugin/plugin.js`, modelo por escenas, pack v1.1: música, transiciones,
texto con estilo, filtros, Ken Burns, velocidad, logo, presets) es la BASE. El editor de la box usa otro modelo
(items/pistas) y no tiene esas funciones; fusionar su código habría obligado a tocar el generador y el modelo.
Por eso NO se copió su esquema ni sus módulos. De él se tomó lo que al PC le faltaba: **arrastrar en la línea de tiempo**.

## Qué trae esta rama (solo en `plugin/plugin.js` + pruebas)
- Arrastrar una escena en la línea de tiempo para reordenarla (hueco de destino resaltado).
- Arrastrar los bordes izquierdo/derecho de la escena seleccionada para recortar (`in` / `out`), con la duración en vivo.
- Un solo paso de deshacer por gesto; guarda con la misma revisión (409 intacto); clic simple sigue seleccionando.
- Teclado y botones existentes sin cambios (flechas, subir/bajar, campos numéricos).
- Tope al alargar con el borde derecho: lo más largo que ese medio ya tuvo en el proyecto (el servicio no informa la
  duración de la fuente); para alargar más se usa el campo numérico, como antes.
- `plugin/tests/pane_drag_e2e.py` y `pane_edit_export_e2e.py` (Playwright en el banco `plugin/harness`).

## Intacto
`core/` (servicio, worker, generate, project, schema), generador y estilo Cinematic: sin cambios.

## No tomado del editor de la box (decisión)
Rotación/escala por item, animaciones por item con keyframes de enter/exit y su `edit_at_time` propio: el modelo por
escenas del PC ya tiene `/projects/{id}/edit` + `/at` y animaciones de texto. Quedan como backlog si se quieren.
La rama de la box queda como referencia en `box/editor-basico` (940b487).
