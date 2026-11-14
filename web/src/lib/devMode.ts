import { useCallback, useEffect, useState } from 'react'

const STORAGE_KEY = 'dev_mode'
const EVENT_NAME = 'dev-mode-change'

function readDevMode(): boolean {
  try {
    const q = new URLSearchParams(window.location.search).get('dev')
    if (q === '1' || q === 'true') {
      localStorage.setItem(STORAGE_KEY, '1')
      return true
    }
    if (q === '0' || q === 'false') {
      localStorage.setItem(STORAGE_KEY, '0')
      return false
    }
    return localStorage.getItem(STORAGE_KEY) === '1'
  } catch {
    return false
  }
}

export function setDevModeGlobal(enabled: boolean): void {
  try {
    localStorage.setItem(STORAGE_KEY, enabled ? '1' : '0')
  } catch {
    /* ignore storage errors */
  }
  window.dispatchEvent(new CustomEvent<boolean>(EVENT_NAME, { detail: enabled }))
}

export function useDevMode(): [boolean, (enabled: boolean) => void] {
  const [devMode, setDevModeState] = useState<boolean>(readDevMode)

  useEffect(() => {
    const onUpdate = (e: Event) => {
      const detail = (e as CustomEvent<boolean>).detail
      setDevModeState(typeof detail === 'boolean' ? detail : readDevMode())
    }
    const onStorage = (e: StorageEvent) => {
      if (e.key === STORAGE_KEY) {
        setDevModeState(e.newValue === '1')
      }
    }
    window.addEventListener(EVENT_NAME, onUpdate)
    window.addEventListener('storage', onStorage)
    return () => {
      window.removeEventListener(EVENT_NAME, onUpdate)
      window.removeEventListener('storage', onStorage)
    }
  }, [])

  const update = useCallback((enabled: boolean) => {
    setDevModeState(enabled)
    setDevModeGlobal(enabled)
  }, [])

  return [devMode, update]
}
