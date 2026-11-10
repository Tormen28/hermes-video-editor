// Editor de vídeo · pane de Hermes Desktop (v0.2)
// ---------------------------------------------------------------------------
// Implementa docs/ui-spec.md §2–§10 contra el servicio local core/service/app.py.
// Reglas duras que este archivo respeta:
//   · El estado real manda: nada de porcentajes, duraciones ni miniaturas de ejemplo.
//   · Cero colores literales: todo deriva de los tokens --ui-* del app.
//   · Ninguna acción vive solo en un arrastre: todo tiene botón/tecla.
//   · El documento canónico (camelCase) es el único que se edita y se envía.
//     La vista `ui` del backend se ignora a propósito para no perder campos.
// ---------------------------------------------------------------------------
import { host, KEYBINDS_AREA, PALETTE_AREA, TITLEBAR_AREAS, useValue } from '@hermes/plugin-sdk'
import { useCallback, useEffect, useLayoutEffect, useMemo, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const DEFAULT_SERVICE = 'http://127.0.0.1:8770'
// El instalador (instalar.py / activar-editor.cmd) sustituye el marcador por el token del
// servicio. Sin token el servicio rechaza toda llamada (anti-CSRF del origen file://).
const SERVICE_TOKEN = '__VE_TOKEN__'
const PRESET = 'mp4-720p30'
const MAX_CAPTION = 90
const MIN_SCENE = 0.3
const AUTOSAVE_MS = 4000
const POLL_MS = 400

const ORIENTATIONS = {
  h: { label: 'Horizontal', short: '16:9', w: 1280, h: 720, ratio: '16 / 9' },
  v: { label: 'Vertical', short: '9:16', w: 720, h: 1280, ratio: '9 / 16' }
}

// Catálogo local de estilos `xfade` (1:1 con core/project.TRANSITION_STYLES).
// El documento no guarda el estilo suelto sino `estilo-duracion` (p. ej.
// `slideleft-0.5`), que es lo que valida el servicio. `/health` publica
// `transitions`: si está, manda esa lista; si no, se usa esta.
const TRANSITION_STYLES = [
  { id: 'fade', label: 'Fundido' },
  { id: 'slideleft', label: 'Deslizar izq.' },
  { id: 'slideright', label: 'Deslizar der.' },
  { id: 'wipeleft', label: 'Barrido izq.' },
  { id: 'wiperight', label: 'Barrido der.' },
  { id: 'circleopen', label: 'Círculo' },
  { id: 'zoomin', label: 'Zoom' }
]
const TRANSITIONS = [{ id: 'none', label: 'Sin transición' }, ...TRANSITION_STYLES]
const TRANSITION_DEFAULT_S = 0.5
const TRANSITION_MIN_S = 0.1
const TRANSITION_MAX_S = 2.0

// Catálogo local de presets. `/health` publica `presets`: los que no estén en
// esa lista se muestran deshabilitados en vez de mandarse y fallar.
const EXPORT_PRESETS = [
  { id: 'mp4-720p30', label: 'MP4 720p · 30 fps' },
  { id: 'mp4-1080p30', label: 'MP4 1080p · 30 fps · requiere medición' },
  { id: 'mp4-720p30-vertical', label: 'MP4 vertical 720p · 30 fps' },
  { id: 'mp4-720p30-square', label: 'MP4 cuadrado 720p · 30 fps' }
]

// Valores con los que nace `doc.music`; el usuario los cambia y se guardan tal cual.
const MUSIC_DEFAULTS = { volume: 50, fadeIn: 0, fadeOut: 0, loop: true, ducking: true }

// Estilo del texto (1:1 con core/project.py: TEXT_*). El estilo vive dentro de
// `scene.text[0]`; los controles solo escriben lo que el usuario toca.
const TEXT_SIZE = { min: 12, max: 120, default: 42 }
const TEXT_BORDER = { min: 0, max: 10, default: 0 }
const TEXT_SHADOW = { min: 0, max: 10, default: 0 }
const TEXT_COLOR_DEFAULT = '#FFFFFF'
const TEXT_ANIMATIONS = [
  { id: 'none', label: 'Ninguna' },
  { id: 'fade', label: 'Fundido' },
  { id: 'slide-up', label: 'Sube' },
  { id: 'slide-down', label: 'Baja' }
]
const HEX_COLOR = /^#[0-9A-Fa-f]{6}$/

// Filtros de color por escena (core/project.SCENE_FILTER_*). El valor neutro no
// se escribe: un filtro sin tocar no ensucia el documento.
const FILTER_DEFAULTS = { brightness: 0, contrast: 1, saturation: 1, grayscale: false, vignette: false, blur: 0 }
const FILTER_SLIDERS = [
  { key: 'brightness', label: 'Brillo', min: -1, max: 1, step: 0.05 },
  { key: 'contrast', label: 'Contraste', min: 0, max: 2, step: 0.05 },
  { key: 'saturation', label: 'Saturación', min: 0, max: 3, step: 0.05 },
  { key: 'blur', label: 'Desenfoque', min: 0, max: 20, step: 0.5, suffix: 'px' }
]
const FILTER_FLAGS = [
  { key: 'grayscale', label: 'Blanco y negro' },
  { key: 'vignette', label: 'Viñeta' }
]

// Ken Burns (solo imágenes) y velocidad de escena (cualquiera).
const KEN_BURNS = { minZoom: 1, maxZoom: 1.5, zoom: 1.2, pan: 'none' }
const PAN_OPTIONS = [
  { id: 'none', label: 'Sin desplazamiento' },
  { id: 'left', label: 'Hacia la izquierda' },
  { id: 'right', label: 'Hacia la derecha' },
  { id: 'up', label: 'Hacia arriba' },
  { id: 'down', label: 'Hacia abajo' }
]
const SCENE_SPEED = { min: 0.5, max: 2, default: 1 }

// Logo del proyecto (core/project.LOGO_*): marca de agua sobre todo el vídeo.
const LOGO_POSITIONS = [
  { id: 'top-left', label: 'Arriba izquierda' },
  { id: 'top-center', label: 'Arriba centro' },
  { id: 'top-right', label: 'Arriba derecha' },
  { id: 'center-left', label: 'Centro izquierda' },
  { id: 'center', label: 'Centro' },
  { id: 'center-right', label: 'Centro derecha' },
  { id: 'bottom-left', label: 'Abajo izquierda' },
  { id: 'bottom-center', label: 'Abajo centro' },
  { id: 'bottom-right', label: 'Abajo derecha' }
]
const LOGO_DEFAULTS = { position: 'bottom-right', opacity: 0.8, scale: 0.15 }
const LOGO_LIMITS = { opacity: [0, 1], scale: [0.05, 0.5] }

const STAGES = [
  { id: 'prepare', label: 'Preparando', from: ['queued', 'probing'] },
  { id: 'render', label: 'Renderizando', from: ['rendering'] },
  { id: 'mux', label: 'Escribiendo MP4', from: ['validating'] },
  { id: 'done', label: 'Listo', from: ['promoting', 'done'] }
]

// --------------------------------------------------------------------------- #
// utilidades
// --------------------------------------------------------------------------- #

const h = (type, props, ...kids) => {
  const merged = props ? { ...props } : {}
  if (kids.length === 1) merged.children = kids[0]
  else if (kids.length > 1) merged.children = kids
  return jsx(type, merged)
}

const clone = (value) => JSON.parse(JSON.stringify(value))
const clamp = (value, lo, hi) => Math.min(hi, Math.max(lo, value))
const round3 = (value) => Math.round(value * 1000) / 1000
const normPath = (value) => String(value || '').replace(/\\/g, '/').replace(/\/+$/, '').toLowerCase()
const within = (child, parent) => {
  const c = normPath(child)
  const p = normPath(parent)
  return !!p && (c === p || c.startsWith(`${p}/`))
}

function fmtTime(seconds) {
  const total = Math.max(0, Number(seconds) || 0)
  const minutes = Math.floor(total / 60)
  const rest = total - minutes * 60
  const whole = Math.floor(rest)
  const tenth = Math.floor((rest - whole) * 10 + 1e-6)
  return `${String(minutes).padStart(2, '0')}:${String(whole).padStart(2, '0')},${tenth}`
}

// Código de tiempo exacto mm:ss.mmm (el que se usa para pedirle cambios a Hermes: "en 01:23.500").
function fmtTimecode(seconds) {
  const total = Math.round(Math.max(0, Number(seconds) || 0) * 1000)
  const mm = Math.floor(total / 60000)
  const ss = Math.floor((total % 60000) / 1000)
  const ms = total % 1000
  return `${String(mm).padStart(2, '0')}:${String(ss).padStart(2, '0')}.${String(ms).padStart(3, '0')}`
}

// Acepta "83.5", "83,5", "1:23.5" o "01:23.500" y devuelve segundos (o null).
function parseTimecode(text) {
  const raw = String(text == null ? '' : text).trim().replace(',', '.')
  if (!raw) return null
  const parts = raw.split(':')
  if (parts.length > 3 || parts.some((part) => !/^\d+(\.\d+)?$/.test(part))) return null
  return parts.reduce((acc, part) => acc * 60 + Number(part), 0)
}

function fmtBytes(bytes) {
  const value = Number(bytes) || 0
  if (value >= 1024 * 1024) return `${(value / (1024 * 1024)).toFixed(1)} MB`
  if (value >= 1024) return `${Math.round(value / 1024)} KB`
  return `${value} B`
}

function relativeTime(ms) {
  if (!ms) return ''
  const diff = Math.max(0, Math.round((Date.now() - ms) / 1000))
  if (diff < 5) return 'ahora'
  if (diff < 60) return `hace ${diff} s`
  const minutes = Math.round(diff / 60)
  if (minutes < 60) return `hace ${minutes} min`
  return `hace ${Math.round(minutes / 60)} h`
}

function sceneDuration(scene) {
  if (!scene) return 0
  return Math.max(0, (Number(scene.out) || 0) - (Number(scene.in) || 0))
}

function captionOf(scene) {
  const first = scene && scene.text && scene.text[0]
  return (first && first.content) || ''
}

function sceneSpeed(scene) {
  const value = Number(scene && scene.speed)
  if (!Number.isFinite(value) || value <= 0) return 1
  return clamp(value, SCENE_SPEED.min, SCENE_SPEED.max)
}

// Lo que la escena dura en pantalla: la velocidad acorta o alarga el metraje
// sin tocar `in`/`out`, y los textos y el cruce se miden contra esto.
function visibleDuration(scene) {
  return round3(sceneDuration(scene) / sceneSpeed(scene))
}

// Primer item de `scene.text` leído sin inventarlo: así los controles enseñan
// los valores por defecto del servicio cuando la escena aún no tiene estilo.
function textItemOf(scene) {
  const item = scene && Array.isArray(scene.text) ? scene.text[0] : null
  return item && typeof item === 'object' ? item : null
}

// Editar estilo/animación completa `scene.text[0]` sin perder `content`, `at`,
// `until` ni `position`. Sin texto no hay item: el servicio rechaza `content`
// vacío, así que el llamante decide (aquí devolvemos null).
function ensureTextItem(scene) {
  const existing = textItemOf(scene)
  if (existing) return existing
  const content = captionOf(scene)
  if (!String(content).trim()) return null
  const item = { content, at: 0, until: round3(visibleDuration(scene)), position: 'bottom' }
  scene.text = [item, ...(Array.isArray(scene.text) ? scene.text.slice(1) : [])]
  return item
}

function hexOr(value, fallback) {
  return HEX_COLOR.test(String(value || '')) ? String(value) : fallback
}

// `scene.filters` solo existe si algo se aparta del neutro.
function cleanFilters(filters) {
  const next = {}
  FILTER_SLIDERS.forEach((slider) => {
    const value = Number(filters && filters[slider.key])
    if (Number.isFinite(value) && Math.abs(value - FILTER_DEFAULTS[slider.key]) > 1e-9) {
      next[slider.key] = round3(value)
    }
  })
  FILTER_FLAGS.forEach((flag) => {
    if (filters && filters[flag.key]) next[flag.key] = true
  })
  return next
}

// Al cambiar la velocidad, textos y cruce no pueden durar más que lo que se ve:
// el servicio rechaza `until` y fundidos por encima de la duración visible.
function fitSceneWindows(scenes, scene, index, previousDuration) {
  if (!scene) return
  const duration = visibleDuration(scene)
  ;(Array.isArray(scene.text) ? scene.text : []).forEach((item) => {
    if (!item || typeof item !== 'object') return
    if (!(Number(item.at) >= 0) || Number(item.at) >= duration - 0.05) item.at = 0
    // Un texto que cubría toda la escena la sigue cubriendo; el resto solo se
    // recorta si la nueva duración visible se queda corta.
    const coveredWhole = Number.isFinite(previousDuration) && Math.abs(Number(item.until) - previousDuration) < 0.05
    if (coveredWhole || !(Number(item.until) > Number(item.at)) || Number(item.until) > duration + 1e-9) {
      item.until = round3(duration)
    }
  })
  if (!scene.transition || scene.transition === 'none') return
  const prev = (scenes || [])[index - 1]
  const limit = round3(
    Math.max(0, Math.min(TRANSITION_MAX_S, duration, prev ? visibleDuration(prev) : TRANSITION_MAX_S))
  )
  const parts = parseTransition(scene.transition)
  if (limit < TRANSITION_MIN_S) scene.transition = 'none'
  else if (parts.seconds > limit + 1e-9) scene.transition = transitionValue(parts.style, limit)
}

const styleField = (key, label, input) =>
  h('label', { key, className: 've-tex__f' }, h('span', { className: 've-tex__k' }, label), input)

// Números cortos para los sliders nuevos; es-ES usa coma decimal.
const fmtNum = (value, decimals = 2) => {
  const fixed = Number(value || 0).toFixed(decimals).replace(/\.?0+$/, '')
  return (fixed === '' ? '0' : fixed).replace('.', ',')
}

const fillPercent = (value, min, max) => {
  if (!(max > min)) return '0%'
  return `${clamp(((Number(value) - min) / (max - min)) * 100, 0, 100)}%`
}

// `estilo-duracion` ⇄ { style, seconds }. Cualquier valor raro (o `none`) cae
// en el estilo "sin transición" sin romper el select.
function parseTransition(value) {
  const raw = String(value == null ? '' : value).trim()
  if (!raw || raw === 'none') return { style: 'none', seconds: TRANSITION_DEFAULT_S }
  const match = /^(.*)-([0-9]+(?:\.[0-9]+)?)$/.exec(raw)
  if (!match) return { style: raw, seconds: TRANSITION_DEFAULT_S }
  const seconds = Number(match[2])
  return {
    style: match[1],
    seconds: Number.isFinite(seconds) ? clamp(seconds, TRANSITION_MIN_S, TRANSITION_MAX_S) : TRANSITION_DEFAULT_S
  }
}

function transitionValue(style, seconds) {
  if (!style || style === 'none') return 'none'
  const safe = clamp(Number(seconds) || TRANSITION_DEFAULT_S, TRANSITION_MIN_S, TRANSITION_MAX_S)
  return `${style}-${round3(safe)}`
}

function transitionLabel(style) {
  const found = TRANSITION_STYLES.find((item) => item.id === style)
  return found ? found.label : style
}

// es-ES: decimal con coma para los textos de segundos.
const fmtSec = (value) => String(round3(Number(value) || 0)).replace('.', ',')

// El servicio rechaza un fundido más largo que la escena **o que la anterior**
// (`transition is longer than the previous scene`), así que el techo real del
// control es el mínimo de los tres.
function maxFadeFor(scenes, index) {
  const list = scenes || []
  const scene = list[index]
  if (!scene) return 0
  const prev = list[index - 1]
  const limit = Math.min(TRANSITION_MAX_S, visibleDuration(scene), prev ? visibleDuration(prev) : TRANSITION_MAX_S)
  return round3(Math.max(0, limit))
}

// Reajusta la transición de una escena cuando cambian sus bordes: nunca deja
// el documento en un estado que el PUT rechazaría.
function fitTransition(scenes, scene) {
  if (!scene || !scene.transition || scene.transition === 'none') return
  const index = scenes.indexOf(scene)
  const limit = maxFadeFor(scenes, index)
  const parts = parseTransition(scene.transition)
  if (limit < TRANSITION_MIN_S) {
    scene.transition = 'none'
    return
  }
  if (parts.seconds > limit + 1e-9) scene.transition = transitionValue(parts.style, limit)
}

function totalOf(doc) {
  if (!doc) return 0
  return (doc.scenes || []).reduce((sum, scene) => sum + sceneDuration(scene), 0)
}

function timeline(doc) {
  let at = 0
  return (doc && doc.scenes ? doc.scenes : []).map((scene) => {
    const dur = sceneDuration(scene)
    const item = { id: scene.id, start: at, duration: dur, scene }
    at += dur
    return item
  })
}

function sceneAt(doc, time) {
  const rows = timeline(doc)
  if (!rows.length) return { index: -1, local: 0, row: null }
  const clamped = clamp(time, 0, totalOf(doc))
  for (let index = 0; index < rows.length; index += 1) {
    const row = rows[index]
    if (clamped < row.start + row.duration - 1e-6 || index === rows.length - 1) {
      return { index, local: clamp(clamped - row.start, 0, row.duration), row }
    }
  }
  return { index: rows.length - 1, local: 0, row: rows[rows.length - 1] }
}

function stageIndex(stage) {
  for (let index = 0; index < STAGES.length; index += 1) {
    if (STAGES[index].from.includes(stage)) return index
  }
  return stage === 'failed' ? -1 : 0
}

// ---- merge:start
// ---------------------------------------------------------------- fusión
// Une tus cambios a mano con los que llegaron del chat (misma revisión base):
// por id de escena/sonido/medio; en la misma escena gana lo que TÚ cambiaste y
// se conserva lo que cambió el chat en el resto de campos. Nada se pierde en silencio.
const sameJson = (a, b) => JSON.stringify(a === undefined ? null : a) === JSON.stringify(b === undefined ? null : b)

function mergeById(base, mine, theirs) {
  const b = new Map((base || []).map((x) => [x.id, x]))
  const m = new Map((mine || []).map((x) => [x.id, x]))
  const t = new Map((theirs || []).map((x) => [x.id, x]))
  const orderBase = (base || []).map((x) => x.id)
  const orderMine = (mine || []).map((x) => x.id)
  const orderTheirs = (theirs || []).map((x) => x.id)
  const mineReordered = !sameJson(orderMine.filter((id) => b.has(id)), orderBase.filter((id) => m.has(id)))
  const first = mineReordered ? orderMine : orderTheirs
  const secondSide = mineReordered ? t : m
  const order = first.slice()
  const other = mineReordered ? orderTheirs : orderMine
  for (const id of other) {
    if (!order.includes(id) && !b.has(id)) order.push(id) // lo añadió el otro lado
  }
  const out = []
  for (const id of order) {
    const mi = m.get(id)
    const th = t.get(id)
    const ba = b.get(id)
    if (!th && ba) continue // el chat la borró
    if (!mi && ba) continue // yo la borré
    if (!th) { out.push(mi); continue }
    if (!mi) { out.push(th); continue }
    if (!ba) { out.push(mi); continue }
    const mineChanged = !sameJson(mi, ba)
    const theirsChanged = !sameJson(th, ba)
    if (!mineChanged) { out.push(th); continue }
    if (!theirsChanged) { out.push(mi); continue }
    const merged = { ...th }
    for (const key of Object.keys(mi)) if (!sameJson(mi[key], ba[key])) merged[key] = mi[key]
    out.push(merged)
  }
  void secondSide
  return out
}

function mergeDocs(base, mine, theirs) {
  const out = JSON.parse(JSON.stringify(theirs))
  const skip = new Set(['scenes', 'assets', 'audioEvents', 'revision', 'baseRevision', 'updatedAt', 'createdAt', 'projectId'])
  for (const key of Object.keys(mine)) {
    if (skip.has(key)) continue
    if (!sameJson(mine[key], base[key])) out[key] = mine[key]
  }
  for (const key of Object.keys(base)) {
    if (skip.has(key)) continue
    if (!(key in mine) && sameJson(theirs[key], base[key])) delete out[key]
  }
  out.scenes = mergeById(base.scenes, mine.scenes, theirs.scenes)
  out.assets = mergeById(base.assets, mine.assets, theirs.assets)
  const events = mergeById(base.audioEvents, mine.audioEvents, theirs.audioEvents)
  if (events.length) out.audioEvents = events
  else delete out.audioEvents
  return out
}
// ---- merge:end

function uid(prefix) {
  const random = Math.random().toString(36).slice(2, 10)
  return `${prefix}_${random}`
}

// --------------------------------------------------------------------------- #
// API
// --------------------------------------------------------------------------- #

class Offline extends Error {}

// Un atom de solo lectura para cuando la app no expone ese dato: useValue exige
// get() y subscribe(), y así los hooks se llaman siempre en el mismo orden.
const staticAtom = (value) => ({ get: () => value, subscribe: () => () => {} })
const stateAtom = (name, fallback) =>
  (host && host.state && host.state[name]) || staticAtom(fallback)

function serviceToken(ctx) {
  const fromWindow = typeof window !== 'undefined' && window.__VE_TOKEN__ ? window.__VE_TOKEN__ : ''
  const fromStorage =
    ctx && ctx.storage && typeof ctx.storage.get === 'function' ? ctx.storage.get('service.token') : ''
  const embedded = SERVICE_TOKEN.startsWith('__VE_') ? '' : SERVICE_TOKEN
  return String(fromWindow || fromStorage || embedded || '')
}

async function request(ctx, path, { method = 'GET', body, timeout = 30000 } = {}) {
  const base = serviceBase(ctx)
  const token = serviceToken(ctx)
  const headers = {}
  if (body !== undefined) headers['Content-Type'] = 'application/json'
  if (token) headers['X-VE-Token'] = token
  const controller = new AbortController()
  const timer = setTimeout(() => controller.abort(), timeout)
  let response
  try {
    response = await fetch(base.replace(/\/+$/, '') + path, {
      method,
      headers,
      body: body === undefined ? undefined : JSON.stringify(body),
      signal: controller.signal
    })
  } catch (error) {
    throw new Offline(error && error.message ? error.message : 'sin conexión')
  } finally {
    clearTimeout(timer)
  }
  let payload = null
  const text = await response.text()
  if (text) {
    try {
      payload = JSON.parse(text)
    } catch (error) {
      payload = { error: text.slice(0, 400) }
    }
  }
  if (!response.ok) {
    const authHint =
      response.status === 401 || response.status === 403
        ? token
          ? 'El servicio no acepta el token de este editor. Ejecuta activar-editor.cmd para volver a emparejarlos.'
          : 'Este editor no tiene el token del servicio. Ejecuta activar-editor.cmd (o instalar.py) y recarga el plugin.'
        : null
    const failure = new Error(authHint || (payload && (payload.error || (payload.errors || []).join(' · '))) || `HTTP ${response.status}`)
    failure.status = response.status
    failure.payload = payload
    throw failure
  }
  return payload || {}
}

function serviceBase(ctx) {
  const override =
    typeof window !== 'undefined' && window.__VE_SERVICE__
      ? window.__VE_SERVICE__
      : ctx && ctx.storage && typeof ctx.storage.get === 'function' && ctx.storage.get('service.url')
  return String(override || DEFAULT_SERVICE).replace(/\/+$/, '')
}

function mediaUrl(ctx, projectId, assetId) {
  return `${serviceBase(ctx)}/media/${projectId}/${assetId}`
}

// --------------------------------------------------------------------------- #
// apertura/cierre del pane (ui.open)
// --------------------------------------------------------------------------- #

const STORAGE_OPEN = 'ui.open'
const PANE_ATTR = 'data-ve-pane'

function readOpen(ctx, fallback = true) {
  try {
    const saved = ctx && ctx.storage && typeof ctx.storage.get === 'function' ? ctx.storage.get(STORAGE_OPEN) : undefined
    return typeof saved === 'boolean' ? saved : fallback
  } catch (error) {
    return fallback
  }
}

// Pausa y suelta los <video> del pane: al cerrar no queda decodificación viva.
function releaseVideos(root) {
  const scope = root && root.querySelectorAll ? root : typeof document !== 'undefined' ? document : null
  if (!scope || !scope.querySelectorAll) return 0
  const nodes = scope.querySelectorAll(`[${PANE_ATTR}] video`)
  nodes.forEach((video) => {
    try {
      video.pause()
      video.removeAttribute('src')
      video.load()
    } catch (error) {
      /* el nodo ya estaba desmontado */
    }
  })
  return nodes.length
}

// `TITLEBAR_AREAS.right` pinta el `render` de la contribución, no su `data`
// (comprobado en apps/desktop/src/contrib/react/slot.tsx). Por eso el tool se
// dibuja aquí en forma de botón y se entera del estado por suscripción: el
// `active` queda vivo sin volver a registrar nada.
function TitlebarToggle({ getOpen, subscribe, onToggle }) {
  ensureStyles()
  const [open, setOpen] = useState(getOpen)

  useEffect(() => {
    setOpen(getOpen())
    return subscribe(setOpen)
  }, [])

  const label = open ? 'Cerrar editor de vídeo' : 'Abrir editor de vídeo'
  return h(
    'button',
    {
      type: 'button',
      className: 've-tb',
      'aria-pressed': open ? 'true' : 'false',
      'aria-label': `${label} (Ctrl+Shift+E)`,
      title: `${label} · Ctrl+Shift+E`,
      'data-ve-titlebar': 'toggle',
      onClick: onToggle
    },
    h(Icon, { name: 'film', size: 'sm' }),
    h('span', null, 'Vídeo')
  )
}

// --------------------------------------------------------------------------- #
// estilos (prefijo ve-, solo tokens)
// --------------------------------------------------------------------------- #

const STYLES = `
.ve-root{
  --ve-fg:var(--ui-text-primary,var(--foreground));
  --ve-ink2:color-mix(in oklab,var(--ve-fg) 80%,transparent);
  --ve-ink3:color-mix(in oklab,var(--ve-fg) 68%,transparent);
  --ve-accent:var(--ui-accent,var(--accent));
  --ve-line:var(--ui-stroke-tertiary,var(--border));
  --ve-surface:var(--ui-bg-editor,var(--card));
  --ve-soft:color-mix(in oklab,var(--ve-fg) 6%,transparent);
  --ve-card:var(--ui-bg-quaternary,var(--card));
  position:relative;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:44px minmax(0,1fr) 44px;
  height:100%;width:100%;min-height:0;overflow:hidden;contain:paint;
  color:var(--ve-fg);background:var(--ve-surface);
  font-size:12px;line-height:1.45;font-family:inherit;-webkit-font-smoothing:antialiased;
}
.ve-root *,.ve-root *::before,.ve-root *::after{box-sizing:border-box}
.ve-root :where(h1,h2,h3,p){margin:0}
.ve-root :where(button){font:inherit;color:inherit}
.ve-i{width:14px;height:14px;flex:none;stroke:currentColor;fill:none;stroke-width:1.6;stroke-linecap:round;stroke-linejoin:round}
.ve-i--sm{width:12px;height:12px}
.ve-hdr{display:flex;align-items:center;gap:8px;min-width:0;padding:0 10px;border-bottom:1px solid var(--ve-line);overflow:hidden}
.ve-plate{width:26px;height:26px;border-radius:4px;display:grid;place-items:center;flex:none;color:var(--ve-accent);background:color-mix(in oklab,var(--ve-accent) 13%,transparent)}
.ve-title{font-size:12.5px;font-weight:600;white-space:nowrap;min-width:0;overflow:hidden;text-overflow:ellipsis}
.ve-sep{width:1px;height:18px;background:var(--ve-line);flex:none;margin:0 2px}
.ve-chip{display:inline-flex;align-items:center;gap:6px;height:28px;padding:0 7px;max-width:230px;border:1px solid var(--ve-line);border-radius:3px;background:transparent;font-size:11.5px;font-weight:500;cursor:pointer;white-space:nowrap;overflow:hidden}
.ve-chip:hover{background:var(--ve-soft)}
.ve-chip__name{overflow:hidden;text-overflow:ellipsis}
.ve-chip--ghost{border-color:transparent;color:var(--ve-ink2);font-weight:400;cursor:default;max-width:220px}
.ve-chip--ghost:hover{background:transparent}
.ve-chat{cursor:pointer;gap:5px}
.ve-chat:hover{background:var(--ve-soft)}
.ve-chat__b{font-size:9.5px;letter-spacing:.04em;text-transform:uppercase;color:var(--ve-ink2)}
.ve-out{display:flex;flex-direction:column;gap:8px;margin-top:10px;padding-top:10px;border-top:1px solid var(--ve-line)}
.ve-out__p{display:block;padding:6px 8px;border:1px solid var(--ve-line);border-radius:3px;background:var(--ve-card);font-family:ui-monospace,SFMono-Regular,Consolas,monospace;font-size:10.5px;color:var(--ve-ink2);word-break:break-all}
.ve-out__a{display:flex;gap:6px;flex-wrap:wrap}
.ve-note{margin:0;font-size:10.5px;color:var(--ve-ink2)}
.ve-auto{display:inline-flex;align-items:center;gap:5px;font-size:10.5px;color:var(--ve-ink2);white-space:nowrap}
.ve-spacer{flex:1 1 auto;min-width:0}
.ve-dot{width:6px;height:6px;border-radius:50%;flex:none;background:var(--ve-ink3)}
.ve-dot--good{background:var(--ve-accent)}
.ve-dot--warn{background:var(--ve-fg);box-shadow:0 0 0 2px var(--ve-soft)}
.ve-dot--bad{background:var(--ve-fg)}
.ve-btn{display:inline-flex;align-items:center;justify-content:center;gap:5px;height:32px;padding:0 10px;flex:none;border:1px solid transparent;border-radius:3px;background:transparent;font-size:11.5px;font-weight:500;white-space:nowrap;cursor:pointer;transition:background-color .1s linear,color .1s linear,border-color .1s linear}
.ve-btn:focus-visible{outline:2px solid var(--ve-accent);outline-offset:2px}
.ve-btn--primary{background:var(--dt-primary-solid,color-mix(in oklab,var(--ve-accent) 10%,var(--ve-surface)));color:var(--dt-primary-foreground,color-mix(in oklab,var(--ve-accent) 70%,var(--ve-fg)));border-color:color-mix(in oklab,var(--ve-accent) 45%,var(--ve-line));font-weight:600}
.ve-btn--primary:hover{background:var(--dt-primary-solid,color-mix(in oklab,var(--ve-accent) 17%,var(--ve-surface)))}
.ve-btn--outline{border-color:var(--ve-line)}
.ve-btn--outline:hover{background:var(--ve-soft)}
.ve-btn--ghost{color:var(--ve-ink2)}
.ve-btn--ghost:hover{background:color-mix(in oklab,var(--ve-fg) 7%,transparent);color:var(--ve-fg)}
.ve-btn--text{color:var(--ve-ink2);padding:0 4px;text-decoration:underline;text-underline-offset:3px;text-decoration-color:color-mix(in oklab,var(--ve-fg) 25%,transparent)}
.ve-btn--text:hover{color:var(--ve-fg)}
.ve-btn--icon{width:32px;padding:0}
.ve-btn--block{width:100%}
.ve-btn[disabled]{opacity:.45;cursor:default;pointer-events:none}
.ve-badge{display:inline-flex;align-items:center;gap:4px;height:18px;padding:0 6px;border-radius:3px;flex:none;font-size:10px;font-weight:600;white-space:nowrap;background:var(--ve-soft);color:var(--ve-ink2)}
.ve-badge--outline{background:transparent;border:1px solid var(--ve-line)}
.ve-badge--accent{background:color-mix(in oklab,var(--ve-accent) 14%,transparent);color:color-mix(in oklab,var(--ve-accent) 78%,var(--ve-fg))}
.ve-badge--warn{background:color-mix(in oklab,var(--ve-fg) 12%,transparent);color:var(--ve-fg)}
.ve-body{position:relative;display:grid;grid-template-columns:minmax(0,1fr) 292px;min-height:0;min-width:0;overflow:hidden;contain:paint}
.ve-left{display:flex;flex-direction:column;min-width:0;min-height:0;border-right:1px solid var(--ve-line)}
.ve-stage{flex:1 1 auto;min-height:0;display:flex;flex-direction:column;padding:8px 12px 10px;background:color-mix(in oklab,var(--ve-fg) 3%,transparent);position:relative;gap:6px}
.ve-stage__bar{display:flex;align-items:center;gap:6px;flex:none;min-height:20px}
.ve-stage__sp{flex:1}
.ve-stage__count{font-size:10.5px;font-variant-numeric:tabular-nums;color:var(--ve-ink2)}
.ve-stage__canvas{flex:1 1 auto;min-height:0;display:grid;place-items:center}
.ve-frame{position:relative;max-height:100%;max-width:100%;overflow:hidden;border:1px solid var(--ve-line);border-radius:2px;background:color-mix(in oklab,var(--ve-fg) 5%,transparent)}
.ve-frame video{display:block;width:100%;height:100%;object-fit:contain;background:color-mix(in oklab,var(--ve-fg) 8%,transparent)}
.ve-frame img{display:block;width:100%;height:100%;object-fit:contain;background:color-mix(in oklab,var(--ve-fg) 8%,transparent)}
.ve-frame__meta{position:absolute;top:7px;left:7px;display:flex;gap:5px;align-items:center;z-index:2}
.ve-frame__meta--r{left:auto;right:7px}
.ve-cap{position:absolute;left:8%;right:8%;bottom:8%;padding:6px 9px;border-radius:3px;background:color-mix(in oklab,var(--ve-surface) 80%,transparent);border:1px solid var(--ve-line);color:var(--ve-fg);font-size:12px;font-weight:500;line-height:1.35;text-align:center;backdrop-filter:blur(3px)}
.ve-guides{position:absolute;inset:6%;border:1px dashed color-mix(in oklab,var(--ve-fg) 30%,transparent);pointer-events:none}
.ve-transport{height:34px;flex:none;display:flex;align-items:center;gap:4px;padding:0 8px;border-top:1px solid var(--ve-line)}
.ve-tc{font-family:ui-monospace,SFMono-Regular,Menlo,Consolas,monospace;font-size:10.5px;font-variant-numeric:tabular-nums;color:var(--ve-ink2);white-space:nowrap}
.ve-tc b{color:var(--ve-fg);font-weight:600}
.ve-scrub{flex:1 1 auto;min-width:60px;display:flex;align-items:center}
.ve-root input[type="range"]{-webkit-appearance:none;appearance:none;width:100%;height:32px;margin:0;background:transparent;cursor:pointer;accent-color:var(--ve-accent)}
.ve-root input[type="range"]:focus-visible{outline:2px solid var(--ve-accent);outline-offset:1px;border-radius:2px}
.ve-root input[type="range"]::-webkit-slider-runnable-track{height:3px;border-radius:2px;background:linear-gradient(to right,var(--ve-accent) 0 var(--ve-p,0%),color-mix(in oklab,var(--ve-fg) 16%,transparent) var(--ve-p,0%) 100%)}
.ve-root input[type="range"]::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:11px;height:11px;border-radius:50%;margin-top:-4px;background:var(--ve-accent);border:2px solid var(--ve-surface);box-shadow:0 0 0 1px color-mix(in oklab,var(--ve-accent) 55%,transparent)}
.ve-root input[type="range"].ve-range--vol{width:64px;flex:none}
.ve-tl{height:118px;flex:none;display:flex;flex-direction:column;border-top:1px solid var(--ve-line);min-height:0;background:transparent}
.ve-tl__ruler{height:20px;margin-left:46px;margin-right:10px;position:relative;flex:none;border-bottom:1px solid var(--ve-line);background-image:repeating-linear-gradient(90deg,color-mix(in oklab,var(--ve-fg) 18%,transparent) 0 1px,transparent 1px 33.5px)}
.ve-tl__ruler span{position:absolute;top:2px;font-size:9px;line-height:1;color:var(--ve-ink2);font-variant-numeric:tabular-nums}
.ve-tl__lane{position:relative;display:flex;min-height:0;flex:1}
.ve-tl__gutter{width:46px;flex:none;display:flex;flex-direction:column;font-size:9px;font-weight:600;letter-spacing:.04em;color:var(--ve-ink2)}
.ve-tl__gutter span{height:46px;display:flex;align-items:center;padding-left:10px}
.ve-tl__gutter span+span{height:22px}
.ve-tl__tracks{position:relative;flex:1;min-width:0;padding-right:10px}
.ve-tl__row{height:46px;display:flex;gap:2px;align-items:stretch}
.ve-clip{position:relative;min-width:0;border:1px solid var(--ve-line);border-radius:2px;background:color-mix(in oklab,var(--ve-fg) 4%,transparent);display:flex;flex-direction:column;justify-content:space-between;padding:4px 6px;overflow:hidden;cursor:pointer;text-align:left;background-image:repeating-linear-gradient(115deg,color-mix(in oklab,var(--ve-fg) 4%,transparent) 0 6px,transparent 6px 13px)}
.ve-clip:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px}
.ve-clip__n{font-size:9.5px;font-weight:600;letter-spacing:.04em;color:var(--ve-ink2)}
.ve-clip__t{font-size:10.5px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.1}
.ve-clip__d{font-size:9px;color:var(--ve-ink2);font-variant-numeric:tabular-nums}
.ve-clip--sel{border-color:var(--ve-accent);border-width:2px;padding:3px 5px;background-color:color-mix(in oklab,var(--ve-accent) 10%,transparent)}
.ve-trim{position:absolute;top:0;bottom:0;width:3px;background:var(--ve-accent);cursor:ew-resize}
.ve-trim::after{content:"";position:absolute;top:50%;left:50%;transform:translate(-50%,-50%);width:7px;height:16px;border-radius:1px;background:var(--ve-accent);opacity:.35}
.ve-trim--l{left:0}
.ve-trim--r{right:0}
.ve-playhead{position:absolute;top:0;bottom:0;left:var(--ve-ph,0%);width:1px;background:var(--ve-accent);pointer-events:none;z-index:2}
.ve-playhead::before{content:"";position:absolute;top:0;left:-4px;width:9px;height:8px;background:var(--ve-accent);clip-path:polygon(0 0,100% 0,50% 100%)}
.ve-audio{height:22px;margin-top:2px;border:1px solid var(--ve-line);border-radius:2px;background:color-mix(in oklab,var(--ve-fg) 3%,transparent);display:flex;align-items:center;padding:0 6px;gap:6px}
.ve-audio small{font-size:9px;color:var(--ve-ink2);white-space:nowrap}
.ve-wave{flex:1;height:12px;color:color-mix(in oklab,var(--ve-accent) 65%,transparent);overflow:hidden;display:flex;align-items:center}
.ve-wave>i{display:block;height:8px;border-radius:1px;background:currentColor;min-width:1px}
.ve-rail{display:flex;flex-direction:column;min-height:0;min-width:0}
.ve-rail__sec{padding:6px 10px;border-bottom:1px solid var(--ve-line);min-width:0}
.ve-rail__sec:last-child{border-bottom:0}
.ve-rail__h{display:flex;align-items:center;gap:6px;height:22px;margin-bottom:5px}
.ve-rail__t{font-size:9.5px;font-weight:700;letter-spacing:.08em;text-transform:uppercase;color:var(--ve-ink2);white-space:nowrap}
.ve-scenes{display:flex;flex-direction:column;gap:2px;max-height:152px;overflow:auto;margin:0 -4px;padding:0 4px}
.ve-scene-row{display:grid;grid-template-columns:minmax(0,1fr) 32px 32px;align-items:center;gap:1px}
.ve-scene{display:grid;grid-template-columns:12px 16px 40px minmax(0,1fr);align-items:center;gap:5px;height:36px;padding:0 2px;border-radius:3px;border:1px solid transparent;background:transparent;text-align:left;cursor:pointer;width:100%}
.ve-scene:hover{background:color-mix(in oklab,var(--ve-fg) 5%,transparent)}
.ve-scene:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px}
.ve-scene[aria-current="true"]{background:color-mix(in oklab,var(--ve-accent) 9%,transparent);border-color:color-mix(in oklab,var(--ve-accent) 38%,transparent)}
.ve-scene__n{font-size:9.5px;color:var(--ve-ink2);font-variant-numeric:tabular-nums}
.ve-scene__grip{color:var(--ve-ink2);opacity:.5;display:grid;place-items:center}
.ve-thumb{width:40px;height:23px;border-radius:2px;border:1px solid var(--ve-line);background:var(--ve-soft)}
.ve-scene__m{min-width:0}
.ve-scene__name{display:block;font-size:11.5px;font-weight:500;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.25}
.ve-scene__dur{display:block;font-size:9px;color:var(--ve-ink2);font-variant-numeric:tabular-nums}
.ve-mv{width:32px;height:32px;display:grid;place-items:center;border-radius:3px;border:0;background:transparent;color:var(--ve-ink2);cursor:pointer}
.ve-mv:hover{background:color-mix(in oklab,var(--ve-fg) 8%,transparent);color:var(--ve-fg)}
.ve-mv:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-1px}
.ve-mv[disabled]{opacity:.35;cursor:default}
.ve-props{display:flex;flex-direction:column;gap:5px;min-width:0}
.ve-f{display:flex;flex-direction:column;gap:3px;min-width:0}
.ve-f__l{font-size:10px;font-weight:600;display:flex;align-items:center;gap:5px}
.ve-f__h{font-size:9.5px;color:var(--ve-ink2);line-height:1.35}
.ve-f__err{font-size:9.5px;color:var(--ve-fg);font-weight:600}
.ve-f__row{display:grid;grid-template-columns:1fr 1fr;gap:6px}
.ve-mus__empty{display:flex;flex-direction:column;gap:6px;align-items:flex-start}
.ve-mus__chks{display:flex;flex-direction:column;gap:2px}
.ve-mus__chk{display:flex;align-items:center;gap:7px;min-height:32px;font-size:11px;cursor:pointer;color:var(--ve-fg);border-radius:3px}
.ve-mus__chk input{accent-color:var(--ve-accent);margin:0;flex:none;width:14px;height:14px}
.ve-mus__chk span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.ve-mus__chk:hover{background:var(--ve-soft)}
.ve-mus__chk:focus-within{outline:2px solid var(--ve-accent);outline-offset:-1px}
.ve-input,.ve-textarea{width:100%;min-width:0;border:1px solid var(--ve-line);border-radius:3px;background:transparent;color:var(--ve-fg);font:inherit;font-size:11.5px;padding:0 7px;height:30px}
.ve-textarea{height:44px;padding:5px 7px;resize:none;line-height:1.35}
.ve-input:focus-visible,.ve-textarea:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-1px}
.ve-input[aria-invalid="true"]{border-color:var(--ve-fg);border-width:2px}
.ve-counter{align-self:flex-end;font-size:9px;color:var(--ve-ink2);font-variant-numeric:tabular-nums}
.ve-volrow{display:flex;align-items:center;gap:8px}
.ve-volrow input[type="range"]{width:auto;flex:1;min-width:0}
.ve-goto{width:62px;height:22px;font-size:11px;background:transparent;border:1px solid var(--ve-line);border-radius:3px;color:var(--ve-fg);padding:0 6px}
.ve-tl__row--audio{position:relative}
.ve-evs{position:absolute;inset:0;pointer-events:none}
.ve-ev{position:absolute;top:1px;bottom:1px;width:9px;margin-left:-4px;padding:0;border:0;border-radius:2px;background:var(--ve-accent);opacity:.85;pointer-events:auto;cursor:pointer;font-size:8px;color:#000;line-height:1}
.ve-ev:hover{opacity:1}
.ve-sfx__row{border-top:1px solid var(--ve-line);padding-top:8px;margin-top:6px}
.ve-out__v{width:100%;max-height:260px;background:#000;border-radius:4px;margin:6px 0}
.ve-volval{font-size:10.5px;font-variant-numeric:tabular-nums;min-width:34px;text-align:right}
.ve-seg{display:inline-grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:2px;padding:2px;border-radius:4px;background:color-mix(in oklab,var(--ve-fg) 7%,transparent);height:30px;width:100%}
.ve-seg button{display:flex;align-items:center;justify-content:center;border-radius:3px;font-size:10.5px;font-weight:600;color:var(--ve-ink2);border:0;background:transparent;cursor:pointer}
.ve-seg button[aria-pressed="true"]{background:var(--ve-surface);color:var(--ve-fg);box-shadow:0 1px 2px color-mix(in oklab,var(--ve-fg) 18%,transparent)}
.ve-seg button:focus-visible{outline:2px solid var(--ve-accent);outline-offset:1px}
.ve-select{display:flex;align-items:center;justify-content:space-between;gap:6px;text-align:left;cursor:pointer;width:100%;border:1px solid var(--ve-line);border-radius:3px;background:transparent;font-size:11.5px;height:30px;padding:0 7px}
.ve-select:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-1px}
.ve-select span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
select.ve-select{display:block;padding:0 6px;-webkit-appearance:auto;appearance:auto;line-height:1.2}
.ve-inout{display:flex;align-items:center;gap:5px}
.ve-tcout{flex:1;height:30px;display:flex;align-items:center;gap:4px;border:1px solid var(--ve-line);border-radius:3px;padding:0 6px;font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10.5px;color:var(--ve-fg)}
.ve-tcout input{border:0;background:transparent;color:inherit;font:inherit;width:100%;min-width:0;padding:0}
.ve-tcout input:focus-visible{outline:2px solid var(--ve-accent);outline-offset:1px;border-radius:2px}
.ve-tex{display:grid;grid-template-columns:1fr 1fr;gap:5px}
.ve-tex__f{display:flex;flex-direction:column;gap:2px;min-width:0}
.ve-tex__k{font-size:9px;letter-spacing:.06em;text-transform:uppercase;color:var(--ve-ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ve-tex__in{height:32px;min-width:0;width:100%;border:1px solid var(--ve-line);border-radius:3px;background:transparent;color:var(--ve-fg);font-size:11.5px;padding:0 6px}
.ve-tex__in:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-1px}
.ve-tex__in[type="color"]{padding:3px;cursor:pointer}
.ve-tex__in:disabled{opacity:.5;cursor:not-allowed}
.ve-tex select.ve-tex__in{padding:0 4px}
.ve-mus__chk--off{opacity:.55;cursor:not-allowed}
.ve-mus__chk--off:hover{background:transparent}
.ve-ftr{display:flex;align-items:center;gap:8px;padding:0 10px;border-top:1px solid var(--ve-line)}
.ve-ftr__hint{font-size:9.5px;color:var(--ve-ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ve-center{flex:1;display:grid;place-items:center;padding:18px;min-height:0}
.ve-es{max-width:430px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:6px}
.ve-es__icon{width:34px;height:34px;border-radius:50%;display:grid;place-items:center;color:var(--ve-ink2);background:var(--ve-soft);margin-bottom:2px}
.ve-es__icon--err{color:var(--ve-surface);background:var(--ve-fg)}
.ve-es__t{font-size:13px;font-weight:600}
.ve-es__b{font-size:11.5px;color:var(--ve-ink2);line-height:1.5;max-width:380px}
.ve-es__actions{display:flex;gap:6px;margin-top:6px;flex-wrap:wrap;justify-content:center}
.ve-drop{width:100%;max-width:430px;height:190px;border:1px dashed color-mix(in oklab,var(--ve-fg) 26%,transparent);border-radius:4px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:7px;text-align:center;padding:14px}
.ve-drop--active{border-color:var(--ve-accent);border-style:solid;background:color-mix(in oklab,var(--ve-accent) 7%,transparent)}
.ve-skel{background:color-mix(in oklab,var(--ve-fg) 9%,transparent);border-radius:3px;animation:ve-pulse 1.7s ease-in-out infinite}
@keyframes ve-pulse{0%,100%{opacity:.55}50%{opacity:1}}
.ve-loadrow{display:flex;align-items:center;gap:7px;font-size:11px;color:var(--ve-ink2)}
.ve-spin{width:12px;height:12px;border-radius:50%;border:1.5px solid color-mix(in oklab,var(--ve-fg) 18%,transparent);border-top-color:var(--ve-accent);animation:ve-spin .8s linear infinite}
@keyframes ve-spin{to{transform:rotate(360deg)}}
.ve-scrim{position:absolute;inset:0;background:color-mix(in oklab,var(--ve-surface) 58%,transparent);backdrop-filter:blur(1.5px);z-index:10}
.ve-dialog{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(430px,92%);max-height:86%;overflow:auto;background:var(--ve-surface);border:1px solid var(--ve-line);border-radius:6px;padding:16px;z-index:11;display:flex;flex-direction:column;gap:10px;box-shadow:0 24px 60px -22px color-mix(in oklab,var(--ve-fg) 60%,transparent)}
.ve-dialog__t{font-size:13px;font-weight:600}
.ve-dialog__b{font-size:11.5px;color:var(--ve-ink2);line-height:1.5}
.ve-dialog__f{display:flex;gap:6px;justify-content:flex-end;flex-wrap:wrap}
.ve-progress{height:4px;border-radius:2px;background:color-mix(in oklab,var(--ve-fg) 12%,transparent);overflow:hidden}
.ve-progress>i{display:block;height:100%;background:var(--ve-accent);transition:width .12s linear}
.ve-stages{display:flex;flex-direction:column;gap:4px;font-size:11px}
.ve-stages li{display:flex;align-items:center;gap:6px;list-style:none;color:var(--ve-ink2)}
.ve-stages li[data-state="active"]{color:var(--ve-fg);font-weight:600}
.ve-stages li[data-state="done"]{color:var(--ve-fg)}
.ve-list{display:flex;flex-direction:column;gap:2px;max-height:230px;overflow:auto;border:1px solid var(--ve-line);border-radius:4px;padding:4px}
.ve-file{display:flex;align-items:center;gap:7px;height:30px;padding:0 6px;border-radius:3px;font-size:11px;cursor:pointer;text-align:left;border:0;background:transparent;width:100%}
.ve-file:hover{background:var(--ve-soft)}
.ve-file input{accent-color:var(--ve-accent);margin:0}
.ve-file__n{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0}
.ve-file__s{font-size:9.5px;color:var(--ve-ink2);font-variant-numeric:tabular-nums}
.ve-menu{position:absolute;z-index:12;min-width:190px;background:var(--ve-surface);border:1px solid var(--ve-line);border-radius:4px;padding:4px;box-shadow:0 16px 40px -20px color-mix(in oklab,var(--ve-fg) 60%,transparent);display:flex;flex-direction:column;gap:1px}
.ve-menu button{display:flex;align-items:center;height:28px;padding:0 8px;border:0;background:transparent;border-radius:3px;font-size:11.5px;text-align:left;cursor:pointer;width:100%}
.ve-menu button:hover{background:var(--ve-soft)}
.ve-log{font-family:ui-monospace,SFMono-Regular,Menlo,monospace;font-size:10px;white-space:pre-wrap;word-break:break-all;max-height:200px;overflow:auto;border:1px solid var(--ve-line);border-radius:4px;padding:6px;color:var(--ve-ink2)}
.ve-stub{border-style:dashed}
.ve-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.ve-compact-hide{display:none}
@media (max-width:520px){
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
.ve-tip{position:absolute;right:10px;top:46px;z-index:13;max-width:240px;padding:6px 9px;border:1px solid var(--ve-line);border-radius:4px;background:var(--ve-card);color:var(--ve-fg);font-size:10.5px;line-height:1.4;box-shadow:0 12px 30px -18px color-mix(in oklab,var(--ve-fg) 60%,transparent)}
@media (prefers-reduced-motion:reduce){
  .ve-root *{transition:none!important;animation:none!important}
}
/* Botón de la barra de título (vive fuera de .ve-root: tokens con fallback). */
.ve-tb{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 8px;border-radius:7px;border:1px solid var(--ui-stroke-tertiary,var(--border));background:transparent;color:var(--ui-text-secondary,var(--foreground));font:inherit;font-size:11px;line-height:1;cursor:pointer;white-space:nowrap}
.ve-tb:hover{background:var(--ui-surface-2,rgba(127,127,127,.14));color:var(--ui-text-primary,var(--foreground))}
.ve-tb[aria-pressed="true"]{color:var(--ui-accent,var(--accent));border-color:color-mix(in oklab,var(--ui-accent,var(--accent)) 55%,transparent);background:color-mix(in oklab,var(--ui-accent,var(--accent)) 12%,transparent)}
.ve-tb:focus-visible{outline:2px solid var(--ui-accent,var(--accent));outline-offset:1px}
`

function ensureStyles() {
  if (typeof document === 'undefined') return
  if (document.getElementById('ve-pane-styles')) return
  const tag = document.createElement('style')
  tag.id = 've-pane-styles'
  tag.textContent = STYLES
  document.head.appendChild(tag)
}

// --------------------------------------------------------------------------- #
// iconos
// --------------------------------------------------------------------------- #

const PATHS = {
  copy: 'M9 9h11v11H9z M5 15V4h11',
  message: 'M4 5h16v11H9l-4 4z M8 9h8 M8 12h5',
  save: 'M5 4h11l3 3v13H5z M8 4v6h7V4 M8 14h8v6H8z',
  film: 'M4 4h16v16H4z M8 4v16 M16 4v16 M4 9h4 M4 15h4 M16 9h4 M16 15h4',
  play: 'M8 5l11 7-11 7z',
  pause: 'M9 5v14 M15 5v14',
  start: 'M6 5v14 M19 5l-9 7 9 7z',
  end: 'M18 5v14 M5 5l9 7-9 7z',
  prev: 'M15 5l-9 7 9 7z',
  next: 'M9 5l9 7-9 7z',
  scissors: 'M6 6l12 12 M18 6L6 18 M8 4a2 2 0 100 4 2 2 0 000-4z M8 16a2 2 0 100 4 2 2 0 000-4z',
  undo: 'M9 7L4 12l5 5 M4 12h10a5 5 0 010 10',
  redo: 'M15 7l5 5-5 5 M20 12H10a5 5 0 000 10',
  upload: 'M12 19V6 M7 11l5-5 5 5 M5 20h14',
  download: 'M12 5v13 M7 13l5 5 5-5 M5 4h14',
  more: 'M6 12h.01 M12 12h.01 M18 12h.01',
  close: 'M6 6l12 12 M18 6L6 18',
  check: 'M5 13l4 4 10-11',
  alert: 'M12 4l9 16H3z M12 10v4 M12 17h.01',
  up: 'M7 14l5-5 5 5',
  down: 'M7 10l5 5 5-5',
  grip: 'M9 6h.01 M15 6h.01 M9 12h.01 M15 12h.01 M9 18h.01 M15 18h.01',
  volume: 'M5 9v6h3l4 4V5L8 9z M17 9a4 4 0 010 6',
  panel: 'M4 5h16v14H4z M15 5v14',
  image: 'M4 5h16v14H4z M8 11l3 3 2-2 3 3'
}

function Icon({ name, size }) {
  const d = PATHS[name] || PATHS.film
  return h(
    'svg',
    {
      className: `ve-i${size === 'sm' ? ' ve-i--sm' : ''}`,
      viewBox: '0 0 24 24',
      'aria-hidden': 'true',
      focusable: 'false'
    },
    h('path', { d })
  )
}

// --------------------------------------------------------------------------- #
// piezas de UI
// --------------------------------------------------------------------------- #

function Btn({ variant = 'ghost', icon, label, onClick, disabled, title, ariaLabel, block, size }) {
  const kids = []
  if (icon) kids.push(h(Icon, { key: 'i', name: icon, size: size === 'sm' ? 'sm' : undefined }))
  if (label) kids.push(h('span', { key: 'l' }, label))
  return h(
    'button',
    {
      type: 'button',
      className: `ve-btn ve-btn--${variant}${!label ? ' ve-btn--icon' : ''}${block ? ' ve-btn--block' : ''}`,
      onClick,
      disabled: !!disabled,
      title: title || label || ariaLabel,
      'aria-label': ariaLabel || label || title || icon
    },
    kids.length === 1 ? kids[0] : kids
  )
}

const Badge = ({ tone, children, outline }) =>
  h('span', { className: `ve-badge${outline ? ' ve-badge--outline' : ''}${tone ? ` ve-badge--${tone}` : ''}` }, children)

const Dot = ({ tone }) => h('span', { className: `ve-dot${tone ? ` ve-dot--${tone}` : ''}`, 'aria-hidden': 'true' })

const Spinner = () => h('span', { className: 've-spin', 'aria-hidden': 'true' })

function EmptyState({ title, body, children }) {
  return h(
    'div',
    { className: 've-es' },
    h('div', { className: 've-es__icon' }, h(Icon, { name: 'film' })),
    h('p', { className: 've-es__t' }, title),
    body ? h('p', { className: 've-es__b' }, body) : null,
    children || null
  )
}

function ErrorState({ title, body, children }) {
  return h(
    'div',
    { className: 've-es' },
    h('div', { className: 've-es__icon ve-es__icon--err' }, h(Icon, { name: 'alert' })),
    h('p', { className: 've-es__t' }, title),
    body ? h('p', { className: 've-es__b' }, body) : null,
    children ? h('div', { className: 've-es__actions' }, children) : null
  )
}

function Dialog({ title, body, children, footer, onClose, describedBy }) {
  return h(
    'div',
    { className: 've-root', style: { position: 'absolute', inset: 0, display: 'block', background: 'transparent' } },
    h('div', { className: 've-scrim', 'aria-hidden': 'true' }),
    h(
      'div',
      { className: 've-dialog', role: 'dialog', 'aria-modal': 'true', 'aria-label': title, 'aria-describedby': describedBy },
      h('p', { className: 've-dialog__t' }, title),
      body ? h('p', { className: 've-dialog__b', id: describedBy }, body) : null,
      children || null,
      footer ? h('div', { className: 've-dialog__f' }, footer) : null
    )
  )
}

// --------------------------------------------------------------------------- #
// pane
// --------------------------------------------------------------------------- #

function VideoPane({ ctx, onClose }) {
  ensureStyles()

  const [phase, setPhase] = useState('boot') // boot | ready | offline | noProject | loading | error
  const [projects, setProjects] = useState([])
  const [doc, setDoc] = useState(null)
  const [media, setMedia] = useState([])
  const [status, setStatus] = useState('idle') // idle | saving | saved | failed
  const [savedAt, setSavedAt] = useState(null)
  const [dirty, setDirty] = useState(false)
  const [loadError, setLoadError] = useState(null)
  const [selId, setSelId] = useState(null)
  const [cursor, setCursor] = useState(0)
  const [playing, setPlaying] = useState(false)
  const [notice, setNotice] = useState('')
  const [chatMsg, setChatMsg] = useState('')
  const [dialog, setDialog] = useState(null)
  const [job, setJob] = useState(null)
  const [importState, setImportState] = useState(null)
  const [menu, setMenu] = useState(null)
  const [guides, setGuides] = useState(false)
  const [muted, setMuted] = useState(true)
  const [mediaRoot, setMediaRoot] = useState('')
  const [incCaptions, setIncCaptions] = useState(true)
  const [exportPreset, setExportPreset] = useState(PRESET)
  const [service, setService] = useState(null)
  const [railOpen, setRailOpen] = useState(false)
  const [libOpen, setLibOpen] = useState(false)
  const [picker, setPicker] = useState(null)
  const [modelTip, setModelTip] = useState(false)
  const [width, setWidth] = useState(900)
  const [undoDepth, setUndoDepth] = useState(0)
  const [redoDepth, setRedoDepth] = useState(0)

  const rootRef = useRef(null)
  const videoRef = useRef(null)
  const undoRef = useRef([])
  const redoRef = useRef([])
  const autoRef = useRef(null)
  const savingRef = useRef(false)
  const seekRef = useRef(0)
  const pollRef = useRef(null)

  const docRef = useRef(null)
  const baseRef = useRef(null)
  docRef.current = doc

  const rows = useMemo(() => timeline(doc), [doc])
  const total = useMemo(() => totalOf(doc), [doc])
  const at = sceneAt(doc, cursor)
  const sel = useMemo(() => (doc && doc.scenes ? doc.scenes.find((s) => s.id === selId) || null : null), [doc, selId])
  const selIndex = sel ? doc.scenes.indexOf(sel) : -1
  // Ken Burns solo aplica a imágenes: el servicio lo rechaza en vídeo.
  const selIsImage = useMemo(() => {
    if (!sel) return false
    const asset = (media || []).find((item) => item.id === (sel.source && sel.source.assetId))
    return !!asset && asset.kind === 'image'
  }, [media, sel])
  const music = (doc && doc.music) || null
  const sfxEvents = (doc && Array.isArray(doc.audioEvents) && doc.audioEvents) || []
  const logo = (doc && doc.logo) || null
  const audioAssets = useMemo(() => (media || []).filter((item) => item && item.kind === 'audio'), [media])
  const imageAssets = useMemo(() => (media || []).filter((item) => item && item.kind === 'image'), [media])
  const musicAsset = music && music.assetId ? (media || []).find((item) => item.id === music.assetId) || null : null

  // `/health` es la fuente cuando publica catálogos; si no contesta, cada
  // control cae al catálogo local (mismos ids que core/project.py).
  const transitionOptions = useMemo(() => {
    const remote = service && Array.isArray(service.transitions) ? service.transitions.filter(Boolean).map(String) : []
    if (!remote.length) return TRANSITIONS
    return [{ id: 'none', label: 'Sin transición' }, ...remote.map((id) => ({ id, label: transitionLabel(id) }))]
  }, [service])

  const transitionList = useMemo(() => {
    const current = sel ? parseTransition(sel.transition).style : 'none'
    if (current === 'none' || transitionOptions.some((item) => item.id === current)) return transitionOptions
    // Estilo que el documento ya usa pero el catálogo no lista: se muestra tal cual.
    return [...transitionOptions, { id: current, label: transitionLabel(current) }]
  }, [transitionOptions, sel])

  const presetOptions = useMemo(() => {
    const remote = service && Array.isArray(service.presets) ? service.presets.filter(Boolean).map(String) : []
    const known = remote.length ? new Set(remote) : null
    const rows = EXPORT_PRESETS.map((item) => ({ ...item, disabled: !!known && !known.has(item.id) }))
    if (known) {
      remote.forEach((id) => {
        if (!EXPORT_PRESETS.some((item) => item.id === id)) rows.push({ id, label: id, disabled: false })
      })
    }
    return rows
  }, [service])

  const presetPicked = presetOptions.find((item) => item.id === exportPreset) || null

  // Techo real del fundido en la escena seleccionada (escena y anterior).
  const fadeLimit = selIndex > 0 ? maxFadeFor(doc && doc.scenes, selIndex) : 0

  const session = (ctx && ctx.session) || {}
  // El SDK real no expone `ctx.session`: el chat vivo se lee de host.state.
  const liveSessionId = useValue(stateAtom('focusedStoredSessionId', null))
  const liveCwd = useValue(stateAtom('cwd', ''))
  const liveBusy = useValue(stateAtom('busy', false))
  // host.state.model es readonlyAtom<string>; si el host no lo expone el
  // atom cae en '' y el chip simplemente no se dibuja (nada inventado).
  const modelSlug = useValue(stateAtom('model', ''))
  const sessionId = liveSessionId || session.sessionId || session.id || null
  const cwd = liveCwd || session.cwd || ''

  // -------------------------------------------------------------- carga

  const loadProjects = useCallback(async () => {
    try {
      const payload = await request(ctx, '/projects')
      const items = payload.projects || []
      setProjects(items)
      setPhase((prev) => (prev === 'boot' || prev === 'offline' ? 'noProject' : prev))
      try {
        const grants = await request(ctx, '/grants')
        if (grants && grants.mediaRoot) setMediaRoot(grants.mediaRoot)
      } catch (error) {
        /* sin concesión declarada: el import avisará al fallar */
      }
      return items
    } catch (error) {
      setPhase('offline')
      setLoadError(error)
      return null
    }
  }, [ctx])

  const openProject = useCallback(
    async (projectId) => {
      setPhase('loading')
      setLoadError(null)
      setPlaying(false)
      try {
        const payload = await request(ctx, `/projects/${encodeURIComponent(projectId)}`)
        setDoc(payload.project)
        setMedia(payload.media || [])
        const first = payload.project.scenes && payload.project.scenes[0]
        setSelId(first ? first.id : null)
        setCursor(0)
        setDirty(false)
        setStatus('idle')
        setSavedAt(Date.parse(payload.updatedAt || payload.project.updatedAt) || null)
        undoRef.current = []
        redoRef.current = []
        setUndoDepth(0)
        setRedoDepth(0)
        setPhase('ready')
        if (ctx && ctx.storage && ctx.storage.set) ctx.storage.set('lastProjectId', projectId)
      } catch (error) {
        setLoadError(error)
        setPhase('error')
      }
    },
    [ctx]
  )

  // Refresco desde el chat: si el servicio tiene una revisión más nueva y el
  // usuario no está escribiendo, se recarga el documento sin cerrar el pane.
  useEffect(() => {
    if (!doc || !doc.projectId) return undefined
    let alive = true
    const timer = setInterval(async () => {
      if (!alive || dirty) return
      const active = document.activeElement
      // Solo se espera si estás escribiendo; un botón con foco no debe impedir ver lo que hizo el chat.
      if (active && /^(INPUT|TEXTAREA|SELECT)$/.test(active.tagName) && active.closest && active.closest('.ve')) return
      try {
        const payload = await request(ctx, `/projects/${encodeURIComponent(doc.projectId)}`)
        if (!alive) return
        const remote = payload.project && payload.project.revision
        if (typeof remote === 'number' && remote > (doc.revision || 0)) {
          setDoc(payload.project)
          setMedia(payload.media || [])
          const first = payload.project.scenes && payload.project.scenes[0]
          setSelId((prev) => ((payload.project.scenes || []).some((s) => s.id === prev) ? prev : first ? first.id : null))
          setSavedAt(Date.now())
          setNotice('Proyecto actualizado desde el chat.')
        }
      } catch (error) {
        /* sin conexión: el siguiente tick reintenta */
      }
    }, 4000)
    return () => {
      alive = false
      clearInterval(timer)
    }
  }, [ctx, doc && doc.projectId, doc && doc.revision, dirty])

  // Catálogos que el servicio publica. Fallar aquí no rompe nada: los
  // controles usan el catálogo local.
  useEffect(() => {
    let alive = true
    ;(async () => {
      try {
        const info = await request(ctx, '/health')
        if (alive && info && typeof info === 'object') setService(info)
      } catch (error) {
        if (alive) setService(null)
      }
    })()
    return () => {
      alive = false
    }
  }, [ctx])

  useEffect(() => {
    let alive = true
    ;(async () => {
      const list = await loadProjects()
      if (!alive) return
      if (list === null) return
      const remembered = ctx && ctx.storage && ctx.storage.get ? ctx.storage.get('lastProjectId') : null
      if (remembered && list.some((item) => item.projectId === remembered)) {
        openProject(remembered)
      } else if (list.length === 1) {
        openProject(list[0].projectId)
      } else {
        setPhase('noProject')
      }
      if (ctx && ctx.storage && ctx.storage.get) {
        const savedGuides = ctx.storage.get('preview.guides')
        if (typeof savedGuides === 'boolean') setGuides(savedGuides)
        const savedMuted = ctx.storage.get('transport.muted')
        if (typeof savedMuted === 'boolean') setMuted(savedMuted)
      }
    })()
    const observer =
      typeof ResizeObserver !== 'undefined' && rootRef.current
        ? new ResizeObserver((entries) => {
            const box = entries[0] && entries[0].contentRect
            if (box) setWidth(box.width)
          })
        : null
    if (observer && rootRef.current) observer.observe(rootRef.current)
    return () => {
      alive = false
      if (observer) observer.disconnect()
      if (autoRef.current) clearTimeout(autoRef.current)
      autoRef.current = null
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = null
      // Al cerrar el pane no queda ni decodificación de vídeo ni temporizador.
      releaseVideos(rootRef.current)
    }
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [])

  // -------------------------------------------------------------- guardado

  const save = useCallback(
    async (options = {}) => {
      const current = docRef.current
      if (!current || savingRef.current) return
      if (!options.force && !dirty) return
      savingRef.current = true
      setStatus('saving')
      const sentJson = JSON.stringify(current)
      try {
        const payload = await request(ctx, `/projects/${encodeURIComponent(current.projectId)}`, {
          method: 'PUT',
          body: { revision: current.revision, project: current }
        })
        const latest = docRef.current
        baseRef.current = payload.project
        if (latest && JSON.stringify(latest) !== sentJson) {
          // Editaste mientras se guardaba: se conservan tus cambios nuevos y solo se
          // actualiza la revisión (antes la respuesta del servidor los pisaba).
          const saved = payload.project
          setDoc({ ...latest, revision: saved.revision, baseRevision: saved.baseRevision, updatedAt: saved.updatedAt })
          setStatus('idle')
        } else {
          setDoc(payload.project)
          setDirty(false)
          setStatus('saved')
          setSavedAt(Date.now())
          setNotice('')
        }
      } catch (error) {
        if (error.status === 409) {
          // Alguien (normalmente Hermes desde el chat) guardó antes: se combinan los dos
          // lados en vez de perder uno. Si no se puede, queda el diálogo de siempre.
          try {
            const remote = await request(ctx, `/projects/${encodeURIComponent(current.projectId)}`)
            const mineNow = docRef.current || current
            setDoc(mergeDocs(baseRef.current || current, mineNow, remote.project))
            baseRef.current = remote.project
            setMedia(remote.media || [])
            setDirty(true)
            setStatus('idle')
            setNotice('Se combinaron tus cambios con los del chat.')
          } catch (mergeError) {
            const theirs = (error.payload && error.payload.current_revision) || '?'
            setDialog({ kind: 'conflict', theirs, mine: current.revision })
            setStatus('idle')
          }
        } else {
          setStatus('failed')
          setNotice(error.message)
        }
      } finally {
        savingRef.current = false
      }
    },
    [ctx, dirty]
  )

  useEffect(() => {
    if (!dirty && doc) baseRef.current = doc
  }, [doc, dirty])

  useEffect(() => {
    if (!dirty || phase !== 'ready') return undefined
    if (autoRef.current) clearTimeout(autoRef.current)
    autoRef.current = setTimeout(() => save(), AUTOSAVE_MS)
    return () => {
      if (autoRef.current) clearTimeout(autoRef.current)
    }
  }, [doc, dirty, phase, save])

  // -------------------------------------------------------------- mutaciones

  const mutate = useCallback((fn) => {
    const current = docRef.current
    if (!current) return
    undoRef.current = [...undoRef.current.slice(-49), JSON.stringify(current)]
    redoRef.current = []
    setUndoDepth(undoRef.current.length)
    setRedoDepth(0)
    const next = fn(clone(current))
    setDoc(next)
    setDirty(true)
  }, [])

  const undo = useCallback(() => {
    const stack = undoRef.current
    if (!stack.length || !docRef.current) return
    const previous = stack[stack.length - 1]
    undoRef.current = stack.slice(0, -1)
    redoRef.current = [...redoRef.current.slice(-49), JSON.stringify(docRef.current)]
    setUndoDepth(undoRef.current.length)
    setRedoDepth(redoRef.current.length)
    setDoc(JSON.parse(previous))
    setDirty(true)
  }, [])

  const redo = useCallback(() => {
    const stack = redoRef.current
    if (!stack.length || !docRef.current) return
    const next = stack[stack.length - 1]
    redoRef.current = stack.slice(0, -1)
    undoRef.current = [...undoRef.current.slice(-49), JSON.stringify(docRef.current)]
    setUndoDepth(undoRef.current.length)
    setRedoDepth(redoRef.current.length)
    setDoc(JSON.parse(next))
    setDirty(true)
  }, [])

  const writeCaption = (text) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      const clean = text.slice(0, MAX_CAPTION)
      const rest = (scene.text || []).slice(1)
      const prev = textItemOf(scene)
      if (!clean.trim()) {
        scene.text = rest
      } else {
        // Reescribir el texto no puede tirar el estilo ni la animación ya
        // elegidos: se conserva el item y solo se cambian contenido y ventana.
        scene.text = [
          {
            ...(prev || {}),
            at: 0,
            until: round3(visibleDuration(scene)),
            content: clean,
            position: (prev && prev.position) || 'bottom'
          },
          ...rest
        ]
      }
      return draft
    })
  }

  const setSceneVolume = (value) => {
    if (!sel) return
    const volume = clamp(Math.round(value / 5) * 5, 0, 100)
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      scene.audio = { ...(scene.audio || {}), volume }
      return draft
    })
  }

  const setIn = (value) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      const next = round3(clamp(value, 0, Number(scene.out) - MIN_SCENE))
      if (!(next >= 0)) return draft
      scene.in = next
      if (scene.text && scene.text[0]) scene.text[0].until = round3(visibleDuration(scene))
      fitTransition(draft.scenes, scene)
      return draft
    })
  }

  const setOut = (value) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      const next = round3(Math.max(Number(scene.in) + MIN_SCENE, value))
      scene.out = next
      if (scene.text && scene.text[0]) scene.text[0].until = round3(visibleDuration(scene))
      fitTransition(draft.scenes, scene)
      return draft
    })
  }

  const trimAtCursor = (edge) => {
    if (!sel || !at.row || at.row.id !== sel.id) return
    if (edge === 'in') setIn(round3(Number(sel.in) + at.local))
    else setOut(round3(Number(sel.in) + at.local))
  }

  const splitHere = () => {
    if (!sel || !at.row || at.row.id !== sel.id) return
    const offset = Number(sel.in) + at.local
    if (at.local < MIN_SCENE || sceneDuration(sel) - at.local < MIN_SCENE) {
      setNotice('Coloca el cursor a más de 0,3 s del borde para partir.')
      return
    }
    mutate((draft) => {
      const index = draft.scenes.findIndex((item) => item.id === sel.id)
      const scene = draft.scenes[index]
      const tail = clone(scene)
      tail.id = uid('sc')
      tail.in = round3(offset)
      tail.text = []
      // El corte no inserta un cruce: la cola entra seca.
      tail.transition = 'none'
      scene.out = round3(offset)
      if (scene.text && scene.text[0]) scene.text[0].until = round3(sceneDuration(scene))
      draft.scenes.splice(index + 1, 0, tail)
      fitTransition(draft.scenes, scene)
      return draft
    })
    setNotice('Escena partida en el cursor.')
  }

  const moveScene = (index, delta) => {
    const target = index + delta
    if (!doc || target < 0 || target >= doc.scenes.length) return
    mutate((draft) => {
      const [item] = draft.scenes.splice(index, 1)
      draft.scenes.splice(target, 0, item)
      return draft
    })
    setNotice(`Escena ${index + 1} movida a la posición ${target + 1}`)
  }

  const deleteScene = (index) => {
    if (!doc) return
    mutate((draft) => {
      draft.scenes.splice(index, 1)
      return draft
    })
    const nextScene = doc.scenes[index + 1] || doc.scenes[index - 1] || null
    setSelId(nextScene ? nextScene.id : null)
    setNotice('Escena eliminada. Ctrl+Z la recupera.')
  }

  const setTransitionStyle = (style) => {
    if (!sel) return
    const current = parseTransition(sel.transition)
    const scenes = docRef.current && docRef.current.scenes ? docRef.current.scenes : []
    const limit = maxFadeFor(scenes, scenes.findIndex((item) => item.id === sel.id))
    if (style !== 'none' && limit < TRANSITION_MIN_S) {
      setNotice('La escena es demasiado corta para un fundido (mínimo 0,1 s en ambas).')
      return
    }
    const seconds = Math.min(current.seconds, Math.max(TRANSITION_MIN_S, limit))
    const next = style === 'none' ? 'none' : transitionValue(style, seconds)
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      scene.transition = next
      return draft
    })
  }

  const setTransitionSeconds = (seconds) => {
    if (!sel) return
    const current = parseTransition(sel.transition)
    if (current.style === 'none') return
    const scenes = docRef.current && docRef.current.scenes ? docRef.current.scenes : []
    const limit = maxFadeFor(scenes, scenes.findIndex((item) => item.id === sel.id))
    if (limit < TRANSITION_MIN_S) return
    const next = transitionValue(current.style, clamp(Number(seconds) || TRANSITION_MIN_S, TRANSITION_MIN_S, limit))
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      scene.transition = next
      return draft
    })
  }

  // -------------------------------------------------------------- música

  const setMusic = (patch) => {
    mutate((draft) => {
      if (!draft.music) return draft
      draft.music = { ...draft.music, ...patch }
      return draft
    })
  }

  const setMusicFade = (key, raw) => {
    const text = String(raw == null ? '' : raw).replace(',', '.').trim()
    if (!text) return
    const value = Number(text)
    if (!Number.isFinite(value)) return
    setMusic({ [key]: round3(clamp(value, 0, 10)) })
  }

  const chooseMusic = (assetId) => {
    if (!assetId) {
      removeMusic()
      return
    }
    mutate((draft) => {
      const prev = draft.music && typeof draft.music === 'object' ? draft.music : {}
      draft.music = {
        assetId,
        volume: typeof prev.volume === 'number' ? prev.volume : MUSIC_DEFAULTS.volume,
        fadeIn: typeof prev.fadeIn === 'number' ? prev.fadeIn : MUSIC_DEFAULTS.fadeIn,
        fadeOut: typeof prev.fadeOut === 'number' ? prev.fadeOut : MUSIC_DEFAULTS.fadeOut,
        loop: typeof prev.loop === 'boolean' ? prev.loop : MUSIC_DEFAULTS.loop,
        ducking: typeof prev.ducking === 'boolean' ? prev.ducking : MUSIC_DEFAULTS.ducking
      }
      return draft
    })
    setNotice('Música de fondo asignada.')
  }

  const removeMusic = () => {
    mutate((draft) => {
      delete draft.music
      return draft
    })
    setNotice('Música quitada del proyecto.')
  }

  // -------------------------------------------------------------- sonidos y voz (audioEvents)

  const setEvent = (id, patch) => {
    mutate((draft) => {
      draft.audioEvents = (draft.audioEvents || []).map((item) => (item.id === id ? { ...item, ...patch } : item))
      return draft
    })
  }

  const commitEventAt = (id, text) => {
    const seconds = parseTimecode(text)
    if (seconds === null) return
    setEvent(id, { at: round3(clamp(seconds, 0, Math.max(total, 0))) })
  }

  const removeEvent = (id) => {
    mutate((draft) => {
      draft.audioEvents = (draft.audioEvents || []).filter((item) => item.id !== id)
      if (!draft.audioEvents.length) delete draft.audioEvents
      return draft
    })
    setNotice('Sonido quitado.')
  }

  const addEventAtCursor = (assetId) => {
    if (!assetId) return
    mutate((draft) => {
      draft.audioEvents = [
        ...(draft.audioEvents || []),
        { id: uid('ae'), assetId, at: round3(clamp(cursor, 0, Math.max(total, 0))), volume: 80 }
      ]
      return draft
    })
    setNotice(`Sonido añadido en ${fmtTimecode(cursor)}.`)
  }

  const setNormalize = (value) => {
    mutate((draft) => {
      draft.audio = { ...(draft.audio || {}), normalize: !!value }
      return draft
    })
  }

  // -------------------------------------------------------------- estilo de texto

  const setTextStyle = (patch) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      const item = ensureTextItem(scene)
      if (!item) return draft
      Object.keys(patch).forEach((key) => {
        if (patch[key] === null || patch[key] === undefined) delete item[key]
        else item[key] = patch[key]
      })
      return draft
    })
  }

  const setTextAnimation = (slot, value) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      const item = ensureTextItem(scene)
      if (!item) return draft
      const prev = item.animation && typeof item.animation === 'object' ? item.animation : {}
      const next = { ...prev, [slot]: value }
      // Dos «ninguna» es lo mismo que no tener animación: no se escribe.
      if ((next.in || 'none') === 'none' && (next.out || 'none') === 'none') delete item.animation
      else item.animation = next
      return draft
    })
  }

  // -------------------------------------------------------------- filtros

  const setFilter = (key, raw) => {
    if (!sel) return
    const slider = FILTER_SLIDERS.find((item) => item.key === key)
    const value = Number(raw)
    if (!slider || !Number.isFinite(value)) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      const next = cleanFilters({ ...(scene.filters || {}), [key]: clamp(value, slider.min, slider.max) })
      if (Object.keys(next).length) scene.filters = next
      else delete scene.filters
      return draft
    })
  }

  const setFilterFlag = (key, on) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      const next = cleanFilters({ ...(scene.filters || {}), [key]: !!on })
      if (Object.keys(next).length) scene.filters = next
      else delete scene.filters
      return draft
    })
  }

  const resetFilters = () => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (scene) delete scene.filters
      return draft
    })
    setNotice('Filtros restablecidos.')
  }

  // -------------------------------------------------------------- ken burns / velocidad

  const toggleKenBurns = (on) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      if (!on) delete scene.kenBurns
      else scene.kenBurns = { zoom: KEN_BURNS.zoom, pan: KEN_BURNS.pan }
      return draft
    })
  }

  const setKenBurns = (patch) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      const prev = scene.kenBurns && typeof scene.kenBurns === 'object' ? scene.kenBurns : {}
      const zoom =
        patch.zoom === undefined
          ? Number(prev.zoom) || KEN_BURNS.zoom
          : clamp(Number(patch.zoom) || KEN_BURNS.zoom, KEN_BURNS.minZoom, KEN_BURNS.maxZoom)
      const pan = patch.pan === undefined ? prev.pan || KEN_BURNS.pan : patch.pan
      scene.kenBurns = { zoom: round3(zoom), pan }
      return draft
    })
  }

  const setSpeed = (raw) => {
    if (!sel) return
    const value = round3(clamp(Number(raw) || SCENE_SPEED.default, SCENE_SPEED.min, SCENE_SPEED.max))
    mutate((draft) => {
      const index = draft.scenes.findIndex((item) => item.id === sel.id)
      const scene = draft.scenes[index]
      if (!scene) return draft
      const before = visibleDuration(scene)
      // 1× es la identidad: la clave no se escribiría nunca en vano.
      if (Math.abs(value - SCENE_SPEED.default) < 1e-9) delete scene.speed
      else scene.speed = value
      fitSceneWindows(draft.scenes, scene, index, before)
      return draft
    })
  }

  // -------------------------------------------------------------- logo

  const setLogo = (patch) => {
    mutate((draft) => {
      const prev = draft.logo && typeof draft.logo === 'object' ? draft.logo : {}
      const merged = {
        assetId: prev.assetId || '',
        position: prev.position || LOGO_DEFAULTS.position,
        opacity: typeof prev.opacity === 'number' ? prev.opacity : LOGO_DEFAULTS.opacity,
        scale: typeof prev.scale === 'number' ? prev.scale : LOGO_DEFAULTS.scale,
        ...patch
      }
      if (!merged.assetId) {
        delete draft.logo
        return draft
      }
      draft.logo = {
        assetId: merged.assetId,
        position: LOGO_POSITIONS.some((item) => item.id === merged.position) ? merged.position : LOGO_DEFAULTS.position,
        opacity: round3(clamp(Number(merged.opacity), LOGO_LIMITS.opacity[0], LOGO_LIMITS.opacity[1])),
        scale: round3(clamp(Number(merged.scale), LOGO_LIMITS.scale[0], LOGO_LIMITS.scale[1]))
      }
      return draft
    })
  }

  const removeLogo = () => {
    mutate((draft) => {
      delete draft.logo
      return draft
    })
    setNotice('Logo quitado del proyecto.')
  }

  const setOrientation = (value) => {
    const target = ORIENTATIONS[value]
    if (!target) return
    mutate((draft) => {
      draft.orientation = value
      draft.width = target.w
      draft.height = target.h
      return draft
    })
    setNotice(value === 'v' ? 'Formato vertical: el export recorta los bordes laterales.' : 'Formato horizontal.')
  }

  const setMasterVolume = (value) => {
    const volume = clamp(Math.round(value / 5) * 5, 0, 100)
    mutate((draft) => {
      draft.audio = { ...(draft.audio || {}), masterVolume: volume }
      return draft
    })
  }

  // -------------------------------------------------------------- reproducción

  useEffect(() => {
    const video = videoRef.current
    if (!video || !at.row) return
    const target = Number(at.row.scene.in) + at.local
    if (Math.abs(video.currentTime - target) > 0.2) {
      try {
        video.currentTime = Math.max(0, target)
      } catch (error) {
        /* el src aún no está listo */
      }
    }
    const scene = at.row.scene
    if (scene) {
      const master = (doc && doc.audio && doc.audio.masterVolume) || 100
      const volume = ((scene.audio && scene.audio.volume) || 0) / 100
      video.volume = clamp(volume * (master / 100), 0, 1)
    }
    video.muted = muted
  }, [at.row && at.row.id, at.local, sel, doc, muted])

  useEffect(() => {
    const video = videoRef.current
    if (!video) return undefined
    if (playing) {
      const play = video.play()
      if (play && play.catch) play.catch(() => setPlaying(false))
      return undefined
    }
    video.pause()
    return undefined
  }, [playing, at.row && at.row.id])

  // las imágenes no emiten timeupdate: el reloj lo mueve un temporizador
  const imageScene = !!(
    at.row &&
    at.row.scene &&
    (media.find((item) => item.id === (at.row.scene.source && at.row.scene.source.assetId)) || {}).kind === 'image'
  )
  useEffect(() => {
    if (!playing || !imageScene) return undefined
    const timer = setInterval(() => {
      setCursor((prev) => {
        const now = totalOf(docRef.current)
        const next = prev + 0.1
        if (next >= now) {
          setPlaying(false)
          return now
        }
        return next
      })
    }, 100)
    return () => clearInterval(timer)
  }, [playing, imageScene])

  const canvasRef = useRef(null)
  const [canvasBox, setCanvasBox] = useState({ w: 0, h: 0 })
  useLayoutEffect(() => {
    const el = canvasRef.current
    if (!el || typeof ResizeObserver === 'undefined') return undefined
    const observer = new ResizeObserver((entries) => {
      const rect = entries[0].contentRect
      setCanvasBox((prev) =>
        Math.abs(prev.w - rect.width) < 0.5 && Math.abs(prev.h - rect.height) < 0.5
          ? prev
          : { w: rect.width, h: rect.height }
      )
    })
    observer.observe(el)
    return () => observer.disconnect()
  }, [phase])

  const onTime = () => {
    const video = videoRef.current
    if (!video || !at.row) return
    const scene = at.row.scene
    const local = video.currentTime - Number(scene.in)
    const limit = sceneDuration(scene)
    if (playing && local >= limit - 0.03) {
      const nextRow = rows[at.index + 1]
      if (nextRow) {
        setCursor(nextRow.start)
        setSelId(nextRow.id)
      } else {
        setPlaying(false)
        setCursor(total)
        setPlaying(false)
      }
      return
    }
    if (playing) setCursor(at.row.start + clamp(local, 0, limit))
  }

  // -------------------------------------------------------------- exportación

  const startExport = async ({ captions, openWhenDone, preset }) => {
    if (!doc) return
    const chosen = preset || exportPreset || PRESET
    setDialog({ kind: 'export', phase: 'queued', captions, openWhenDone })
    try {
      await save({ force: false })
      const payload = await request(ctx, `/projects/${encodeURIComponent(doc.projectId)}/export`, {
        method: 'POST',
        body: { preset: chosen, captions }
      })
      setJob({ jobId: payload.jobId, state: payload.state || 'queued', stage: 'queued', progress: 0 })
      setDialog({ kind: 'export', phase: 'running', jobId: payload.jobId, captions, openWhenDone })
      if (pollRef.current) clearInterval(pollRef.current)
      pollRef.current = setInterval(async () => {
        try {
          const statusPayload = await request(ctx, `/jobs/${encodeURIComponent(payload.jobId)}`)
          setJob(statusPayload)
          if (['succeeded', 'failed', 'cancelled', 'interrupted'].includes(statusPayload.state)) {
            clearInterval(pollRef.current)
            pollRef.current = null
            setDialog((prev) =>
              prev && prev.kind === 'export'
                ? { ...prev, phase: statusPayload.state === 'succeeded' ? 'done' : 'failed', job: statusPayload }
                : prev
            )
            if (statusPayload.state === 'succeeded' && openWhenDone && ctx.os && ctx.os.openExternal) {
              try {
                ctx.os.openExternal(statusPayload.outputPath)
              } catch (error) {
                /* abrir es opcional */
              }
            }
          }
        } catch (error) {
          clearInterval(pollRef.current)
          pollRef.current = null
          setDialog((prev) => (prev && prev.kind === 'export' ? { ...prev, phase: 'failed', job: { error: error.message } } : prev))
        }
      }, POLL_MS)
    } catch (error) {
      setDialog({ kind: 'export', phase: 'failed', job: { error: error.message } })
    }
  }

  const cancelExport = async () => {
    const jobId = job && job.jobId
    if (!jobId) return
    setDialog((prev) => (prev ? { ...prev, phase: 'cancelling' } : prev))
    try {
      await request(ctx, `/jobs/${encodeURIComponent(jobId)}/cancel`, { method: 'POST', body: {} })
    } catch (error) {
      setNotice(error.message)
    }
  }

  // -------------------------------------------------------------- importación

  const importFolder = async () => {
    if (!doc) return
    if (!ctx || !ctx.files) {
      setNotice('Este build no expone ctx.files: importa desde la carpeta concedida del servicio.')
      return
    }
    setImportState({ phase: 'picking' })
    try {
      let folder = null
      if (ctx.files.folders) {
        const known = await ctx.files.folders()
        folder = known && known.length ? known[0] : null
      }
      if (!folder) {
        const picked = await ctx.files.requestFolder()
        if (!picked || !picked.ok || !picked.folder) {
          setImportState(picked && picked.error ? { phase: 'error', error: picked.error } : null)
          return
        }
        folder = picked.folder
      }
      if (mediaRoot && !within(folder.path, mediaRoot)) {
        setImportState({
          phase: 'error',
          error: `Esa carpeta no es la que el servicio tiene concedida. Concede y usa: ${mediaRoot}`
        })
        return
      }
      const listing = await ctx.files.list(folder.id, '')
      if (!listing || !listing.ok) {
        setImportState({ phase: 'error', error: (listing && listing.error) || 'no se pudo listar' })
        return
      }
      const allowed = /\.(png|jpe?g|mp4|mov|m4v|mp3|wav)$/i
      const entries = (listing.entries || []).filter((entry) => allowed.test(entry.path))
      setImportState({ phase: 'list', folder, entries, chosen: {} })
    } catch (error) {
      setImportState({ phase: 'error', error: error.message })
    }
  }

  const doImport = async () => {
    const state = importState
    if (!state || state.phase !== 'list' || !doc) return
    const chosen = state.entries.filter((entry) => state.chosen[entry.path])
    if (!chosen.length) return
    setImportState({ ...state, phase: 'importing', done: 0, failures: [] })
    const failures = []
    let done = 0
    for (const entry of chosen) {
      const absolute = `${String(state.folder.path).replace(/[\\/]+$/, '')}/${entry.path}`
      try {
        const payload = await request(ctx, `/projects/${encodeURIComponent(doc.projectId)}/media`, {
          method: 'POST',
          body: { path: absolute.replace(/\\/g, '/') }
        })
        setDoc(payload.project)
        setMedia(payload.media || [])
        setDirty(false)
        setSavedAt(Date.now())
        const last = payload.project.scenes[payload.project.scenes.length - 1]
        if (last) setSelId(last.id)
        done += 1
      } catch (error) {
        failures.push(`${entry.path}: ${error.message}`)
      }
      setImportState((prev) => (prev ? { ...prev, done, failures } : prev))
    }
    setImportState({ phase: 'result', done, total: chosen.length, failures })
    setPhase('ready')
    setNotice(done === 1 ? 'Medio importado.' : `${done} medios importados.`)
  }

  // -------------------------------------------------------------- teclado

  useEffect(() => {
    const node = rootRef.current
    if (!node) return undefined
    const onKey = (event) => {
      const tag = (event.target && event.target.tagName) || ''
      const typing = ['INPUT', 'TEXTAREA', 'SELECT'].includes(tag) || (event.target && event.target.isContentEditable)
      const mod = event.ctrlKey || event.metaKey
      if (event.key === 'Escape') {
        if (dialog) {
          setDialog(null)
          setPlaying(false)
        } else if (menu) {
          setMenu(null)
        } else if (libOpen || railOpen) {
          setLibOpen(false)
          setRailOpen(false)
        } else {
          setPlaying(false)
        }
        return
      }
      if (mod && (event.key === 's' || event.key === 'S')) {
        event.preventDefault()
        save({ force: true })
        return
      }
      if (mod && (event.key === 'z' || event.key === 'Z')) {
        event.preventDefault()
        if (event.shiftKey) redo()
        else undo()
        return
      }
      if (mod && (event.key === 'e' || event.key === 'E')) {
        event.preventDefault()
        if (phase === 'ready') setDialog({ kind: 'exportForm' })
        return
      }
      if (typing || dialog) return
      if (event.key === ' ') {
        event.preventDefault()
        setPlaying((prev) => !prev)
        return
      }
      if (event.key === 'ArrowLeft' || event.key === 'ArrowRight') {
        event.preventDefault()
        const rate = docRef.current && docRef.current.fps ? (docRef.current.fps.num || 30) / (docRef.current.fps.den || 1) : 30
        const step = event.shiftKey ? 1 : 1 / (rate || 30)
        setCursor((prev) => clamp(prev + (event.key === 'ArrowLeft' ? -step : step), 0, total))
        return
      }
      if (event.key === 'Home') {
        event.preventDefault()
        setCursor(0)
        return
      }
      if (event.key === 'End') {
        event.preventDefault()
        setCursor(total)
        return
      }
      if (event.altKey && (event.key === 'ArrowUp' || event.key === 'ArrowDown')) {
        event.preventDefault()
        if (selIndex >= 0) moveScene(selIndex, event.key === 'ArrowUp' ? -1 : 1)
        return
      }
      if (event.key === 'i' || event.key === 'I') trimAtCursor('in')
      if (event.key === 'o' || event.key === 'O') trimAtCursor('out')
      if (event.key === 's' || event.key === 'S') splitHere()
      if (event.key === 'Delete' && selIndex >= 0) deleteScene(selIndex)
    }
    node.addEventListener('keydown', onKey)
    return () => node.removeEventListener('keydown', onKey)
  })

  // -------------------------------------------------------------- derivados de render

  const compact = width < 1100
  const tight = width < 760
  const modelName = (() => {
    const raw = typeof modelSlug === 'string' ? modelSlug.trim() : ''
    if (!raw) return ''
    const tail = raw.split('/').pop() || raw
    return tail.length > 26 ? `${tail.slice(0, 25)}…` : tail
  })()
  const baseName = (value) => String(value || '').split(/[\\/]+/).pop() || String(value || '')
  const assetFor = (scene) => (scene.source && scene.source.assetId) || null
  const missing = (doc ? doc.scenes || [] : []).filter(
    (scene) => scene.needsRelink || !assetFor(scene) || (media.find((item) => item.id === assetFor(scene)) || {}).exists === false
  )
  const canExport = !!doc && (doc.scenes || []).length > 0 && dirty === false && missing.length === 0 && status !== 'saving'
  const orient = ORIENTATIONS[(doc && doc.orientation) || 'h'] || ORIENTATIONS.h
  const docFps = doc && doc.fps ? Math.round((doc.fps.num || 30) / (doc.fps.den || 1)) : 30
  const frameStep = 1 / (docFps || 30)
  const aspect = orient.w / orient.h
  const fitStyle =
    canvasBox.w > 4 && canvasBox.h > 4
      ? (() => {
          const width = Math.min(canvasBox.w, canvasBox.h * aspect)
          return { width: `${Math.floor(width)}px`, height: `${Math.floor(width / aspect)}px` }
        })()
      : { aspectRatio: orient.ratio, width: '100%' }
  const currentScene = at.row ? at.row.scene : null
  const activeAsset = currentScene ? assetFor(currentScene) : null
  const activeKind = currentScene
    ? (media.find((item) => item.id === activeAsset) || {}).kind ||
      (currentScene.source && currentScene.source.kind) ||
      'video'
    : 'video'
  const videoSrc = doc && activeAsset ? mediaUrl(ctx, doc.projectId, activeAsset) : null
  const savedLabel = status === 'saving' ? 'Guardando…' : status === 'failed' ? 'No se pudo guardar' : savedAt ? `Guardado ${relativeTime(savedAt)}` : 'Sin guardar'
  const autosaveTone = status === 'saving' ? 'warn' : status === 'failed' ? 'bad' : 'good'

  // -------------------------------------------------------------- picker + biblioteca

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

  const header = () =>
    h(
      'header',
      { className: 've-hdr' },
      h('span', { className: 've-plate' }, h(Icon, { name: 'film' })),
      h('span', { className: 've-title' }, compact ? 'Editor' : 'Editor de vídeo'),
      doc ? h(Badge, { outline: true }, `Rev ${doc.revision}`) : h(Badge, { outline: true }, 'Sin proyecto'),
      dirty ? h(Badge, { tone: 'warn' }, 'Sin guardar') : null,
      h('span', { className: 've-sep' }),
      h(
        'button',
        {
          type: 'button',
          className: 've-chip',
          onClick: () => setMenu(menu === 'projects' ? null : 'projects'),
          'aria-haspopup': 'menu',
          'aria-expanded': menu === 'projects'
        },
        h(Icon, { name: 'panel', size: 'sm' }),
        h('span', { className: 've-chip__name' }, doc ? doc.title : 'Sin proyecto'),
        h(Icon, { name: 'down', size: 'sm' })
      ),
      h(
        'button',
        {
          type: 'button',
          className: 've-chip ve-chip--ghost ve-chat',
          title: sessionId
            ? `Vinculado al chat de Hermes · ${cwd || 'sin carpeta'}`
            : 'Sin chat vinculado: abre un chat y el editor se enlaza solo',
          onClick: goChat,
          'aria-label': sessionId
            ? `Chat ${shortChat(sessionId)}${liveBusy ? ', trabajando ahora' : ''}. Ir al chat`
            : 'Ir al chat'
        },
        h(Dot, { tone: sessionId ? (liveBusy ? 'warn' : 'good') : 'bad' }),
        h('span', { className: 've-chip__name' }, sessionId ? `Chat ${shortChat(sessionId)}` : 'Sin chat'),
        liveBusy ? h('span', { className: 've-chat__b' }, 'trabajando') : null
      ),
      modelName
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
      h('span', { className: 've-auto', 'aria-live': 'polite' }, h(Dot, { tone: autosaveTone }), savedLabel),
      h(Btn, { icon: 'undo', variant: 'ghost', ariaLabel: 'Deshacer', title: 'Deshacer · Ctrl+Z', onClick: undo, disabled: !undoDepth }),
      h(Btn, { icon: 'redo', variant: 'ghost', ariaLabel: 'Rehacer', title: 'Rehacer · Ctrl+Shift+Z', onClick: redo, disabled: !redoDepth }),
      h(Btn, {
        variant: 'primary',
        ...(compact
          ? { icon: 'save', ariaLabel: 'Guardar', title: 'Guardar · Ctrl+S' }
          : { label: status === 'saving' ? 'Guardando…' : 'Guardar' }),
        onClick: () => save({ force: true }),
        disabled: !doc
      }),
      h(Btn, {
        icon: 'more',
        variant: 'ghost',
        ariaLabel: 'Más acciones',
        onClick: () => setMenu(menu === 'more' ? null : 'more')
      }),
      compact
        ? h(Btn, {
            icon: 'film',
            variant: 'ghost',
            ariaLabel: 'Medios',
            title: 'Medios · biblioteca del proyecto',
            onClick: () => {
              setLibOpen((prev) => !prev)
              setRailOpen(false)
            }
          })
        : null,
      compact
        ? h(Btn, {
            icon: 'panel',
            variant: 'ghost',
            ariaLabel: 'Propiedades',
            title: 'Escenas y propiedades',
            onClick: () => {
              setRailOpen((prev) => !prev)
              setLibOpen(false)
            }
          })
        : null,
      h(Btn, {
        icon: 'close',
        variant: 'ghost',
        ariaLabel: 'Cerrar editor de vídeo (Ctrl+Shift+E)',
        title: 'Cerrar (Ctrl+Shift+E)',
        label: compact ? undefined : 'Cerrar editor',
        onClick: () => {
          if (typeof onClose === 'function') onClose()
        }
      })
    )

  const stage = () => {
    if (phase === 'boot') {
      return h(
        'div',
        { className: 've-stage' },
        h('div', { className: 've-skel', style: { width: '100%', height: '100%', aspectRatio: orient.ratio } }),
        h('div', { className: 've-loadrow', style: { position: 'absolute' }, 'aria-live': 'polite' }, h(Spinner), 'Conectando con el servicio…')
      )
    }
    if (phase === 'loading') {
      return h(
        'div',
        { className: 've-stage' },
        h('div', { className: 've-skel', style: { width: '100%', height: '100%', aspectRatio: orient.ratio } }),
        h('div', { className: 've-loadrow', style: { position: 'absolute' }, 'aria-live': 'polite' }, h(Spinner), 'Cargando proyecto…')
      )
    }
    if (phase === 'noProject') {
      return h(
        'div',
        { className: 've-center' },
        h(
          EmptyState,
          { title: 'Todavía no hay proyecto abierto', body: 'Elige un proyecto de esta sesión o crea uno nuevo para montar tu vídeo.' },
          h(
            'div',
            { className: 've-es__actions' },
            h(Btn, { variant: 'outline', label: 'Elegir proyecto', onClick: () => setMenu('projects') }),
            h(Btn, { variant: 'primary', label: 'Crear proyecto', onClick: createProject })
          )
        )
      )
    }
    if (phase === 'offline' || phase === 'error') {
      return h(
        'div',
        { className: 've-center' },
        h(
          ErrorState,
          {
            title: 'No se pudo cargar el proyecto',
            body:
              phase === 'offline'
                ? `El servicio del editor no responde en ${serviceBase(ctx).replace(/^https?:\/\//, '')}. Tus medios no se han modificado.`
                : (loadError && loadError.message) || 'Error desconocido del servicio.'
          },
          h(Btn, { variant: 'outline', label: 'Reintentar', onClick: () => (doc ? openProject(doc.projectId) : loadProjects()) }),
          h(Btn, { variant: 'text', label: 'Volver al chat', onClick: goChat })
        )
      )
    }
    if (!doc) return h('div', { className: 've-stage' })
    if (!(doc.scenes || []).length) {
      return h(
        'div',
        { className: 've-stage' },
        h(
          'div',
          {
            className: `ve-drop${dialog === 'drop' ? ' ve-drop--active' : ''}`,
            onDragOver: (event) => {
              event.preventDefault()
              setDialog('drop')
            },
            onDragLeave: () => setDialog(null),
            onDrop: onDrop
          },
          h('div', { className: 've-es__icon' }, h(Icon, { name: 'upload' })),
          h('p', { className: 've-es__t' }, dialog === 'drop' ? 'Suelta para importar' : 'Arrastra clips, audio o capturas aquí'),
          h('p', { className: 've-es__b' }, 'PNG, JPG, MP4, MOV, MP3 y WAV · se importa a la carpeta concedida del proyecto.'),
          h(Btn, { variant: 'primary', label: 'Importar medios', onClick: importFolder })
        )
      )
    }
    return h(
      'div',
      { className: 've-stage' },
      h(
        'div',
        { className: 've-stage__bar' },
        h(Badge, { outline: true }, 'Escena'),
        h(Badge, { tone: 'accent' }, orient.short),
        h('span', { className: 've-stage__sp' }),
        h('span', { className: 've-stage__count' }, `${at.index + 1} / ${doc.scenes.length}`)
      ),
      h(
        'div',
        { className: 've-stage__canvas', ref: canvasRef },
        h(
          'div',
          { className: 've-frame', style: fitStyle },
          videoSrc
          ? activeKind === 'image'
            ? h('img', {
                src: videoSrc,
                alt: currentScene ? `Imagen de ${currentScene.name || 'la escena'}` : '',
                draggable: false
              })
            : h('video', {
              ref: videoRef,
              src: videoSrc,
              playsInline: true,
              preload: 'metadata',
              onTimeUpdate: onTime,
              onLoadedMetadata: () => {
                const video = videoRef.current
                if (!video || !currentScene) return
                try {
                  video.currentTime = Number(currentScene.in) + at.local
                } catch (error) {
                  /* metadatos aún no listos */
                }
              },
              'aria-label': `Vista previa de ${currentScene ? currentScene.name : 'la escena'}`
            })
          : null,
          guides ? h('div', { className: 've-guides', 'aria-hidden': 'true' }) : null,
          currentScene && captionOf(currentScene)
            ? h('div', { className: 've-cap' }, captionOf(currentScene))
            : null
        )
      )
    )
  }

  const transport = () =>
    h(
      'div',
      { className: 've-transport' },
      h(Btn, { icon: 'start', variant: 'ghost', ariaLabel: 'Ir al inicio', onClick: () => setCursor(0) }),
      h(Btn, {
        icon: 'prev',
        variant: 'ghost',
        ariaLabel: 'Escena anterior',
        disabled: at.index <= 0,
        onClick: () => {
          const row = rows[Math.max(0, at.index - 1)]
          if (row) {
            setCursor(row.start)
            setSelId(row.id)
          }
        }
      }),
      h(Btn, {
        icon: playing ? 'pause' : 'play',
        variant: 'ghost',
        ariaLabel: playing ? 'Pausar' : 'Reproducir',
        disabled: !doc || !(doc.scenes || []).length,
        onClick: () => setPlaying((prev) => !prev)
      }),
      h(Btn, {
        icon: 'next',
        variant: 'ghost',
        ariaLabel: 'Escena siguiente',
        disabled: at.index < 0 || at.index >= rows.length - 1,
        onClick: () => {
          const row = rows[Math.min(rows.length - 1, at.index + 1)]
          if (row) {
            setCursor(row.start)
            setSelId(row.id)
          }
        }
      }),
      h(Btn, { icon: 'end', variant: 'ghost', ariaLabel: 'Ir al final', onClick: () => setCursor(total) }),
      h('span', { className: 've-tc', title: 'Tiempo exacto (mm:ss.ms). Escribe uno a la derecha para saltar.' }, h('b', null, fmtTimecode(cursor)), ` / ${fmtTimecode(total)}`),
      h('input', {
        key: `goto-${Math.round(cursor * 1000)}`,
        className: 've-goto',
        defaultValue: '',
        placeholder: 'ir a…',
        inputMode: 'decimal',
        'aria-label': 'Ir al tiempo (mm:ss.ms)',
        onKeyDown: (event) => {
          if (event.key !== 'Enter') return
          const seconds = parseTimecode(event.target.value)
          if (seconds !== null) setCursor(clamp(seconds, 0, total))
          event.target.value = ''
        }
      }),
      h(
        'div',
        { className: 've-scrub' },
        h('input', {
          type: 'range',
          min: 0,
          max: Math.max(total, 0.001),
          step: frameStep,
          value: cursor,
          style: { '--ve-p': `${total ? (cursor / total) * 100 : 0}%` },
          'aria-label': 'Posición de reproducción',
          'aria-valuetext': `${fmtTimecode(cursor)} de ${fmtTimecode(total)}`,
          onChange: (event) => setCursor(Number(event.target.value))
        })
      ),
      h(Btn, { icon: 'scissors', variant: 'ghost', ariaLabel: 'Partir en el cursor', title: 'Partir · S', onClick: splitHere, disabled: !sel }),
      h(Btn, {
        icon: 'volume',
        variant: 'ghost',
        ariaLabel: muted ? 'Activar sonido' : 'Silenciar',
        onClick: () => {
          const next = !muted
          setMuted(next)
          if (ctx && ctx.storage && ctx.storage.set) ctx.storage.set('transport.muted', next)
        }
      })
    )

  const ruler = () => {
    const step = total > 90 ? 20 : total > 40 ? 10 : 5
    const marks = []
    for (let t = 0; t <= total + 0.01; t += step) {
      marks.push(h('span', { key: `m${t}`, style: { left: `${total ? (t / total) * 100 : 0}%` } }, `${Math.round(t)}s`))
    }
    return h('div', { className: 've-tl__ruler' }, marks)
  }

  const timelineBlock = () => {
    if (!doc || !(doc.scenes || []).length) return null
    return h(
      'div',
      { className: 've-tl' },
      ruler(),
      h(
        'div',
        { className: 've-tl__lane' },
        h('div', { className: 've-tl__gutter' }, h('span', null, 'V1'), h('span', null, 'A1')),
        h(
          'div',
          { className: 've-tl__tracks' },
          h(
            'div',
            { className: 've-tl__row', role: 'list', 'aria-label': `Línea de tiempo, ${total.toFixed(1)} segundos` },
            rows.map((row, index) =>
              h(
                'button',
                {
                  key: row.id,
                  type: 'button',
                  role: 'listitem',
                  className: `ve-clip${row.id === selId ? ' ve-clip--sel' : ''}`,
                  style: { flex: `${Math.max(row.duration, 0.1)} 1 0%` },
                  onClick: () => {
                    setSelId(row.id)
                    setCursor(row.start)
                  },
                  'aria-label': `Escena ${index + 1}, ${row.scene.name || 'sin nombre'}, ${row.duration.toFixed(1)} segundos`,
                  'aria-current': row.id === selId ? 'true' : undefined
                },
                h('span', { className: 've-clip__n' }, String(index + 1).padStart(2, '0')),
                h('span', { className: 've-clip__t' }, row.scene.name || `Escena ${index + 1}`),
                h('span', { className: 've-clip__d' }, `${fmtTime(row.duration)}`),
                row.id === selId
                  ? [
                      h('span', { key: 'l', className: 've-trim ve-trim--l', role: 'presentation' }),
                      h('span', { key: 'r', className: 've-trim ve-trim--r', role: 'presentation' })
                    ]
                  : null,
                row.scene.needsRelink ? h(Badge, { tone: 'warn' }, 'falta') : null
              )
            )
          ),
          h(
            'div',
            { className: 've-tl__row ve-tl__row--audio' },
            h(
              'span',
              { className: 've-wave', 'aria-hidden': 'true' },
              h('i', { style: { width: `${clamp((sel && sel.audio && sel.audio.volume) || 0, 0, 100)}%` } })
            ),
            h('small', null, sel ? `Audio ${(sel.audio && sel.audio.volume) || 0}%` : 'Audio'),
            sfxEvents.length
              ? h(
                  'div',
                  { className: 've-evs' },
                  sfxEvents.map((ev, index) =>
                    h(
                      'button',
                      {
                        key: ev.id,
                        type: 'button',
                        className: 've-ev',
                        style: { left: `${total ? clamp((Number(ev.at) || 0) / total, 0, 1) * 100 : 0}%` },
                        title: `Sonido ${index + 1} · ${fmtTimecode(ev.at)} · volumen ${ev.volume == null ? 100 : ev.volume}%`,
                        'aria-label': `Sonido ${index + 1} en ${fmtTimecode(ev.at)}`,
                        onClick: () => setCursor(clamp(Number(ev.at) || 0, 0, total))
                      },
                      '♪'
                    )
                  )
                )
              : null
          ),
          h('div', { className: 've-playhead', style: { '--ve-ph': `${total ? (cursor / total) * 100 : 0}%` }, 'aria-hidden': 'true' })
        )
      )
    )
  }

  const rail = () => {
    if (!doc) return null
    return h(
      'aside',
      { className: 've-rail', 'aria-label': 'Escenas y propiedades', style: compact && !railOpen ? { display: 'none' } : undefined },
      h(
        'div',
        { className: 've-rail__sec' },
        h(
          'div',
          { className: 've-rail__h' },
          h('span', { className: 've-rail__t' }, 'Escenas'),
          h(Badge, { outline: true }, String((doc.scenes || []).length)),
          h('span', { className: 've-spacer' }),
          h(Btn, { icon: 'upload', variant: 'ghost', ariaLabel: 'Importar medios', onClick: importFolder })
        ),
        h(
          'div',
          { className: 've-scenes', role: 'group', 'aria-label': 'Lista de escenas' },
          (doc.scenes || []).map((scene, index) =>
            h(
              'div',
              { key: scene.id, className: 've-scene-row' },
              h(
                'button',
                {
                  type: 'button',
                  className: 've-scene',
                  'aria-current': scene.id === selId ? 'true' : undefined,
                  'aria-label': `Escena ${index + 1}, ${scene.name || 'sin nombre'}, ${fmtTime(sceneDuration(scene))}`,
                  onClick: () => {
                    setSelId(scene.id)
                    const row = rows[index]
                    if (row) setCursor(row.start)
                  }
                },
                h('span', { className: 've-scene__grip', 'aria-hidden': 'true' }, h(Icon, { name: 'grip', size: 'sm' })),
                h('span', { className: 've-scene__n' }, String(index + 1).padStart(2, '0')),
                h('span', { className: 've-thumb', 'aria-hidden': 'true' }),
                h(
                  'span',
                  { className: 've-scene__m' },
                  h('span', { className: 've-scene__name' }, scene.name || `Escena ${index + 1}`),
                  h('span', { className: 've-scene__dur' }, `${fmtTime(sceneDuration(scene))}${captionOf(scene) ? ' · texto' : ''}${scene.needsRelink ? ' · falta medio' : ''}`)
                )
              ),
              h(
                'button',
                {
                  type: 'button',
                  className: 've-mv',
                  'aria-label': `Subir escena ${index + 1}`,
                  disabled: index === 0,
                  onClick: () => moveScene(index, -1)
                },
                h(Icon, { name: 'up', size: 'sm' })
              ),
              h(
                'button',
                {
                  type: 'button',
                  className: 've-mv',
                  'aria-label': `Bajar escena ${index + 1}`,
                  disabled: index === (doc.scenes || []).length - 1,
                  onClick: () => moveScene(index, 1)
                },
                h(Icon, { name: 'down', size: 'sm' })
              )
            )
          )
        ),
        h(
          'div',
          { style: { display: 'flex', gap: '4px', marginTop: '6px' } },
          h(Btn, { variant: 'outline', label: 'Añadir escena', onClick: importFolder, size: 'sm' })
        )
      ),
      h(
        'div',
        { className: 've-rail__sec' },
        h(
          'div',
          { className: 've-rail__h' },
          h('span', { className: 've-rail__t' }, 'Propiedades'),
          h(Badge, { outline: true }, sel ? `Escena ${selIndex + 1}` : '—')
        ),
        !sel
          ? h(EmptyState, {
              title: 'Elige una escena',
              body: 'Selecciona una escena de la lista o de la línea de tiempo para editar su texto, volumen y encuadre.'
            })
          : h(
              'div',
              { className: 've-props' },
              h(
                'label',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Texto en pantalla', h('span', { className: 've-counter' }, `${captionOf(sel).length}/${MAX_CAPTION}`)),
                h('textarea', {
                  className: 've-textarea',
                  value: captionOf(sel),
                  maxLength: MAX_CAPTION,
                  placeholder: 'Se muestra al inicio de la escena',
                  onChange: (event) => writeCaption(event.target.value),
                  onBlur: () => save()
                })
              ),
              (() => {
                const item = textItemOf(sel) || {}
                const hasText = !!String(captionOf(sel)).trim()
                const anim = item.animation && typeof item.animation === 'object' ? item.animation : {}
                const fields = [
                  {
                    key: 'size',
                    label: 'Tamaño',
                    type: 'number',
                    min: TEXT_SIZE.min,
                    max: TEXT_SIZE.max,
                    step: 1,
                    value: Number.isFinite(Number(item.size)) ? Number(item.size) : TEXT_SIZE.default,
                    aria: 'Tamaño del texto en puntos'
                  },
                  { key: 'color', label: 'Color', type: 'color', value: hexOr(item.color, TEXT_COLOR_DEFAULT), aria: 'Color del texto' },
                  {
                    key: 'border',
                    label: 'Borde',
                    type: 'number',
                    min: TEXT_BORDER.min,
                    max: TEXT_BORDER.max,
                    step: 1,
                    value: Number.isFinite(Number(item.border)) ? Number(item.border) : TEXT_BORDER.default,
                    aria: 'Grosor del borde del texto'
                  },
                  {
                    key: 'shadow',
                    label: 'Sombra',
                    type: 'number',
                    min: TEXT_SHADOW.min,
                    max: TEXT_SHADOW.max,
                    step: 1,
                    value: Number.isFinite(Number(item.shadow)) ? Number(item.shadow) : TEXT_SHADOW.default,
                    aria: 'Grosor de la sombra del texto'
                  }
                ]
                return h(
                  'div',
                  { className: 've-f' },
                  h('span', { className: 've-f__l' }, 'Estilo del texto'),
                  h(
                    'div',
                    { className: 've-tex' },
                    fields.map((field) =>
                      styleField(
                        field.key,
                        field.label,
                        h('input', {
                          className: 've-tex__in',
                          type: field.type,
                          min: field.type === 'color' ? undefined : field.min,
                          max: field.type === 'color' ? undefined : field.max,
                          step: field.type === 'color' ? undefined : field.step,
                          value: field.value,
                          disabled: !hasText,
                          'aria-label': field.aria,
                          title: hasText ? undefined : 'Escribe un texto en la escena para darle estilo',
                          onChange: (event) => {
                            const raw = event.target.value
                            if (field.type === 'color') {
                              setTextStyle({ color: hexOr(raw, TEXT_COLOR_DEFAULT) })
                              return
                            }
                            const value = Number(raw)
                            if (!Number.isFinite(value)) return
                            setTextStyle({ [field.key]: Math.round(clamp(value, field.min, field.max)) })
                          },
                          onBlur: () => save()
                        })
                      )
                    )
                  ),
                  h(
                    'div',
                    { className: 've-f__row' },
                    h(
                      'label',
                      { className: 've-tex__f' },
                      h('span', { className: 've-tex__k' }, 'Entrada'),
                      h(
                        'select',
                        {
                          className: 've-tex__in',
                          value: anim.in || 'none',
                          disabled: !hasText,
                          'aria-label': 'Animación de entrada del texto',
                          onChange: (event) => setTextAnimation('in', event.target.value)
                        },
                        TEXT_ANIMATIONS.map((opt) => h('option', { key: opt.id, value: opt.id }, opt.label))
                      )
                    ),
                    h(
                      'label',
                      { className: 've-tex__f' },
                      h('span', { className: 've-tex__k' }, 'Salida'),
                      h(
                        'select',
                        {
                          className: 've-tex__in',
                          value: anim.out || 'none',
                          disabled: !hasText,
                          'aria-label': 'Animación de salida del texto',
                          onChange: (event) => setTextAnimation('out', event.target.value)
                        },
                        TEXT_ANIMATIONS.map((opt) => h('option', { key: opt.id, value: opt.id }, opt.label))
                      )
                    )
                  ),
                  h(
                    'span',
                    { className: 've-f__h' },
                    hasText ? 'Tamaño, color, borde, sombra y animación de este texto.' : 'Escribe un texto para darle estilo.'
                  )
                )
              })(),
              h(
                'div',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Volumen'),
                h(
                  'div',
                  { className: 've-volrow' },
                  h('input', {
                    type: 'range',
                    min: 0,
                    max: 100,
                    step: 5,
                    value: (sel.audio && sel.audio.volume) || 0,
                    style: { '--ve-p': `${(sel.audio && sel.audio.volume) || 0}%` },
                    'aria-label': 'Volumen de la escena',
                    'aria-valuetext': `${(sel.audio && sel.audio.volume) || 0} %`,
                    onChange: (event) => setSceneVolume(event.target.value)
                  }),
                  h('span', { className: 've-volval' }, `${(sel.audio && sel.audio.volume) || 0} %`)
                ),
                h(Btn, {
                  variant: 'text',
                  size: 'sm',
                  label: ((sel.audio && sel.audio.volume) || 0) === 0 ? 'Activar el sonido de la escena' : 'Silenciar la escena',
                  ariaLabel: ((sel.audio && sel.audio.volume) || 0) === 0 ? 'Activar el sonido de la escena' : 'Silenciar la escena',
                  onClick: () => setSceneVolume(((sel.audio && sel.audio.volume) || 0) === 0 ? 100 : 0)
                })
              ),
              h(
                'div',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Orientación'),
                h(
                  'div',
                  { className: 've-seg', role: 'group', 'aria-label': 'Orientación del vídeo' },
                  ['h', 'v'].map((id) =>
                    h(
                      'button',
                      {
                        key: id,
                        type: 'button',
                        'aria-pressed': (doc.orientation || 'h') === id,
                        onClick: () => setOrientation(id)
                      },
                      ORIENTATIONS[id].label
                    )
                  )
                ),
                h('span', { className: 've-f__h' }, 'Vertical recorta los bordes laterales.')
              ),
              h(
                'div',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Transición de entrada'),
                h(
                  'select',
                  {
                    className: 've-select',
                    value: parseTransition(sel.transition).style,
                    disabled: selIndex === 0,
                    'aria-label': 'Estilo de la transición de entrada',
                    title: selIndex === 0 ? 'La primera escena no tiene transición de entrada' : undefined,
                    onChange: (event) => setTransitionStyle(event.target.value)
                  },
                  transitionList.map((item) => h('option', { key: item.id, value: item.id }, item.label))
                ),
                h(
                  'div',
                  { className: 've-volrow' },
                  h('input', {
                    type: 'range',
                    min: TRANSITION_MIN_S,
                    max: Math.max(TRANSITION_MIN_S, fadeLimit),
                    step: 0.1,
                    value: Math.min(parseTransition(sel.transition).seconds, Math.max(TRANSITION_MIN_S, fadeLimit)),
                    disabled: selIndex === 0 || parseTransition(sel.transition).style === 'none' || fadeLimit < TRANSITION_MIN_S,
                    'aria-label': 'Duración de la transición en segundos',
                    'aria-valuetext': `${fmtSec(parseTransition(sel.transition).seconds)} s`,
                    onChange: (event) => setTransitionSeconds(event.target.value)
                  }),
                  h('span', { className: 've-volval' }, `${fmtSec(parseTransition(sel.transition).seconds)} s`)
                ),
                h(
                  'span',
                  { className: 've-f__h' },
                  selIndex === 0
                    ? 'La escena 1 no lleva transición de entrada.'
                    : fadeLimit < TRANSITION_MIN_S
                      ? 'La escena es demasiado corta para cruzarse con la anterior.'
                      : parseTransition(sel.transition).style === 'none'
                        ? 'Corte seco: entra sin cruce.'
                        : `Se cruza con la escena anterior durante ${fmtSec(parseTransition(sel.transition).seconds)} s (máximo ${fmtSec(fadeLimit)} s aquí).`
                )
              ),
              h(
                'div',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Entrada / Salida'),
                h(
                  'div',
                  { className: 've-f__row' },
                  h(
                    'span',
                    { className: 've-tcout' },
                    h('input', {
                      value: Number(sel.in).toFixed(2),
                      inputMode: 'decimal',
                      'aria-label': 'Entrada de la escena en segundos',
                      onChange: (event) => {
                        const value = Number(String(event.target.value).replace(',', '.'))
                        if (Number.isFinite(value) && value >= 0) setIn(value)
                      },
                      onBlur: () => save()
                    }),
                    h('small', null, 's')
                  ),
                  h(
                    'span',
                    { className: 've-tcout' },
                    h('input', {
                      value: Number(sel.out).toFixed(2),
                      inputMode: 'decimal',
                      'aria-label': 'Salida de la escena en segundos',
                      onChange: (event) => {
                        const value = Number(String(event.target.value).replace(',', '.'))
                        if (Number.isFinite(value) && value > Number(sel.in)) setOut(value)
                      },
                      onBlur: () => save()
                    }),
                    h('small', null, 's')
                  )
                ),
                sceneDuration(sel) < MIN_SCENE
                  ? h('span', { className: 've-f__err', role: 'alert' }, 'La salida debe ser al menos 0,3 s después de la entrada.')
                  : h('span', { className: 've-f__h' }, `Duración ${fmtTime(sceneDuration(sel))}`)
              ),
              (() => {
                const filters = sel.filters && typeof sel.filters === 'object' ? sel.filters : {}
                const active = Object.keys(cleanFilters(filters)).length
                return h(
                  'div',
                  { className: 've-f' },
                  h('span', { className: 've-f__l' }, 'Filtros', active ? h(Badge, { outline: true }, String(active)) : null),
                  FILTER_SLIDERS.map((slider) => {
                    const raw = filters[slider.key]
                    const value = Number.isFinite(Number(raw)) ? Number(raw) : FILTER_DEFAULTS[slider.key]
                    const text = `${fmtNum(value)}${slider.suffix ? ` ${slider.suffix}` : ''}`
                    return h(
                      'div',
                      { key: slider.key, className: 've-f' },
                      h('span', { className: 've-f__l' }, slider.label),
                      h(
                        'div',
                        { className: 've-volrow' },
                        h('input', {
                          type: 'range',
                          min: slider.min,
                          max: slider.max,
                          step: slider.step,
                          value,
                          style: { '--ve-p': fillPercent(value, slider.min, slider.max) },
                          'aria-label': `${slider.label} de la escena`,
                          'aria-valuetext': text,
                          onChange: (event) => setFilter(slider.key, event.target.value),
                          onBlur: () => save()
                        }),
                        h('span', { className: 've-volval' }, text)
                      )
                    )
                  }),
                  h(
                    'div',
                    { className: 've-mus__chks' },
                    FILTER_FLAGS.map((flag) =>
                      h(
                        'label',
                        { key: flag.key, className: 've-mus__chk' },
                        h('input', {
                          type: 'checkbox',
                          checked: !!filters[flag.key],
                          'aria-label': flag.label,
                          onChange: (event) => setFilterFlag(flag.key, event.target.checked)
                        }),
                        h('span', null, flag.label)
                      )
                    )
                  ),
                  h(Btn, {
                    variant: 'text',
                    size: 'sm',
                    label: 'Restablecer filtros',
                    disabled: !active,
                    onClick: resetFilters
                  })
                )
              })(),
              (() => {
                const motion = sel.kenBurns && typeof sel.kenBurns === 'object' ? sel.kenBurns : null
                const speed = sceneSpeed(sel)
                const visible = visibleDuration(sel)
                const zoom = motion && Number.isFinite(Number(motion.zoom)) ? Number(motion.zoom) : KEN_BURNS.zoom
                return h(
                  'div',
                  { className: 've-f' },
                  h('span', { className: 've-f__l' }, 'Movimiento'),
                  h(
                    'label',
                    {
                      className: `ve-mus__chk${selIsImage ? '' : ' ve-mus__chk--off'}`,
                      title: selIsImage ? 'Zoom lento sobre la imagen' : 'Solo imágenes'
                    },
                    h('input', {
                      type: 'checkbox',
                      checked: !!motion,
                      disabled: !selIsImage,
                      'aria-label': 'Ken Burns en la imagen',
                      onChange: (event) => toggleKenBurns(event.target.checked)
                    }),
                    h('span', null, 'Ken Burns')
                  ),
                  selIsImage
                    ? motion
                      ? h(
                          'div',
                          { className: 've-f' },
                          h('span', { className: 've-f__l' }, 'Zoom'),
                          h(
                            'div',
                            { className: 've-volrow' },
                            h('input', {
                              type: 'range',
                              min: KEN_BURNS.minZoom,
                              max: KEN_BURNS.maxZoom,
                              step: 0.05,
                              value: zoom,
                              style: { '--ve-p': fillPercent(zoom, KEN_BURNS.minZoom, KEN_BURNS.maxZoom) },
                              'aria-label': 'Zoom de Ken Burns',
                              'aria-valuetext': `×${fmtNum(zoom)}`,
                              onChange: (event) => setKenBurns({ zoom: event.target.value }),
                              onBlur: () => save()
                            }),
                            h('span', { className: 've-volval' }, `×${fmtNum(zoom)}`)
                          ),
                          h(
                            'label',
                            { className: 've-f' },
                            h('span', { className: 've-f__l' }, 'Desplazamiento'),
                            h(
                              'select',
                              {
                                className: 've-select',
                                value: motion.pan || KEN_BURNS.pan,
                                'aria-label': 'Dirección del desplazamiento de Ken Burns',
                                onChange: (event) => setKenBurns({ pan: event.target.value })
                              },
                              PAN_OPTIONS.map((opt) => h('option', { key: opt.id, value: opt.id }, opt.label))
                            )
                          )
                        )
                      : h('span', { className: 've-f__h' }, 'Actívalo para un zoom lento sobre la imagen.')
                    : h('span', { className: 've-f__h' }, 'Solo imágenes'),
                  h(
                    'div',
                    { className: 've-f' },
                    h('span', { className: 've-f__l' }, 'Velocidad'),
                    h(
                      'div',
                      { className: 've-volrow' },
                      h('input', {
                        type: 'range',
                        min: SCENE_SPEED.min,
                        max: SCENE_SPEED.max,
                        step: 0.05,
                        value: speed,
                        style: { '--ve-p': fillPercent(speed, SCENE_SPEED.min, SCENE_SPEED.max) },
                        'aria-label': 'Velocidad de la escena',
                        'aria-valuetext': `×${fmtNum(speed)}`,
                        onChange: (event) => setSpeed(event.target.value),
                        onBlur: () => save()
                      }),
                      h('span', { className: 've-volval' }, `×${fmtNum(speed)}`)
                    ),
                    h('span', { className: 've-f__h' }, `Duración visible ${fmtTime(visible)} a esta velocidad.`)
                  )
                )
              })(),
              missing.length
                ? h(
                    'div',
                    { className: 've-f' },
                    h(Badge, { tone: 'warn' }, `Falta ${missing.length} medio${missing.length > 1 ? 's' : ''}`),
                    h(Btn, { variant: 'text', label: 'Volver a vincular', onClick: importFolder })
                  )
                : null,
              h(Btn, {
                variant: 'text',
                label: 'Reemplazar medio',
                title: 'Cambia el archivo de la escena sin tocar in/out',
                onClick: () => {
                  setDialog({ kind: 'picker' })
                  openPicker('replace', sel.id)
                }
              }),
              h(Btn, { variant: 'text', label: 'Restablecer escena', onClick: () => resetScene(sel) })
            )
      ),
      h(
        'div',
        { className: 've-rail__sec ve-sfx', 'aria-label': 'Sonidos y voz' },
        h(
          'div',
          { className: 've-rail__h' },
          h('span', { className: 've-rail__t' }, 'Sonidos y voz'),
          h(Badge, { outline: true }, String(sfxEvents.length))
        ),
        h(
          'div',
          { className: 've-props' },
          !audioAssets.length
            ? h('span', { className: 've-f__h' }, 'Importa o genera audios para colocarlos en la línea de tiempo.')
            : h(Btn, {
                variant: 'outline',
                size: 'sm',
                label: `Añadir sonido en ${fmtTimecode(cursor)}`,
                ariaLabel: 'Añadir sonido en el cursor',
                onClick: () => addEventAtCursor((audioAssets.find((item) => !music || item.id !== music.assetId) || audioAssets[0]).id)
              }),
          sfxEvents.map((ev, index) =>
            h(
              'div',
              { key: ev.id, className: 've-props ve-sfx__row' },
              h(
                'label',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, `Sonido ${index + 1}`),
                h(
                  'select',
                  {
                    className: 've-select',
                    value: ev.assetId,
                    'aria-label': `Archivo del sonido ${index + 1}`,
                    onChange: (event) => setEvent(ev.id, { assetId: event.target.value })
                  },
                  audioAssets.map((item) => h('option', { key: item.id, value: item.id }, baseName(item.path) || item.id))
                )
              ),
              h(
                'div',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Empieza en (mm:ss.ms)'),
                h('input', {
                  key: `${ev.id}:${ev.at}`,
                  className: 've-goto',
                  style: { width: '100%' },
                  defaultValue: fmtTimecode(ev.at),
                  inputMode: 'decimal',
                  'aria-label': `Inicio del sonido ${index + 1}`,
                  onBlur: (event) => commitEventAt(ev.id, event.target.value),
                  onKeyDown: (event) => {
                    if (event.key === 'Enter') event.target.blur()
                  }
                })
              ),
              h(
                'div',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Volumen'),
                h(
                  'div',
                  { className: 've-volrow' },
                  h('input', {
                    type: 'range',
                    min: 0,
                    max: 100,
                    step: 5,
                    value: ev.volume == null ? 100 : ev.volume,
                    'aria-label': `Volumen del sonido ${index + 1}`,
                    onChange: (event) => setEvent(ev.id, { volume: clamp(Math.round(Number(event.target.value) / 5) * 5, 0, 100) })
                  }),
                  h('span', { className: 've-volval' }, `${ev.volume == null ? 100 : ev.volume} %`)
                )
              ),
              h(Btn, { variant: 'text', size: 'sm', label: 'Quitar sonido', ariaLabel: `Quitar sonido ${index + 1}`, onClick: () => removeEvent(ev.id) })
            )
          )
        )
      ),
      h(
        'div',
        { className: 've-rail__sec ve-mus', 'aria-label': 'Música de fondo' },
        h(
          'div',
          { className: 've-rail__h' },
          h('span', { className: 've-rail__t' }, 'Música'),
          h(Badge, { outline: true }, music ? 'Fondo' : '—')
        ),
        !audioAssets.length
          ? h(
              'div',
              { className: 've-mus__empty' },
              h('span', { className: 've-f__h' }, 'Importa un audio para usarlo como música.'),
              h(Btn, { variant: 'outline', size: 'sm', label: 'Importar medios', onClick: importFolder, disabled: !doc })
            )
          : h(
              'div',
              { className: 've-props' },
              h(
                'label',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Pista'),
                h(
                  'select',
                  {
                    className: 've-select',
                    value: music ? music.assetId : '',
                    'aria-label': 'Música de fondo del proyecto',
                    onChange: (event) => chooseMusic(event.target.value)
                  },
                  h('option', { value: '' }, 'Sin música'),
                  audioAssets.map((item) =>
                    h('option', { key: item.id, value: item.id }, baseName(item.path) || item.id)
                  )
                ),
                music
                  ? h('span', { className: 've-f__h' }, `Suena de fondo durante ${fmtTime(total)}.`)
                  : h('span', { className: 've-f__h' }, 'Sin música: el vídeo lleva solo el audio de las escenas.')
              ),
              music
                ? h(
                    'div',
                    { className: 've-f' },
                    h('span', { className: 've-f__l' }, 'Volumen de la música'),
                    h(
                      'div',
                      { className: 've-volrow' },
                      h('input', {
                        type: 'range',
                        min: 0,
                        max: 100,
                        step: 5,
                        value: typeof music.volume === 'number' ? music.volume : MUSIC_DEFAULTS.volume,
                        'aria-label': 'Volumen de la música',
                        'aria-valuetext': `${typeof music.volume === 'number' ? music.volume : MUSIC_DEFAULTS.volume} %`,
                        onChange: (event) => setMusic({ volume: clamp(Math.round(Number(event.target.value) / 5) * 5, 0, 100) })
                      }),
                      h('span', { className: 've-volval' }, `${typeof music.volume === 'number' ? music.volume : MUSIC_DEFAULTS.volume} %`)
                    )
                  )
                : null,
              music
                ? h(
                    'div',
                    { className: 've-f' },
                    h('span', { className: 've-f__l' }, 'Fundido de entrada / salida'),
                    h(
                      'div',
                      { className: 've-f__row' },
                      h(
                        'span',
                        { className: 've-tcout' },
                        h('input', {
                          value: fmtSec(typeof music.fadeIn === 'number' ? music.fadeIn : 0),
                          inputMode: 'decimal',
                          'aria-label': 'Fundido de entrada de la música en segundos',
                          onChange: (event) => setMusicFade('fadeIn', event.target.value),
                          onBlur: () => save()
                        }),
                        h('small', null, 's')
                      ),
                      h(
                        'span',
                        { className: 've-tcout' },
                        h('input', {
                          value: fmtSec(typeof music.fadeOut === 'number' ? music.fadeOut : 0),
                          inputMode: 'decimal',
                          'aria-label': 'Fundido de salida de la música en segundos',
                          onChange: (event) => setMusicFade('fadeOut', event.target.value),
                          onBlur: () => save()
                        }),
                        h('small', null, 's')
                      )
                    ),
                    h('span', { className: 've-f__h' }, 'De 0 a 10 s; 0 la deja sin fundido.')
                  )
                : null,
              music
                ? h(
                    'div',
                    { className: 've-mus__chks' },
                    h(
                      'label',
                      { className: 've-mus__chk' },
                      h('input', {
                        type: 'checkbox',
                        checked: !!music.loop,
                        onChange: (event) => setMusic({ loop: event.target.checked })
                      }),
                      h('span', null, 'Repetir en bucle')
                    ),
                    h(
                      'label',
                      { className: 've-mus__chk' },
                      h('input', {
                        type: 'checkbox',
                        checked: !!music.ducking,
                        onChange: (event) => setMusic({ ducking: event.target.checked })
                      }),
                      h('span', null, 'Bajar bajo la voz (ducking)')
                    )
                  )
                : null,
              h(
                'label',
                { className: 've-mus__chk' },
                h('input', {
                  type: 'checkbox',
                  checked: !!(doc.audio && doc.audio.normalize),
                  onChange: (event) => setNormalize(event.target.checked)
                }),
                h('span', null, 'Normalizar audio del proyecto')
              ),
              h(Btn, {
                variant: 'text',
                label: 'Quitar música',
                disabled: !music,
                title: music ? 'Elimina la música del proyecto' : 'No hay música asignada',
                onClick: removeMusic
              })
            )
      ),
      h(
        'div',
        { className: 've-rail__sec', 'aria-label': 'Logo del proyecto' },
        h(
          'div',
          { className: 've-rail__h' },
          h('span', { className: 've-rail__t' }, 'Logo'),
          h(Badge, { outline: true }, logo ? 'Marca' : '—')
        ),
        !imageAssets.length
          ? h(
              'div',
              { className: 've-mus__empty' },
              h('span', { className: 've-f__h' }, 'Importa una imagen para usarla como logo.'),
              h(Btn, { variant: 'outline', size: 'sm', label: 'Importar medios', onClick: importFolder, disabled: !doc })
            )
          : h(
              'div',
              { className: 've-props' },
              h(
                'label',
                { className: 've-f' },
                h('span', { className: 've-f__l' }, 'Imagen'),
                h(
                  'select',
                  {
                    className: 've-select',
                    value: logo ? logo.assetId : '',
                    'aria-label': 'Imagen del logo del proyecto',
                    onChange: (event) => {
                      if (event.target.value) setLogo({ assetId: event.target.value })
                      else removeLogo()
                    }
                  },
                  h('option', { value: '' }, 'Sin logo'),
                  imageAssets.map((item) => h('option', { key: item.id, value: item.id }, baseName(item.path) || item.id))
                ),
                h('span', { className: 've-f__h' }, 'Marca de agua sobre todo el vídeo.')
              ),
              logo
                ? h(
                    'label',
                    { className: 've-f' },
                    h('span', { className: 've-f__l' }, 'Posición'),
                    h(
                      'select',
                      {
                        className: 've-select',
                        value: logo.position || LOGO_DEFAULTS.position,
                        'aria-label': 'Posición del logo',
                        onChange: (event) => setLogo({ position: event.target.value })
                      },
                      LOGO_POSITIONS.map((opt) => h('option', { key: opt.id, value: opt.id }, opt.label))
                    )
                  )
                : null,
              logo
                ? h(
                    'div',
                    { className: 've-f' },
                    h('span', { className: 've-f__l' }, 'Opacidad'),
                    h(
                      'div',
                      { className: 've-volrow' },
                      h('input', {
                        type: 'range',
                        min: LOGO_LIMITS.opacity[0],
                        max: LOGO_LIMITS.opacity[1],
                        step: 0.05,
                        value: typeof logo.opacity === 'number' ? logo.opacity : LOGO_DEFAULTS.opacity,
                        style: {
                          '--ve-p': fillPercent(
                            typeof logo.opacity === 'number' ? logo.opacity : LOGO_DEFAULTS.opacity,
                            LOGO_LIMITS.opacity[0],
                            LOGO_LIMITS.opacity[1]
                          )
                        },
                        'aria-label': 'Opacidad del logo',
                        'aria-valuetext': `${Math.round((typeof logo.opacity === 'number' ? logo.opacity : LOGO_DEFAULTS.opacity) * 100)} %`,
                        onChange: (event) => setLogo({ opacity: event.target.value }),
                        onBlur: () => save()
                      }),
                      h(
                        'span',
                        { className: 've-volval' },
                        `${Math.round((typeof logo.opacity === 'number' ? logo.opacity : LOGO_DEFAULTS.opacity) * 100)} %`
                      )
                    )
                  )
                : null,
              logo
                ? h(
                    'div',
                    { className: 've-f' },
                    h('span', { className: 've-f__l' }, 'Escala'),
                    h(
                      'div',
                      { className: 've-volrow' },
                      h('input', {
                        type: 'range',
                        min: LOGO_LIMITS.scale[0],
                        max: LOGO_LIMITS.scale[1],
                        step: 0.01,
                        value: typeof logo.scale === 'number' ? logo.scale : LOGO_DEFAULTS.scale,
                        style: {
                          '--ve-p': fillPercent(
                            typeof logo.scale === 'number' ? logo.scale : LOGO_DEFAULTS.scale,
                            LOGO_LIMITS.scale[0],
                            LOGO_LIMITS.scale[1]
                          )
                        },
                        'aria-label': 'Escala del logo',
                        'aria-valuetext': `${Math.round((typeof logo.scale === 'number' ? logo.scale : LOGO_DEFAULTS.scale) * 100)} %`,
                        onChange: (event) => setLogo({ scale: event.target.value }),
                        onBlur: () => save()
                      }),
                      h(
                        'span',
                        { className: 've-volval' },
                        `${Math.round((typeof logo.scale === 'number' ? logo.scale : LOGO_DEFAULTS.scale) * 100)} %`
                      )
                    )
                  )
                : null,
              h(Btn, { variant: 'text', label: 'Quitar logo', disabled: !logo, onClick: removeLogo })
            )
      )
    )
  }

  const resetScene = (scene) => {
    mutate((draft) => {
      const target = draft.scenes.find((item) => item.id === scene.id)
      target.audio = { ...(target.audio || {}), volume: 100, fadeIn: 0, fadeOut: 0 }
      target.transition = 'none'
      target.text = []
      return draft
    })
    setNotice('Escena restablecida.')
  }

  const footer = () =>
    h(
      'footer',
      { className: 've-ftr' },
      h(Btn, { variant: 'outline', icon: 'upload', label: 'Importar medios', onClick: importFolder, disabled: !doc }),
      h('span', { className: 've-ftr__hint', 'aria-live': 'polite' }, notice || queueLabel()),
      h('span', { className: 've-spacer' }),
      !compact ? h(Btn, { variant: 'text', label: 'Ver chat', onClick: goChat }) : null,
      h(Btn, {
        variant: 'primary',
        icon: 'download',
        label: `Exportar ${doc ? `${doc.height}p · ${docFps}` : 'MP4'}`,
        disabled: !canExport,
        title: canExport ? 'Exportar MP4' : missing.length ? 'Falta un medio' : 'Guarda o añade escenas primero',
        onClick: () => setDialog({ kind: 'exportForm' })
      })
    )

  function queueLabel() {
    if (job && ['queued', 'running', 'probing', 'rendering', 'validating', 'promoting'].includes(job.state)) {
      return typeof job.progress === 'number' ? `Exportando ${Math.round(job.progress)} %` : 'Exportando…'
    }
    if (job && job.state === 'failed') return 'La exportación falló'
    return 'Sin trabajos en cola'
  }

  useEffect(() => {
    if (!modelTip) return undefined
    const timer = setTimeout(() => setModelTip(false), 4000)
    return () => clearTimeout(timer)
  }, [modelTip])

  function goChat() {
    // No navegar: el chat sigue vivo al lado/arriba del editor. Solo enfocamos
    // su compositor para que el usuario escriba sin perder el panel.
    try {
      if (host && host.composer && typeof host.composer.focus === 'function') {
        host.composer.focus(null)
        setNotice('Chat enfocado. El editor sigue abierto.')
      } else {
        setNotice('Escribe en el chat de arriba; el editor sigue abierto.')
      }
    } catch (error) {
      setNotice('Escribe en el chat de arriba; el editor sigue abierto.')
    }
  }

  // --- chat vivo -----------------------------------------------------------
  // El chat es la otra mitad del editor: el pane sabe a qué sesión pertenece
  // (host.state) y devuelve el resultado al compositor del chat (host.composer).

  const shortChat = (id) =>
    String(id || '')
      .replace(/^sess(ion)?[_-]?/i, '')
      .slice(0, 8)
      .replace(/[_-]+$/, '')

  function exportSummary() {
    const path = (job && job.outputPath) || ''
    const bytes = (job && job.outputBytes) || 0
    const lines = ['Vídeo exportado con el editor de Hermes']
    if (doc) lines.push(`${doc.title || 'Vídeo'} — ${fmtTime(total)}, ${doc.width}×${doc.height}, ${docFps} fps`)
    if (bytes) lines.push(`Tamaño: ${fmtBytes(bytes)}`)
    if (path) lines.push(`Archivo: ${path}`)
    if (doc) lines.push(`Proyecto: ${doc.projectId} · revisión ${doc.revision}`)
    return lines.join('\n')
  }

  async function addToChat(text) {
    const body = String(text || '').trim()
    if (!body) return
    const composer = host && host.composer
    if (!composer || typeof composer.insertText !== 'function') {
      setChatMsg('Esta versión de Hermes no expone el compositor del chat; copia la ruta y pégala.')
      return
    }
    try {
      const ok = await composer.insertText(sessionId, body, { mode: 'block' })
      if (!ok) {
        setChatMsg('No hay un chat abierto donde insertar. Abre un chat y reintenta.')
        return
      }
      setChatMsg('Añadido al chat de Hermes. Revísalo y pulsa enviar.')
      if (typeof composer.focus === 'function') composer.focus(sessionId)
    } catch (error) {
      setChatMsg(`No se pudo insertar en el chat: ${(error && error.message) || error}`)
    }
  }

  async function copyText(text) {
    if (!text) {
      setChatMsg('Todavía no hay una ruta que copiar.')
      return
    }
    const door = ctx && ctx.os
    if (door && typeof door.writeClipboard === 'function') {
      try {
        const ok = await door.writeClipboard(String(text))
        setChatMsg(ok ? 'Ruta copiada al portapapeles.' : 'El sistema no permitió copiar la ruta.')
      } catch (error) {
        setChatMsg(`No se pudo copiar: ${(error && error.message) || error}`)
      }
      return
    }
    setChatMsg('Esta versión no permite copiar desde el panel; selecciona la ruta.')
  }

  async function createProject() {
    try {
      const payload = await request(ctx, '/projects', {
        method: 'POST',
        body: { title: 'Vídeo sin título', session_id: sessionId, cwd }
      })
      await loadProjects()
      await openProject(payload.projectId)
    } catch (error) {
      setNotice(error.message)
    }
  }

  function onDrop(event) {
    event.preventDefault()
    setDialog(null)
    const files = Array.from((event.dataTransfer && event.dataTransfer.files) || [])
    if (!files.length) return
    const allowed = /\.(png|jpe?g|mp4|mov|m4v|mp3|wav)$/i
    const rejected = files.filter((file) => !allowed.test(file.name))
    if (rejected.length) setNotice(`Formato no admitido: ${rejected.map((f) => f.name.split('.').pop()).join(', ')}`)
    const usable = files.filter((file) => allowed.test(file.name) && file.path)
    if (!usable.length) {
      if (!rejected.length) setNotice('Este build no expone la ruta del archivo: usa «Importar medios».')
      return
    }
    ;(async () => {
      let imported = 0
      for (const file of usable) {
        try {
          const payload = await request(ctx, `/projects/${encodeURIComponent(doc.projectId)}/media`, {
            method: 'POST',
            body: { path: String(file.path).replace(/\\/g, '/') }
          })
          setDoc(payload.project)
          setMedia(payload.media || [])
          imported += 1
        } catch (error) {
          setNotice(error.message)
        }
      }
      setNotice(`${imported} de ${usable.length} archivo(s) importados.`)
    })()
  }

  // -------------------------------------------------------------- diálogos

  const dialogs = () => {
    if (!dialog) return null
    if (dialog === 'drop') return null
    if (dialog.kind === 'projects') {
      return h(
        Dialog,
        {
          title: 'Tus proyectos',
          onClose: () => setDialog(null),
          footer: [
            h(Btn, { key: 'c', variant: 'text', label: 'Cerrar', onClick: () => setDialog(null) }),
            h(Btn, { key: 'n', variant: 'primary', label: 'Crear proyecto', onClick: createProject })
          ]
        },
        h(
          'div',
          { className: 've-list' },
          projects.length
            ? projects.map((item) =>
                h(
                  'button',
                  {
                    key: item.projectId,
                    type: 'button',
                    className: 've-file',
                    onClick: () => {
                      setDialog(null)
                      openProject(item.projectId)
                    }
                  },
                  h(Icon, { name: 'film', size: 'sm' }),
                  h('span', { className: 've-file__n' }, item.title || item.projectId),
                  h('span', { className: 've-file__s' }, `Rev ${item.revision}`)
                )
              )
            : h('p', { className: 've-dialog__b', style: { padding: '8px' } }, 'No hay proyectos todavía.')
        )
      )
    }
    if (dialog.kind === 'exportForm') {
      return h(
        Dialog,
        {
          title: 'Exportar vídeo',
          body: `${fmtTime(total)} · ${doc.width}×${doc.height} · ${docFps} fps · MP4 (H.264 + AAC)`,
          onClose: () => setDialog(null),
          footer: [
            h(Btn, { key: 'c', variant: 'outline', label: 'Cancelar', onClick: () => setDialog(null) }),
            h(Btn, {
              key: 'e',
              variant: 'primary',
              label: 'Exportar',
              disabled: !!(presetPicked && presetPicked.disabled),
              title: presetPicked && presetPicked.disabled ? 'Ese preset no está disponible en este servicio' : 'Exportar MP4',
              onClick: () => startExport({ captions: incCaptions, openWhenDone: false, preset: exportPreset })
            })
          ]
        },
        h(
          'div',
          { className: 've-props' },
          h(
            'label',
            { className: 've-f' },
            h('span', { className: 've-f__l' }, 'Preset de exportación'),
            h(
              'select',
              {
                className: 've-select',
                value: exportPreset,
                'aria-label': 'Preset de exportación',
                onChange: (event) => setExportPreset(event.target.value)
              },
              presetOptions.map((item) =>
                h('option', { key: item.id, value: item.id, disabled: !!item.disabled }, item.label)
              )
            ),
            presetPicked && presetPicked.disabled
              ? h('span', { className: 've-f__err', role: 'alert' }, 'El servicio todavía no ofrece este preset: elige otro o expórtalo cuando esté medido.')
              : h(
                  'span',
                  { className: 've-f__h' },
                  service && Array.isArray(service.presets) && service.presets.length
                    ? 'Presets informados por el servicio.'
                    : 'Catálogo local: el servicio valida el preset al exportar.'
                )
          ),
          h(
            'label',
            { className: 've-file', style: { cursor: 'pointer' } },
            h('input', { type: 'checkbox', checked: incCaptions, onChange: (event) => setIncCaptions(event.target.checked) }),
            h('span', { className: 've-file__n' }, 'Incluir subtítulos')
          ),
          h('span', { className: 've-f__h' }, `${(doc.scenes || []).length} escenas · ${missing.length ? 'faltan medios' : 'medios vinculados'}`)
        )
      )
    }
    if (dialog.kind === 'export') {
      const live = job || dialog.job || null
      const index = live ? stageIndex(live.stage) : 0
      const pct = live && typeof live.progress === 'number' ? live.progress : null
      const running = ['queued', 'running', 'cancelling'].includes(dialog.phase)
      return h(
        Dialog,
        {
          title: dialog.phase === 'done' ? 'Exportación terminada' : dialog.phase === 'failed' ? 'La exportación falló' : 'Exportando vídeo',
          onClose: running ? undefined : () => setDialog(null),
          footer: running
            ? [h(Btn, { key: 'c', variant: 'outline', label: dialog.phase === 'cancelling' ? 'Cancelando…' : 'Cancelar exportación', onClick: cancelExport })]
            : [
                h(Btn, { key: 'r', variant: 'outline', label: 'Reintentar', onClick: () => startExport({ captions: incCaptions, openWhenDone: false }) }),
                h(Btn, { key: 'c', variant: 'primary', label: 'Cerrar', onClick: () => setDialog(null) })
              ]
        },
        h(
          'div',
          { className: 've-props', 'aria-busy': running ? 'true' : 'false' },
          dialog.phase === 'failed'
            ? h(ErrorState, { title: 'No se generó el MP4', body: (live && live.error) || 'El servicio devolvió un error.' })
            : h(
                'ul',
                { className: 've-stages' },
                STAGES.map((item, position) =>
                  h(
                    'li',
                    {
                      key: item.id,
                      'data-state': position < index ? 'done' : position === index ? (dialog.phase === 'done' ? 'done' : 'active') : 'pending'
                    },
                    position < index || dialog.phase === 'done' ? h(Icon, { name: 'check', size: 'sm' }) : position === index ? h(Spinner) : h(Dot, null),
                    item.label
                  )
                )
              ),
          pct !== null && running
            ? h(
                'div',
                { className: 've-progress', role: 'progressbar', 'aria-valuemin': 0, 'aria-valuemax': 100, 'aria-valuenow': Math.round(pct) },
                h('i', { style: { width: `${clamp(pct, 0, 100)}%` } })
              )
            : null,
          dialog.phase === 'done'
            ? h(
                'div',
                { className: 've-out' },
                h(
                  'p',
                  { className: 've-dialog__b' },
                  `Listo · ${(live && live.artifacts && live.artifacts[0]) || 'output.mp4'}${live && live.outputBytes ? ` · ${fmtBytes(live.outputBytes)}` : ''}`
                ),
                live && live.jobId
                  ? h('video', {
                      className: 've-out__v',
                      controls: true,
                      preload: 'metadata',
                      src: `${serviceBase(ctx)}/jobs/${encodeURIComponent(live.jobId)}/output`,
                      'aria-label': 'Vídeo exportado: reproducir aquí'
                    })
                  : null,
                h('code', { className: 've-out__p' }, (live && live.outputPath) || 'ruta no disponible'),
                h(
                  'div',
                  { className: 've-out__a' },
                  h(Btn, {
                    icon: 'message',
                    variant: 'primary',
                    label: 'Agregar al chat',
                    title: 'Inserta el resultado en el chat activo para que Hermes lo use',
                    onClick: () => addToChat(exportSummary())
                  }),
                  h(Btn, {
                    icon: 'copy',
                    variant: 'outline',
                    label: 'Copiar ruta',
                    onClick: () => copyText((live && live.outputPath) || '')
                  })
                ),
                chatMsg ? h('p', { className: 've-note', 'aria-live': 'polite' }, chatMsg) : null
              )
            : null
        )
      )
    }
    if (dialog.kind === 'conflict') {
      return h(
        Dialog,
        {
          title: 'Hay cambios más nuevos',
          body: `La revisión ${dialog.theirs} se guardó en otro lugar. Tu copia es la ${dialog.mine}.`,
          onClose: () => setDialog(null),
          footer: [
            h(Btn, { key: 'c', variant: 'text', label: 'Cancelar', onClick: () => setDialog(null) }),
            h(Btn, {
              key: 'r',
              variant: 'outline',
              label: 'Recargar y perder mis cambios',
              onClick: () => {
                setDialog(null)
                openProject(doc.projectId)
              }
            })
          ]
        },
        h('p', { className: 've-f__h' }, 'Nada se sobrescribe en silencio: recargar trae la revisión más nueva.')
      )
    }
    if (dialog.kind === 'import') {
      const state = importState
      if (!state) return null
      if (state.phase === 'picking') {
        return h(Dialog, { title: 'Importar medios', onClose: () => setDialog(null) }, h('div', { className: 've-loadrow' }, h(Spinner), 'Abriendo la carpeta concedida…'))
      }
      if (state.phase === 'error') {
        return h(
          Dialog,
          { title: 'No se pudo importar', onClose: () => setDialog(null), footer: h(Btn, { variant: 'text', label: 'Cerrar', onClick: () => setDialog(null) }) },
          h(ErrorState, { title: 'La carpeta no está disponible', body: state.error })
        )
      }
      if (state.phase === 'list') {
        return h(
          Dialog,
          {
            title: 'Importar medios',
            body: `${state.entries.length} archivos admitidos · solo se importa lo que marques`,
            onClose: () => setDialog(null),
            footer: [
              h(Btn, { key: 'c', variant: 'outline', label: 'Cancelar', onClick: () => setDialog(null) }),
              h(Btn, {
                key: 'i',
                variant: 'primary',
                label: 'Importar seleccionados',
                disabled: !Object.values(state.chosen).some(Boolean),
                onClick: doImport
              })
            ]
          },
          h(
            'div',
            { className: 've-list' },
            state.entries.map((entry) =>
              h(
                'label',
                { key: entry.path, className: 've-file' },
                h('input', {
                  type: 'checkbox',
                  checked: !!state.chosen[entry.path],
                  onChange: (event) =>
                    setImportState((prev) => ({ ...prev, chosen: { ...prev.chosen, [entry.path]: event.target.checked } }))
                }),
                h('span', { className: 've-file__n' }, entry.path),
                h('span', { className: 've-file__s' }, fmtBytes(entry.size))
              )
            )
          )
        )
      }
      if (state.phase === 'importing') {
        return h(
          Dialog,
          { title: 'Importando medios', onClose: () => {}, footer: null },
          h('div', { className: 've-props', 'aria-live': 'polite' }, h('div', { className: 've-loadrow' }, h(Spinner), `${state.done} de ${state.total}`))
        )
      }
      return h(
        Dialog,
        {
          title: 'Importación terminada',
          onClose: () => setDialog(null),
          footer: h(Btn, { variant: 'primary', label: 'Cerrar', onClick: () => setDialog(null) })
        },
        h(
          'p',
          { className: 've-dialog__b' },
          `${state.done} de ${state.total} importados${state.failures.length ? ` · ${state.failures.length} con error` : ''}`
        ),
        state.failures.length ? h('div', { className: 've-log' }, state.failures.join('\n')) : null
      )
    }
    if (dialog.kind === 'picker') {
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
    if (dialog.kind === 'service') {
      const lines = []
      if (job) {
        lines.push(`Trabajo ${job.jobId || ''}: ${job.state || 'sin estado'}`)
        if (job.stage) lines.push(`Etapa: ${job.stage}`)
        if (typeof job.progress === 'number') lines.push(`Progreso: ${Math.round(job.progress)} %`)
        if (job.error) lines.push(`Error: ${job.error}`)
        if (job.outputPath) {
          lines.push(`Salida: ${job.outputPath}${job.outputBytes ? ` (${fmtBytes(job.outputBytes)})` : ''}`)
        }
      } else {
        lines.push('Sin trabajos de exportación en esta sesión.')
      }
      if (loadError && loadError.message) lines.push(`Último error de carga: ${loadError.message}`)
      return h(
        Dialog,
        {
          title: 'Estado del servicio',
          onClose: () => setDialog(null),
          footer: h(Btn, { variant: 'text', label: 'Cerrar', onClick: () => setDialog(null) })
        },
        h('div', { className: 've-log' }, lines.join('\n'))
      )
    }
    return null
  }

  const menus = () => {
    if (!menu) return null
    if (menu === 'projects') return dialogsProjectsMenu()
    return h(
      'div',
      { className: 've-menu', style: { right: '10px', top: '42px' }, role: 'menu' },
      h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); setDialog({ kind: 'service' }) } }, 'Estado del servicio'),
      h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); setGuides((prev) => { if (ctx?.storage?.set) ctx.storage.set('preview.guides', !prev); return !prev }) } },
        `${guides ? 'Ocultar' : 'Mostrar'} guías de zona segura`),
      h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); save({ force: true }) } }, 'Guardar ahora (Ctrl+S)'),
      h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); addToChat(exportSummary()) } }, 'Agregar el resultado al chat'),
      h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); copyText((job && job.outputPath) || '') } }, 'Copiar ruta del MP4'),
      h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); goChat() } }, 'Volver al chat')
    )
  }

  function dialogsProjectsMenu() {
    return h(
      'div',
      { className: 've-menu', style: { left: '10px', top: '42px' }, role: 'menu' },
      projects.length
        ? projects.map((item) =>
            h(
              'button',
              {
                key: item.projectId,
                type: 'button',
                role: 'menuitem',
                onClick: () => {
                  setMenu(null)
                  openProject(item.projectId)
                }
              },
              `${item.title || item.projectId} · Rev ${item.revision}`
            )
          )
        : h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); setDialog({ kind: 'projects' }) } }, 'Ver proyectos…'),
      h('button', { type: 'button', role: 'menuitem', onClick: () => { setMenu(null); createProject() } }, 'Crear proyecto…')
    )
  }

  // -------------------------------------------------------------- montaje

  return h(
    'div',
    {
      className: 've-root',
      ref: rootRef,
      lang: 'es',
      tabIndex: -1,
      'data-ve-pane': '1',
      'data-compact': compact ? '1' : '0',
      'data-tight': tight ? '1' : '0',
      'aria-busy': phase === 'loading' || (job && job.state === 'running') ? 'true' : 'false',
      onDragOver: (event) => {
        if (phase !== 'ready' || !doc) return
        if (!(doc.scenes || []).length) return
        event.preventDefault()
      },
      onDrop: (event) => {
        if (!doc) return
        if (!(doc.scenes || []).length) return
        onDrop(event)
      }
    },
    header(),
    h(
      'div',
      { className: 've-body' },
      h('div', { className: 've-left' }, stage(), transport(), timelineBlock()),
      compact && libOpen ? h('div', { className: 've-ov', 'aria-hidden': 'true', onClick: () => setLibOpen(false) }) : null,
      compact ? library() : null,
      rail()
    ),
    footer(),
    menus(),
    dialogs(),
    modelTip ? h('div', { className: 've-tip', role: 'status' }, 'Cambia el modelo en el selector del chat.') : null,
    h('div', { className: 've-sr', role: 'status', 'aria-live': 'polite' }, notice)
  )
}

