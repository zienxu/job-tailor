import { useRef, type TextareaHTMLAttributes } from 'react'
import { Bold } from 'lucide-react'

// Wraps the selection in **. The button has no text (only an aria-label) so it doesn't change the text of an enclosing <label>.
export default function BoldTextarea(props: TextareaHTMLAttributes<HTMLTextAreaElement>) {
  const ref = useRef<HTMLTextAreaElement>(null)
  const locked = props.readOnly || props.disabled
  const name = props['aria-label']

  const bold = () => {
    const ta = ref.current
    if (!ta || locked || ta.selectionStart === ta.selectionEnd) return // empty selection would print a literal ****
    const wrapped = `**${ta.value.slice(ta.selectionStart, ta.selectionEnd)}**`
    ta.focus()
    // execCommand keeps the edit on the browser's undo stack; where it's missing (jsdom), fall back to
    // setRangeText plus a real input event, which React's onChange still picks up.
    let done = false
    try { done = document.execCommand('insertText', false, wrapped) } catch { /* not supported */ }
    if (!done) {
      ta.setRangeText(wrapped, ta.selectionStart, ta.selectionEnd, 'end')
      ta.dispatchEvent(new Event('input', { bubbles: true }))
    }
  }

  return (
    <span className="relative block w-full min-w-0 flex-1">{/* flex-1: fills the row when placed in a flex container */}
      <textarea
        {...props}
        className={`${props.className ?? ''} pr-8`}
        ref={ref}
        onKeyDown={(e) => {
          props.onKeyDown?.(e)
          if ((e.ctrlKey || e.metaKey) && e.key.toLowerCase() === 'b') { e.preventDefault(); bold() }
        }}
      />
      <button type="button" className="btn btn-quiet absolute right-1 top-1 !p-1" aria-label={name ? `Bold ${name}` : 'Bold'} title="Bold (Ctrl/Cmd+B)" disabled={locked} onMouseDown={(e) => e.preventDefault()} onClick={bold}>
        <Bold aria-hidden size={14} />
      </button>
    </span>
  )
}
