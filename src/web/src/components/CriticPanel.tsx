import { RefreshCw } from 'lucide-react'
import type { Critique } from '../api'

const LISTS = [['unmet_must_haves', 'Unmet must-haves'], ['missing_keywords', 'Missing keywords']] as const
const NOTES = [['weak_bullets', 'Weak bullets'], ['overstated_claims', 'Overstated claims']] as const

type Props = { critic: Critique | null; loading: boolean; disabled: boolean; onRerun: () => void }

export default function CriticPanel({ critic, loading, disabled, onRerun }: Props) {
  return (
    <section className="record" aria-labelledby="critic-title" aria-busy={loading}>
      <div className="flex items-center justify-between gap-2">
        <h2 id="critic-title" className="text-sm font-semibold text-muted">Devil's advocate</h2>
        <button type="button" className="btn btn-secondary" disabled={disabled || loading} onClick={onRerun}>
          <RefreshCw aria-hidden size={16} />Re-run critic
        </button>
      </div>
      {loading && <p className="mt-3 text-sm text-muted">Thinking...</p>}
      {!loading && critic?.error && <p role="alert" className="alert mt-3">Critic failed ({critic.error}). Try re-running it.</p>}
      {!loading && critic && !critic.error && (
        <div className="mt-3 flex flex-col gap-3 text-sm">
          {critic.readiness && (
            <div data-testid="readiness">
              <h3 className="font-medium">
                {critic.readiness.verdict === 'ready' ? 'Ready to send' : 'Needs work'} <span className="font-normal text-muted">(advice only)</span>
              </h3>
              <p className="text-muted">{critic.readiness.reason}</p>
            </div>
          )}
          {LISTS.map(([k, title]) => critic[k].length > 0 && (
            <div key={k}><h3 className="font-medium">{title}</h3><p className="text-muted">{critic[k].join(', ')}</p></div>
          ))}
          {NOTES.map(([k, title]) => critic[k].length > 0 && (
            <div key={k}>
              <h3 className="font-medium">{title}</h3>
              <ul className="mt-1 flex flex-col gap-1">
                {critic[k].map((n, i) => <li key={i}><span className="font-serif">{n.text}</span> <span className="text-muted">- {n.reason}</span></li>)}
              </ul>
            </div>
          ))}
          {[...LISTS, ...NOTES].every(([k]) => critic[k].length === 0) && <p className="text-muted">No objections.</p>}
        </div>
      )}
    </section>
  )
}
