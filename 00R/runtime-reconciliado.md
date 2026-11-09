# VIDEO-EDITOR · Fase 0R · Runtime reconciliado (informe vs medido)

- **Fecha:** 2026-11-08 14:16 UTC-4 (Caracas)
- **Autor:** rafael (operaciones/entorno) · **Destino:** Hermes (Padre)
- **Modo:** 100 % read-only. Sin reinicio de gateway, sin enable/disable de plugins, sin editar config ni perfiles, sin borrar nada.
- **Objeto:** contrastar el informe aportado (plan consolidado, línea 23) con el runtime real de esta PC.

## 0. Resumen ejecutivo

1. **«178 skills registradas» no es Hermes core: es el corpus de Tormen-skill.** Medido: 177 `SKILL.md` en `C:/Users/EgtYP/tormen-skill/skills/` + 1 `router/SKILL.md` = **178**. El gateway lo registra con la línea `tormen-skill: 177 skills registradas`. Hermes core en el perfil Padre tiene **235** skills (28 habilitadas); en el perfil `rafael`, **19** (19 habilitadas).
2. **«4 unsupported» se reproduce con 3 casos reales + 1 falso positivo probable.** 3 skills del corpus declaran `platforms: [linux, macos]`; la cuarta sería `what-have-we-done-today`, que declara `[platform-agnostic]` — un clasificador que solo busque `windows` la marcaría como no soportada. **Hipótesis, no certificado:** no ejecuté el verificador original (prohibido salir del read-only).
3. **El resto del informe se sostiene en lo comprobable:** suites BSK/Tormen/JEV realmente aisladas por perfil (verificado en config), gateway corriendo, 6 perfiles con alias, 4 desktop plugins en disco. **Lifecycle del Panteón sigue no verificable sin reiniciar** → estacionado.

## 1. Restricciones respetadas

| Prohibición | Estado |
|---|---|
| Reiniciar el gateway | No ejecutado. Gateway corriendo (PID 7356, arranque 09:47:54) |
| `plugins enable/disable` | No ejecutado (solo `list`) |
| Editar `config.yaml` / perfiles | No ejecutado (solo lectura de la clave `plugins`) |
| `doctor --fix` | No ejecutado (`hermes doctor` sin flags; `--live` tampoco, para no hacer llamadas de red) |
| Instalar / desinstalar | No ejecutado |

## 2. Tabla: informe vs medido

