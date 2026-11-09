// Emula react/jsx-runtime sobre createElement (misma semántica de children).
const R = window.React

const make = (type, props, key) => {
  const source = props || {}
  const { children, ...rest } = source
  if (key !== undefined) rest.key = key
  if (children === undefined) return R.createElement(type, rest)
  if (Array.isArray(children)) return R.createElement(type, rest, ...children)
  return R.createElement(type, rest, children)
}

export const jsx = make
export const jsxs = make
export const jsxDEV = make
export const Fragment = R.Fragment

export default { jsx, jsxs, Fragment }
