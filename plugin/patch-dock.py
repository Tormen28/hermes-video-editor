# -*- coding: utf-8 -*-
"""Aplica v3.1 (dock derecho) a plugin/plugin.js con anclas exactas.

Idempotente por bloques: cada reemplazo exige que el ancla vieja exista.
"""
from pathlib import Path
import shutil
import sys

TARGET = Path(__file__).resolve().parent / "plugin.js"
src = TARGET.read_text(encoding="utf-8")
backup = TARGET.with_suffix(".js.v31bak")
if not backup.exists():
    shutil.copy2(TARGET, backup)

steps = []


def rep(old, new, label):
    global src
    if new in src and old not in src:
        steps.append(f"SKIP {label} (ya aplicado)")
        return
    if old not in src:
        print(f"FALTA ANCLA: {label}")
        sys.exit(1)
    if src.count(old) != 1:
        print(f"ANCLA NO ÚNICA ({src.count(old)}): {label}")
        sys.exit(1)
    src = src.replace(old, new, 1)
    steps.append(f"OK   {label}")


# ---------------------------------------------------------------- CSS
rep(
    "  height:100%;width:100%;min-height:0;overflow:hidden;\n",
    "  height:100%;width:100%;min-height:0;overflow:hidden;contain:paint;\n",
    "css: contain paint en .ve-root",
)

rep(
    ".ve-body{display:grid;grid-template-columns:minmax(0,1fr) 292px;min-height:0;min-width:0}",
    ".ve-body{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 292px;min-height:0;min-width:0;overflow:hidden;contain:paint}",
    "css: .ve-body contiene overlays",
)

OLD_MQ = """@media (max-width:520px){
  .ve-auto{display:none}
  .ve-chat .ve-chip__name,.ve-chat__b{display:none}
  .ve-chat{padding:0 6px}
  .ve-hdr .ve-badge{display:none}
  .ve-hdr .ve-title,.ve-hdr .ve-sep{display:none}
  .ve-hdr{padding:0 6px;gap:5px}
  .ve-chip{max-width:112px}
  .ve-transport{gap:1px;padding:0 4px}
  .ve-transport [aria-label="Partir en el cursor"]{display:none}
  .ve-tc{font-size:10px}
}
@media (max-width:860px){
  .ve-body{grid-template-columns:minmax(0,1fr)}
  .ve-left{border-right:0}
  .ve-rail{position:absolute;right:0;top:44px;bottom:44px;width:292px;background:var(--ve-surface);border-left:1px solid var(--ve-line);z-index:8;box-shadow:-14px 0 30px -22px color-mix(in oklab,var(--ve-fg) 60%,transparent)}
  .ve-tl{height:96px}
}"""

