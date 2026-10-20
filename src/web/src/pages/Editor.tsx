import { useEffect, useRef, useState } from 'react'
import { Download, Maximize2, Sparkles, TriangleAlert, Unlink, X } from 'lucide-react'
import * as api from '../api'
import CriticPanel from '../components/CriticPanel'
import ScorePanel from '../components/ScorePanel'

type Bullet = api.DraftBullet & { key: number; kept?: boolean }
let nextKey = 0
const PAGE_W = 816 // US Letter at 96dpi
const PAGE_H = 1056

// unsupported_fact = the text says something its cited source doesn't; everything else is a citation problem.
const kindOf = (flag: string) => (flag === 'unsupported_fact' ? 'contradicts' : 'missing')
const CHIPS = {
  missing: { label: 'Missing citation', Icon: Unlink, cls: 'border-warn/50 bg-warn/10 text-warn' },
  contradicts: { label: 'Contradicts source', Icon: TriangleAlert, cls: 'border-danger/50 bg-danger/10 text-danger' },
}

const lines = (s: string) => s.split('\n').map((l) => l.trim()).filter(Boolean)

function toResume(name: string, contacts: string, summary: string, roles: api.Role[], bullets: Bullet[]): api.Resume {
  return {
    name,
    contacts: lines(contacts),
    summary,
    experience: roles
      .map((r) => ({
        company: r.company,
        title: r.title,
        dates: [r.start_date, r.end_date].filter(Boolean).join(' - '),
        bullets: bullets.filter((b) => b.role_id === `role_${r.id}`).map((b) => b.text),
      }))
      .filter((x) => x.bullets.length > 0),
  }
}

