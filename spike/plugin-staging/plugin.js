// editor-video-spike — pane de prueba para el spike F1 del editor de vídeo.
// Carga sin compilar: solo jsx()/jsxs(), imports permitidos (@hermes/plugin-sdk, react, react/jsx-runtime).
// Demuestra: (1) un pane NUEVO dentro de la app, (2) fetch directo a un servicio local
// http://127.0.0.1:8765 (incógnita CSP/CORS), (3) render FFmpeg real con progreso y cancelación,
// (4) preview <video> servido con Range por el backend local.
import { host } from '@hermes/plugin-sdk'
import { useEffect, useRef, useState } from 'react'
import { jsx, jsxs } from 'react/jsx-runtime'

const BASE = 'http://127.0.0.1:8765'

async function postProbe(stage, detail) {
  try {
    await fetch(`${BASE}/probe`, {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ stage, detail, at: new Date().toISOString() })
    })
  } catch (err) {
    // Si el fetch está bloqueado por CSP esto también falla: es esperado y queda en la UI.
    console.warn('[editor-video-spike] probe no enviado', stage, err && err.message)
  }
}

const box = 'rounded-md border border-(--ui-border) p-2'
const btn = 'rounded-md border border-(--ui-border) px-2 py-1 text-xs hover:bg-(--ui-surface-2) disabled:opacity-40'
const mono = 'font-mono text-[0.6875rem] break-all whitespace-pre-wrap'

function Metric({ label, value }) {
  return jsxs('div', {
    className: 'flex items-baseline justify-between gap-2',
    children: [
      jsx('span', { className: 'text-(--ui-text-tertiary)', children: label }),
      jsx('span', { className: mono, children: value == null ? '—' : String(value) })
    ]
  })
}

