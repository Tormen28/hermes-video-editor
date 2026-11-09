// Reexporta los hooks de React desde el UMD global, como hace la app.
const R = window.React

export const useState = R.useState
export const useEffect = R.useEffect
export const useLayoutEffect = R.useLayoutEffect
export const useRef = R.useRef
export const useMemo = R.useMemo
export const useCallback = R.useCallback
export const useReducer = R.useReducer
export const useContext = R.useContext
export const createContext = R.createContext
export const memo = R.memo
export const Fragment = R.Fragment
export const createElement = R.createElement

export default R