export default function Editor() {
  const [roles, setRoles] = useState<api.Role[]>([])
  const [jobText, setJobText] = useState('')
  const [jobId, setJobId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [contacts, setContacts] = useState('')
  const [summary, setSummary] = useState('')
  const [bullets, setBullets] = useState<Bullet[]>([])
  const [ats, setAts] = useState<api.Ats | null>(null)
  const [critic, setCritic] = useState<api.Critique | null>(null)
  const [criticLoading, setCriticLoading] = useState(false)
  const [html, setHtml] = useState('')
  const [reviewed, setReviewed] = useState(false)
  const [busy, setBusy] = useState(false)
  // True from an edit until its fact check returns, so the gate never trusts flags from an older draft.
  const [checking, setChecking] = useState(false)
  const jobRef = useRef<number | null>(null)
  const previewRef = useRef<HTMLDivElement>(null)
  const [scale, setScale] = useState(0.55)
  const fullRef = useRef<HTMLDialogElement>(null)
  const [error, setError] = useState('')

  useEffect(() => {
    Promise.all([api.listRoles(), api.latestVersion()]).then(([rs, v]) => {
      setRoles(rs)
      if (v) {
        setName(v.content.name ?? '')
        setContacts((v.content.contacts ?? []).join('\n'))
      }
    }).catch((e) => setError(e.message))
  }, [])

  const resume = toResume(name, contacts, summary, roles, bullets)
  // Flags and "kept" are left out, so a re-check result doesn't trigger another re-check.
  const draftKey = JSON.stringify([resume, bullets.map((b) => [b.text, b.source_id])])

  useEffect(() => setReviewed(false), [draftKey])

  useEffect(() => {
    if (jobId === null) return
    let stale = false
    setChecking(true)
    const t = setTimeout(() => {
      const text = [resume.summary, ...resume.experience.flatMap((x) => [x.company, x.title, ...x.bullets])].join('\n')
      api.check(jobId, text, bullets).then((r) => {
        if (stale) return
        setAts(r.ats)
        setChecking(false)
        setBullets((bs) => bs.map((b, i) => ({ ...b, flags: r.flags[i] ?? b.flags })))
      }).catch((e) => !stale && setError(e.message))
      api.preview(resume).then((h) => !stale && setHtml(h)).catch((e) => !stale && setError(e.message))
    }, 400)
    return () => { stale = true; clearTimeout(t) }
    // draftKey covers resume and bullet text; listing those objects would re-run on every render.
  }, [jobId, draftKey])

  // Scale the page to fill whatever width the preview card has.
  const hasPreview = html !== ''
  useEffect(() => {
    const el = previewRef.current
    if (!el || typeof ResizeObserver === 'undefined') return
    const ro = new ResizeObserver(([e]) => setScale(e.contentRect.width / PAGE_W))
    ro.observe(el)
    return () => ro.disconnect()
  }, [hasPreview])

  async function runCritic(id: number, bs: api.DraftBullet[]) {
    setCriticLoading(true)
    try {
      const c = await api.critique(id, bs)
      if (jobRef.current === id) setCritic(c) // a newer tailor run owns the panel now
    } catch (e) {
      setError((e as Error).message)
    }
    if (jobRef.current === id) setCriticLoading(false)
  }

  async function runTailor() {
    if (!jobText.trim()) return setError('Paste the job text first')
    setBusy(true)
    setError('')
    try {
      const job = await api.createJob(jobText)
      const out = await api.tailor(job.id)
      const bs = out.bullets.map((b) => ({ ...b, key: nextKey++ }))
      jobRef.current = job.id
      setJobId(job.id)
      setBullets(bs)
      setCritic(null)
      runCritic(job.id, bs)
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(false)
  }

  async function download() {
    if (jobId === null) return
    setBusy(true)
    setError('')
    try {
      await api.saveVersion(jobId, { name, contacts: lines(contacts), summary, bullets: bullets.map(({ key, kept, ...b }) => b) })
      const url = URL.createObjectURL(await api.pdf(resume))
      const a = document.createElement('a')
      a.href = url
      a.download = 'resume.pdf'
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 0) // revoking during click() can cancel the download
    } catch (e) {
      setError((e as Error).message)
    }
    setBusy(false)
  }

  const editBullet = (key: number, patch: Partial<Bullet>) =>
    setBullets((bs) => bs.map((b) => (b.key === key ? { ...b, ...patch } : b)))
  const removeBullet = (key: number) => setBullets((bs) => bs.filter((b) => b.key !== key))

  const unresolved = bullets.filter((b) => b.flags.length > 0 && !b.kept).length
  const canDownload = jobId !== null && unresolved === 0 && reviewed && !checking && !busy

  const groups = [
    ...roles.map((r) => ({ id: `role_${r.id}`, title: `${r.company} - ${r.title}`, cited: true })),
    { id: null, title: 'Uncited (left out of the PDF)', cited: false },
  ].map((g) => ({ ...g, items: bullets.filter((b) => b.role_id === g.id) })).filter((g) => g.items.length > 0)

  function renderBullet(b: Bullet, cited: boolean) {
    const n = bullets.indexOf(b) + 1
    const kinds = [...new Set(b.flags.map(kindOf))]
    return (
      <li key={b.key} className="flex flex-col gap-2">
        <div className="flex items-start gap-2">
          <textarea
            aria-label={`Bullet ${n}`}
            className="field font-serif leading-relaxed"
            rows={2}
            value={b.text}
            onChange={(e) => editBullet(b.key, { text: e.target.value, kept: false })}
          />
          <button type="button" className="btn btn-quiet px-2" title="Remove bullet" aria-label={`Remove bullet ${n}`} onClick={() => removeBullet(b.key)}>
            <X aria-hidden size={16} />
          </button>
        </div>
        {kinds.length > 0 && (
          <div className="flex flex-wrap items-center gap-2">
            {kinds.map((k) => {
              const { label, Icon, cls } = CHIPS[k]
              return (
                <span key={k} data-flag={k} className={`inline-flex items-center gap-1 rounded-full border px-2 py-0.5 text-xs font-semibold ${cls}`}>
                  <Icon aria-hidden size={12} />{label}
                </span>
              )
            })}
            {cited && (
              <label className="inline-flex items-center gap-1.5 text-xs text-muted">
                <input type="checkbox" checked={!!b.kept} onChange={(e) => editBullet(b.key, { kept: e.target.checked })} />
                Keep anyway
              </label>
            )}
          </div>
        )}
      </li>
    )
  }

  const page = (title: string, style?: React.CSSProperties) => (
    // No allow-scripts: preview markup can never run code. Same-origin only so the fonts load.
    <iframe title={title} sandbox="allow-same-origin" srcDoc={html} className="block max-w-none bg-white" width={PAGE_W} height={PAGE_H} style={style} />
  )

  return (
    <section>
      <header className="mb-8">
        <h1 className="page-title">Editor</h1>
        <p className="page-lede">Paste a job, tailor your bullets to it, then check every flag before downloading the PDF.</p>
      </header>
      {error && <p role="alert" className="alert">{error}</p>}
      <div className="grid gap-6 xl:grid-cols-[minmax(0,1fr)_28rem]">
        <div className="flex min-w-0 flex-col gap-5">
          <div className="record">
            <label className="label">Job text<textarea className="field" rows={6} value={jobText} onChange={(e) => setJobText(e.target.value)} /></label>
            <button type="button" className="btn btn-primary mt-4" disabled={busy} onClick={runTailor}>
              <Sparkles aria-hidden size={16} />{busy && jobId === null ? 'Tailoring...' : 'Tailor'}
            </button>
          </div>
          <div className="record flex flex-col gap-4">
            <label className="label">Name<input className="field" value={name} onChange={(e) => setName(e.target.value)} /></label>
            <label className="label">Contacts (one per line)<textarea className="field" rows={3} value={contacts} onChange={(e) => setContacts(e.target.value)} /></label>
            <label className="label">Summary<textarea className="field font-serif leading-relaxed" rows={3} value={summary} onChange={(e) => setSummary(e.target.value)} /></label>
          </div>
          {groups.map((g) => (
            <div key={g.id ?? 'uncited'} className="record">
              <h2 className="font-serif text-lg font-semibold">{g.title}</h2>
              <ul className="mt-3 flex flex-col gap-4">{g.items.map((b) => renderBullet(b, g.cited))}</ul>
            </div>
          ))}
          {jobId !== null && (
            <div className="record flex flex-col gap-3">
              <p className="text-sm text-muted" aria-live="polite">
                {unresolved > 0 ? `${unresolved} flagged bullet${unresolved > 1 ? 's' : ''} to fix, keep or remove.` : 'No unresolved flags.'}
              </p>
              <label className="inline-flex items-center gap-2 text-sm font-medium">
                <input type="checkbox" checked={reviewed} onChange={(e) => setReviewed(e.target.checked)} />
                I've reviewed this draft
              </label>
              <button type="button" className="btn btn-primary self-start" disabled={!canDownload} onClick={download}>
                <Download aria-hidden size={16} />Download PDF
              </button>
            </div>
          )}
        </div>
        <aside className="flex min-w-0 flex-col gap-5">
          <ScorePanel ats={ats} />
          <CriticPanel critic={critic} loading={criticLoading} disabled={jobId === null} onRerun={() => jobId !== null && runCritic(jobId, bullets)} />
          {html && (
            <div className="flex flex-col gap-2">
              <button type="button" className="btn btn-secondary self-end" onClick={() => fullRef.current?.showModal()}>
                <Maximize2 aria-hidden size={16} />Open full size
              </button>
              {/* transform, not CSS zoom: Chrome passes zoom into the frame's page too, shrinking it twice. */}
              <div ref={previewRef} className="record overflow-hidden p-0 sm:p-0" style={{ height: PAGE_H * scale }}>
                {page('Resume preview', { transform: `scale(${scale})`, transformOrigin: 'top left' })}
              </div>
              <dialog ref={fullRef} aria-label="Full size preview" className="m-auto max-h-[95vh] max-w-[95vw] rounded-xl border border-line bg-surface p-0 text-ink backdrop:bg-black/60">
                <form method="dialog" className="sticky top-0 z-10 flex justify-end border-b border-line bg-surface p-2">
                  <button className="btn btn-secondary"><X aria-hidden size={16} />Close</button>
                </form>
                {page('Resume preview, full size')}
              </dialog>
            </div>
          )}
        </aside>
      </div>
    </section>
  )
}