NEW_MQ = """@media (max-width:520px){
  .ve-auto{display:none}
  .ve-chat .ve-chip__name,.ve-chat__b{display:none}
  .ve-chat{padding:0 6px}
  .ve-hdr .ve-badge{display:none}
  .ve-hdr .ve-title,.ve-hdr .ve-sep{display:none}
  .ve-hdr{padding:0 6px;gap:5px}
  .ve-chip{max-width:112px}
  .ve-transport{gap:1px;padding:0 4px}
  .ve-transport [aria-label="Partir en el cursor"]{display:none}
  .ve-tc{font-size:10px}
}
/* --- v3.1 · dock derecho (922 px / 655 px) -------------------------------
   Los drawers son absolute DENTRO de .ve-body (position:relative + contain:paint),
   nunca fixed: si el pane cambia de sitio, el overlay viaja con él. ---------- */
.ve-lib{position:absolute;left:0;top:0;bottom:0;width:220px;display:flex;flex-direction:column;min-height:0;background:var(--ve-surface);border-right:1px solid var(--ve-line);z-index:9;overflow:hidden;contain:paint;box-shadow:14px 0 30px -24px color-mix(in oklab,var(--ve-fg) 60%,transparent)}
.ve-lib__h{display:flex;align-items:center;gap:6px;height:34px;flex:none;padding:0 6px 0 10px;border-bottom:1px solid var(--ve-line);min-width:0}
.ve-lib__t{font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ve-ink2);white-space:nowrap}
.ve-lib__list{flex:1 1 auto;min-height:0;overflow:auto;display:flex;flex-direction:column;gap:2px;padding:4px}
.ve-lib__item{display:grid;grid-template-columns:9px minmax(0,1fr);align-items:center;gap:7px;height:32px;padding:0 6px;border:1px solid transparent;border-radius:3px;background:transparent;text-align:left;cursor:pointer;width:100%;min-width:0}
.ve-lib__item:hover{background:var(--ve-soft)}
.ve-lib__item[aria-current="true"]{border-color:color-mix(in oklab,var(--ve-accent) 38%,transparent);background:color-mix(in oklab,var(--ve-accent) 9%,transparent)}
.ve-lib__m{min-width:0;display:flex;flex-direction:column;gap:1px}
.ve-lib__n{font-size:11px;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;line-height:1.2}
.ve-lib__s{font-size:9px;color:var(--ve-ink2);font-variant-numeric:tabular-nums;line-height:1.2}
.ve-lib__empty{padding:10px;font-size:10.5px;color:var(--ve-ink2);line-height:1.45}
.ve-ov{position:absolute;inset:0;background:color-mix(in oklab,var(--ve-surface) 52%,transparent);z-index:8}
.ve-root[data-compact="1"] .ve-body{grid-template-columns:minmax(0,1fr)}
.ve-root[data-compact="1"] .ve-left{border-right:0}
.ve-root[data-compact="1"] .ve-rail{position:absolute;left:0;right:0;bottom:0;height:240px;max-height:72%;width:auto;background:var(--ve-surface);border-top:1px solid var(--ve-line);z-index:9;overflow:auto;box-shadow:0 -18px 40px -24px color-mix(in oklab,var(--ve-fg) 60%,transparent)}
.ve-root[data-compact="1"] .ve-scenes{max-height:96px}
.ve-root[data-compact="1"] .ve-tl{height:96px}
.ve-root[data-compact="1"] .ve-rail__sec{padding:6px 10px}
.ve-root[data-tight="1"] .ve-tl{height:84px}
.ve-root[data-tight="1"] .ve-hdr{padding:0 6px;gap:5px}
.ve-root[data-tight="1"] .ve-auto,.ve-root[data-tight="1"] .ve-title{display:none}
.ve-root[data-tight="1"] .ve-chat .ve-chip__name{display:none}
.ve-root[data-tight="1"] .ve-chip{max-width:124px}
.ve-tip{position:absolute;right:10px;top:46px;z-index:13;max-width:240px;padding:6px 9px;border:1px solid var(--ve-line);border-radius:4px;background:var(--ve-card);color:var(--ve-fg);font-size:10.5px;line-height:1.4;box-shadow:0 12px 30px -18px color-mix(in oklab,var(--ve-fg) 60%,transparent)}"""

rep(OLD_MQ, NEW_MQ, "css: media queries v3.1 + drawers")

# ---------------------------------------------------------------- JS estado
rep(
    "  const [railOpen, setRailOpen] = useState(false)\n",
    "  const [railOpen, setRailOpen] = useState(false)\n"
    "  const [libOpen, setLibOpen] = useState(false)\n"
    "  const [picker, setPicker] = useState(null)\n"
    "  const [modelTip, setModelTip] = useState(false)\n",
    "js: estado de drawers/picker/tip",
)

rep(
    "  const compact = width < 860\n",
    "  const compact = width < 1100\n  const tight = width < 760\n",
    "js: umbrales 1100 / 760",
)

# ---------------------------------------------------------------- modelo
rep(
    "  const liveBusy = useValue(stateAtom('busy', false))\n",
    "  const liveBusy = useValue(stateAtom('busy', false))\n"
    "  // host.state.model es readonlyAtom<string>; si el host no lo expone el\n"
    "  // atom cae en '' y el chip simplemente no se dibuja (nada inventado).\n"
    "  const modelSlug = useValue(stateAtom('model', ''))\n",
    "js: leer host.state.model",
)

