import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'
import App from './App'
import './index.css'

// macOS browsers only bind Cmd+Z; also map Ctrl+Z / Ctrl+Shift+Z / Ctrl+Y onto the browser's own undo stack in text fields.
document.addEventListener('keydown', (e) => {
  const t = e.target as HTMLElement
  if (!e.ctrlKey || e.metaKey || e.altKey || !t.matches('textarea, input')) return
  const k = e.key.toLowerCase()
  const cmd = k === 'z' ? (e.shiftKey ? 'redo' : 'undo') : k === 'y' && !e.shiftKey ? 'redo' : null
  if (!cmd) return
  e.preventDefault() // stops Windows/Linux from also running its native undo (double step)
  document.execCommand(cmd)
})

createRoot(document.getElementById('root')!).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
