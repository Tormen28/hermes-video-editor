# VIDEO-EDITOR · Fase 0 · Inventario medido (hardware y software)

Fecha: 2026-11-08 (hora local Caracas). Método: comandos ejecutados en esta PC; cada dato tiene su comando. Sin self-report. **Revisión 2 (14:35)**: incorporadas las correcciones C1–C8 de Dike (`auditoria/F0-veredicto.md`).

## Hardware (medido con PowerShell/CIM)

| Componente | Valor real | Comando |
|---|---|---|
| SO | Microsoft Windows 11 Pro Build 26200 | `Get-CimInstance Win32_OperatingSystem` |
| CPU | AMD Ryzen 5 3600 · 6 cores / 12 hilos | `Get-CimInstance Win32_Processor` |
| RAM total | **23.9 GB** · libres: 12.9 GB a las 14:03 y 10.9 GB a las 14:26 (varía; el total es el dato estable) | `Win32_ComputerSystem.TotalPhysicalMemory` / `FreePhysicalMemory` |
| GPU | NVIDIA GeForce GT 1030 · 2 GB VRAM · driver 32.0.15.8108 | `Win32_VideoController` |
| Disco C: | 223 GB total · 189–193 GB usados · **31–35 GB libres (85–87% usado)** según el momento de medición | `df -h /c` / `Win32_LogicalDisk` |

**Deltas contra el plan consolidado:**
1. El plan asumía «si realmente hay 8 GB». **Falso: hay 23.9 GB.** La concurrencia 1 sigue siendo prudente por CPU/disco, pero el presupuesto de memoria no es el cuello de botella que el plan temía.
2. **GPU débil (GT 1030, 2 GB)**. Medición directa (Dike, reproducida): `ffmpeg -f lavfi -i testsrc2 -c:v h264_nvenc -f null -` **falla al abrir** con `Cannot load nvEncodeAPI64.dll` y «The minimum required Nvidia driver for nvenc is 610.00 or newer» (driver instalado 32.0.15.8108). Motivo = driver/capacidad, no un «silicio sin NVENC» inferido. **Consecuencia operativa: libx264 por CPU.**
3. **Disco justo**: 31–35 GB libres según el momento. El presupuesto de 10 GB temporales entra, pero hay que limpiar derivados por job y vigilar la ocupación.

## Software (medido)

| Herramienta | Versión | Estado |
|---|---|---|
| Hermes Agent | **v0.23.0 (2026.9.24) stable · local 2bd378ed1b8d · git install** | OK |
| Node | v24.15.0 | OK (>=22 que exige HyperFrames) |
| npm | 12.0.2 | OK |
| FFmpeg | **n9.0.1** (build con `--enable-gpl --enable-libx264 --enable-libfreetype --enable-libass --enable-libmp3lame --enable-libopus --enable-libvpx`) | OK, completo |
| ffprobe | n9.0.1 | OK |
| Python | 3.11.15 | OK |
| Rust | **NO instalado** | FilmCraft compilaría desde cero → usar binario oficial o descartar |
| Git | 2.53.0.windows.3 | OK |
| Chrome | **NO instalado** (solo Edge Chromium en `Program Files (x86)`) | HyperFrames/Puppeteer y Remotion requerirían descargar Chrome Headless Shell (~150 MB) |

## Capacidades del motor ya instalado (medidas con `ffmpeg -filters` / `-encoders`)

- Codificación: `libx264`, `aac`, `libmp3lame`, `libopus`.
- Filtros NLE presentes: `trim`, `concat`, `xfade`, `scale`, `crop`, `overlay`, `drawtext` (libfreetype), `subtitles`/`ass` (libass), `afade`, `acrossfade`, `fade`.
- **Conclusión técnica**: el MVP del plan (escenas, trim, reordenar, texto/captions, volumen, horizontal/vertical, export MP4 H.264/AAC) es realizable **solo con el FFmpeg instalado**, sin Node, sin Chrome, sin Remotion ni HyperFrames.
- Licencia del build: **GPLv3-or-later** (`--enable-gpl --enable-version3`; `ffmpeg -L` lo confirma). El binario vive dentro de la instalación de Hermes (`hermes/tools/…`): invocarlo como proceso externo **no redistribuye**; empaquetarlo dentro del plugin arrastraría obligaciones GPLv3 → ver `docs/licencias.md` (apollo).

## Plugins de Hermes instalados (contexto para 0R)

- `~/.hermes/plugins/` (gateway): 16 entradas, entre ellas `bsk-studio`, `tormen-skill`, `hermes-jev`, `candado-kanban`, `padre-flow`, `pixel-forge`, `meshy`, `model-providers`, `pruner-pilot`, `bot-chat-agent`, `bot-agente`, `homeassistant`, `github-copilot`, `blender`, `advanced-delegation`, `hermes-handoff`.
- `plugins.enabled` (config): advanced-delegation, blender, bot-chat-agent, bsk-studio, github-copilot, hermes-handoff, hermes-jev, meshy, pixel-forge, tormen-skill.
- `~/.hermes/desktop-plugins/` (UI): **bot-agente, bot-chat-agent, meshy, padre-flow** en disco con código válido (`node --check` OK). **Runtime probado con el pane NUEVO `editor-video-spike` (F1): `Hermes.exe` PID 12832 mantiene conexiones ESTABLISHED contra `127.0.0.1:8765` y `service.access.log` registra `GET/POST /probe → 200` (14:19–14:20).** El loader no escribe en `desktop.log`; la prueba válida es la conexión del proceso.

## Qué NO se midió aquí

- fps/timebase de muestras reales (no hay medios autorizados aún) → se hará con fixtures sintéticos en el spike y con material real cuando Tormen lo autorice.
- Baseline p95 del gateway antes/durante render → spike.
- Conteo real de skills (178/174/4 del informe) → resuelto por rafael en 0R: **178 = corpus de tormen-skill, no Hermes core** (Hermes Padre: 235, 28 habilitadas). Ver `00R/runtime-reconciliado.md`.