rep(
    "  const compact = width < 1100\n  const tight = width < 760\n",
    "  const compact = width < 1100\n  const tight = width < 760\n"
    "  const modelName = (() => {\n"
    "    const raw = typeof modelSlug === 'string' ? modelSlug.trim() : ''\n"
    "    if (!raw) return ''\n"
    "    const tail = raw.split('/').pop() || raw\n"
    "    return tail.length > 26 ? `${tail.slice(0, 25)}…` : tail\n"
    "  })()\n"
    "  const baseName = (value) => String(value || '').split(/[\\\\/]+/).pop() || String(value || '')\n",
    "js: nombre corto de modelo + baseName",
)

rep(
    """  function goChat() {""",
    """  useEffect(() => {
    if (!modelTip) return undefined
    const timer = setTimeout(() => setModelTip(false), 4000)
    return () => clearTimeout(timer)
  }, [modelTip])

  function goChat() {""",
    "js: auto-ocultar el tip del modelo",
)

# ---------------------------------------------------------------- picker + biblioteca
rep(
    """  // -------------------------------------------------------------- regiones

  const header = () =>""",
    """  // -------------------------------------------------------------- picker + biblioteca

  const openPicker = (mode, sceneId) => {
    const current = docRef.current
    setLibOpen(false)
    setRailOpen(false)
    if (!current) {
      setPicker({ mode, sceneId: sceneId || null, phase: 'error', items: [], error: 'No hay proyecto abierto.' })
      return
    }
    setPicker({ mode, sceneId: sceneId || null, phase: 'loading', items: [] })
    request(ctx, `/projects/${encodeURIComponent(current.projectId)}`)
      .then((payload) => {
        const items = (payload && payload.media) || []
        setMedia(items)
        setPicker((prev) => (prev && prev.mode === mode ? { ...prev, phase: 'ready', items } : prev))
      })
      .catch((error) =>
        setPicker((prev) => (prev && prev.mode === mode ? { ...prev, phase: 'error', error: error.message } : prev))
      )
  }

  const applyAdd = async (item) => {
    const current = docRef.current
    if (!current || !item) return
    setPicker((prev) => (prev ? { ...prev, phase: 'busy' } : prev))
    try {
      // `path` es la ruta RELATIVA del asset: el servicio la resuelve contra
      // la carpeta concedida y añade la escena en la misma llamada.
      const payload = await request(ctx, `/projects/${encodeURIComponent(current.projectId)}/media`, {
        method: 'POST',
        body: { path: item.path }
      })
      setDoc(payload.project)
      setMedia(payload.media || [])
      setDirty(false)
      setSavedAt(Date.now())
      const scenes = (payload.project && payload.project.scenes) || []
      if (scenes.length) setSelId(scenes[scenes.length - 1].id)
      setDialog(null)
      setPicker(null)
      setNotice(`Medio añadido: ${baseName(item.path)}`)
    } catch (error) {
      setPicker((prev) => (prev ? { ...prev, phase: 'error', error: error.message } : prev))
    }
  }

  const applyReplace = (item) => {
    const sceneId = (picker && picker.sceneId) || (sel && sel.id)
    if (!sceneId || !item) return
    mutate((draft) => {
      const target = (draft.scenes || []).find((entry) => entry.id === sceneId)
      if (!target) return draft
      // Solo cambia el asset: in/out, audio y transición quedan intactos.
      target.source = { ...(target.source || {}), assetId: item.id, kind: item.kind || (target.source || {}).kind || 'video' }
      target.needsRelink = false
      return draft
    })
    setDialog(null)
    setPicker(null)
    setNotice(`Medio reemplazado: ${baseName(item.path)} · in/out conservados`)
  }

  const library = () =>
    !libOpen || !doc
      ? null
      : h(
          'aside',
          { className: 've-lib', 'aria-label': 'Biblioteca de medios del proyecto' },
          h(
            'div',
            { className: 've-lib__h' },
            h('span', { className: 've-lib__t' }, 'Medios'),
            h('span', { className: 've-spacer' }),
            h(Btn, {
              variant: 'text',
              label: 'Añadir',
              title: 'Añadir un medio de la biblioteca como escena',
              onClick: () => {
                setDialog({ kind: 'picker' })
                openPicker('add')
              }
            }),
            h(Btn, { icon: 'close', variant: 'ghost', ariaLabel: 'Cerrar medios', onClick: () => setLibOpen(false) })
          ),
          media.length
            ? h(
                'div',
                { className: 've-lib__list' },
                media.map((item) =>
                  h(
                    'button',
                    {
                      key: item.id,
                      type: 'button',
                      className: 've-lib__item',
                      'aria-current': activeAsset === item.id ? 'true' : undefined,
                      title: item.path,
                      onClick: () => {
                        const target = (doc.scenes || []).find((scene) => (scene.source && scene.source.assetId) === item.id)
                        if (target) setSelId(target.id)
                        setLibOpen(false)
                        setNotice(`Medio seleccionado: ${baseName(item.path)}`)
                      }
                    },
                    h(Dot, { tone: activeAsset === item.id ? 'good' : item.exists === false ? 'bad' : undefined }),
                    h(
                      'span',
                      { className: 've-lib__m' },
                      h('span', { className: 've-lib__n' }, baseName(item.path)),
                      h('span', { className: 've-lib__s' }, `${item.kind || 'medio'}${item.exists === false ? ' · falta' : ''}${item.bytes ? ` · ${fmtBytes(item.bytes)}` : ''}`)
                    )
                  )
                )
              )
            : h('p', { className: 've-lib__empty' }, 'Sin medios todavía. «Añadir» elige de la biblioteca; «Importar medios» trae archivos de la carpeta concedida.')
        )

  // -------------------------------------------------------------- regiones

  const header = () =>""",
    "js: openPicker/applyAdd/applyReplace/library",
)

