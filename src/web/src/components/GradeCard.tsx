import { useId } from 'react'
import { RefreshCw } from 'lucide-react'
import type { Grade, Requirement } from '../api'

const BAND_CLS = { Apply: 'border-accent/50 bg-accent/10 text-accent', Stretch: 'border-warn/50 bg-warn/10 text-warn', Skip: 'border-danger/50 bg-danger/10 text-danger' }
const STATUS_CLS = { met: 'text-accent', partial: 'text-warn', missing: 'text-danger' }

const SENIORITY = { under: 'Role is more senior than your experience', match: 'Seniority matches', over: 'You are more senior than the role' }

type Props = { grade: Grade | null | undefined; loading?: boolean; error?: string; onRegrade?: () => void }

export default function GradeCard({ grade, loading, error, onRegrade }: Props) {
  const titleId = useId() // the Tracker can show several cards at once
  const musts = grade?.requirements.filter((r) => r.kind === 'must') ?? []
  // The band only differs from the score when a missing must-have held an Apply score at Stretch.
  const gates = grade && grade.band === 'Stretch' && grade.score >= 3.8 ? musts.filter((r) => r.status === 'missing') : []
  return (
    <section className="record" aria-labelledby={titleId} aria-busy={loading}>
      <div className="flex items-center justify-between gap-2">
        <h2 id={titleId} className="text-sm font-semibold text-muted">Fit grade <span className="font-normal">(advice only)</span></h2>
        {onRegrade && (
          <button type="button" className="btn btn-secondary" disabled={loading} onClick={onRegrade}>
            <RefreshCw aria-hidden size={16} />Re-grade
          </button>
        )}
      </div>
      {loading && <p className="mt-3 text-sm text-muted">Grading...</p>}
      {!loading && error && <p role="alert" className="alert mt-3">Grade failed ({error}). You can still tailor.</p>}
      {!loading && !error && grade && (
        <>
          <p className="mt-1 flex items-center gap-3">
            <span className="font-serif text-4xl font-semibold" data-testid="grade-score">{grade.score.toFixed(1)} / 5</span>
            <span data-testid="grade-band" className={`rounded-full border px-2 py-0.5 text-xs font-semibold ${BAND_CLS[grade.band]}`}>{grade.band}</span>
          </p>
          {/* Mirrors fit.band in src/api/fit.py. */}
          <p className="mt-1 text-xs text-muted">Apply ≥ 3.8 · Stretch 3.0–3.7 · Skip below 3.0</p>
          {gates.length > 0 && (
            <p className="mt-1 text-xs text-warn" data-testid="grade-gated">
              Held at Stretch: a must-have is missing ({gates.map((r) => r.text).join('; ')})
            </p>
          )}
          {grade.summary && <p className="mt-2 text-sm" data-testid="grade-summary">{grade.summary}</p>}
          {grade.seniority_fit && <p className="mt-1 text-xs text-muted" data-testid="grade-seniority">{SENIORITY[grade.seniority_fit]}</p>}
          <Requirements title="Must-haves" reqs={musts} />
          <Requirements title="Nice-to-haves" reqs={grade.requirements.filter((r) => r.kind === 'nice')} />
        </>
      )}
    </section>
  )
}

function Requirements({ title, reqs }: { title: string; reqs: Requirement[] }) {
  if (!reqs.length) return null
  return (
    <>
      <h3 className="mt-3 text-sm font-medium text-muted">{title}</h3>
      <ul className="mt-1 flex flex-col gap-2 text-sm">
        {reqs.map((r, i) => (
          <li key={i} data-status={r.status}>
            <span className={`font-semibold ${STATUS_CLS[r.status]}`}>{r.status}</span> {r.text}
            {r.hard_gate && <span className="ml-1.5 rounded border border-line px-1 text-xs text-muted">hard requirement</span>}
            {r.status !== 'missing' && Array.isArray(r.evidence) && r.evidence.length > 0 && (
              <ul className="ml-4 list-disc text-muted">{r.evidence.map((t, j) => <li key={j}>{t}</li>)}</ul>
            )}
          </li>
        ))}
      </ul>
    </>
  )
}