| # | Afirmación del informe | Medido en esta PC | Clasificación |
|---|---|---|---|
| 1 | «Tormen desplegado: **178 skills registradas**» | `find tormen-skill/skills -name SKILL.md` = **177**; `+ router/SKILL.md` = **178**. `gateway.log`: `hermes_plugins.tormen_skill: tormen-skill: 177 skills registradas` (última 2026-11-08 08:40) | ✅ **Probado, pero de Tormen-skill, no de Hermes core.** El plan lo lee como si fuera el registro de Hermes |
| 1b | (implícito) registro de skills de Hermes | `hermes -p default skills list` → `34 hub-installed, 19 builtin, 182 local — 28 enabled, 207 disabled` (**235**) | ✅ Probado. **Discrepancia de alcance con el informe** |
| 2 | «**174 available**» | 178 registradas − 4 no soportadas = 174: la aritmética del corpus es coherente. «Available» es un cálculo del plugin, no un campo de Hermes core | 🟡 **Solo consistente por aritmética**; no re-ejecutado |
| 3 | «**4 unsupported**» | Corpus Tormen: 3 con `platforms: [linux, macos]` (`evaluating-llms-harness`, `serving-llms-vllm`, `research-paper-writing`) + 1 con `[platform-agnostic]` (`what-have-we-done-today`) = **4**, con 1 falso positivo probable | 🟡 **Parcialmente reproducido** (3 reales + 1 caso dudoso) |
| 4 | «No hubo recarga runtime» | Proceso actual PID 7356 arrancado 09:47:54; entradas de registro de plugins en `gateway.log` a 08:40 (tormen) y 09:40 (bsk), anteriores al proceso vivo. No se provocó ninguna recarga | 🟡 No concluyente por logs; **no se hizo recarga** |
| 5 | «BSK y JEV: **suites aisladas aprobadas**» | `hermes -p default plugins list`: `bsk-studio` enabled (user), `tormen-skill` enabled (user), `hermes-jev` enabled (user) 0.19.0. `config.yaml` del perfil `rafael` declara solo 5 plugins: `candado-kanban, github-copilot, hermes-handoff, hermes-jev, pruner-pilot` — **no incluye bsk-studio ni tormen-skill** | ✅ **Aislamiento probado por configuración.** «Aprobadas» es gobernanza: `run_isolated.py` **no** re-ejecutado (fuera de alcance) |
| 6 | «integración pendiente» | Ninguna skill de BSK/Tormen aparece en `hermes skills list` (ni en default ni en rafael): los plugins las registran en su propio namespace, no en el registro de Hermes | ✅ **Confirmado.** Integración cross-perfil sigue abierta |
| 7 | «Panteón: **ficha registrada**» | `hermes profile list` → 6 filas: `Padre (default)`, `apollo`, `dike`, `harmonia`, `hephaestus`, `rafael`; todas con alias y `gateway running`. `hermes doctor`: «5 profile(s) found» (no cuenta `default`) | ✅ **Probado** |
| 8 | «lifecycle completo **no probado**» | Solo se midió «gateway running» + PID. Crear/pausar/reiniciar/reload no se ejecutó (irreversible sin ventana) | 🚫 **No verificable sin reiniciar** |
| 9 | (nuevo) skills de BSK | Plugin registra **168** (`gateway.log`, 2026-11-08 09:40); en disco hay **176** `SKILL.md` con **176 nombres únicos** (no es deduplicación) | ⚠️ **Delta abierto de 8**, causa no determinada en read-only |

## 3. Conteos de skills medidos (tres alcances distintos — no mezclar)

| Alcance | Comando | Total | Desglose |
|---|---|---|---|
| Hermes core · perfil `Padre` (default) | `hermes -p default skills list` | **235** | 34 hub · 19 builtin · 182 local → **28 enabled / 207 disabled** |
| Hermes core · perfil `rafael` | `hermes skills list` | **19** | 0 hub · 2 builtin · 17 local → **19 enabled / 0 disabled** |
| Corpus Tormen-skill (plugin) | `find tormen-skill/skills -name SKILL.md` | **178** | 177 en `skills/` + 1 en `router/` |
| Corpus BSK Studio (plugin) | `find bsk-studio/skills -name SKILL.md` | **176** archivos | plugin registra **168** en el gateway |

Disco de skills del perfil Padre: **345** `SKILL.md` = 283 efectivos + 62 en `.archive/` (239 en `~/.hermes/skills` + 44 bundled del install).

### Skills incompatibles con Windows en el registro de Hermes (scopes distintos al «4» del informe)

8 de las 283 efectivas declaran plataformas sin Windows: 4 bundled `[macos]` (`apple-notes`, `apple-reminders`, `findmy`, `imessage`), 1 bundled `[linux, macos]` (`xurl`), 3 de usuario `[linux, macos]` (`evaluating-llms-harness`, `serving-llms-vllm`, `research-paper-writing`). Corrobora el síntoma (macOS-only no carga en Windows: `~/.hermes/skills/apple/` tiene 0 `SKILL.md`), pero **no es el mismo conjunto** que las 4 del corpus Tormen.

## 4. Plugins medidos

| Perfil | Total | enabled | not enabled | disabled |
|---|---|---|---|---|
| `default` (Padre) | 79 | 69 | 5 bundled (`chronos`, `disk-cleanup`, `google_meet`, `security-guidance`, `teams_pipeline`) | 5: `bot-agente`, `candado-kanban`, `homeassistant`, `padre-flow`, `pruner-pilot` |
| `rafael` | 72 | 64 | 5 bundled (los mismos) | 3: `advanced-delegation`, `blender`, `lunacia-studio` |