// --------------------------------------------------------------------------- #
// registro
// --------------------------------------------------------------------------- #

export default {
  id: 'video-editor-v2',
  name: 'Editor de vídeo',
  defaultEnabled: true,
  register(ctx) {
    // Estado de apertura: `ui.open` en ctx.storage manda; el pane es solo una
    // consecuencia. Titlebar, paleta y atajo existen siempre, abierto o no.
    let open = readOpen(ctx)
    let paneDisposer = null
    const listeners = new Set()

    const getOpen = () => open
    const subscribe = (fn) => {
      listeners.add(fn)
      return () => listeners.delete(fn)
    }
    const notify = () => {
      listeners.forEach((fn) => {
        try {
          fn(open)
        } catch (error) {
          console.warn('[video-editor] suscriptor del toggle falló', error && error.message)
        }
      })
    }
    const persist = (value) => {
      try {
        if (ctx.storage && typeof ctx.storage.set === 'function') ctx.storage.set(STORAGE_OPEN, value)
      } catch (error) {
        console.warn('[video-editor] ui.open no persistido', error && error.message)
      }
    }

    const mountPane = () => {
      if (paneDisposer) return
      paneDisposer = ctx.register({
        id: 'pane',
        area: 'panes',
        title: 'Editor de vídeo',
        data: { placement: 'right', dock: { pane: 'workspace', pos: 'right' }, width: '64%' },
        render: () => jsx(VideoPane, { ctx, onClose: () => setOpen(false) })
      })
      console.info('[video-editor] pane montado')
    }

    const unmountPane = () => {
      // Suelta los <video> antes del teardown: si el layout tarda en desmontar,
      // no queda audio ni decodificación viva.
      releaseVideos()
      if (!paneDisposer) return
      const dispose = paneDisposer
      paneDisposer = null
      try {
        dispose()
      } catch (error) {
        console.warn('[video-editor] no se pudo disponer el pane', error && error.message)
      }
      console.info('[video-editor] pane cerrado')
    }

    const setOpen = (next) => {
      const want = !!next
      if (want === open) {
        if (want) mountPane()
        return
      }
      open = want
      persist(open)
      if (open) mountPane()
      else unmountPane()
      notify()
    }

    const toggle = () => setOpen(!open)

    // (a) barra de título — mismo par de tokens que el resto del chrome.
    ctx.register({
      id: 'titlebar-toggle',
      area: TITLEBAR_AREAS.right,
      order: 40,
      render: () => jsx(TitlebarToggle, { getOpen, subscribe, onToggle: toggle })
    })

    // (b) ⌘K — `action` hace que la fila muestre el atajo vivo.
    ctx.register({
      id: 'palette-toggle',
      area: PALETTE_AREA,
      data: {
        id: 'video-editor.toggle',
        label: 'Abrir/Cerrar editor de vídeo',
        action: 'videoEditor.toggle',
        keywords: ['video', 'editor', 'pane', 'abrir', 'cerrar'],
        run: toggle
      }
    })

    // (c) Ctrl+Shift+E (canónico `mod+shift+e`; en Windows `ctrl` se normaliza a `mod`).
    ctx.register({
      id: 'keybind-toggle',
      area: KEYBINDS_AREA,
      data: {
        id: 'videoEditor.toggle',
        category: 'view',
        label: 'Abrir/Cerrar editor de vídeo',
        defaults: ['mod+shift+e'],
        run: toggle
      }
    })

    // (4) al montar, `ui.open: false` deja el plugin sin pane.
    if (open) mountPane()

    ctx.onDispose(() => {
      open = false
      releaseVideos()
      listeners.clear()
      paneDisposer = null
    })
  }
}
