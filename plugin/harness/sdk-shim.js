// Shim de @hermes/plugin-sdk para el banco de pruebas (fuera de la app).
// Refleja el contrato real: host.state son atoms de nanostores, host.composer
// es la puerta de escritura al chat y las áreas son constantes de texto.

const params = new URLSearchParams(location.search)

const atom = (initial) => {
  let value = initial
  const subs = new Set()
  return {
    get: () => value,
    set: (next) => {
      value = next
      subs.forEach((fn) => fn(next))
    },
    subscribe: (fn) => {
      subs.add(fn)
      return () => subs.delete(fn)
    }
  }
}

export const chatAtom = atom(params.get('chat') || 'sess_harness_chat')
export const busyAtom = atom(params.get('busy') === '1')
export const cwdAtom = atom(params.get('cwd') || 'C:/proyectos/harness')

export const host = {
  navigate: (to) => {
    window.__VE_NAV__ = to
  },
  state: {
    focusedStoredSessionId: chatAtom,
    activeSessionId: chatAtom,
    cwd: cwdAtom,
    busy: busyAtom
  },
  composer: {
    insertText: async (sessionId, text, opts) => {
      window.__VE_CHAT__ = { sessionId, text, opts, at: Date.now() }
      return true
    },
    focus: (sessionId) => {
      window.__VE_CHAT_FOCUS__ = sessionId
    },
    getDraft: async () => '',
    setDraft: async () => true,
    submit: () => true
  }
}

if (params.get('nocomposer') === '1') {
  delete host.composer
}

// nanostores/react usa useSyncExternalStore por debajo.
export const useValue = (store) =>
  React.useSyncExternalStore(store.subscribe, store.get, store.get)

export const TITLEBAR_AREAS = { left: 'titlebar.left', right: 'titlebar.right' }
export const PALETTE_AREA = 'palette'
export const KEYBINDS_AREA = 'keybinds'
export const COMPOSER_AREAS = { before: 'composer.before', after: 'composer.after' }

export default { host, useValue, TITLEBAR_AREAS, PALETTE_AREA, KEYBINDS_AREA, COMPOSER_AREAS }