- **No-bundled enabled en `default` (10):** `advanced-delegation`, `blender`, `bot-chat-agent`, `bsk-studio`, `github-copilot`, `hermes-handoff`, `hermes-jev`, `meshy`, `pixel-forge`, `tormen-skill` → **coincide exactamente** con la lista `plugins.enabled` del dossier Fase 0.
- **`hermes plugins list` es por perfil.** En `rafael` no aparecen ni `bsk-studio` ni `tormen-skill` ni `meshy` ni `pixel-forge` ni `padre-flow`: no están declarados en su `config.yaml`. Cualquier verificación de esas suites debe hacerse desde el perfil Padre.
- **Desktop plugins (UI):** 4 carpetas en `~/.hermes/desktop-plugins/` → `bot-agente`, `bot-chat-agent`, `meshy`, `padre-flow`. Superficie UI corroborada **en disco**; la carga visual no se re-probó (requiere la app y sería una intervención, no un comando).

## 5. Entorno re-medido por mí (no copiado del dossier)

| Dato | Valor medido | Comando |
|---|---|---|
| Hermes | v0.23.0 (2026.9.24) stable · local `2bd378ed1b8d` · git · Python 3.11.15 · «Up to date» | `hermes --version` |
| Runtime del proceso | Python 3.14.9 · SQLite 3.53.1 · `state.db` WAL 16.8 MB · 34 sesiones / 1 161 mensajes | `hermes doctor` |
| Gateway | running · PID 7356 · multiplexer del perfil default | `hermes gateway status` + `ps -W` |
| RAM | **25.7 GB decimal = 23.9 GiB** · libre 11.6 GB · uso 54 % | `GlobalMemoryStatusEx` |
| Disco C: | 223 GB · 189 usados · **35 GB libres (85 %)** | `df -h /c` |
| FFmpeg | `n9.0.1-11-ge47273f4d9` · `--enable-gpl --enable-libx264 --enable-libass --enable-libfreetype` · filtros `ass`, `drawtext`, `xfade`, `concat`, `overlay`, `subtitles`; encoders `libx264`, `aac`, `libmp3lame` | `ffmpeg -version / -filters / -encoders` |
| `hermes doctor` | **exit 1**, 1 incidencia: «Run `hermes setup` to configure missing API keys» (Nous Portal y MiniMax sin login). Sin avisos de seguridad activos | `hermes doctor` |

> El dossier dice «23.9 GB»: es GiB. La cifra es correcta; solo cambia la unidad (25.7 GB decimales).

## 6. Clasificación en tres cubos

**A · Probado (comando reproducible, salida real)**
- Versión/instalación de Hermes y estado «Up to date».
- Gateway corriendo + PID; 6 perfiles con alias.
- Conteos de skills core (235 default / 19 rafael) y corpus Tormen (178 archivos).
- 10 plugins no-bundled habilitados en `default`, coincidentes con el dossier.
- Aislamiento por perfil de BSK/Tormen (config de `rafael` no los declara).
- 4 desktop plugins presentes en disco.
- RAM 23.9 GiB, disco 35 GB libres, FFmpeg n9.0.1 con x264/ass/drawtext/xfade.
- `hermes doctor` sin avisos de seguridad; 1 incidencia de claves.

**B · Solo instalado (existe y carga, sin ejercicio funcional en esta pasada)**
- `bsk-studio` / `tormen-skill` / `hermes-jev`: enabled y registran al arrancar el gateway (líneas de log), pero **no** se ejercitó `skill_view('tormen-skill:…')` ni la cadena router→JEV→despacho.
- Suites `run_isolated.py` de BSK (61/61) y JEV (68/68 + 97/97) citadas en `log.md` del vault: **no re-ejecutadas** aquí.
- Carga real de los 4 desktop plugins en la app: no re-probada.
- Corpus BSK: 176 archivos en disco vs 168 registradas.

**C · No verificable sin reiniciar / intervención externa**
- Lifecycle del Panteón: crear, pausar, reanudar, reiniciar perfiles, reload de plugins.
- Import de `plugin_api.py` (requiere recarga del gateway) → bloqueo conocido del spike F1.
- Gate R completo (skill namespaced → JEV → identidad → despacho → kanban → retorno).
- Visibilidad de un plugin recién habilitado en una sesión ya abierta.

