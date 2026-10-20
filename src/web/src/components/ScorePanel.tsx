import type { Ats } from '../api'

export default function ScorePanel({ ats }: { ats: Ats | null }) {
  return (
    <section className="record" aria-labelledby="ats-title">
      <h2 id="ats-title" className="text-sm font-semibold text-muted">
        ATS keyword match <span className="font-normal">({ats?.label ?? 'local estimate'})</span>
      </h2>
      <p className="mt-1 font-serif text-4xl font-semibold" aria-live="polite" data-testid="ats-score">
        {ats ? `${ats.score}%` : '-'}
      </p>
      {ats && ats.missing.length > 0 && (
        <>
          <h3 className="mt-3 text-sm font-medium text-muted">Missing keywords</h3>
          <ul className="mt-1 flex flex-wrap gap-1.5">
            {ats.missing.map((k) => <li key={k} className="rounded border border-line px-1.5 py-0.5 text-xs">{k}</li>)}
          </ul>
        </>
      )}
    </section>
  )
}