# ---------------------------------------------------------------- topbar
rep(
    """      h('span', { className: 've-spacer' }),
      h('span', { className: 've-auto', 'aria-live': 'polite' }, h(Dot, { tone: autosaveTone }), savedLabel),""",
    """      modelName
        ? h(
            'button',
            {
              type: 'button',
              className: 've-chip ve-chip--ghost ve-model',
              title: 'Modelo activo del chat · solo lectura',
              'aria-label': `Modelo ${modelName}. Cambia el modelo en el selector del chat`,
              onClick: () => {
                try {
                  if (host && host.composer && typeof host.composer.focus === 'function') host.composer.focus(null)
                } catch (error) {
                  console.warn('[video-editor] compositor no enfocable', error && error.message)
                }
                setModelTip(true)
                setNotice('Cambia el modelo en el selector del chat.')
              }
            },
            h(Icon, { name: 'panel', size: 'sm' }),
            h('span', { className: 've-chip__name' }, modelName)
          )
        : null,
      h('span', { className: 've-spacer' }),
      h('span', { className: 've-auto', 'aria-live': 'polite' }, h(Dot, { tone: autosaveTone }), savedLabel),""",
    "js: chip de modelo en la topbar",
)

rep(
    "      compact ? h(Btn, { icon: 'panel', variant: 'ghost', ariaLabel: 'Escenas y propiedades', onClick: () => setRailOpen((prev) => !prev) }) : null,\n",
    "      compact\n"
    "        ? h(Btn, {\n"
    "            icon: 'film',\n"
    "            variant: 'ghost',\n"
    "            ariaLabel: 'Medios',\n"
    "            title: 'Medios · biblioteca del proyecto',\n"
    "            onClick: () => {\n"
    "              setLibOpen((prev) => !prev)\n"
    "              setRailOpen(false)\n"
    "            }\n"
    "          })\n"
    "        : null,\n"
    "      compact\n"
    "        ? h(Btn, {\n"
    "            icon: 'panel',\n"
    "            variant: 'ghost',\n"
    "            ariaLabel: 'Propiedades',\n"
    "            title: 'Escenas y propiedades',\n"
    "            onClick: () => {\n"
    "              setRailOpen((prev) => !prev)\n"
    "              setLibOpen(false)\n"
    "            }\n"
    "          })\n"
    "        : null,\n",
    "js: botones Medios / Propiedades",
)

# ---------------------------------------------------------------- inspector
rep(
    "              h(Btn, { variant: 'text', label: 'Restablecer escena', onClick: () => resetScene(sel) })\n",
    "              h(Btn, {\n"
    "                variant: 'text',\n"
    "                label: 'Reemplazar medio',\n"
    "                title: 'Cambia el archivo de la escena sin tocar in/out',\n"
    "                onClick: () => {\n"
    "                  setDialog({ kind: 'picker' })\n"
    "                  openPicker('replace', sel.id)\n"
    "                }\n"
    "              }),\n"
    "              h(Btn, { variant: 'text', label: 'Restablecer escena', onClick: () => resetScene(sel) })\n",
    "js: botón Reemplazar en inspector",
)

