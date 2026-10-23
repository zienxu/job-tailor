import { RefreshCw } from 'lucide-react'
import type { Critique } from '../api'

type Props = { critic: Critique | null; loading: boolean; disabled: boolean; onRerun: () => void }

export default function CriticPanel({ critic, loading, disabled, onRerun }: Props) {
  return (
    <section className="record" aria-labelledby="critic-title" aria-busy={loading}>
      <div className="flex items-center justify-between gap-2">
        <h2 id="critic-title" className="text-sm font-semibold text-muted">Critic</h2>
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
          {critic.items.length > 0 ? (
            <ol className="flex list-decimal flex-col gap-2 pl-5">
              {critic.items.map((it, i) => (
                <li key={i}>
                  <p className="font-serif">{it.bullet}</p>
                  <p><span className="font-medium">Problem:</span> <span className="text-muted">{it.problem}</span></p>
                  <p><span className="font-medium">Fix:</span> <span className="text-muted">{it.fix}</span></p>
                </li>
              ))}
            </ol>
          ) : <p className="text-muted">No objections.</p>}
        </div>
      )}
    </section>
  )
}
