import { useEffect, useState } from 'react'
import { Button } from '@/design/primitives'

type Theme = 'system' | 'dark' | 'light'

function apply(t: Theme) {
  if (t === 'system') document.documentElement.removeAttribute('data-theme')
  else document.documentElement.setAttribute('data-theme', t)
}

function load(): Theme {
  try {
    return (localStorage.getItem('theme') as Theme) || 'system'
  } catch {
    return 'system'
  }
}

export function ThemeToggle() {
  const [theme, setTheme] = useState<Theme>(load)
  useEffect(() => {
    apply(theme)
    try {
      localStorage.setItem('theme', theme)
    } catch {
      /* ignore */
    }
  }, [theme])
  const next: Theme = theme === 'system' ? 'dark' : theme === 'dark' ? 'light' : 'system'
  return (
    <Button variant="ghost" mono onClick={() => setTheme(next)} title="Toggle theme">
      theme: {theme}
    </Button>
  )
}
