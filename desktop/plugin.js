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
const COALESCE_MS = 900
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
  { id: 'mp4-1080p30', label: 'MP4 1080p · 30 fps' },
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
const TEXT_POSITIONS = [
  { id: 'top', label: 'Arriba' },
  { id: 'center', label: 'Centro' },
  { id: 'bottom', label: 'Abajo' }
]
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
  return round3((doc.scenes || []).reduce((sum, scene) => sum + visibleDuration(scene), 0))
}

// Lo que dura el MP4 de verdad: cada transición solapa la escena con la anterior,
// así que el vídeo final es más corto que la suma de las escenas.
function finalDuration(doc) {
  const scenes = (doc && doc.scenes) || []
  let overlap = 0
  scenes.forEach((scene, index) => {
    if (index === 0) return
    const parts = parseTransition(scene.transition)
    if (parts.style !== 'none') overlap += parts.seconds
  })
  return Math.max(0, round3(totalOf(doc) - overlap))
}

function timeline(doc) {
  let at = 0
  return (doc && doc.scenes ? doc.scenes : []).map((scene) => {
    const dur = visibleDuration(scene)
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
/* Editor de vídeo · rediseño v0.5 — «estudio oscuro» sobre los tokens de Hermes Web
   (--ui-bg-*, --ui-text-*, --ui-accent, --ui-stroke-*). Escala de 8 px. Cada token
   tiene un respaldo oscuro propio por si el pane vive fuera de Hermes. */
.ve-root{
  --ve-fg:var(--ui-text-primary,#e8e9ee);
  --ve-ink2:color-mix(in oklab,var(--ve-fg) 76%,transparent);
  --ve-ink3:color-mix(in oklab,var(--ve-fg) 56%,transparent);
  --ve-accent:var(--ui-accent,#6f9dff);
  --ve-base:var(--ui-bg-editor,#15161b);
  --ve-chrome:var(--ui-bg-chrome,color-mix(in oklab,var(--ve-base) 86%,#000));
  --ve-deep:color-mix(in oklab,var(--ve-base) 62%,#000);
  --ve-raise:color-mix(in oklab,var(--ve-base) 91%,var(--ve-fg));
  --ve-raise2:color-mix(in oklab,var(--ve-base) 84%,var(--ve-fg));
  --ve-line:color-mix(in oklab,var(--ve-fg) 11%,transparent);
  --ve-line2:color-mix(in oklab,var(--ve-fg) 18%,transparent);
  --ve-soft:color-mix(in oklab,var(--ve-fg) 7%,transparent);
  --ve-surface:var(--ve-base);
  --ve-card:var(--ve-raise);
  --ve-ok:var(--ui-green,#3ec486);
  --ve-warn:var(--ui-yellow,#e2b04a);
  --ve-bad:var(--ui-red,#ef5f7a);
  --ve-c-video:var(--ve-accent);
  --ve-c-text:var(--ui-purple,#b19cf2);
  --ve-c-audio:var(--ve-ok);
  --ve-c-music:var(--ui-orange,#f0925f);
  --ve-r:8px;
  --ve-ease:cubic-bezier(.2,.7,.2,1);
  position:relative;display:grid;grid-template-columns:minmax(0,1fr);grid-template-rows:48px minmax(0,1fr);
  height:100%;width:100%;min-height:0;overflow:hidden;contain:paint;
  color:var(--ve-fg);background:var(--ve-chrome);
  font-size:12px;line-height:1.5;font-family:inherit;-webkit-font-smoothing:antialiased;
}
.ve-root *,.ve-root *::before,.ve-root *::after{box-sizing:border-box}
.ve-root :where(h1,h2,h3,p){margin:0}
.ve-root :where(button){font:inherit;color:inherit}
.ve-root ::-webkit-scrollbar{width:8px;height:8px}
.ve-root ::-webkit-scrollbar-thumb{background:var(--ve-line2);border-radius:8px;border:2px solid transparent;background-clip:content-box}
.ve-root ::-webkit-scrollbar-thumb:hover{background:color-mix(in oklab,var(--ve-fg) 32%,transparent);background-clip:content-box}
.ve-root ::-webkit-scrollbar-track{background:transparent}
.ve-i{width:16px;height:16px;flex:none;stroke:currentColor;fill:none;stroke-width:1.7;stroke-linecap:round;stroke-linejoin:round}
.ve-i--sm{width:14px;height:14px}
.ve-i--fill{fill:currentColor}
/* ---- barra superior ------------------------------------------------------ */
.ve-hdr{display:flex;align-items:center;gap:8px;min-width:0;padding:0 12px;background:var(--ve-base);border-bottom:1px solid var(--ve-line);overflow:hidden}
.ve-plate{width:32px;height:32px;border-radius:8px;display:grid;place-items:center;flex:none;color:var(--ve-accent);background:color-mix(in oklab,var(--ve-accent) 16%,transparent)}
.ve-title{font-size:13px;font-weight:600;letter-spacing:.01em;white-space:nowrap;min-width:0;overflow:hidden;text-overflow:ellipsis}
.ve-sep{width:1px;height:24px;background:var(--ve-line);flex:none;margin:0 4px}
.ve-spacer{flex:1 1 auto;min-width:0}
.ve-chip{display:inline-flex;align-items:center;gap:8px;height:32px;padding:0 8px 0 12px;flex:0 1 auto;min-width:40px;max-width:240px;border:1px solid transparent;border-radius:8px;background:var(--ve-soft);font-size:12px;font-weight:600;cursor:pointer;white-space:nowrap;overflow:hidden;transition:background-color .15s,border-color .15s}
.ve-chip:hover{background:color-mix(in oklab,var(--ve-fg) 11%,transparent)}
.ve-chip:focus-visible{outline:2px solid var(--ve-accent);outline-offset:1px}
.ve-chip__name{overflow:hidden;text-overflow:ellipsis}
.ve-chip--ghost{background:transparent;color:var(--ve-ink2);font-weight:500;max-width:168px;padding:0 12px}
.ve-chip--ghost:hover{background:var(--ve-soft);color:var(--ve-fg)}
.ve-chat__b{font-size:10px;letter-spacing:.06em;text-transform:uppercase;color:var(--ve-warn)}
.ve-auto{display:inline-flex;align-items:center;gap:8px;height:24px;padding:0 12px 0 8px;border-radius:12px;font-size:11px;color:var(--ve-ink2);white-space:nowrap;background:transparent;transition:background-color .2s,color .2s}
.ve-auto--warn{color:var(--ve-warn)}
.ve-auto--bad{color:var(--ve-bad);background:color-mix(in oklab,var(--ve-bad) 12%,transparent)}
.ve-dot{width:8px;height:8px;border-radius:50%;flex:none;background:var(--ve-ink3);transition:background-color .2s,box-shadow .2s}
.ve-dot--good{background:var(--ve-ok);box-shadow:0 0 0 3px color-mix(in oklab,var(--ve-ok) 18%,transparent)}
.ve-dot--warn{background:var(--ve-warn);box-shadow:0 0 0 3px color-mix(in oklab,var(--ve-warn) 18%,transparent)}
.ve-dot--bad{background:var(--ve-bad);box-shadow:0 0 0 3px color-mix(in oklab,var(--ve-bad) 18%,transparent)}
/* ---- botones ------------------------------------------------------------- */
.ve-btn{display:inline-flex;align-items:center;justify-content:center;gap:8px;height:32px;padding:0 12px;flex:none;border:1px solid transparent;border-radius:8px;background:transparent;font-size:12px;font-weight:500;white-space:nowrap;cursor:pointer;transition:background-color .15s,color .15s,border-color .15s,transform .1s,box-shadow .15s}
.ve-btn:active{transform:translateY(1px)}
.ve-btn:focus-visible{outline:2px solid var(--ve-accent);outline-offset:2px}
.ve-btn--primary{background:var(--ve-accent);color:var(--ui-accent-foreground,#0b0f1a);border-color:transparent;font-weight:600;box-shadow:0 1px 0 color-mix(in oklab,#fff 25%,transparent) inset,0 4px 14px -6px var(--ve-accent)}
.ve-btn--primary:hover{background:color-mix(in oklab,var(--ve-accent) 88%,#fff)}
.ve-btn--outline{border-color:var(--ve-line2);background:transparent}
.ve-btn--outline:hover{background:var(--ve-soft);border-color:color-mix(in oklab,var(--ve-fg) 28%,transparent)}
.ve-btn--ghost{color:var(--ve-ink2)}
.ve-btn--ghost:hover{background:var(--ve-soft);color:var(--ve-fg)}
.ve-btn--ghost[aria-pressed="true"]{background:color-mix(in oklab,var(--ve-accent) 16%,transparent);color:var(--ve-accent)}
.ve-btn--text{color:var(--ve-ink2);padding:0 8px}
.ve-btn--text:hover{color:var(--ve-fg);background:var(--ve-soft)}
.ve-btn--icon{width:32px;padding:0}
.ve-btn--block{width:100%}
.ve-btn--sm{height:24px;padding:0 8px;font-size:11px;border-radius:8px}
.ve-btn--sm.ve-btn--icon{width:24px;padding:0}
.ve-btn[disabled]{opacity:.38;cursor:default;pointer-events:none}
.ve-badge{display:inline-flex;align-items:center;gap:4px;height:20px;padding:0 8px;border-radius:10px;flex:none;font-size:10.5px;font-weight:600;white-space:nowrap;background:var(--ve-soft);color:var(--ve-ink2)}
.ve-badge--outline{background:transparent;border:1px solid var(--ve-line2)}
.ve-badge--accent{background:color-mix(in oklab,var(--ve-accent) 20%,transparent);color:color-mix(in oklab,var(--ve-accent) 70%,var(--ve-fg))}
.ve-badge--warn{background:color-mix(in oklab,var(--ve-warn) 20%,transparent);color:var(--ve-warn)}
/* ---- cuerpo: panel izquierdo · centro · inspector --------------------------- */
.ve-body{position:relative;display:grid;grid-template-columns:minmax(0,1fr);min-height:0;min-width:0;overflow:hidden;contain:paint}
.ve-root[data-layout="wide"] .ve-body{grid-template-columns:256px minmax(0,1fr) 312px}
.ve-root[data-layout="mid"] .ve-body{grid-template-columns:minmax(0,1fr) 296px}
.ve-root[data-doc="0"] .ve-body{grid-template-columns:minmax(0,1fr)!important}
.ve-main{display:flex;flex-direction:column;min-width:0;min-height:0;background:var(--ve-chrome)}
.ve-ov{position:absolute;inset:0;background:color-mix(in oklab,#000 52%,transparent);backdrop-filter:blur(2px);z-index:8;animation:ve-fade .18s var(--ve-ease)}
@keyframes ve-fade{from{opacity:0}to{opacity:1}}
/* ---- panel izquierdo: escenas y medios -------------------------------------- */
.ve-side{display:flex;flex-direction:column;min-height:0;min-width:0;background:var(--ve-base);border-right:1px solid var(--ve-line)}
.ve-root:not([data-layout="wide"]) .ve-side{position:absolute;left:0;top:0;bottom:0;width:min(296px,92%);z-index:9;box-shadow:24px 0 48px -24px #000;animation:ve-slide-l .22s var(--ve-ease)}
@keyframes ve-slide-l{from{transform:translateX(-24px);opacity:0}to{transform:none;opacity:1}}
@keyframes ve-slide-r{from{transform:translateX(24px);opacity:0}to{transform:none;opacity:1}}
.ve-pt{display:flex;align-items:center;gap:8px;height:40px;flex:none;padding:0 8px 0 16px;border-bottom:1px solid var(--ve-line)}
.ve-pt__t{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--ve-ink2)}
.ve-segtabs{display:grid;grid-template-columns:1fr 1fr;gap:4px;margin:12px 12px 8px;padding:4px;border-radius:8px;background:var(--ve-deep);flex:none}
.ve-segtabs button{display:flex;align-items:center;justify-content:center;gap:8px;height:28px;border:0;border-radius:6px;background:transparent;color:var(--ve-ink2);font-size:12px;font-weight:600;cursor:pointer;transition:background-color .15s,color .15s}
.ve-segtabs button:hover{color:var(--ve-fg)}
.ve-segtabs button[aria-pressed="true"]{background:var(--ve-raise2);color:var(--ve-fg);box-shadow:0 1px 2px #0006}
.ve-segtabs button:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px}
.ve-segtabs em{font-style:normal;font-size:10.5px;color:var(--ve-ink3);font-variant-numeric:tabular-nums}
.ve-side__bar{display:flex;align-items:center;gap:8px;padding:4px 12px 8px 16px;flex:none}
.ve-side__cnt{font-size:11px;color:var(--ve-ink3)}
.ve-side__foot{flex:none;padding:12px;border-top:1px solid var(--ve-line);display:flex;flex-direction:column;gap:8px}
.ve-scenes,.ve-lib__list{flex:1 1 auto;min-height:0;overflow-y:auto;display:flex;flex-direction:column;gap:4px;padding:0 8px 8px}
.ve-scene-row,.ve-lib__row{position:relative;display:flex;align-items:center;gap:4px;border-radius:8px;transition:background-color .15s}
.ve-scene,.ve-lib__item{display:grid;align-items:center;gap:8px;min-height:56px;padding:8px;border-radius:8px;border:1px solid transparent;background:transparent;text-align:left;cursor:pointer;width:100%;min-width:0;flex:1 1 auto;transition:background-color .15s,border-color .15s}
.ve-scene{grid-template-columns:16px 64px minmax(0,1fr)}
.ve-lib__item{grid-template-columns:64px minmax(0,1fr)}
.ve-scene:hover,.ve-lib__item:hover{background:var(--ve-soft)}
.ve-scene:focus-visible,.ve-lib__item:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px}
.ve-scene[aria-current="true"],.ve-lib__item[aria-current="true"]{background:color-mix(in oklab,var(--ve-accent) 14%,transparent);border-color:color-mix(in oklab,var(--ve-accent) 55%,transparent)}
.ve-scene__n{font-size:10.5px;color:var(--ve-ink3);font-variant-numeric:tabular-nums;font-weight:600}
.ve-scene__m,.ve-lib__m{min-width:0;display:flex;flex-direction:column;gap:2px}
.ve-scene__name,.ve-lib__n{display:block;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.3}
.ve-scene__dur,.ve-lib__s{display:block;font-size:11px;color:var(--ve-ink3);font-variant-numeric:tabular-nums;line-height:1.3;white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ve-thumb{width:64px;height:36px;object-fit:cover;display:grid;place-items:center;color:var(--ve-ink3);background:var(--ve-deep);border-radius:4px;overflow:hidden;pointer-events:none;flex:none}
.ve-scene-row__mv{display:flex;flex-direction:column;opacity:0;transition:opacity .15s;flex:none}
.ve-scene-row:hover .ve-scene-row__mv,.ve-scene-row:focus-within .ve-scene-row__mv,.ve-scene-row:has([aria-current="true"]) .ve-scene-row__mv{opacity:1}
.ve-mv{width:24px;height:24px;display:grid;place-items:center;border-radius:6px;border:0;background:transparent;color:var(--ve-ink2);cursor:pointer;flex:none;transition:background-color .15s,color .15s}
.ve-mv:hover{background:var(--ve-raise2);color:var(--ve-fg)}
.ve-mv:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-1px}
.ve-mv[disabled]{opacity:.3;cursor:default}
.ve-lib__row .ve-mv{width:32px;height:32px}
.ve-lib__empty{margin:8px 16px;padding:16px;border:1px dashed var(--ve-line2);border-radius:8px;font-size:12px;color:var(--ve-ink3);line-height:1.5;text-align:center}
/* ---- escena: vista previa ----------------------------------------------------- */
.ve-stage{flex:1 1 auto;min-height:160px;display:flex;flex-direction:column;padding:48px 24px 16px;background:radial-gradient(120% 90% at 50% 0%,color-mix(in oklab,var(--ve-deep) 88%,var(--ve-accent)) 0%,var(--ve-deep) 62%);position:relative;gap:8px}
.ve-stage__bar{position:absolute;top:8px;left:16px;right:16px;display:flex;align-items:center;gap:8px;height:32px;pointer-events:none}
.ve-stage__name{font-size:13px;font-weight:600;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap}
.ve-stage__sp{flex:1}
.ve-stage__count{font-size:11px;font-variant-numeric:tabular-nums;color:var(--ve-ink2);padding:4px 8px;border-radius:12px;background:color-mix(in oklab,#000 40%,transparent)}
.ve-stage__canvas{flex:1 1 auto;min-height:0;display:grid;place-items:center}
.ve-frame{position:relative;max-height:100%;max-width:100%;overflow:hidden;border-radius:8px;background:#000;box-shadow:0 0 0 1px var(--ve-line2),0 24px 64px -24px #000,0 8px 24px -12px #000}
.ve-frame video,.ve-frame img{display:block;width:100%;height:100%;object-fit:contain;background:#000}
.ve-cap{position:absolute;left:6%;right:6%;bottom:8%;padding:0 4px;color:#fff;font-size:12px;font-weight:600;line-height:1.35;text-align:center;text-shadow:0 1px 3px rgba(0,0,0,.8),0 0 2px rgba(0,0,0,.7);pointer-events:none}
.ve-cap--top{top:8%;bottom:auto}
.ve-cap--center{top:50%;bottom:auto;transform:translateY(-50%)}
.ve-guides{position:absolute;inset:6%;border:1px dashed color-mix(in oklab,#fff 45%,transparent);border-radius:4px;pointer-events:none}
/* ---- transporte --------------------------------------------------------------- */
.ve-transport{flex:none;display:flex;flex-direction:column;background:var(--ve-base);border-top:1px solid var(--ve-line)}
.ve-scrub{display:flex;align-items:center;height:16px;padding:0;margin-top:-8px;position:relative;z-index:2}
.ve-root input[type="range"]{-webkit-appearance:none;appearance:none;width:100%;height:24px;margin:0;background:transparent;cursor:pointer;accent-color:var(--ve-accent)}
.ve-root input[type="range"]:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px;border-radius:4px}
.ve-root input[type="range"]::-webkit-slider-runnable-track{height:4px;border-radius:2px;background:linear-gradient(to right,var(--ve-accent) 0 var(--ve-p,0%),color-mix(in oklab,var(--ve-fg) 18%,transparent) var(--ve-p,0%) 100%)}
.ve-root input[type="range"]::-webkit-slider-thumb{-webkit-appearance:none;appearance:none;width:12px;height:12px;border-radius:50%;margin-top:-4px;background:#fff;border:0;box-shadow:0 0 0 3px color-mix(in oklab,var(--ve-accent) 55%,transparent),0 1px 4px #0008;transition:transform .12s}
.ve-root input[type="range"]:hover::-webkit-slider-thumb{transform:scale(1.25)}
.ve-scrub input[type="range"]{height:16px}
.ve-scrub input[type="range"]::-webkit-slider-runnable-track{height:3px}
.ve-scrub input[type="range"]:hover::-webkit-slider-runnable-track{height:5px}
.ve-transport__row{display:grid;grid-template-columns:minmax(0,1fr) auto minmax(0,1fr);align-items:center;gap:8px;height:56px;padding:0 16px}
.ve-transport__c{display:flex;align-items:center;gap:4px}
.ve-transport__r{display:flex;align-items:center;justify-content:flex-end;gap:8px;min-width:0}
.ve-tc{font-family:var(--dt-font-mono,ui-monospace,SFMono-Regular,Menlo,Consolas,monospace);font-size:12px;font-variant-numeric:tabular-nums;color:var(--ve-ink3);white-space:nowrap}
.ve-tc b{color:var(--ve-fg);font-weight:600;font-size:15px;letter-spacing:.01em}
.ve-play{width:40px;height:40px;border-radius:50%;padding:0;background:var(--ve-fg);color:var(--ve-base);border:0;margin:0 8px;box-shadow:0 4px 16px -6px #000}
.ve-play:hover{background:var(--ve-fg);transform:scale(1.06)}
.ve-play:active{transform:scale(.97)}
.ve-play .ve-i{width:18px;height:18px;fill:currentColor;stroke:currentColor}
.ve-goto{width:80px;height:32px;font-size:12px;background:var(--ve-raise);border:1px solid transparent;border-radius:8px;color:var(--ve-fg);padding:0 8px;transition:border-color .15s,background-color .15s}
.ve-goto:hover{background:var(--ve-raise2)}
.ve-goto:focus-visible{outline:none;border-color:var(--ve-accent)}
/* ---- línea de tiempo ------------------------------------------------------------ */
.ve-tl{flex:none;display:flex;flex-direction:column;background:var(--ve-base);border-top:1px solid var(--ve-line);min-height:0;--h-ruler:24px;--h-video:56px;--h-text:32px;--h-audio:32px;--h-music:24px;--w-head:96px}
.ve-tl__bar{display:flex;align-items:center;gap:8px;height:40px;flex:none;padding:0 12px 0 8px;border-bottom:1px solid var(--ve-line)}
.ve-tl__sum{font-size:11px;color:var(--ve-ink2);white-space:nowrap;overflow:hidden;text-overflow:ellipsis;min-width:0;font-variant-numeric:tabular-nums}
.ve-zoom{display:flex;align-items:center;gap:4px}
.ve-zoom__v{min-width:48px;text-align:center;font-size:11px;font-variant-numeric:tabular-nums;color:var(--ve-ink2)}
.ve-tl__body{display:grid;grid-template-columns:var(--w-head) minmax(0,1fr);min-height:0;overflow:hidden;padding-bottom:8px}
.ve-tl__heads{display:flex;flex-direction:column;border-right:1px solid var(--ve-line);padding-top:var(--h-ruler);background:var(--ve-base);position:relative;z-index:3}
.ve-lh{display:flex;align-items:center;gap:8px;padding:0 12px;font-size:11px;font-weight:600;color:var(--ve-ink2);margin-top:4px;white-space:nowrap}
.ve-lh .ve-i{color:var(--lc)}
.ve-lh--video{height:var(--h-video);--lc:var(--ve-c-video)}
.ve-lh--text{height:var(--h-text);--lc:var(--ve-c-text)}
.ve-lh--audio{height:var(--h-audio);--lc:var(--ve-c-audio)}
.ve-lh--music{height:var(--h-music);--lc:var(--ve-c-music)}
.ve-tl__scroll{min-width:0;overflow-x:hidden;overflow-y:hidden;position:relative}
.ve-tl__scroll[data-zoom="1"]{overflow-x:hidden}
.ve-tl__scroll:not([data-zoom="1"]){overflow-x:auto}
.ve-tl__inner{position:relative;min-width:100%}
.ve-tl__lanes{position:relative;margin:0 16px 0 8px}
.ve-tl__ruler{height:var(--h-ruler);position:relative;border-bottom:1px solid var(--ve-line);cursor:col-resize;touch-action:none;user-select:none;background:color-mix(in oklab,var(--ve-deep) 55%,transparent)}
.ve-tick{position:absolute;bottom:0;height:8px;border-left:1px solid var(--ve-line2)}
.ve-tick--major{height:100%}
.ve-tick em{position:absolute;top:4px;left:4px;font-style:normal;font-size:10.5px;line-height:1;color:var(--ve-ink3);font-variant-numeric:tabular-nums;white-space:nowrap}
.ve-tl__row{position:relative;display:flex;align-items:stretch;margin-top:4px;min-width:0}
.ve-tl__row--video{height:var(--h-video)}
.ve-tl__row--text{height:var(--h-text);border-radius:8px;background:repeating-linear-gradient(90deg,var(--ve-soft) 0 1px,transparent 1px 24px)}
.ve-tl__row--audio{height:var(--h-audio);border-radius:8px;background:color-mix(in oklab,var(--ve-deep) 55%,transparent)}
.ve-tl__row--music{height:var(--h-music);border-radius:8px;background:color-mix(in oklab,var(--ve-deep) 55%,transparent);align-items:center}
.ve-clip{position:relative;min-width:0;border:0;border-radius:8px;display:block;padding:0;overflow:hidden;cursor:grab;text-align:left;touch-action:none;user-select:none;color:#fff;background:color-mix(in oklab,var(--ve-c-video) 26%,var(--ve-deep));box-shadow:0 0 0 1px var(--ve-base) inset,0 0 0 2px var(--ve-base);transition:box-shadow .15s,filter .15s}
.ve-clip:hover{filter:brightness(1.15)}
.ve-clip:focus-visible{outline:2px solid var(--ve-accent);outline-offset:1px}
.ve-clip__thumbs{position:absolute;inset:0;display:flex;opacity:.62;pointer-events:none}
.ve-clip__thumbs .ve-thumb{flex:1 1 0;min-width:56px;width:auto;height:100%;border-radius:0;background:transparent;object-fit:cover}
.ve-clip::before{content:"";position:absolute;inset:0;background:linear-gradient(to top,#000b 0%,#0004 52%,#0001 100%);pointer-events:none}
.ve-clip__n{position:absolute;top:4px;right:8px;font-size:10px;font-weight:700;color:#fffc;font-variant-numeric:tabular-nums;text-shadow:0 1px 2px #000}
.ve-clip__t{position:absolute;left:8px;right:28px;bottom:20px;font-size:12px;font-weight:600;white-space:nowrap;overflow:hidden;text-overflow:ellipsis;line-height:1.2;text-shadow:0 1px 3px #000}
.ve-clip__d{position:absolute;left:8px;bottom:4px;font-size:10.5px;color:#fffd;font-variant-numeric:tabular-nums;text-shadow:0 1px 2px #000;line-height:1.2}
.ve-clip--sel{box-shadow:0 0 0 2px var(--ve-accent) inset,0 0 0 2px var(--ve-base),0 0 18px -4px var(--ve-accent);z-index:1}
.ve-clip--drag{opacity:.92;z-index:5;box-shadow:0 12px 28px -8px #000,0 0 0 2px var(--ve-accent) inset;cursor:grabbing;transition:none}
.ve-clip--drop::after{content:"";position:absolute;left:0;top:0;bottom:0;width:4px;background:var(--ve-ok);box-shadow:0 0 12px var(--ve-ok);z-index:4}
.ve-trim{position:absolute;top:0;bottom:0;width:8px;background:var(--ve-accent);cursor:ew-resize;touch-action:none;z-index:2;display:grid;place-items:center;transition:filter .15s}
.ve-trim::after{content:"";width:2px;height:14px;border-radius:1px;background:#0b0f1a;opacity:.7}
.ve-trim:hover{filter:brightness(1.2)}
.ve-trim--l{left:0;border-radius:8px 0 0 8px}
.ve-trim--r{right:0;border-radius:0 8px 8px 0}
.ve-clip .ve-badge{position:absolute;top:4px;left:8px;z-index:3}
.ve-tx{position:relative;min-width:0;height:100%}
.ve-txb{position:absolute;top:2px;bottom:2px;display:flex;align-items:center;gap:8px;padding:0 8px;border:0;border-radius:6px;background:color-mix(in oklab,var(--ve-c-text) 34%,var(--ve-deep));box-shadow:0 0 0 1px color-mix(in oklab,var(--ve-c-text) 60%,transparent) inset;color:var(--ve-fg);font-size:11px;font-weight:500;cursor:pointer;overflow:hidden;white-space:nowrap;text-align:left;transition:filter .15s,box-shadow .15s}
.ve-txb:hover{filter:brightness(1.18)}
.ve-txb:focus-visible{outline:2px solid var(--ve-accent);outline-offset:1px}
.ve-txb--sel{box-shadow:0 0 0 2px var(--ve-c-text) inset,0 0 14px -4px var(--ve-c-text)}
.ve-txb span{overflow:hidden;text-overflow:ellipsis}
.ve-txb .ve-i{color:var(--ve-c-text);width:14px;height:14px}
.ve-ab{position:relative;min-width:0;display:flex;align-items:flex-end;overflow:hidden;border-radius:6px;background:color-mix(in oklab,var(--ve-c-audio) 18%,var(--ve-deep));box-shadow:0 0 0 1px var(--ve-base) inset,0 0 0 2px var(--ve-base)}
.ve-ab i{display:block;width:100%;background:repeating-linear-gradient(90deg,color-mix(in oklab,var(--ve-c-audio) 62%,transparent) 0 2px,transparent 2px 5px);min-height:0;transition:height .2s var(--ve-ease)}
.ve-ab small{position:absolute;left:8px;top:50%;transform:translateY(-50%);font-size:10.5px;font-weight:600;color:var(--ve-fg);white-space:nowrap;text-shadow:0 1px 2px #000a}
.ve-ab--sel{box-shadow:0 0 0 1px var(--ve-c-audio) inset,0 0 0 2px var(--ve-base)}
.ve-evs{position:absolute;inset:0;pointer-events:none}
.ve-ev{position:absolute;top:2px;bottom:2px;width:16px;margin-left:-8px;padding:0;border:0;border-radius:4px;background:var(--ve-warn);pointer-events:auto;cursor:pointer;font-size:10px;color:#1a1305;line-height:1;transition:transform .12s}
.ve-ev:hover{transform:scaleY(1.1)}
.ve-mrow{position:relative;height:100%;width:100%;display:flex;align-items:center;gap:8px;padding:0 12px;border-radius:6px;background:color-mix(in oklab,var(--ve-c-music) 30%,var(--ve-deep));box-shadow:0 0 0 1px color-mix(in oklab,var(--ve-c-music) 55%,transparent) inset;font-size:11px;color:var(--ve-fg);overflow:hidden;white-space:nowrap}
.ve-mrow .ve-i{color:var(--ve-c-music);width:14px;height:14px}
.ve-lane-hint{position:absolute;left:12px;top:50%;transform:translateY(-50%);font-size:11px;color:var(--ve-ink3);pointer-events:none;white-space:nowrap}
.ve-playhead{position:absolute;top:0;bottom:0;left:var(--ve-ph,0%);width:2px;margin-left:-1px;background:#fff;pointer-events:none;z-index:6;box-shadow:0 0 0 1px #0006}
.ve-playhead::before{content:"";position:absolute;top:0;left:-6px;width:14px;height:14px;background:#fff;clip-path:polygon(0 0,100% 0,100% 55%,50% 100%,0 55%);border-radius:2px}
.ve-snapline{position:absolute;top:0;bottom:0;left:var(--ve-sn,0%);width:1px;margin-left:-.5px;background:var(--ve-ok);z-index:5;pointer-events:none;box-shadow:0 0 8px var(--ve-ok)}
.ve-snapline::after{content:"";position:absolute;top:calc(var(--h-ruler) - 6px);left:-3px;width:7px;height:7px;transform:rotate(45deg);background:var(--ve-ok)}
/* ---- inspector ----------------------------------------------------------------- */
.ve-rail{display:flex;flex-direction:column;min-height:0;min-width:0;overflow:hidden;background:var(--ve-base);border-left:1px solid var(--ve-line)}
.ve-root[data-compact="1"] .ve-rail{position:absolute;top:0;right:0;bottom:0;width:min(344px,94%);z-index:9;box-shadow:-24px 0 48px -24px #000;animation:ve-slide-r .22s var(--ve-ease)}
.ve-rail__top{display:flex;align-items:center;gap:8px;height:40px;flex:none;padding:0 8px 0 16px;border-bottom:1px solid var(--ve-line)}
.ve-rail__t{font-size:11px;font-weight:600;letter-spacing:.08em;text-transform:uppercase;color:var(--ve-ink2);white-space:nowrap}
.ve-rail__who{font-size:12px;font-weight:600;min-width:0;overflow:hidden;text-overflow:ellipsis;white-space:nowrap;color:var(--ve-fg);text-transform:none;letter-spacing:0}
.ve-tabs{display:grid;grid-template-columns:repeat(4,minmax(0,1fr));flex:none;padding:0 8px;border-bottom:1px solid var(--ve-line)}
.ve-tabs button{position:relative;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:4px;height:56px;border:0;background:transparent;color:var(--ve-ink3);font-size:11px;font-weight:600;cursor:pointer;white-space:nowrap;transition:color .15s}
.ve-tabs button::after{content:"";position:absolute;left:12px;right:12px;bottom:0;height:2px;border-radius:2px 2px 0 0;background:var(--ve-accent);transform:scaleX(0);transition:transform .2s var(--ve-ease)}
.ve-tabs button:hover{color:var(--ve-fg)}
.ve-tabs button[aria-selected="true"]{color:var(--ve-fg)}
.ve-tabs button[aria-selected="true"]::after{transform:scaleX(1)}
.ve-tabs button[aria-selected="true"] .ve-i{color:var(--ve-accent)}
.ve-tabs button:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px;border-radius:6px}
.ve-rail__body{flex:1 1 auto;min-height:0;overflow-y:auto;overflow-x:hidden;overscroll-behavior:contain;display:flex;flex-direction:column}
.ve-rail__body>*{flex:none;padding:16px;border-bottom:1px solid var(--ve-line);min-width:0}
.ve-rail__body>:last-child{border-bottom:0;padding-bottom:32px}
.ve-rail__body>.ve-es{margin:32px auto;border:0;max-width:264px}
.ve-rail__sec{min-width:0}
.ve-rail__body .ve-rail__t{font-size:12px;font-weight:600;letter-spacing:0;text-transform:none;color:var(--ve-fg)}
.ve-rail__h{display:flex;align-items:center;gap:8px;margin-bottom:12px}
.ve-props{display:flex;flex-direction:column;gap:16px;min-width:0}
.ve-f{display:flex;flex-direction:column;gap:8px;min-width:0}
.ve-f__l{display:flex;align-items:center;gap:8px;width:100%;font-size:12px;font-weight:600;color:var(--ve-fg)}
.ve-f__h{font-size:11px;color:var(--ve-ink3);line-height:1.5}
.ve-f__err{font-size:11px;color:var(--ve-bad);font-weight:600}
.ve-f__row{display:grid;grid-template-columns:1fr 1fr;gap:8px}
.ve-counter{margin-left:auto;font-size:11px;font-weight:500;color:var(--ve-ink3);font-variant-numeric:tabular-nums}
.ve-input,.ve-textarea,.ve-select,.ve-tex__in{width:100%;min-width:0;border:1px solid transparent;border-radius:8px;background:var(--ve-raise);color:var(--ve-fg);font:inherit;font-size:12px;padding:0 12px;height:32px;transition:border-color .15s,background-color .15s,box-shadow .15s}
.ve-input:hover,.ve-textarea:hover,.ve-select:hover,.ve-tex__in:hover{background:var(--ve-raise2)}
.ve-input:focus,.ve-textarea:focus,.ve-select:focus,.ve-tex__in:focus,.ve-input:focus-visible,.ve-textarea:focus-visible,.ve-select:focus-visible,.ve-tex__in:focus-visible{outline:none;border-color:var(--ve-accent);background:var(--ve-raise);box-shadow:0 0 0 3px color-mix(in oklab,var(--ve-accent) 22%,transparent)}
.ve-input::placeholder,.ve-textarea::placeholder{color:var(--ve-ink3)}
.ve-input[aria-invalid="true"]{border-color:var(--ve-bad)}
.ve-textarea{height:80px;padding:8px 12px;resize:vertical;min-height:56px;max-height:200px;line-height:1.5}
select.ve-select,.ve-tex select.ve-tex__in{display:block;-webkit-appearance:auto;appearance:auto;padding:0 8px;line-height:1.2;cursor:pointer;background-color:var(--ve-raise)}
.ve-select option,.ve-tex__in option{background:var(--ve-base);color:var(--ve-fg)}
.ve-tex{display:grid;grid-template-columns:1fr 1fr;gap:12px 8px}
.ve-tex__f{display:flex;flex-direction:column;gap:4px;min-width:0}
.ve-tex__k{font-size:10.5px;font-weight:600;letter-spacing:.06em;text-transform:uppercase;color:var(--ve-ink3);white-space:nowrap;overflow:hidden;text-overflow:ellipsis}
.ve-tex__in[type="color"]{padding:4px;cursor:pointer}
.ve-tex__in:disabled{opacity:.45;cursor:not-allowed}
.ve-seg{display:grid;grid-auto-flow:column;grid-auto-columns:1fr;gap:4px;padding:4px;border-radius:8px;background:var(--ve-deep);height:40px;width:100%}
.ve-seg button{display:flex;align-items:center;justify-content:center;border-radius:6px;font-size:12px;font-weight:600;color:var(--ve-ink2);border:0;background:transparent;cursor:pointer;transition:background-color .15s,color .15s}
.ve-seg button:hover{color:var(--ve-fg)}
.ve-seg button[aria-pressed="true"]{background:var(--ve-raise2);color:var(--ve-fg);box-shadow:0 1px 2px #0006}
.ve-seg button[disabled]{opacity:.45;cursor:default}
.ve-seg button:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px}
.ve-volrow{display:flex;align-items:center;gap:12px}
.ve-volrow input[type="range"]{width:auto;flex:1;min-width:0}
.ve-volval{font-size:12px;font-variant-numeric:tabular-nums;min-width:48px;text-align:right;color:var(--ve-ink2)}
.ve-actions{display:flex;flex-direction:row;flex-wrap:wrap;gap:8px}
.ve-facts{display:grid;grid-template-columns:auto minmax(0,1fr);gap:8px 16px;margin:0;font-size:12px}
.ve-facts dt{color:var(--ve-ink3)}
.ve-facts dd{margin:0;font-variant-numeric:tabular-nums}
.ve-mus__empty{display:flex;flex-direction:column;gap:8px;align-items:flex-start}
.ve-mus__chks{display:flex;flex-direction:column;gap:4px}
.ve-mus__chk{display:flex;align-items:center;gap:8px;min-height:32px;padding:0 8px;margin:0 -8px;font-size:12px;cursor:pointer;color:var(--ve-fg);border-radius:8px;transition:background-color .15s}
.ve-mus__chk input{accent-color:var(--ve-accent);margin:0;flex:none;width:16px;height:16px}
.ve-mus__chk span{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;min-width:0}
.ve-mus__chk:hover{background:var(--ve-soft)}
.ve-mus__chk:focus-within{outline:2px solid var(--ve-accent);outline-offset:-1px}
.ve-mus__chk--off{opacity:.5;cursor:not-allowed}
.ve-mus__chk--off:hover{background:transparent}
.ve-sfx__row{border-top:1px solid var(--ve-line);padding-top:12px;margin-top:8px}
.ve-tcout{flex:1;height:32px;display:flex;align-items:center;gap:4px;border-radius:8px;background:var(--ve-raise);padding:0 12px;font-family:var(--dt-font-mono,ui-monospace,SFMono-Regular,Menlo,monospace);font-size:12px;color:var(--ve-fg)}
.ve-tcout input{border:0;background:transparent;color:inherit;font:inherit;width:100%;min-width:0;padding:0}
.ve-tcout input:focus-visible{outline:2px solid var(--ve-accent);outline-offset:2px;border-radius:2px}
.ve-note{margin:0;font-size:11px;color:var(--ve-ink3)}
.ve-out{display:flex;flex-direction:column;gap:8px;margin-top:8px;padding-top:12px;border-top:1px solid var(--ve-line)}
.ve-out__p{display:block;padding:8px;border-radius:8px;background:var(--ve-deep);font-family:var(--dt-font-mono,ui-monospace,SFMono-Regular,Consolas,monospace);font-size:11px;color:var(--ve-ink2);word-break:break-all}
.ve-out__a{display:flex;gap:8px;flex-wrap:wrap}
.ve-out__v{width:100%;max-height:260px;background:#000;border-radius:8px;margin:8px 0}
/* ---- estados: vacío, carga, error ------------------------------------------------ */
.ve-center{flex:1;display:grid;place-items:center;padding:24px;min-height:0}
.ve-es{max-width:440px;text-align:center;display:flex;flex-direction:column;align-items:center;gap:8px}
.ve-es__icon{width:48px;height:48px;border-radius:16px;display:grid;place-items:center;color:var(--ve-accent);background:color-mix(in oklab,var(--ve-accent) 15%,transparent);margin-bottom:8px}
.ve-es__icon .ve-i{width:24px;height:24px}
.ve-es__icon--err{color:var(--ve-bad);background:color-mix(in oklab,var(--ve-bad) 15%,transparent)}
.ve-es__t{font-size:16px;font-weight:600}
.ve-es__b{font-size:12px;color:var(--ve-ink2);line-height:1.6;max-width:384px}
.ve-es__actions{display:flex;gap:8px;margin-top:8px;flex-wrap:wrap;justify-content:center}
.ve-drop{width:100%;max-width:480px;min-height:216px;border:1.5px dashed var(--ve-line2);border-radius:16px;display:flex;flex-direction:column;align-items:center;justify-content:center;gap:8px;text-align:center;padding:24px;background:color-mix(in oklab,var(--ve-fg) 3%,transparent);transition:border-color .15s,background-color .15s}
.ve-drop--active{border-color:var(--ve-accent);border-style:solid;background:color-mix(in oklab,var(--ve-accent) 10%,transparent)}
.ve-skel{background:linear-gradient(100deg,var(--ve-raise) 30%,var(--ve-raise2) 50%,var(--ve-raise) 70%);background-size:200% 100%;border-radius:8px;animation:ve-shimmer 1.4s linear infinite}
@keyframes ve-shimmer{to{background-position:-200% 0}}
.ve-loadrow{display:flex;align-items:center;gap:8px;font-size:12px;color:var(--ve-ink2);padding:8px 16px;border-radius:20px;background:var(--ve-base);box-shadow:0 8px 24px -12px #000}
.ve-spin{width:14px;height:14px;border-radius:50%;border:2px solid var(--ve-line2);border-top-color:var(--ve-accent);animation:ve-spin .8s linear infinite;flex:none}
@keyframes ve-spin{to{transform:rotate(360deg)}}
.ve-plist{display:flex;flex-direction:column;gap:4px;width:min(400px,92%);max-height:232px;overflow:auto;border:1px solid var(--ve-line);border-radius:12px;padding:8px;margin-top:8px;background:var(--ve-base)}
/* ---- avisos (toasts) -------------------------------------------------------------- */
.ve-toasts{position:absolute;top:56px;left:50%;transform:translateX(-50%);z-index:14;display:flex;flex-direction:column;align-items:center;gap:8px;pointer-events:none;width:min(480px,92%)}
.ve-toast{pointer-events:auto;display:flex;align-items:center;gap:12px;min-width:200px;max-width:100%;padding:8px 8px 8px 16px;border-radius:12px;background:var(--ve-raise2);color:var(--ve-fg);font-size:12px;box-shadow:0 12px 32px -12px #000,0 0 0 1px var(--ve-line2);animation:ve-toast-in .24s var(--ve-ease)}
.ve-toast .ve-i{flex:none}
.ve-toast--ok .ve-i:first-child{color:var(--ve-ok)}
.ve-toast--bad{box-shadow:0 12px 32px -12px #000,0 0 0 1px color-mix(in oklab,var(--ve-bad) 60%,transparent)}
.ve-toast--bad .ve-i:first-child{color:var(--ve-bad)}
.ve-toast--info .ve-i:first-child{color:var(--ve-accent)}
.ve-toast__m{flex:1;min-width:0;line-height:1.4;overflow-wrap:anywhere}
.ve-toast__bar{display:block;height:3px;border-radius:2px;background:var(--ve-line2);overflow:hidden;margin-top:4px}
.ve-toast__bar i{display:block;height:100%;background:var(--ve-accent);transition:width .2s linear}
@keyframes ve-toast-in{from{opacity:0;transform:translateY(-8px) scale(.98)}to{opacity:1;transform:none}}
/* ---- diálogos, menús ------------------------------------------------------------- */
.ve-scrim{position:absolute;inset:0;background:color-mix(in oklab,#000 55%,transparent);backdrop-filter:blur(3px);z-index:10;animation:ve-fade .18s var(--ve-ease)}
.ve-dialog{position:absolute;left:50%;top:50%;transform:translate(-50%,-50%);width:min(448px,92%);max-height:88%;overflow:auto;background:var(--ve-base);border:1px solid var(--ve-line2);border-radius:16px;padding:24px;z-index:11;display:flex;flex-direction:column;gap:16px;box-shadow:0 32px 80px -24px #000;animation:ve-pop .2s var(--ve-ease)}
@keyframes ve-pop{from{opacity:0;transform:translate(-50%,-48%) scale(.97)}to{opacity:1;transform:translate(-50%,-50%)}}
.ve-dialog__t{font-size:16px;font-weight:600}
.ve-dialog__b{font-size:12px;color:var(--ve-ink2);line-height:1.6}
.ve-dialog__f{display:flex;gap:8px;justify-content:flex-end;flex-wrap:wrap}
.ve-progress{height:6px;border-radius:3px;background:var(--ve-line2);overflow:hidden}
.ve-progress>i{display:block;height:100%;background:var(--ve-accent);border-radius:3px;transition:width .15s linear}
.ve-stages{display:flex;flex-direction:column;gap:8px;font-size:12px;padding:0;margin:0}
.ve-stages li{display:flex;align-items:center;gap:8px;list-style:none;color:var(--ve-ink3)}
.ve-stages li[data-state="active"]{color:var(--ve-fg);font-weight:600}
.ve-stages li[data-state="done"]{color:var(--ve-ink2)}
.ve-list{display:flex;flex-direction:column;gap:4px;max-height:232px;overflow:auto;border:1px solid var(--ve-line);border-radius:12px;padding:8px}
.ve-file{display:flex;align-items:center;gap:8px;height:32px;padding:0 8px;border-radius:8px;font-size:12px;cursor:pointer;text-align:left;border:0;background:transparent;width:100%;transition:background-color .15s}
.ve-file:hover{background:var(--ve-soft)}
.ve-file input{accent-color:var(--ve-accent);margin:0}
.ve-file__n{overflow:hidden;text-overflow:ellipsis;white-space:nowrap;flex:1;min-width:0}
.ve-file__s{font-size:11px;color:var(--ve-ink3);font-variant-numeric:tabular-nums}
.ve-menu{position:absolute;z-index:12;min-width:216px;background:var(--ve-raise);border:1px solid var(--ve-line2);border-radius:12px;padding:4px;box-shadow:0 20px 48px -16px #000;display:flex;flex-direction:column;gap:2px;animation:ve-pop-m .16s var(--ve-ease)}
@keyframes ve-pop-m{from{opacity:0;transform:translateY(-4px)}to{opacity:1;transform:none}}
.ve-menu button{display:flex;align-items:center;height:32px;padding:0 12px;border:0;background:transparent;border-radius:8px;font-size:12px;text-align:left;cursor:pointer;width:100%;transition:background-color .12s}
.ve-menu button:hover{background:var(--ve-soft)}
.ve-menu button:focus-visible{outline:2px solid var(--ve-accent);outline-offset:-2px}
.ve-log{font-family:var(--dt-font-mono,ui-monospace,SFMono-Regular,Menlo,monospace);font-size:11px;white-space:pre-wrap;word-break:break-all;max-height:200px;overflow:auto;border-radius:8px;background:var(--ve-deep);padding:8px;color:var(--ve-ink2)}
.ve-stub{border-style:dashed}
.ve-sr{position:absolute;width:1px;height:1px;overflow:hidden;clip:rect(0 0 0 0);white-space:nowrap}
.ve-compact-hide{display:none}
.ve-tip{position:absolute;right:16px;top:56px;z-index:13;max-width:264px;padding:8px 12px;border-radius:12px;background:var(--ve-raise2);color:var(--ve-fg);font-size:12px;line-height:1.5;box-shadow:0 12px 32px -12px #000,0 0 0 1px var(--ve-line2)}
/* ---- anchos ----------------------------------------------------------------------- */
.ve-root[data-layout="mid"] .ve-hdr .ve-model,.ve-root[data-layout="mid"] .ve-title{display:none}
.ve-root[data-layout="mid"] .ve-transport__row{padding:0 12px}
.ve-root[data-layout="narrow"] .ve-hdr{padding:0 8px;gap:4px}
.ve-root[data-layout="narrow"] .ve-hdr .ve-title,.ve-root[data-layout="narrow"] .ve-hdr .ve-model,.ve-root[data-layout="narrow"] .ve-hdr .ve-sep,.ve-root[data-layout="narrow"] .ve-hdr .ve-chip--ghost{display:none}
.ve-root[data-layout="narrow"] .ve-chip{max-width:136px}
.ve-root[data-layout="narrow"] .ve-auto{padding:0 4px}
.ve-root[data-layout="narrow"] .ve-auto span.ve-auto__t{display:none}
.ve-root[data-layout="narrow"] .ve-stage{padding:40px 12px 8px}
.ve-root[data-layout="narrow"] .ve-transport__row{padding:0 8px;grid-template-columns:auto 1fr auto}
.ve-root[data-layout="narrow"] .ve-transport__r .ve-goto{display:none}
.ve-root[data-layout="narrow"] .ve-tl{--w-head:40px}
.ve-root[data-layout="narrow"] .ve-lh{padding:0;justify-content:center}
.ve-root[data-layout="narrow"] .ve-lh span{display:none}
.ve-root[data-layout="narrow"] .ve-tl__bar .ve-tl__sum{display:none}
.ve-root[data-layout="narrow"] .ve-tc{font-size:11px}
.ve-root[data-layout="narrow"] .ve-tc b{font-size:13px}
.ve-root[data-layout="narrow"] .ve-play{margin:0 4px}
@media (max-height:700px){.ve-tl{--h-video:48px;--h-text:24px;--h-audio:24px;--h-music:24px}}
@media (prefers-reduced-motion:reduce){.ve-root *{transition:none!important;animation:none!important}}
/* Botón de la barra de título (vive fuera de .ve-root: tokens con respaldo). */
.ve-tb{display:inline-flex;align-items:center;gap:6px;height:26px;padding:0 8px;border-radius:7px;border:1px solid var(--ui-stroke-tertiary,var(--border));background:transparent;color:var(--ui-text-secondary,var(--foreground));font:inherit;font-size:11px;line-height:1;cursor:pointer;white-space:nowrap}
.ve-tb:hover{background:var(--ui-surface-2,rgba(127,127,127,.14));color:var(--ui-text-primary,var(--foreground))}
.ve-tb[aria-pressed="true"]{color:var(--ui-accent,var(--accent));border-color:color-mix(in oklab,var(--ui-accent,var(--accent)) 55%,transparent);background:color-mix(in oklab,var(--ui-accent,var(--accent)) 12%,transparent)}
.ve-tb:focus-visible{outline:2px solid var(--ui-accent,var(--accent));outline-offset:1px}
/* Cine — pantalla de la skill cinematic-film */
.ve-dialog--wide{width:min(920px,94%);max-height:90%}
.ve-cine__head{display:flex;align-items:center;gap:10px;flex-wrap:wrap}
.ve-cine{display:flex;flex-direction:column;gap:14px;min-height:0}
.ve-cine__cols{display:grid;grid-template-columns:minmax(220px,300px) 1fr;gap:20px;min-height:0}
@media (max-width:720px){.ve-cine__cols{grid-template-columns:1fr}}
.ve-cine__col{display:flex;flex-direction:column;gap:10px;min-width:0}
.ve-cine__col--main{overflow:auto}
.ve-cine__h{font-size:11px;letter-spacing:.08em;text-transform:uppercase;color:var(--ve-ink3);font-weight:600;margin:0}
.ve-cine__list{list-style:none;margin:0;padding:0;display:flex;flex-direction:column;gap:4px;max-height:210px;overflow:auto}
.ve-cine__item{display:flex;flex-direction:column;gap:2px;width:100%;text-align:left;padding:8px 10px;border-radius:9px;border:1px solid transparent;background:transparent;color:var(--ve-ink);font:inherit;cursor:pointer}
.ve-cine__item:hover{background:var(--ve-hover,rgba(127,127,127,.12))}
.ve-cine__item.is-on{border-color:var(--ve-accent);background:color-mix(in oklab,var(--ve-accent) 14%,transparent)}
.ve-cine__item-n{font-size:13px;font-weight:600}
.ve-cine__item-s{font-size:11px;color:var(--ve-ink2)}
.ve-cine__muted{font-size:12px;color:var(--ve-ink2);margin:0}
.ve-cine__meta{font-size:12px;color:var(--ve-ink2);margin:0 0 10px}
.ve-cine__warn{font-size:12px;padding:10px 12px;border-radius:9px;background:color-mix(in oklab,#e6a700 16%,transparent);color:var(--ve-ink)}
.ve-cine__error{font-size:12px;padding:10px 12px;border-radius:9px;background:color-mix(in oklab,#e5484d 18%,transparent);color:var(--ve-ink)}
.ve-cine__video{width:100%;max-height:300px;border-radius:11px;margin-top:12px;background:#000}
.ve-cine__lines{margin:12px 0 0;padding-left:20px;display:flex;flex-direction:column;gap:5px;font-size:12px;color:var(--ve-ink2);line-height:1.5}
.ve-cine__note{font-size:11px;color:var(--ve-ink3);line-height:1.55;margin-top:14px}
.ve-cine__pick{display:flex;flex-direction:column;gap:5px}
.ve-cine__hint{font-size:11px;color:var(--ve-ink3);line-height:1.45}
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
  image: 'M4 5h16v14H4z M8 11l3 3 2-2 3 3',
  plus: 'M12 5v14 M5 12h14',
  mute: 'M5 9v6h3l4 4V5L8 9z M17 9l5 6 M22 9l-5 6',
  type: 'M5 6V4h14v2 M12 4v16 M9 20h6',
  music: 'M9 18V5l11-2v13 M6 21a3 3 0 100-6 3 3 0 000 6z M17 19a3 3 0 100-6 3 3 0 000 6z',
  zoomin: 'M11 4a7 7 0 100 14 7 7 0 000-14z M21 21l-5-5 M8 11h6 M11 8v6',
  zoomout: 'M11 4a7 7 0 100 14 7 7 0 000-14z M21 21l-5-5 M8 11h6',
  fit: 'M4 9V4h5 M20 9V4h-5 M4 15v5h5 M20 15v5h-5',
  layers: 'M12 3l9 5-9 5-9-5z M3 13l9 5 9-5',
  sliders: 'M4 7h9 M17 7h3 M4 12h3 M11 12h9 M4 17h11 M19 17h1 M15 5v4 M9 10v4 M17 15v4',
  info: 'M12 4a8 8 0 100 16 8 8 0 000-16z M12 11v5 M12 8h.01',
  checkcircle: 'M12 4a8 8 0 100 16 8 8 0 000-16z M8 12l3 3 5-6',
  sparkle: 'M12 3l1.8 5.2L19 10l-5.2 1.8L12 17l-1.8-5.2L5 10l5.2-1.8z M19 16l.8 2.2L22 19l-2.2.8L19 22l-.8-2.2L16 19l2.2-.8z',
  trash: 'M5 7h14 M9 7V4h6v3 M7 7l1 13h8l1-13 M10 11v6 M14 11v6'
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
      className: `ve-btn ve-btn--${variant}${!label ? ' ve-btn--icon' : ''}${block ? ' ve-btn--block' : ''}${size === 'sm' ? ' ve-btn--sm' : ''}`,
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

// ---------------------------------------------------------------- cine
// Pantalla de la skill cinematic-film: crear un film, lanzarlo y verlo, sin
// salir del pane. Todo pasa por la API del servicio (/cinematic/...).

function CinePanel({ ctx, onClose }) {
  const [cargando, setCargando] = useState(true)
  const [error, setError] = useState('')
  const [proyectos, setProyectos] = useState([])
  const [estadoSkill, setEstadoSkill] = useState(null)
  const [sel, setSel] = useState('')
  const [detalle, setDetalle] = useState(null)
  const [nombre, setNombre] = useState('')
  const [titulo, setTitulo] = useState('')
  const [piel, setPiel] = useState('studio')
  const [pieles, setPieles] = useState({})
  const [lineas, setLineas] = useState([])
  const [creando, setCreando] = useState(false)
  const [lanzando, setLanzando] = useState(false)
  const vivoRef = useRef(true)

  const cargar = async () => {
    try {
      const datos = await request(ctx, '/cinematic')
      if (!vivoRef.current) return
      setProyectos((datos && datos.proyectos) || [])
      setEstadoSkill((datos && datos.status) || null)
      setPieles(((datos && datos.status) || {}).pieles || {})
      setError('')
    } catch (fallo) {
      if (vivoRef.current) setError(fallo && fallo.message ? fallo.message : String(fallo))
    } finally {
      if (vivoRef.current) setCargando(false)
    }
  }

  const verDetalle = async (nombreProyecto) => {
    if (!nombreProyecto) {
      setDetalle(null)
      setLineas([])
      return
    }
    try {
      const [est, guion] = await Promise.all([
        request(ctx, `/cinematic/projects/${encodeURIComponent(nombreProyecto)}`),
        request(ctx, `/cinematic/projects/${encodeURIComponent(nombreProyecto)}/script`).catch(() => ({ lineas: [] }))
      ])
      if (!vivoRef.current) return
      setDetalle(est)
      setLineas((guion && guion.lineas) || [])
    } catch (fallo) {
      if (vivoRef.current) setError(fallo && fallo.message ? fallo.message : String(fallo))
    }
  }

  useEffect(() => {
    vivoRef.current = true
    cargar()
    return () => {
      vivoRef.current = false
    }
  }, [])

  useEffect(() => {
    verDetalle(sel)
  }, [sel])

  // Mientras hay un render en marcha, se pregunta cada 3 s. Fuera de eso, nada.
  useEffect(() => {
    if (!detalle || !detalle.corriendo) return undefined
    const t = setInterval(async () => {
      await verDetalle(sel)
      await cargar()
    }, 3000)
    return () => clearInterval(t)
  }, [detalle, sel])

  const crear = async () => {
    const limpio = nombre.trim().toLowerCase().replace(/[^a-z0-9-]+/g, '-').replace(/^-+|-+$/g, '')
    if (!limpio) {
      setError('Ponle un nombre: minúsculas, números y guiones.')
      return
    }
    setCreando(true)
    setError('')
    try {
      await request(ctx, '/cinematic/projects', {
        method: 'POST',
        body: { name: limpio, title: titulo.trim() || limpio, look: piel }
      })
      await cargar()
      setSel(limpio)
      setNombre('')
      setTitulo('')
    } catch (fallo) {
      setError(fallo && fallo.message ? fallo.message : String(fallo))
    } finally {
      setCreando(false)
    }
  }

  const renderizar = async () => {
    if (!sel) return
    setLanzando(true)
    setError('')
    try {
      await request(ctx, `/cinematic/projects/${encodeURIComponent(sel)}/render`, { method: 'POST' })
      await verDetalle(sel)
      await cargar()
    } catch (fallo) {
      setError(fallo && fallo.message ? fallo.message : String(fallo))
    } finally {
      setLanzando(false)
    }
  }

  const salidaUrl = detalle && detalle.salida ? `${serviceBase(ctx).replace(/\/+$/, '')}/cinematic/projects/${encodeURIComponent(sel)}/output` : ''

  return h(
    'div',
    { className: 've-ov', role: 'presentation', onClick: onClose },
    h(
      'div',
      { className: 've-dialog ve-dialog--wide', role: 'dialog', 'aria-modal': 'true', 'aria-label': 'Cine · cinematic-film', onClick: (e) => e.stopPropagation() },
      h(
        'div',
        { className: 've-cine__head' },
        h(Icon, { name: 'film' }),
        h('h2', { className: 've-dialog__t' }, 'Cine'),
        h('span', { className: 've-dialog__b' }, 'cinematic-film · voz, cámara y sonido'),
        h(Btn, { variant: 'text', label: 'Cerrar', onClick: onClose })
      ),
      h(
        'div',
        { className: 've-cine' },
        estadoSkill && !estadoSkill.disponible
          ? h(
              'p',
              { className: 've-cine__warn' },
              `La skill no está completa. Faltan: ${(estadoSkill.faltan || []).join(', ') || 'varios scripts'}.`
            )
          : null,
        error ? h('p', { className: 've-cine__error', role: 'alert' }, error) : null,
        cargando
          ? h('p', { className: 've-cine__muted' }, 'Mirando qué hay…')
          : h(
              'div',
              { className: 've-cine__cols' },
              h(
                'div',
                { className: 've-cine__col' },
                h('h3', { className: 've-cine__h' }, 'Películas'),
                proyectos.length
                  ? h(
                      'ul',
                      { className: 've-cine__list' },
                      proyectos.map((p) =>
                        h(
                          'li',
                          { key: p.proyecto },
                          h(
                            'button',
                            {
                              type: 'button',
                              className: `ve-cine__item${sel === p.proyecto ? ' is-on' : ''}`,
                              onClick: () => setSel(p.proyecto)
                            },
                            h('span', { className: 've-cine__item-n' }, p.proyecto),
                            h(
                              'span',
                              { className: 've-cine__item-s' },
                              p.terminado ? 'lista' : p.corriendo ? `${p.etapa || 'render'} · ${p.porcentaje || 0}%` : 'sin render'
                            )
                          )
                        )
                      )
                    )
                  : h('p', { className: 've-cine__muted' }, 'Todavía no hay ninguna.'),
                h('h3', { className: 've-cine__h' }, 'Nueva'),
                h('input', {
                  className: 've-input',
                  placeholder: 'nombre (ej. lanzamiento)',
                  value: nombre,
                  onInput: (e) => setNombre(e.target.value)
                }),
                h('input', {
                  className: 've-input',
                  placeholder: 'título visible',
                  value: titulo,
                  onInput: (e) => setTitulo(e.target.value)
                }),
                h(
                  'label',
                  { className: 've-cine__pick' },
                  h('span', { className: 've-cine__h' }, 'Piel'),
                  h(
                    'select',
                    {
                      className: 've-input',
                      value: piel,
                      onChange: (e) => setPiel(e.target.value)
                    },
                    Object.keys(pieles).length
                      ? Object.keys(pieles).map((k) => h('option', { key: k, value: k }, k))
                      : ['studio', 'blueprint', 'night', 'slate', 'charcoal', 'wall', 'paper'].map((k) =>
                          h('option', { key: k, value: k }, k)
                        )
                  ),
                  pieles[piel] ? h('span', { className: 've-cine__hint' }, pieles[piel]) : null
                ),
                h(Btn, {
                  variant: 'primary',
                  block: true,
                  label: creando ? 'Creando…' : 'Crear película',
                  disabled: creando,
                  onClick: crear
                })
              ),
              h(
                'div',
                { className: 've-cine__col ve-cine__col--main' },
                !sel
                  ? h('p', { className: 've-cine__muted' }, 'Elige una película de la izquierda.')
                  : h(
                      'div',
                      {},
                      h('h3', { className: 've-cine__h' }, sel),
                      detalle
                        ? h(
                            'p',
                            { className: 've-cine__meta' },
                            detalle.error
                              ? `Error: ${detalle.error}`
                              : detalle.terminado
                                ? `Lista${detalle.segundos ? ` en ${Math.round(detalle.segundos)} s` : ''}`
                                : detalle.corriendo
                                  ? `${detalle.etapa || 'trabajando'} · ${detalle.porcentaje || 0}%`
                                  : 'Sin render todavía. Lanza cuando quieras.'
                          )
                        : null,
                      h(Btn, {
                        variant: 'primary',
                        label: lanzando ? 'Lanzando…' : detalle && detalle.corriendo ? 'Renderizando…' : 'Renderizar',
                        disabled: lanzando || (detalle && detalle.corriendo),
                        onClick: renderizar
                      }),
                      salidaUrl
                        ? h('video', {
                            className: 've-cine__video',
                            src: salidaUrl,
                            controls: true,
                            preload: 'metadata'
                          })
                        : null,
                      lineas.length
                        ? h(
                            'ol',
                            { className: 've-cine__lines' },
                            lineas.slice(0, 12).map((l, i) => h('li', { key: i }, l.text || l.vo || ''))
                          )
                        : null,
                      h(
                        'p',
                        { className: 've-cine__note' },
                        'La película se cronometra contra la voz: primero se graba la narración y la cámara se coloca sobre ella. Un film corto tarda decenas de minutos.'
                      )
                    )
              )
            )
      )
    )
  )
}


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

// Campo numérico escribible: guarda lo que tecleas mientras tienes el foco (así
// "2.", "2,5" o "6" camino de "60" no se pisan) y solo aplica valores válidos y
// dentro de rango; al salir vuelve al valor real. Flechas: ±step (Mayús ×10).
function NumField({ value, onCommit, min = -Infinity, max = Infinity, step = 1, decimals = 2, format, ariaLabel, className, disabled, title, onBlur }) {
  const show = (v) => (format ? format(v) : decimals === 0 ? String(Math.round(Number(v) || 0)) : Number(v || 0).toFixed(decimals))
  const [draft, setDraft] = useState(null)
  const parse = (raw) => {
    const text = String(raw == null ? '' : raw).trim().replace(',', '.')
    if (!text) return null
    const number = Number(text)
    return Number.isFinite(number) ? number : null
  }
  return h('input', {
    className,
    inputMode: 'decimal',
    autoComplete: 'off',
    value: draft === null ? show(value) : draft,
    disabled: !!disabled,
    title,
    'aria-label': ariaLabel,
    onFocus: (event) => {
      setDraft(show(value))
      if (event.target && event.target.select) event.target.select()
    },
    onChange: (event) => {
      const raw = event.target.value
      if (!/^[-+]?\d*[.,]?\d*$/.test(raw)) return
      setDraft(raw)
      const number = parse(raw)
      if (number !== null && number >= min && number <= max) onCommit(number)
    },
    onKeyDown: (event) => {
      if (event.key === 'Enter') {
        event.preventDefault()
        event.target.blur()
      } else if (event.key === 'Escape') {
        setDraft(null)
        event.target.blur()
      } else if (event.key === 'ArrowUp' || event.key === 'ArrowDown') {
        event.preventDefault()
        const base = parse(draft === null ? show(value) : draft)
        const next = clamp((base === null ? Number(value) || 0 : base) + (event.key === 'ArrowUp' ? 1 : -1) * step * (event.shiftKey ? 10 : 1), min, max)
        const rounded = round3(next)
        setDraft(show(rounded))
        onCommit(rounded)
      }
    },
    onBlur: () => {
      const number = parse(draft === null ? '' : draft)
      if (number !== null && draft !== null) onCommit(clamp(number, min, max))
      setDraft(null)
      if (onBlur) onBlur()
    }
  })
}

// Miniatura real de la escena (primer fotograma del tramo). Las imágenes usan la
// propia imagen; el vídeo carga solo metadatos y un fotograma, nunca reproduce.
function Thumb({ src, kind, at, large }) {
  const cls = `ve-thumb${large ? ' ve-thumb--lg' : ''}`
  if (!src) return h('span', { className: cls, 'aria-hidden': 'true' }, h(Icon, { name: 'film', size: 'sm' }))
  if (kind === 'image') return h('img', { className: cls, src, alt: '', draggable: false, loading: 'lazy' })
  if (kind === 'audio') return h('span', { className: cls, 'aria-hidden': 'true' }, h(Icon, { name: 'volume', size: 'sm' }))
  return h('video', {
    className: cls,
    src: `${src}#t=${Math.max(0.05, Number(at) || 0.05).toFixed(2)}`,
    muted: true,
    playsInline: true,
    preload: 'metadata',
    tabIndex: -1,
    'aria-hidden': 'true'
  })
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
  const [railTab, setRailTab] = useState('scene')
  const [libOpen, setLibOpen] = useState(false)
  const [picker, setPicker] = useState(null)
  const [modelTip, setModelTip] = useState(false)
  const [width, setWidth] = useState(900)
  const [undoDepth, setUndoDepth] = useState(0)
  const [redoDepth, setRedoDepth] = useState(0)
  const [cineOpen, setCineOpen] = useState(false)

  const [, setTick] = useState(0)
  const rootRef = useRef(null)
  const videoRef = useRef(null)
  const undoRef = useRef([])
  const redoRef = useRef([])
  const autoRef = useRef(null)
  const savingRef = useRef(false)
  const seekRef = useRef(0)
  const pollRef = useRef(null)
  const tlRowRef = useRef(null)
  const dragRef = useRef(null)
  const [dragUi, setDragUi] = useState(null)
  const [zoom, setZoom] = useState(1)
  const [leftTab, setLeftTab] = useState('scenes')
  const [snapT, setSnapT] = useState(null)
  const tlScrollRef = useRef(null)

  const docRef = useRef(null)
  const baseRef = useRef(null)
  const lastMutRef = useRef(null)
  const dirtyRef = useRef(false)
  const scrubRef = useRef(null)
  const saveRef = useRef(null)
  const pendingSaveRef = useRef(false)
  docRef.current = doc
  dirtyRef.current = dirty

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

  // La etiqueta «Guardado hace…» se refresca sola; los avisos se apagan a los 6 s.
  useEffect(() => {
    const timer = setInterval(() => setTick((value) => (value + 1) % 1000), 15000)
    return () => clearInterval(timer)
  }, [])
  useEffect(() => {
    if (!notice) return undefined
    const timer = setTimeout(() => setNotice(''), /^Guardado$/.test(notice) ? 2200 : 6000)
    return () => clearTimeout(timer)
  }, [notice])
  // Con zoom, el cursor se mantiene a la vista mientras reproduces o saltas.
  useEffect(() => {
    const box = tlScrollRef.current
    if (!box || zoom <= 1.001 || !total) return
    const x = (cursor / total) * (box.scrollWidth - 24)
    if (x < box.scrollLeft + 24 || x > box.scrollLeft + box.clientWidth - 48) box.scrollLeft = Math.max(0, x - box.clientWidth * 0.35)
  }, [cursor, zoom, total])

  // -------------------------------------------------------------- guardado

  const save = useCallback(
    async (options = {}) => {
      const current = docRef.current
      if (!current) return false
      if (savingRef.current) {
        // Ya hay un guardado en vuelo: este se encadena justo después (antes se perdía).
        pendingSaveRef.current = true
        return true
      }
      if (!options.force && !dirtyRef.current) return true
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
          setNotice(options.force ? 'Guardado' : '')
        }
        return true
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
        return false
      } finally {
        savingRef.current = false
        if (pendingSaveRef.current) {
          pendingSaveRef.current = false
          setTimeout(() => saveRef.current && saveRef.current(), 0)
        }
      }
    },
    [ctx]
  )
  saveRef.current = save
  // Al salir de un campo: el guardado espera a que React aplique el cambio que
  // ese mismo evento acaba de hacer (si no, se guardaba el documento anterior).
  const saveSoon = useCallback(() => {
    setTimeout(() => saveRef.current && saveRef.current(), 0)
  }, [])

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

  // `key` agrupa ediciones seguidas del mismo control (teclear, arrastrar un
  // slider): un solo paso de deshacer por gesto, no uno por pulsación.
  const mutate = useCallback((fn, key) => {
    const current = docRef.current
    if (!current) return
    const now = Date.now()
    const last = lastMutRef.current
    const merge = !!key && !!last && last.key === key && now - last.at < COALESCE_MS && undoRef.current.length > 0
    lastMutRef.current = key ? { key, at: now } : null
    if (!merge) {
      undoRef.current = [...undoRef.current.slice(-49), JSON.stringify(current)]
      setUndoDepth(undoRef.current.length)
    }
    redoRef.current = []
    setRedoDepth(0)
    const next = fn(clone(current))
    setDoc(next)
    setDirty(true)
  }, [])

  const undo = useCallback(() => {
    const stack = undoRef.current
    if (!stack.length || !docRef.current) return
    const previous = stack[stack.length - 1]
    lastMutRef.current = null
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
    lastMutRef.current = null
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
    }, `caption:${sel.id}`)
  }

  const setSceneVolume = (value) => {
    if (!sel) return
    const volume = clamp(Math.round(value / 5) * 5, 0, 100)
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (!scene) return draft
      scene.audio = { ...(scene.audio || {}), volume }
      return draft
    }, `vol:${sel.id}`)
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
    }, `in:${sel.id}`)
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
    }, `out:${sel.id}`)
  }

  const trimAtCursor = (edge) => {
    if (!sel || !at.row || at.row.id !== sel.id) return
    const local = at.local * sceneSpeed(sel)
    if (edge === 'in') setIn(round3(Number(sel.in) + local))
    else setOut(round3(Number(sel.in) + local))
  }

  const splitHere = () => {
    if (!sel || !at.row || at.row.id !== sel.id) return
    const localSrc = at.local * sceneSpeed(sel)
    const offset = Number(sel.in) + localSrc
    if (localSrc < MIN_SCENE || sceneDuration(sel) - localSrc < MIN_SCENE) {
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
      if (scene.text && scene.text[0]) scene.text[0].until = round3(visibleDuration(scene))
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
    }, `trs:${sel.id}`)
  }

  // -------------------------------------------------------------- música

  const setMusic = (patch) => {
    mutate((draft) => {
      if (!draft.music) return draft
      draft.music = { ...draft.music, ...patch }
      return draft
    }, `music:${Object.keys(patch).join(',')}`)
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
    }, `ev:${id}:${Object.keys(patch).join(',')}`)
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
    }, `txt:${sel.id}:${Object.keys(patch).join(',')}`)
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
    }, `flt:${sel.id}:${key}`)
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
    }, `kb:${sel.id}:${Object.keys(patch).join(',')}`)
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
    }, `spd:${sel.id}`)
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
    }, `logo:${Object.keys(patch).join(',')}`)
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
    }, 'master')
  }

  // -------------------------------------------------------------- reproducción

  useEffect(() => {
    const video = videoRef.current
    if (!video || !at.row) return
    const rate = sceneSpeed(at.row.scene)
    const target = Number(at.row.scene.in) + at.local * rate
    try {
      video.playbackRate = rate
    } catch (error) {
      /* velocidad no admitida por este medio */
    }
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
    const speed = sceneSpeed(scene)
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
    if (playing) setCursor(at.row.start + clamp(local / speed, 0, at.row.duration))
  }

  // -------------------------------------------------------------- exportación

  const startExport = async ({ captions, openWhenDone, preset }) => {
    if (!doc) return
    const chosen = preset || exportPreset || PRESET
    setDialog({ kind: 'export', phase: 'queued', captions, openWhenDone })
    try {
      // Un autoguardado en curso se espera; si hay cambios sin guardar se guardan
      // ahora. Exportar nunca usa una revisión vieja del documento.
      for (let waited = 0; savingRef.current && waited < 150; waited += 1) await new Promise((resolve) => setTimeout(resolve, 100))
      if (dirtyRef.current) {
        const saved = await save({ force: false })
        if (saved === false) throw new Error('No se pudo guardar antes de exportar. Revisa el aviso y vuelve a intentarlo.')
      }
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

  const layout = width >= 1100 ? 'wide' : width >= 760 ? 'mid' : 'narrow'
  const compact = layout === 'narrow'
  const tight = width < 600
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
  const canExport = !!doc && (doc.scenes || []).length > 0 && missing.length === 0 && !(job && ['queued', 'running', 'probing', 'rendering', 'validating', 'promoting'].includes(job.state))
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
  const savedLabel =
    status === 'saving'
      ? 'Guardando…'
      : status === 'failed'
        ? 'No se pudo guardar'
        : dirty
          ? 'Cambios sin guardar'
          : savedAt
            ? `Guardado ${relativeTime(savedAt)}`
            : 'Sin cambios'
  const autosaveTone = status === 'saving' || (dirty && status !== 'failed') ? 'warn' : status === 'failed' ? 'bad' : 'good'

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

  // -------------------------------------------------------------- regiones

  const header = () => {
    const layoutName = layout
    const wide = layoutName === 'wide'
    const narrow = layoutName === 'narrow'
    return h(
      'header',
      { className: 've-hdr' },
      h('span', { className: 've-plate' }, h(Icon, { name: 'film' })),
      !narrow ? h('span', { className: 've-title' }, 'Editor de vídeo') : null,
      h('span', { className: 've-sep' }),
      h(
        'button',
        {
          type: 'button',
          className: 've-chip',
          onClick: () => setMenu(menu === 'projects' ? null : 'projects'),
          title: doc ? `Cambiar de proyecto · revisión ${doc.revision}` : 'Elegir un proyecto',
          'aria-haspopup': 'menu',
          'aria-expanded': menu === 'projects'
        },
        h('span', { className: 've-chip__name' }, doc ? doc.title : 'Sin proyecto'),
        h(Icon, { name: 'down', size: 'sm' })
      ),
      h(Btn, {
        variant: 'ghost',
        size: 'sm',
        icon: 'film',
        label: narrow ? undefined : 'Cine',
        title: 'Cine · la skill cinematic-film: voz, cámara y sonido',
        ariaLabel: 'Abrir Cine',
        onClick: () => setCineOpen(true)
      }),
      h(
        'span',
        { className: `ve-auto ve-auto--${autosaveTone}`, 'aria-live': 'polite', title: savedLabel },
        status === 'saving' ? h(Spinner) : h(Dot, { tone: autosaveTone }),
        h('span', { className: 've-auto__t' }, savedLabel)
      ),
      h('span', { className: 've-spacer' }),
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
      modelName && wide
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
            h(Icon, { name: 'message', size: 'sm' }),
            h('span', { className: 've-chip__name' }, modelName)
          )
        : null,
      h('span', { className: 've-sep' }),
      h(Btn, { icon: 'undo', variant: 'ghost', ariaLabel: 'Deshacer', title: 'Deshacer · Ctrl+Z', onClick: undo, disabled: !undoDepth }),
      h(Btn, { icon: 'redo', variant: 'ghost', ariaLabel: 'Rehacer', title: 'Rehacer · Ctrl+Shift+Z', onClick: redo, disabled: !redoDepth }),
      !wide
        ? h(Btn, {
            icon: 'layers',
            variant: libOpen ? 'outline' : 'ghost',
            ariaLabel: 'Medios y escenas',
            title: 'Medios y escenas',
            disabled: !doc,
            onClick: () => {
              setLibOpen((prev) => !prev)
              setRailOpen(false)
            }
          })
        : null,
      compact
        ? h(Btn, {
            icon: 'sliders',
            variant: railOpen ? 'outline' : 'ghost',
            ariaLabel: 'Propiedades',
            title: 'Escenas y propiedades',
            disabled: !doc,
            onClick: () => {
              setRailOpen((prev) => !prev)
              setLibOpen(false)
            }
          })
        : null,
      h(Btn, {
        icon: 'save',
        variant: 'outline',
        ...(wide ? { label: status === 'saving' ? 'Guardando…' : 'Guardar', title: 'Guardar · Ctrl+S' } : { ariaLabel: 'Guardar', title: 'Guardar · Ctrl+S' }),
        onClick: () => save({ force: true }),
        disabled: !doc
      }),
      h(Btn, { icon: 'more', variant: 'ghost', ariaLabel: 'Más acciones', onClick: () => setMenu(menu === 'more' ? null : 'more') }),
      h(Btn, {
        variant: 'primary',
        icon: 'download',
        label: narrow ? 'Exportar' : `Exportar ${doc ? `${doc.height}p · ${docFps}` : 'MP4'}`,
        disabled: !canExport,
        title: canExport ? 'Exportar MP4 (Ctrl+E)' : !(doc && (doc.scenes || []).length) ? 'Añade al menos una escena para exportar' : missing.length ? 'Falta un medio: vuelve a vincularlo' : 'Ya hay una exportación en curso',
        onClick: () => setDialog({ kind: 'exportForm' })
      }),
      h(Btn, {
        icon: 'close',
        variant: 'ghost',
        ariaLabel: 'Cerrar editor de vídeo (Ctrl+Shift+E)',
        title: 'Cerrar (Ctrl+Shift+E)',
        onClick: () => {
          if (typeof onClose === 'function') onClose()
        }
      })
    )
  }

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
          {
            title: projects.length ? 'Elige un proyecto' : 'Empieza tu primer vídeo',
            body: projects.length
              ? 'Abre uno de tus proyectos o crea uno nuevo para montar tu vídeo.'
              : 'Crea un proyecto, importa tus clips e imágenes y exporta un MP4. También puedes pedírselo a Hermes en el chat.'
          },
          projects.length
            ? h(
                'div',
                { className: 've-plist', role: 'list', 'aria-label': 'Tus proyectos' },
                projects.slice(0, 8).map((item) =>
                  h(
                    'button',
                    { key: item.projectId, type: 'button', role: 'listitem', className: 've-file', onClick: () => openProject(item.projectId) },
                    h(Icon, { name: 'film', size: 'sm' }),
                    h('span', { className: 've-file__n' }, item.title || item.projectId),
                    h('span', { className: 've-file__s' }, item.updatedAt ? relativeTime(Date.parse(item.updatedAt)) : '')
                  )
                )
              )
            : null,
          h('div', { className: 've-es__actions' }, h(Btn, { variant: 'primary', icon: 'plus', label: 'Crear proyecto', onClick: createProject }))
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
        h('span', { className: 've-stage__name' }, currentScene ? currentScene.name || `Escena ${at.index + 1}` : 'Vista previa'),
        h(Badge, { tone: 'accent' }, orient.short),
        h('span', { className: 've-stage__sp' }),
        h('span', { className: 've-stage__count' }, `Escena ${at.index + 1} de ${doc.scenes.length}`)
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
                  video.currentTime = Number(currentScene.in) + at.local * sceneSpeed(currentScene)
                } catch (error) {
                  /* metadatos aún no listos */
                }
              },
              'aria-label': `Vista previa de ${currentScene ? currentScene.name : 'la escena'}`
            })
          : null,
          guides ? h('div', { className: 've-guides', 'aria-hidden': 'true' }) : null,
          currentScene && captionOf(currentScene)
            ? (() => {
                // La vista previa respeta posición, color y tamaño reales del texto.
                const item = textItemOf(currentScene) || {}
                const frameH = parseInt(fitStyle.height, 10) || canvasBox.h || 360
                const px = clamp(((Number(item.size) || TEXT_SIZE.default) / orient.h) * frameH, 9, 90)
                const shadow = Number(item.shadow) || 0
                return h(
                  'div',
                  {
                    className: `ve-cap ve-cap--${item.position === 'top' || item.position === 'center' ? item.position : 'bottom'}`,
                    style: {
                      fontSize: `${Math.round(px)}px`,
                      color: hexOr(item.color, undefined),
                      textShadow: shadow ? `0 0 ${shadow}px #000, 0 ${Math.ceil(shadow / 2)}px ${shadow}px #000` : undefined
                    }
                  },
                  captionOf(currentScene)
                )
              })()
            : null
        )
      )
    )
  }

  const transport = () => {
    if (!doc || !(doc.scenes || []).length) return null
    const hasScenes = true
    return h(
      'div',
      { className: 've-transport' },
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
      h(
        'div',
        { className: 've-transport__row' },
        h('span', { className: 've-tc', title: 'Tiempo exacto (mm:ss.ms). Escribe uno a la derecha para saltar.' }, h('b', null, fmtTimecode(cursor)), ` / ${fmtTimecode(total)}`),
        h(
          'div',
          { className: 've-transport__c' },
          h(Btn, { icon: 'start', variant: 'ghost', ariaLabel: 'Ir al inicio', title: 'Ir al inicio · Inicio', onClick: () => setCursor(0) }),
          h(Btn, {
            icon: 'prev',
            variant: 'ghost',
            ariaLabel: 'Escena anterior',
            title: 'Escena anterior',
            disabled: at.index <= 0,
            onClick: () => {
              const row = rows[Math.max(0, at.index - 1)]
              if (row) {
                setCursor(row.start)
                setSelId(row.id)
              }
            }
          }),
          h('button', {
            type: 'button',
            className: 've-btn ve-btn--icon ve-play',
            'aria-label': playing ? 'Pausar' : 'Reproducir',
            title: playing ? 'Pausar · Espacio' : 'Reproducir · Espacio',
            disabled: !hasScenes,
            onClick: () => setPlaying((prev) => !prev)
          }, h(Icon, { name: playing ? 'pause' : 'play' })),
          h(Btn, {
            icon: 'next',
            variant: 'ghost',
            ariaLabel: 'Escena siguiente',
            title: 'Escena siguiente',
            disabled: at.index < 0 || at.index >= rows.length - 1,
            onClick: () => {
              const row = rows[Math.min(rows.length - 1, at.index + 1)]
              if (row) {
                setCursor(row.start)
                setSelId(row.id)
              }
            }
          }),
          h(Btn, { icon: 'end', variant: 'ghost', ariaLabel: 'Ir al final', title: 'Ir al final · Fin', onClick: () => setCursor(total) })
        ),
        h(
          'div',
          { className: 've-transport__r' },
          h('input', {
            className: 've-goto',
            defaultValue: '',
            placeholder: 'Ir a…',
            title: 'Escribe un tiempo (ej. 1:23.5) y pulsa Enter para saltar',
            inputMode: 'decimal',
            'aria-label': 'Ir al tiempo (mm:ss.ms)',
            onKeyDown: (event) => {
              if (event.key !== 'Enter') return
              const seconds = parseTimecode(event.target.value)
              if (seconds !== null) setCursor(clamp(seconds, 0, total))
              event.target.value = ''
            }
          }),
          h(Btn, {
            icon: muted ? 'mute' : 'volume',
            variant: 'ghost',
            ariaLabel: muted ? 'Activar sonido' : 'Silenciar',
            title: muted ? 'Activar sonido' : 'Silenciar',
            onClick: () => {
              const next = !muted
              setMuted(next)
              if (ctx && ctx.storage && ctx.storage.set) ctx.storage.set('transport.muted', next)
            }
          })
        )
      )
    )
  }

  const fmtRuler = (t) => (total >= 90 || t >= 60 ? `${Math.floor(t / 60)}:${String(Math.round(t % 60)).padStart(2, '0')}` : `${Math.round(t * 10) / 10}s`.replace('.', ','))

  // Imán: el cursor se pega a los bordes de escena si pasa a ≤7 px (con aviso visual).
  const scrubTo = (event, settle) => {
    const rect = event.currentTarget.getBoundingClientRect()
    if (!(rect.width > 0) || !total) return
    let time = round3(clamp(((event.clientX - rect.left) / rect.width) * total, 0, total))
    const threshold = 7 / (rect.width / total)
    const marks = [0, ...rows.map((row) => row.start + row.duration)]
    const near = marks.find((mark) => Math.abs(mark - time) <= threshold)
    if (near !== undefined && !event.altKey) {
      time = round3(clamp(near, 0, total))
      setSnapT(time)
    } else {
      setSnapT(null)
    }
    setCursor(time)
    if (settle) {
      const hit = sceneAt(docRef.current, time)
      if (hit.row) setSelId(hit.row.id)
      setTimeout(() => setSnapT(null), 450)
    }
  }

  const ruler = () => {
    const pxFull = 600 * zoom
    const want = Math.max(1, total / Math.max(3, Math.floor(pxFull / 90)))
    const steps = [0.5, 1, 2, 5, 10, 15, 30, 60, 120, 300]
    const step = steps.find((value) => value >= want) || 600
    const marks = []
    for (let t = 0; t <= total + 0.01; t += step) {
      const pct = total ? (t / total) * 100 : 0
      marks.push(h('span', { key: `m${t}`, className: 've-tick ve-tick--major', style: { left: `${pct}%` } }, h('em', null, fmtRuler(t))))
      const minor = step / 2
      if (minor >= 0.25 && t + minor <= total) {
        marks.push(h('span', { key: `n${t}`, className: 've-tick', style: { left: `${((t + minor) / total) * 100}%` }, 'aria-hidden': 'true' }))
      }
    }
    return h(
      'div',
      {
        className: 've-tl__ruler',
        role: 'presentation',
        title: 'Haz clic o arrastra para mover el cursor (Alt: sin imán)',
        onPointerDown: (event) => {
          scrubRef.current = event.pointerId
          try { event.currentTarget.setPointerCapture(event.pointerId) } catch (error) { /* no-op */ }
          scrubTo(event, false)
        },
        onPointerMove: (event) => {
          if (scrubRef.current === event.pointerId) scrubTo(event, false)
        },
        onPointerUp: (event) => {
          if (scrubRef.current !== event.pointerId) return
          scrubRef.current = null
          try { event.currentTarget.releasePointerCapture(event.pointerId) } catch (error) { /* no-op */ }
          scrubTo(event, true)
        },
        onPointerCancel: () => {
          scrubRef.current = null
          setSnapT(null)
        }
      },
      marks
    )
  }

  // ---- Arrastrar en la línea de tiempo (mover escenas y recortar bordes) -----
  // Se apoya en las mismas mutaciones que los botones y las flechas: un solo
  // paso de deshacer por gesto y el mismo guardado con revisión.
  const moveSceneTo = (from, to) => {
    if (!doc || from === to || to < 0 || to >= doc.scenes.length) return
    mutate((draft) => {
      const [item] = draft.scenes.splice(from, 1)
      draft.scenes.splice(to, 0, item)
      return draft
    })
    setNotice(`Escena ${from + 1} movida a la posición ${to + 1}`)
  }

  const trimLimits = (scene) => {
    const assetId = assetFor(scene)
    const asset = (media || []).find((item) => item.id === assetId)
    if (asset && asset.kind === 'image') return { maxOut: 600 }
    // El servicio no entrega la duración de la fuente: el tope es lo más largo que
    // ese medio ha tenido en el proyecto (se puede alargar más con el campo numérico).
    let maxOut = Number(scene.out) || 0
    ;(doc.scenes || []).forEach((other) => {
      if (assetFor(other) === assetId) maxOut = Math.max(maxOut, Number(other.out) || 0)
    })
    const video = videoRef.current
    if (video && Number.isFinite(video.duration) && activeAsset === assetId) maxOut = Math.max(maxOut, video.duration)
    return { maxOut }
  }

  const trimScene = (id, edge, value) => {
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === id)
      if (!scene) return draft
      if (edge === 'in') scene.in = round3(clamp(value, 0, Number(scene.out) - MIN_SCENE))
      else scene.out = round3(Math.max(Number(scene.in) + MIN_SCENE, value))
      if (scene.text && scene.text[0]) scene.text[0].until = round3(visibleDuration(scene))
      fitTransition(draft.scenes, scene)
      return draft
    })
  }

  const clipPointerDown = (event, row, index) => {
    if (event.button !== undefined && event.button !== 0) return
    const rowEl = tlRowRef.current
    const el = event.currentTarget
    if (!rowEl || !el) return
    const rect = el.getBoundingClientRect()
    const cls = (event.target && event.target.className) || ''
    const edge = typeof cls === 'string' && cls.includes('ve-trim--l') ? 'in' : typeof cls === 'string' && cls.includes('ve-trim--r') ? 'out' : null
    dragRef.current = {
      id: row.id,
      index,
      mode: edge ? 'trim' : 'move',
      edge,
      startX: event.clientX,
      pxPerSec: rect.width / Math.max(row.duration, 0.1),
      speed: sceneSpeed(row.scene),
      startIn: Number(row.scene.in) || 0,
      startOut: Number(row.scene.out) || 0,
      limits: trimLimits(row.scene),
      moved: false,
      pointerId: event.pointerId
    }
    try { el.setPointerCapture(event.pointerId) } catch (error) { /* no-op */ }
  }

  const clipPointerMove = (event) => {
    const d = dragRef.current
    if (!d) return
    const dx = event.clientX - d.startX
    if (!d.moved && Math.abs(dx) < 4) return
    d.moved = true
    if (d.mode === 'move') {
      const rowEl = tlRowRef.current
      let target = d.index
      if (rowEl) {
        const kids = Array.from(rowEl.children)
        const x = event.clientX
        // el clip arrastrado lleva un translateX: se mide en su hueco original
        const spans = kids.map((kid, i) => {
          const r = kid.getBoundingClientRect()
          const shift = i === d.index ? d.lastDx || 0 : 0
          return { left: r.left - shift, right: r.right - shift }
        })
        target = spans.findIndex((r) => x >= r.left && x <= r.right)
        if (target < 0) target = x < spans[0].left ? 0 : spans.length - 1
      }
      d.target = target
      d.lastDx = dx
      setDragUi({ id: d.id, mode: 'move', dx, target })
      return
    }
    const delta = (dx / d.pxPerSec) * (d.speed || 1)
    let nextIn = d.startIn
    let nextOut = d.startOut
    if (d.edge === 'in') nextIn = round3(clamp(d.startIn + delta, 0, d.startOut - MIN_SCENE))
    else nextOut = round3(clamp(d.startOut + delta, d.startIn + MIN_SCENE, Math.max(d.limits.maxOut, d.startOut)))
    d.nextIn = nextIn
    d.nextOut = nextOut
    setDragUi({ id: d.id, mode: 'trim', dur: (nextOut - nextIn) / (d.speed || 1), edge: d.edge })
  }

  const clipPointerUp = (event) => {
    const d = dragRef.current
    if (!d) return
    try { event.currentTarget.releasePointerCapture(d.pointerId) } catch (error) { /* no-op */ }
    setDragUi(null)
    if (!d.moved) {
      dragRef.current = null
      return
    }
    // el click que sigue al arrastre no debe cambiar la selección ni el cursor
    const done = d
    setTimeout(() => { if (dragRef.current === done) dragRef.current = null }, 0)
    d.settled = true
    if (d.mode === 'move') {
      if (typeof d.target === 'number' && d.target !== d.index) moveSceneTo(d.index, d.target)
    } else if (d.edge === 'in') {
      if (Math.abs(d.nextIn - d.startIn) > 1e-6) trimScene(d.id, 'in', d.nextIn)
    } else if (Math.abs(d.nextOut - d.startOut) > 1e-6) {
      trimScene(d.id, 'out', d.nextOut)
    }
  }

  const clipPointerCancel = () => {
    dragRef.current = null
    setDragUi(null)
  }

  const zoomBy = (factor) => setZoom((prev) => clamp(Math.round(prev * factor * 100) / 100, 1, 12))

  const clipThumbs = (row, index) => {
    const scene = row.scene
    const assetId = assetFor(scene)
    const asset = assetId ? (media || []).find((item) => item.id === assetId) : null
    if (!asset || asset.exists === false || !doc) return null
    const src = mediaUrl(ctx, doc.projectId, assetId)
    const tiles = index < 8 && asset.kind !== 'image' ? (zoom >= 3 ? 6 : zoom >= 1.5 ? 4 : 3) : 1
    const span = Math.max(0, (Number(scene.out) || 0) - (Number(scene.in) || 0))
    const list = []
    for (let k = 0; k < tiles; k += 1) {
      list.push(h(Thumb, { key: k, src, kind: asset.kind, at: (Number(scene.in) || 0) + (span * k) / Math.max(1, tiles) }))
    }
    return h('span', { className: 've-clip__thumbs', 'aria-hidden': 'true' }, list)
  }

  const timelineBlock = () => {
    if (!doc) return null
    const scenes = doc.scenes || []
    const empty = !scenes.length
    const hasText = rows.some((row) => captionOf(row.scene))
    const pct = (value) => (total ? clamp(value / total, 0, 1) * 100 : 0)
    const tcls = (extra) => `ve-tl__row ve-tl__row--${extra}`
    return h(
      'div',
      { className: 've-tl' },
      h(
        'div',
        { className: 've-tl__bar' },
        h(Btn, { icon: 'scissors', variant: 'ghost', size: 'sm', label: layout === 'narrow' ? undefined : 'Dividir', ariaLabel: 'Partir en el cursor', title: 'Partir en el cursor · S', onClick: splitHere, disabled: !sel }),
        h('span', { className: 've-sep' }),
        h('span', { className: 've-tl__sum ve-ftr__hint', 'aria-live': 'polite' }, queueLabel()),
        h('span', { className: 've-spacer' }),
        h(
          'div',
          { className: 've-zoom', role: 'group', 'aria-label': 'Zoom de la línea de tiempo' },
          h(Btn, { icon: 'zoomout', variant: 'ghost', size: 'sm', ariaLabel: 'Alejar', title: 'Alejar · Ctrl+rueda', disabled: zoom <= 1, onClick: () => zoomBy(1 / 1.5) }),
          h('span', { className: 've-zoom__v', 'aria-live': 'polite' }, `${Math.round(zoom * 100)} %`),
          h(Btn, { icon: 'zoomin', variant: 'ghost', size: 'sm', ariaLabel: 'Acercar', title: 'Acercar · Ctrl+rueda', disabled: zoom >= 12, onClick: () => zoomBy(1.5) }),
          h(Btn, { icon: 'fit', variant: 'ghost', size: 'sm', ariaLabel: 'Ajustar a la ventana', title: 'Ajustar a la ventana', disabled: zoom === 1, onClick: () => setZoom(1) })
        )
      ),
      h(
        'div',
        { className: 've-tl__body' },
        h(
          'div',
          { className: 've-tl__heads' },
          h('div', { className: 've-lh ve-lh--video', title: 'Vídeo y escenas' }, h(Icon, { name: 'film', size: 'sm' }), h('span', null, 'Vídeo')),
          h('div', { className: 've-lh ve-lh--text', title: 'Texto en pantalla' }, h(Icon, { name: 'type', size: 'sm' }), h('span', null, 'Texto')),
          h('div', { className: 've-lh ve-lh--audio', title: 'Audio de las escenas y voz' }, h(Icon, { name: 'volume', size: 'sm' }), h('span', null, 'Audio')),
          h('div', { className: 've-lh ve-lh--music', title: 'Música de fondo' }, h(Icon, { name: 'music', size: 'sm' }), h('span', null, 'Música'))
        ),
        h(
          'div',
          {
            className: 've-tl__scroll',
            ref: tlScrollRef,
            'data-zoom': zoom <= 1.001 ? '1' : '0',
            onWheel: (event) => {
              if (!(event.ctrlKey || event.metaKey)) return
              event.preventDefault()
              zoomBy(event.deltaY < 0 ? 1.25 : 1 / 1.25)
            }
          },
          h(
            'div',
            { className: 've-tl__inner', style: { width: zoom <= 1.001 ? undefined : `${zoom * 100}%` } },
            h(
              'div',
              { className: 've-tl__lanes' },
            ruler(),
            h(
              'div',
              { className: tcls('video'), ref: tlRowRef, role: 'list', 'aria-label': `Línea de tiempo, ${total.toFixed(1)} segundos` },
              empty ? h('span', { className: 've-lane-hint' }, 'Aquí aparecerán tus escenas · importa medios para empezar') : null,
              rows.map((row, index) =>
                h(
                  'button',
                  {
                    key: row.id,
                    type: 'button',
                    role: 'listitem',
                    className: `ve-clip${row.id === selId ? ' ve-clip--sel' : ''}${dragUi && dragUi.id === row.id && dragUi.mode === 'move' ? ' ve-clip--drag' : ''}${dragUi && dragUi.mode === 'move' && dragUi.target === index && dragUi.id !== row.id ? ' ve-clip--drop' : ''}`,
                    style: {
                      flex: `${Math.max(dragUi && dragUi.mode === 'trim' && dragUi.id === row.id ? dragUi.dur : row.duration, 0.1)} 1 0%`,
                      transform: dragUi && dragUi.mode === 'move' && dragUi.id === row.id ? `translateX(${Math.round(dragUi.dx)}px)` : undefined,
                      touchAction: 'none'
                    },
                    onPointerDown: (event) => clipPointerDown(event, row, index),
                    onPointerMove: clipPointerMove,
                    onPointerUp: clipPointerUp,
                    onPointerCancel: clipPointerCancel,
                    onClick: (event) => {
                      if (dragRef.current && dragRef.current.moved) return
                      setSelId(row.id)
                      // Clic de ratón: salta al punto exacto del clip; teclado: al inicio.
                      const rect = event.currentTarget.getBoundingClientRect()
                      const frac = event.detail > 0 && rect.width > 0 ? clamp((event.clientX - rect.left) / rect.width, 0, 0.999) : 0
                      setCursor(round3(row.start + frac * row.duration))
                    },
                    'aria-label': `Escena ${index + 1}, ${row.scene.name || 'sin nombre'}, ${row.duration.toFixed(1)} segundos`,
                    'aria-current': row.id === selId ? 'true' : undefined
                  },
                  clipThumbs(row, index),
                  h('span', { className: 've-clip__n' }, String(index + 1).padStart(2, '0')),
                  h('span', { className: 've-clip__t' }, row.scene.name || `Escena ${index + 1}`),
                  h('span', { className: 've-clip__d' }, `${fmtTime(dragUi && dragUi.mode === 'trim' && dragUi.id === row.id ? dragUi.dur : row.duration)}`),
                  row.id === selId
                    ? [
                        h('span', { key: 'l', className: 've-trim ve-trim--l', role: 'presentation', title: 'Arrastra para recortar el inicio' }),
                        h('span', { key: 'r', className: 've-trim ve-trim--r', role: 'presentation', title: 'Arrastra para recortar el final' })
                      ]
                    : null,
                  row.scene.needsRelink ? h(Badge, { tone: 'warn' }, 'falta') : null
                )
              )
            ),
            h(
              'div',
              { className: tcls('text'), 'aria-label': 'Textos en pantalla' },
              rows.map((row, index) => {
                const text = captionOf(row.scene)
                const item = textItemOf(row.scene) || {}
                const vis = Math.max(row.duration, 0.1)
                const from = clamp((Number(item.at) || 0) / vis, 0, 0.98)
                const to = clamp((item.until == null ? vis : Number(item.until)) / vis, from + 0.02, 1)
                return h(
                  'div',
                  { key: row.id, className: 've-tx', style: { flex: `${vis} 1 0%` } },
                  text
                    ? h(
                        'button',
                        {
                          type: 'button',
                          className: `ve-txb${row.id === selId ? ' ve-txb--sel' : ''}`,
                          style: { left: `${from * 100}%`, width: `${(to - from) * 100}%` },
                          title: `Texto de la escena ${index + 1}: ${text}`,
                          'aria-label': `Texto de la escena ${index + 1}`,
                          onClick: () => {
                            setSelId(row.id)
                            setRailTab('scene')
                            setCursor(round3(row.start + from * vis))
                          }
                        },
                        h(Icon, { name: 'type', size: 'sm' }),
                        h('span', null, text)
                      )
                    : null
                )
              }),
              !hasText ? h('span', { className: 've-lane-hint' }, empty ? 'Sin textos' : 'Sin textos · escríbelos en Escena › Texto en pantalla') : null
            ),
            h(
              'div',
              { className: tcls('audio'), 'aria-label': 'Volumen de cada escena' },
              rows.map((row) => {
                const volume = clamp(Number(row.scene.audio && row.scene.audio.volume), 0, 100) || 0
                return h(
                  'span',
                  {
                    key: row.id,
                    className: `ve-ab${row.id === selId ? ' ve-ab--sel' : ''}`,
                    style: { flex: `${Math.max(row.duration, 0.1)} 1 0%` },
                    title: `Escena ${rows.indexOf(row) + 1}: audio al ${volume} %`
                  },
                  h('i', { style: { height: `${Math.max(volume, volume ? 8 : 0)}%` } }),
                  h('small', null, volume === 0 ? 'mudo' : `${volume} %`)
                )
              }),
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
                          style: { left: `${pct(Number(ev.at) || 0)}%` },
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
            h(
              'div',
              { className: tcls('music') },
              music && musicAsset
                ? h(
                    'div',
                    { className: 've-mrow', title: `Música de fondo: ${baseName(musicAsset.path)} · ${typeof music.volume === 'number' ? music.volume : MUSIC_DEFAULTS.volume} %` },
                    h(Icon, { name: 'music', size: 'sm' }),
                    h('span', null, `${baseName(musicAsset.path)} · ${typeof music.volume === 'number' ? music.volume : MUSIC_DEFAULTS.volume} %`)
                  )
                : h('span', { className: 've-lane-hint' }, 'Sin música · elige una pista en Audio')
            ),
            snapT !== null ? h('div', { className: 've-snapline', style: { '--ve-sn': `${pct(snapT)}%` }, 'aria-hidden': 'true' }) : null,
            h('div', { className: 've-playhead', style: { '--ve-ph': `${pct(cursor)}%` }, 'aria-hidden': 'true' })
            )
          )
        )
      )
    )
  }

  const side = () => {
    if (!doc) return null
    const drawer = layout !== 'wide'
    if (drawer && !libOpen) return null
    const scenesList = doc.scenes || []
    const sceneList = () =>
      scenesList.length
        ? h(
            'div',
            { className: 've-scenes', role: 'group', 'aria-label': 'Lista de escenas' },
            scenesList.map((scene, index) =>
              h(
                'div',
                { key: scene.id, className: 've-scene-row' },
                h(
                  'button',
                  {
                    type: 'button',
                    className: 've-scene',
                    'aria-current': scene.id === selId ? 'true' : undefined,
                    'aria-label': `Escena ${index + 1}, ${scene.name || 'sin nombre'}, ${fmtTime(visibleDuration(scene))}`,
                    onClick: () => {
                      setSelId(scene.id)
                      const row = rows[index]
                      if (row) setCursor(row.start)
                      if (drawer) setLibOpen(false)
                    }
                  },
                  h('span', { className: 've-scene__n' }, String(index + 1).padStart(2, '0')),
                  thumbFor(scene, index, false),
                  h(
                    'span',
                    { className: 've-scene__m' },
                    h('span', { className: 've-scene__name' }, scene.name || `Escena ${index + 1}`),
                    h('span', { className: 've-scene__dur' }, `${fmtTime(visibleDuration(scene))}${captionOf(scene) ? ' · con texto' : ''}${scene.needsRelink ? ' · falta medio' : ''}`)
                  )
                ),
                h(
                  'div',
                  { className: 've-scene-row__mv' },
                  h('button', { type: 'button', className: 've-mv', 'aria-label': `Subir escena ${index + 1}`, title: 'Subir (Alt+↑)', disabled: index === 0, onClick: () => moveScene(index, -1) }, h(Icon, { name: 'up', size: 'sm' })),
                  h('button', { type: 'button', className: 've-mv', 'aria-label': `Bajar escena ${index + 1}`, title: 'Bajar (Alt+↓)', disabled: index === scenesList.length - 1, onClick: () => moveScene(index, 1) }, h(Icon, { name: 'down', size: 'sm' }))
                )
              )
            )
          )
        : h('p', { className: 've-lib__empty' }, 'Aún no hay escenas. Importa un clip, una imagen o una captura y aparecerá aquí.')
    const mediaList = () =>
      media.length
        ? h(
            'div',
            { className: 've-lib__list' },
            media.map((item) =>
              h(
                'div',
                { key: item.id, className: 've-lib__row' },
                h(
                  'button',
                  {
                    type: 'button',
                    className: 've-lib__item',
                    'aria-current': activeAsset === item.id ? 'true' : undefined,
                    title: item.path,
                    onClick: () => {
                      const target = (doc.scenes || []).find((scene) => (scene.source && scene.source.assetId) === item.id)
                      if (target) setSelId(target.id)
                      if (drawer) setLibOpen(false)
                      setNotice(`Medio seleccionado: ${baseName(item.path)}`)
                    }
                  },
                  h(Thumb, { src: item.exists === false ? null : mediaUrl(ctx, doc.projectId, item.id), kind: item.kind, at: 0.1 }),
                  h(
                    'span',
                    { className: 've-lib__m' },
                    h('span', { className: 've-lib__n' }, baseName(item.path)),
                    h('span', { className: 've-lib__s' }, `${item.kind || 'medio'}${item.exists === false ? ' · falta' : ''}${item.bytes ? ` · ${fmtBytes(item.bytes)}` : ''}`)
                  )
                ),
                item.kind !== 'audio'
                  ? h('button', { type: 'button', className: 've-mv', 'aria-label': `Añadir ${baseName(item.path)} como escena`, title: 'Añadir como escena', onClick: () => applyAdd(item) }, h(Icon, { name: 'plus', size: 'sm' }))
                  : null
              )
            )
          )
        : h('p', { className: 've-lib__empty' }, 'Sin medios todavía. Pulsa «Importar medios» para traer archivos de la carpeta concedida.')
    return h(
      'aside',
      { className: 've-side', 'aria-label': 'Medios y escenas' },
      drawer
        ? h('div', { className: 've-pt' }, h('span', { className: 've-pt__t' }, 'Medios y escenas'), h('span', { className: 've-spacer' }), h(Btn, { icon: 'close', variant: 'ghost', ariaLabel: 'Cerrar medios y escenas', onClick: () => setLibOpen(false) }))
        : null,
      h(
        'div',
        { className: 've-segtabs', role: 'group', 'aria-label': 'Ver' },
        h('button', { type: 'button', id: 've-ltab-scenes', 'aria-pressed': leftTab === 'scenes', onClick: () => setLeftTab('scenes') }, h(Icon, { name: 'layers', size: 'sm' }), 'Escenas', h('em', { 'aria-hidden': 'true' }, String(scenesList.length))),
        h('button', { type: 'button', id: 've-ltab-media', 'aria-pressed': leftTab === 'media', onClick: () => setLeftTab('media') }, h(Icon, { name: 'image', size: 'sm' }), 'Medios', h('em', { 'aria-hidden': 'true' }, String(media.length)))
      ),
      leftTab === 'media' ? mediaList() : sceneList(),
      h('div', { className: 've-side__foot' }, h(Btn, { variant: 'outline', icon: 'upload', label: 'Importar medios', block: true, onClick: importFolder, disabled: !doc }))
    )
  }

  const toastTone = (text) => (/no se pudo|error|fall[óo]|rechaz|inv[áa]lid|no responde|falta/i.test(text) ? 'bad' : /guardad|importad|a[ñn]adid|reemplazad|combinaron|actualizado|restablecid/i.test(text) ? 'ok' : 'info')

  const toasts = () => {
    const busy = job && ['queued', 'running', 'probing', 'rendering', 'validating', 'promoting'].includes(job.state) && !dialog
    if (!notice && !busy) return null
    const tone = notice ? toastTone(notice) : 'info'
    return h(
      'div',
      { className: 've-toasts', role: 'status', 'aria-live': 'polite' },
      notice
        ? h(
            'div',
            { key: notice, className: `ve-toast ve-toast--${tone}` },
            h(Icon, { name: tone === 'bad' ? 'alert' : tone === 'ok' ? 'checkcircle' : 'info' }),
            h('span', { className: 've-toast__m' }, notice),
            h(Btn, { icon: 'close', variant: 'ghost', size: 'sm', ariaLabel: 'Cerrar aviso', onClick: () => setNotice('') })
          )
        : null,
      busy
        ? h(
            'div',
            { key: 'job', className: 've-toast ve-toast--info' },
            h(Spinner),
            h(
              'span',
              { className: 've-toast__m' },
              typeof job.progress === 'number' ? `Exportando… ${Math.round(job.progress)} %` : 'Exportando…',
              h('span', { className: 've-toast__bar' }, h('i', { style: { width: `${clamp(Number(job.progress) || 4, 2, 100)}%` } }))
            ),
            h(Btn, { variant: 'text', size: 'sm', label: 'Ver', onClick: () => setDialog({ kind: 'export', phase: 'running', jobId: job.jobId, captions: incCaptions }) })
          )
        : null
    )
  }

  const railTabs = [
    { id: 'scene', label: 'Escena', icon: 'film' },
    { id: 'fx', label: 'Efectos', icon: 'sparkle' },
    { id: 'audio', label: 'Audio', icon: 'volume' },
    { id: 'project', label: 'Proyecto', icon: 'sliders' }
  ]

  const setSceneName = (value) => {
    if (!sel) return
    mutate((draft) => {
      const scene = draft.scenes.find((item) => item.id === sel.id)
      if (scene) scene.name = String(value).slice(0, 120)
      return draft
    }, `name:${sel.id}`)
  }

  const thumbFor = (scene, index, large) => {
    const assetId = assetFor(scene)
    const asset = assetId ? (media || []).find((item) => item.id === assetId) : null
    const src = doc && assetId && index < 40 ? mediaUrl(ctx, doc.projectId, assetId) : null
    return h(Thumb, { src: asset && asset.exists === false ? null : src, kind: asset ? asset.kind : 'video', at: scene.in, large })
  }

  // ---- piezas de la pestaña «Escena» -----------------------------------------
  const pName = () =>
    h(
      'label',
      { className: 've-f' },
      h('span', { className: 've-f__l' }, 'Nombre de la escena'),
      h('input', {
        className: 've-input',
        value: sel.name || '',
        maxLength: 120,
        placeholder: `Escena ${selIndex + 1}`,
        'aria-label': 'Nombre de la escena',
        onChange: (event) => setSceneName(event.target.value),
        onBlur: saveSoon
      })
    )

  const pCaption = () => (
              h(
      'label',
      { className: 've-f' },
      h('span', { className: 've-f__l' }, 'Texto en pantalla', h('span', { className: 've-counter' }, `${captionOf(sel).length}/${MAX_CAPTION}`)),
      h('textarea', {
        className: 've-textarea',
        value: captionOf(sel),
        maxLength: MAX_CAPTION,
        placeholder: 'Escribe lo que se verá en pantalla durante la escena',
        onChange: (event) => writeCaption(event.target.value),
        onBlur: saveSoon
      })
    )
  )

  const pTextStyle = () => {
    const item = textItemOf(sel) || {}
    const hasText = !!String(captionOf(sel)).trim()
    const anim = item.animation && typeof item.animation === 'object' ? item.animation : {}
    const position = item.position || 'bottom'
    const num = (key, label, limits, aria) =>
      styleField(
        key,
        label,
        h(NumField, {
          className: 've-tex__in',
          value: Number.isFinite(Number(item[key])) ? Number(item[key]) : limits.default,
          min: limits.min,
          max: limits.max,
          step: 1,
          decimals: 0,
          disabled: !hasText,
          title: hasText ? undefined : 'Escribe un texto en la escena para darle estilo',
          ariaLabel: aria,
          onCommit: (value) => setTextStyle({ [key]: Math.round(value) }),
          onBlur: saveSoon
        })
      )
    const anims = (slot, label, aria) =>
      h(
        'label',
        { className: 've-tex__f' },
        h('span', { className: 've-tex__k' }, label),
        h(
          'select',
          {
            className: 've-tex__in',
            value: anim[slot] || 'none',
            disabled: !hasText,
            'aria-label': aria,
            onChange: (event) => setTextAnimation(slot, event.target.value)
          },
          TEXT_ANIMATIONS.map((opt) => h('option', { key: opt.id, value: opt.id }, opt.label))
        )
      )
    return h(
      'div',
      { className: 've-f' },
      h('span', { className: 've-f__l' }, 'Posición y estilo del texto'),
      h(
        'div',
        { className: 've-seg', role: 'group', 'aria-label': 'Posición del texto' },
        TEXT_POSITIONS.map((opt) =>
          h(
            'button',
            {
              key: opt.id,
              type: 'button',
              disabled: !hasText,
              'aria-pressed': position === opt.id,
              onClick: () => setTextStyle({ position: opt.id })
            },
            opt.label
          )
        )
      ),
      h(
        'div',
        { className: 've-tex' },
        num('size', 'Tamaño', TEXT_SIZE, 'Tamaño del texto en puntos'),
        styleField(
          'color',
          'Color',
          h('input', {
            className: 've-tex__in',
            type: 'color',
            value: hexOr(item.color, TEXT_COLOR_DEFAULT),
            disabled: !hasText,
            'aria-label': 'Color del texto',
            onChange: (event) => setTextStyle({ color: hexOr(event.target.value, TEXT_COLOR_DEFAULT) }),
            onBlur: saveSoon
          })
        ),
        num('border', 'Borde', TEXT_BORDER, 'Grosor del borde del texto'),
        num('shadow', 'Sombra', TEXT_SHADOW, 'Grosor de la sombra del texto')
      ),
      h('div', { className: 've-f__row' }, anims('in', 'Entrada', 'Animación de entrada del texto'), anims('out', 'Salida', 'Animación de salida del texto')),
      h('span', { className: 've-f__h' }, hasText ? 'El texto aparece durante toda la escena.' : 'Escribe un texto para darle estilo.')
    )
  }

  const pInOut = () =>
    h(
      'div',
      { className: 've-f' },
      h('span', { className: 've-f__l' }, 'Recorte del clip'),
      h(
        'div',
        { className: 've-f__row' },
        h(
          'label',
          { className: 've-tex__f' },
          h('span', { className: 've-tex__k' }, 'Entrada'),
          h(
            'span',
            { className: 've-tcout' },
            h(NumField, {
              value: Number(sel.in),
              min: 0,
              max: Math.max(0, Number(sel.out) - MIN_SCENE),
              step: 0.1,
              ariaLabel: 'Entrada de la escena en segundos',
              onCommit: setIn,
              onBlur: saveSoon
            }),
            h('small', null, 's')
          )
        ),
        h(
          'label',
          { className: 've-tex__f' },
          h('span', { className: 've-tex__k' }, 'Salida'),
          h(
            'span',
            { className: 've-tcout' },
            h(NumField, {
              value: Number(sel.out),
              min: Number(sel.in) + MIN_SCENE,
              step: 0.1,
              ariaLabel: 'Salida de la escena en segundos',
              onCommit: setOut,
              onBlur: saveSoon
            }),
            h('small', null, 's')
          )
        )
      ),
      sceneDuration(sel) < MIN_SCENE
        ? h('span', { className: 've-f__err', role: 'alert' }, 'La salida debe ser al menos 0,3 s después de la entrada.')
        : h('span', { className: 've-f__h' }, `Dura ${fmtTime(sceneDuration(sel))}${sceneSpeed(sel) !== 1 ? ` · ${fmtTime(visibleDuration(sel))} en pantalla a ×${fmtNum(sceneSpeed(sel))}` : ''}. También puedes arrastrar los bordes del clip en la línea de tiempo.`)
    )

  const pMissing = () => (
              missing.length
      ? h(
          'div',
          { className: 've-f' },
          h(Badge, { tone: 'warn' }, `Falta ${missing.length} medio${missing.length > 1 ? 's' : ''}`),
          h(Btn, { variant: 'text', label: 'Volver a vincular', onClick: importFolder })
        )
      : null
  )

  const pActions = () =>
    h(
      'div',
      { className: 've-f ve-actions' },
      h(Btn, {
        variant: 'outline',
        size: 'sm',
        label: 'Reemplazar medio',
        title: 'Cambia el archivo de la escena sin tocar la entrada y la salida',
        onClick: () => {
          setDialog({ kind: 'picker' })
          openPicker('replace', sel.id)
        }
      }),
      h(Btn, { variant: 'outline', size: 'sm', label: 'Restablecer escena', title: 'Quita texto, transición y ajustes de audio de esta escena', onClick: () => resetScene(sel) }),
      h(Btn, {
        variant: 'outline',
        size: 'sm',
        icon: 'trash',
        label: 'Eliminar escena',
        title: 'Elimina la escena (Supr). Ctrl+Z la recupera',
        onClick: () => deleteScene(selIndex)
      })
    )

  // ---- «Efectos» y «Audio» -----------------------------------------------------
  const pVolume = () => (
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
    )
  )
  const pTransition = () => (
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
    )
  )
  const pFilters = () => (
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
                onBlur: saveSoon
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
    })()
  )
  const pMotion = () => (
              (() => {
      const motion = sel.kenBurns && typeof sel.kenBurns === 'object' ? sel.kenBurns : null
      const speed = sceneSpeed(sel)
      const visible = visibleDuration(sel)
      const zoom = motion && Number.isFinite(Number(motion.zoom)) ? Number(motion.zoom) : KEN_BURNS.zoom
      return h(
        'div',
        { className: 've-f' },
        h('span', { className: 've-f__l' }, 'Movimiento y velocidad'),
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
                    onBlur: saveSoon
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
              onBlur: saveSoon
            }),
            h('span', { className: 've-volval' }, `×${fmtNum(speed)}`)
          ),
          h('span', { className: 've-f__h' }, `Duración visible ${fmtTime(visible)} a esta velocidad.`)
        )
      )
    })()
  )
  const pOrientation = () => (
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
    )
  )
  const pProjectInfo = () =>
    h(
      'div',
      { className: 've-f' },
      h('span', { className: 've-f__l' }, 'Resumen del proyecto'),
      h(
        'dl',
        { className: 've-facts' },
        h('dt', null, 'Resolución'),
        h('dd', null, `${doc.width}×${doc.height} · ${docFps} fps`),
        h('dt', null, 'Escenas'),
        h('dd', null, String((doc.scenes || []).length)),
        h('dt', null, 'Suma de escenas'),
        h('dd', null, fmtTime(total)),
        h('dt', null, 'Vídeo final'),
        h('dd', null, `${fmtTime(finalDuration(doc))}${finalDuration(doc) !== total ? ' (las transiciones se solapan)' : ''}`)
      )
    )

  const sfxSection = () => (
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
    )
  )
  const musicSection = () => (
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
                      h(NumField, {
                        value: typeof music.fadeIn === 'number' ? music.fadeIn : 0,
                        min: 0,
                        max: 10,
                        step: 0.5,
                        format: fmtSec,
                        ariaLabel: 'Fundido de entrada de la música en segundos',
                        onCommit: (value) => setMusicFade('fadeIn', value),
                        onBlur: saveSoon
                      }),
                      h('small', null, 's')
                    ),
                    h(
                      'span',
                      { className: 've-tcout' },
                      h(NumField, {
                        value: typeof music.fadeOut === 'number' ? music.fadeOut : 0,
                        min: 0,
                        max: 10,
                        step: 0.5,
                        format: fmtSec,
                        ariaLabel: 'Fundido de salida de la música en segundos',
                        onCommit: (value) => setMusicFade('fadeOut', value),
                        onBlur: saveSoon
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
    )
  )
  const logoSection = () => (
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
                      onBlur: saveSoon
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
                      onBlur: saveSoon
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

  const rail = () => {
    if (!doc) return null
    const needScene = (children) =>
      sel
        ? children
        : h(EmptyState, {
            title: 'Elige una escena',
            body: 'Selecciona una escena de la lista o de la línea de tiempo para editarla.'
          })
    let body = null
    if (railTab === 'scene') body = needScene([pMissing && sel ? pMissing() : null, sel ? pName() : null, sel ? pCaption() : null, sel ? pTextStyle() : null, sel ? pInOut() : null, sel ? pActions() : null])
    else if (railTab === 'fx') body = needScene([sel ? pTransition() : null, sel ? pFilters() : null, sel ? pMotion() : null])
    else if (railTab === 'audio') body = [sel ? pVolume() : null, sfxSection(), musicSection()]
    else body = [pOrientation(), pProjectInfo(), logoSection()]
    const moveTab = (event, index) => {
      if (event.key !== 'ArrowRight' && event.key !== 'ArrowLeft') return
      event.preventDefault()
      const next = railTabs[(index + (event.key === 'ArrowRight' ? 1 : railTabs.length - 1)) % railTabs.length]
      setRailTab(next.id)
      const node = rootRef.current && rootRef.current.querySelector(`#ve-tab-${next.id}`)
      if (node) node.focus()
    }
    return h(
      'aside',
      { className: 've-rail', 'aria-label': 'Propiedades de la escena', style: compact && !railOpen ? { display: 'none' } : undefined },
      h(
        'div',
        { className: 've-rail__top' },
        h('span', { className: 've-rail__t' }, 'Propiedades'),
        sel ? h('span', { className: 've-rail__who' }, `· ${sel.name || `Escena ${selIndex + 1}`}`) : null,
        h('span', { className: 've-spacer' }),
        compact ? h(Btn, { icon: 'close', variant: 'ghost', ariaLabel: 'Cerrar propiedades', onClick: () => setRailOpen(false) }) : null
      ),
      h(
        'div',
        { className: 've-tabs', role: 'tablist', 'aria-label': 'Propiedades' },
        railTabs.map((tab, index) =>
          h(
            'button',
            {
              key: tab.id,
              id: `ve-tab-${tab.id}`,
              type: 'button',
              role: 'tab',
              'aria-selected': railTab === tab.id,
              'aria-controls': 've-tabpanel',
              tabIndex: railTab === tab.id ? 0 : -1,
              onClick: () => setRailTab(tab.id),
              onKeyDown: (event) => moveTab(event, index)
            },
            h(Icon, { name: tab.icon }),
            h('span', null, tab.label)
          )
        )
      ),
      h('div', { className: 've-rail__body', id: 've-tabpanel', role: 'tabpanel', 'aria-labelledby': `ve-tab-${railTab}` }, body)
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

  function queueLabel() {
    if (job && ['queued', 'running', 'probing', 'rendering', 'validating', 'promoting'].includes(job.state)) {
      return typeof job.progress === 'number' ? `Exportando ${Math.round(job.progress)} %` : 'Exportando…'
    }
    if (job && job.state === 'failed') return 'La exportación falló'
    if (!doc) return ''
    const count = (doc.scenes || []).length
    if (!count) return 'Sin escenas todavía'
    const finalLen = finalDuration(doc)
    return `${count} escena${count === 1 ? '' : 's'} · vídeo final ${fmtTime(finalLen)}`
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
          body: `Dura ${fmtTime(finalDuration(doc))}${finalDuration(doc) !== total ? ' (las transiciones solapan escenas)' : ''} · ${doc.width}×${doc.height} · ${docFps} fps · MP4 (H.264 + AAC)`,
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
            h('span', { className: 've-f__l' }, 'Formato de exportación'),
            h(
              'select',
              {
                className: 've-select',
                value: exportPreset,
                'aria-label': 'Formato de exportación',
                onChange: (event) => setExportPreset(event.target.value)
              },
              presetOptions.map((item) =>
                h('option', { key: item.id, value: item.id, disabled: !!item.disabled }, item.disabled ? `${item.label} · no disponible` : item.label)
              )
            ),
            presetPicked && presetPicked.disabled
              ? h('span', { className: 've-f__err', role: 'alert' }, 'Este formato no está disponible en tu servicio. Elige otro.')
              : h(
                  'span',
                  { className: 've-f__h' },
                  'El archivo se guarda en la carpeta del proyecto y podrás enviarlo al chat.'
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
      { className: 've-menu', style: { right: '12px', top: '52px' }, role: 'menu' },
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
      { className: 've-menu', style: { left: '56px', top: '52px' }, role: 'menu' },
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
      'data-layout': layout,
      'data-doc': doc ? '1' : '0',
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
      side(),
      h('div', { className: 've-main' }, stage(), transport(), timelineBlock()),
      (layout !== 'wide' && libOpen) || (compact && railOpen)
        ? h('div', { className: 've-ov', 'aria-hidden': 'true', onClick: () => { setLibOpen(false); setRailOpen(false) } })
        : null,
      rail()
    ),
    toasts(),
    menus(),
    dialogs(),
    cineOpen ? jsx(CinePanel, { ctx, onClose: () => setCineOpen(false) }) : null,
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