# ---------------------------------------------------------------- diálogo picker
rep(
    """    if (dialog.kind === 'service') {""",
    """    if (dialog.kind === 'picker') {
      const state = picker
      const close = () => {
        setDialog(null)
        setPicker(null)
      }
      if (!state) return null
      const replacing = state.mode === 'replace'
      const busy = state.phase === 'busy'
      return h(
        Dialog,
        {
          title: replacing ? 'Reemplazar el medio de la escena' : 'Añadir medio',
          body: replacing
            ? 'Se conservan la entrada y la salida de la escena; solo cambia el archivo.'
            : 'Elige un medio de la biblioteca del proyecto.',
          onClose: close,
          footer: [
            h(Btn, { key: 'c', variant: 'outline', label: 'Cancelar', onClick: close }),
            h(Btn, {
              key: 'f',
              variant: 'text',
              label: 'Otra carpeta…',
              onClick: () => {
                close()
                importFolder()
              }
            })
          ]
        },
        state.phase === 'loading'
          ? h('div', { className: 've-loadrow' }, h(Spinner), 'Leyendo la biblioteca…')
          : state.phase === 'error'
            ? h(ErrorState, { title: 'No se pudo leer la biblioteca', body: state.error })
            : h(
                'div',
                { className: 've-list', 'aria-busy': busy ? 'true' : 'false' },
                busy ? h('div', { className: 've-loadrow' }, h(Spinner), 'Vinculando el medio…') : null,
                state.items.length
                  ? state.items.map((item) =>
                      h(
                        'button',
                        {
                          key: item.id,
                          type: 'button',
                          className: 've-file',
                          disabled: busy || item.exists === false,
                          title: item.path,
                          onClick: () => (replacing ? applyReplace(item) : applyAdd(item))
                        },
                        h('span', { className: 've-file__n' }, baseName(item.path)),
                        h(
                          'span',
                          { className: 've-file__s' },
                          `${item.kind || 'medio'}${item.exists === false ? ' · falta' : ''}`
                        )
                      )
                    )
                  : h('p', { className: 've-dialog__b' }, 'La biblioteca está vacía. Usa «Otra carpeta…» para traer archivos de la carpeta concedida.')
              )
      )
    }
    if (dialog.kind === 'service') {""",
    "js: diálogo picker",
)

# ---------------------------------------------------------------- Escape + body + root
rep(
    """        } else if (menu) {
          setMenu(null)
        } else {
          setPlaying(false)
        }""",
    """        } else if (menu) {
          setMenu(null)
        } else if (libOpen || railOpen) {
          setLibOpen(false)
          setRailOpen(false)
        } else {
          setPlaying(false)
        }""",
    "js: Escape cierra drawers",
)

rep(
    "    h('div', { className: 've-body' }, h('div', { className: 've-left' }, stage(), transport(), timelineBlock()), rail()),",
    """    h(
      'div',
      { className: 've-body' },
      h('div', { className: 've-left' }, stage(), transport(), timelineBlock()),
      compact && libOpen ? h('div', { className: 've-ov', 'aria-hidden': 'true', onClick: () => setLibOpen(false) }) : null,
      compact ? library() : null,
      rail()
    ),""",
    "js: body con drawer de biblioteca contenido",
)

rep(
    """      'data-ve-pane': '1',""",
    """      'data-ve-pane': '1',
      'data-compact': compact ? '1' : '0',
      'data-tight': tight ? '1' : '0',""",
    "js: atributos data-compact/data-tight",
)

rep(
    "    h('div', { className: 've-sr', role: 'status', 'aria-live': 'polite' }, notice)\n",
    "    modelTip ? h('div', { className: 've-tip', role: 'status' }, 'Cambia el modelo en el selector del chat.') : null,\n"
    "    h('div', { className: 've-sr', role: 'status', 'aria-live': 'polite' }, notice)\n",
    "js: tip visible bajo el chip",
)

TARGET.write_text(src, encoding="utf-8")
print("\n".join(steps))
print("líneas:", src.count("\n") + 1)