## 7. Riesgos y bloqueos abiertos

1. **El plan apoya su calendario en un número de otro sistema.** La línea 23 mezcla el corpus de Tormen-skill con el registro de Hermes. Riesgo de decisión sobre dato equivocado; ver propuesta de redacción en §8.1.
2. **BSK 168 vs 176 (delta 8)** sin causa determinada. No es deduplicación por `name`.
3. **«4 unsupported» con 1 falso positivo probable** (`[platform-agnostic]`). Si el clasificador es ingenuo, el informe subestima lo soportado (4 → 3).
4. **`hermes plugins list` es por perfil:** verificar BSK/Tormen desde `rafael` da falsos negativos (aparecen como inexistentes, no como «disabled»).
5. **`hermes doctor` sale con exit 1** por claves ausentes (Nous Portal, MiniMax). No bloquea el editor; sí ensucia cualquier gate que exija «doctor limpio».
6. **Disco al 85 %** (35 GB libres) con presupuesto de 10 GB temporales del plan.

## 8. Decisiones necesarias (Tormen / Hermes)

1. **Redacción del plan, línea 23** — propuesta: *«Tormen-skill desplegado: 178 skills registradas en su propio corpus (177 + router), 174 disponibles y 4 no soportadas en Windows según el verificador del plugin. Registro de Hermes core: 235 skills, 28 habilitadas. No hubo recarga runtime. BSK y JEV: suites aisladas aprobadas, integración cross-perfil pendiente. Panteón: perfiles registrados, lifecycle completo no probado.»* — ¿se aplica? (yo no edito el plan sin OK).
2. **Ventana de recarga del gateway** para 0R.4/0R.5 (lifecycle + Gate R). Mientras no exista, esos puntos quedan **estacionados**, no «pendientes de mí».
3. **¿Autorizo re-ejecutar** `bsk/run_isolated.py`, `jev/run_isolated.py` y el descubridor del plugin BSK para cerrar el delta 168/176? Es lectura + tests locales, pero sale del contrato estricto de 0R.
4. **Vault:** dejé commit **local** de la ficha. `git push` a `segundo-cerebro` **no** ejecutado (requiere OK).

## 9. Evidencia (comandos y rutas)

```
hermes --version
hermes -p default skills list [--source all|builtin|local|hub] [--enabled-only]
hermes skills list
hermes plugins list          # perfil rafael
hermes -p default plugins list
hermes profile list
hermes gateway status
hermes doctor                # sin --fix, sin --live
find <root> -name SKILL.md | wc -l ; parseo de frontmatter (platforms, name)
df -h /c ; GlobalMemoryStatusEx ; ffmpeg -version|-filters|-encoders
```

- Logs citados: `C:/Users/EgtYP/AppData/Local/hermes/logs/gateway.log` (líneas `bsk-studio: 168 skills registradas`, `tormen-skill: 177 skills registradas`).
- Configs leídas (solo clave `plugins`): `profiles/rafael/config.yaml`, `config.yaml`.
- Corpus: `C:/Users/EgtYP/tormen-skill/skills` (177), `C:/Users/EgtYP/tormen-skill/router` (1), `C:/Users/EgtYP/bsk-studio/skills` (176).
- Sin credenciales, tokens ni claves en este documento.

## 10. Ficha durable

`C:/Users/EgtYP/vaults/segundo-cerebro/wiki/entities/video-editor.md` (creada; enlaza, no copia).

- Commit **local** `b986c52` (solo la página nueva). `home.md`, `index.md` y `log.md` quedan con los cambios en el árbol de trabajo porque ya traían ediciones en curso de otra sesión (SYNERGY): no las barro en un commit ajeno. `git push` **no ejecutado** (requiere OK).
- Lint del vault: mi página **sin enlaces rotos, sin huérfanas y con frontmatter válido**. Los 2 enlaces rotos y 7 huérfanas que reporta `lint_wiki.py` son preexistentes (`pantheon/`, `ops/`, `synthesis/modelos-*`), no de esta entrega.