function VideoPane() {
  const [health, setHealth] = useState({ state: 'idle' })
  const [job, setJob] = useState(null)
  const [error, setError] = useState(null)
  const [busy, setBusy] = useState(false)
  const timer = useRef(null)

  const testHealth = async () => {
    const t0 = performance.now()
    try {
      const res = await fetch(`${BASE}/health`, { cache: 'no-store' })
      const body = await res.text()
      const ms = Math.round(performance.now() - t0)
      setHealth({ state: 'ok', status: res.status, ms, body: body.slice(0, 400) })
      postProbe('health_ok', { status: res.status, ms, body: body.slice(0, 300) })
    } catch (err) {
      const ms = Math.round(performance.now() - t0)
      const text = `${err && err.name ? err.name : 'Error'}: ${err && err.message ? err.message : String(err)}`
      setHealth({ state: 'fail', ms, error: text })
      postProbe('health_failed', { error: text, ms })
    }
  }

  const poll = async (id) => {
    try {
      const res = await fetch(`${BASE}/jobs/${id}`, { cache: 'no-store' })
      const data = await res.json()
      setJob(data)
      if (['succeeded', 'failed', 'cancelled', 'interrupted'].includes(data.state)) {
        if (timer.current) {
          clearInterval(timer.current)
          timer.current = null
        }
        setBusy(false)
        if (data.state === 'succeeded') postProbe('render_succeeded', { id, wall_s: data.wall_s, cpu_s: data.cpu_s })
        if (data.state !== 'succeeded') postProbe('render_ended', { id, state: data.state, error: data.error })
      }
    } catch (err) {
      setError(`poll falló: ${err && err.message}`)
    }
  }

  const startRender = async () => {
    setError(null)
    setBusy(true)
    try {
      const res = await fetch(`${BASE}/jobs`, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({ kind: 'demo', preset: 'veryfast', crf: 23, label: 'desde el pane' })
      })
      if (!res.ok) throw new Error(`HTTP ${res.status}`)
      const data = await res.json()
      setJob({ id: data.id, state: data.state, progress: 0 })
      postProbe('render_submitted', { id: data.id, state: data.state })
      if (timer.current) clearInterval(timer.current)
      timer.current = setInterval(() => poll(data.id), 700)
    } catch (err) {
      setBusy(false)
      setError(`POST /jobs falló: ${err && err.message}`)
      postProbe('render_submit_failed', { error: String(err && err.message) })
    }
  }

  const cancelRender = async () => {
    if (!job || !job.id) return
    try {
      const res = await fetch(`${BASE}/jobs/${job.id}/cancel`, { method: 'POST' })
      const data = await res.json()
      postProbe('cancel_clicked', { id: job.id, taskkill: data.taskkill, status: res.status })
      poll(job.id)
    } catch (err) {
      setError(`cancel falló: ${err && err.message}`)
    }
  }

  useEffect(() => {
    postProbe('pane_mounted', {
      href: location.href,
      origin: location.origin,
      protocol: location.protocol,
      ua: navigator.userAgent.slice(0, 160)
    })
    testHealth()
    return () => {
      if (timer.current) clearInterval(timer.current)
    }
  }, [])

  const pct = job && job.progress != null ? Math.round(job.progress) : 0
  const running = job && ['queued', 'running'].includes(job.state)

  return jsxs('div', {
    className: 'flex h-full flex-col gap-2 overflow-auto p-3 text-sm',
    children: [
      jsxs('div', {
        className: 'flex items-center justify-between gap-2',
        children: [
          jsx('div', { className: 'font-medium', children: 'Editor de vídeo · spike F1' }),
          jsx('span', { className: 'text-(--ui-text-tertiary) text-[0.6875rem]', children: 'FFmpeg local' })
        ]
      }),

      // 1) prueba de red del renderer (CSP/CORS)
      jsxs('div', {
        className: box,
        children: [
          jsxs('div', {
            className: 'mb-1 flex items-center justify-between',
            children: [
              jsx('div', { className: 'font-medium text-xs', children: '1 · Conexión al servicio' }),
              jsx('button', { type: 'button', className: btn, onClick: testHealth, children: 'Probar /health' })
            ]
          }),
          health.state === 'idle'
            ? jsx('div', { className: 'text-(--ui-text-tertiary) text-xs', children: 'probando…' })
            : health.state === 'ok'
              ? jsxs('div', {
                  className: 'flex flex-col gap-1',
                  children: [
                    jsx('div', {
                      className: 'text-xs',
                      children: `OK · HTTP ${health.status} · ${health.ms} ms`
                    }),
                    jsx('div', { className: `${mono} text-(--ui-text-tertiary)`, children: health.body })
                  ]
                })
              : jsxs('div', {
                  className: 'flex flex-col gap-1',
                  children: [
                    jsx('div', { className: 'text-xs text-(--ui-danger,#e5484d)', children: `FALLÓ tras ${health.ms} ms` }),
                    jsx('div', { className: `${mono} text-(--ui-text-tertiary)`, children: health.error })
                  ]
                })
        ]
      }),

      // 2) render
      jsxs('div', {
        className: box,
        children: [
          jsxs('div', {
            className: 'mb-1 flex items-center justify-between gap-2',
            children: [
              jsx('div', { className: 'font-medium text-xs', children: '2 · Render de prueba' }),
              jsxs('div', {
                className: 'flex gap-1',
                children: [
                  jsx('button', {
                    type: 'button',
                    className: btn,
                    disabled: busy || running,
                    onClick: startRender,
                    children: 'Render demo'
                  }),
                  jsx('button', {
                    type: 'button',
                    className: btn,
                    disabled: !running,
                    onClick: cancelRender,
                    children: 'Cancelar'
                  })
                ]
              })
            ]
          }),
          jsxs('div', {
            className: 'flex flex-col gap-1',
            children: [
              jsx('div', {
                className: 'h-2 w-full overflow-hidden rounded bg-(--ui-surface-2)',
                children: jsx('div', {
                  style: { width: `${pct}%`, height: '100%', background: 'var(--ui-accent, #6e56cf)', transition: 'width .3s' }
                })
              }),
              jsxs('div', {
                className: 'flex justify-between text-[0.6875rem] text-(--ui-text-tertiary)',
                children: [
                  jsx('span', { children: job ? `${job.state} · ${pct}%` : 'sin job' }),
                  jsx('span', { children: job && job.speed ? `${job.fps || '—'} fps · ${job.speed}x` : '' })
                ]
              }),
              job
                ? jsxs('div', {
                    className: 'flex flex-col gap-0.5 pt-1',
                    children: [
                      jsx(Metric, { label: 'job', value: job.id }),
                      jsx(Metric, { label: 'stage', value: job.stage }),
                      jsx(Metric, { label: 'pid', value: job.pid }),
                      jsx(Metric, { label: 'pared', value: job.wall_s ? `${job.wall_s.toFixed(2)} s` : '—' }),
                      jsx(Metric, { label: 'CPU ffmpeg', value: job.cpu_s ? `${job.cpu_s.toFixed(2)} s` : '—' }),
                      jsx(Metric, { label: 'RSS pico', value: job.rss_peak_kb ? `${Math.round(job.rss_peak_kb / 1024)} MB` : '—' })
                    ]
                  })
                : null
            ]
          }),
          error ? jsx('div', { className: `${mono} pt-1 text-(--ui-danger,#e5484d)`, children: error }) : null
        ]
      }),

      // 3) preview del MP4 servido con Range
      job && job.state === 'succeeded' && job.out_path
        ? jsxs('div', {
            className: box,
            children: [
              jsx('div', { className: 'mb-1 font-medium text-xs', children: '3 · Resultado' }),
              jsx('video', {
                controls: true,
                playsInline: true,
                style: { width: '100%', borderRadius: '6px', background: '#000' },
                src: `${BASE}/out/${job.id}.mp4`
              }),
              jsxs('div', {
                className: 'pt-1 flex items-center justify-between text-[0.6875rem] text-(--ui-text-tertiary)',
                children: [
                  jsx('span', { children: `${Math.round((job.out_bytes || 0) / 1024)} KB` }),
                  jsx('button', {
                    type: 'button',
                    className: btn,
                    onClick: () => host.notify({ kind: 'info', message: `Render listo: ${job.id}.mp4` }),
                    children: 'Notificar'
                  })
                ]
              })
            ]
          })
        : null,

      jsx('div', {
        className: 'mt-auto text-[0.6875rem] text-(--ui-text-tertiary)',
        children: 'spike · servicio local 127.0.0.1:8765 · 1 job a la vez'
      })
    ]
  })
}

export default {
  id: 'editor-video-spike',
  name: 'Editor de vídeo (spike)',
  defaultEnabled: true,
  register(ctx) {
    ctx.register({
      id: 'pane',
      area: 'panes',
      title: 'Editor vídeo',
      data: { placement: 'right', width: '380px' },
      render: () => jsx(VideoPane, {})
    })
  }
}
