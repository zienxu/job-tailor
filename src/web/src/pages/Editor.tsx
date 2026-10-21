import { useEffect, useRef, useState } from 'react'
import { ArrowDown, ArrowUp, Download, Maximize2, Sparkles, TriangleAlert, Unlink, X } from 'lucide-react'
import * as api from '../api'
import CriticPanel from '../components/CriticPanel'
import ScorePanel from '../components/ScorePanel'

type Bullet = api.DraftBullet & { key: number; kept?: boolean; included: boolean }
// Education and skills are copied as saved, never sent to the LLM; edits here stay in this draft.
type Extra = { key: string; section: 'education' | 'skills'; label: string; sub: string; date: string; text: string; on: boolean }
const DEFAULT_ORDER: api.SectionKey[] = ['summary', 'education', 'experience', 'leadership', 'projects', 'skills']
const SECTION_NAMES: Record<api.SectionKey, string> = {
  summary: 'Summary', education: 'Education', experience: 'Experience', leadership: 'Leadership', projects: 'Projects', skills: 'Skills',
}
let nextKey = 0
const PAGE_W = 816 // US Letter at 96dpi
const PAGE_H = 1056

// unsupported_fact = the text says something its cited source doesn't; everything else is a citation problem.
const kindOf = (flag: string) => (flag === 'unsupported_fact' ? 'contradicts' : 'missing')
const CHIPS = {
  missing: { label: 'Missing citation', Icon: Unlink, cls: 'border-warn/50 bg-warn/10 text-warn' },
  contradicts: { label: 'Not in your saved text', Icon: TriangleAlert, cls: 'border-danger/50 bg-danger/10 text-danger' },
}

const lines = (s: string) => s.split('\n').map((l) => l.trim()).filter(Boolean)

const dates = (r: api.Role) => [r.start_date, r.end_date].filter(Boolean).join(' - ')

function toResume(name: string, contacts: string, summary: string, roles: api.Role[], bullets: Bullet[],
  extras: Extra[], order: api.SectionKey[]): api.Resume {
  const cited = (kind: api.RoleKind) => roles
    .filter((r) => r.kind === kind)
    .map((r) => ({ r, bullets: bullets.filter((b) => b.included && b.role_id === `role_${r.id}`).map((b) => b.text) }))
  const on = (section: Extra['section']) => extras.filter((e) => e.on && e.section === section)
  const rows = (kind: api.RoleKind) => cited(kind).map(({ r, bullets }) => ({ name: r.company, role: r.title, dates: dates(r), bullets }))
  return {
    name,
    contacts: lines(contacts),
    summary,
    education: on('education').map((e) => ({ school: e.label, degree: e.sub, date: e.date, details: lines(e.text) })),
    experience: cited('experience').map(({ r, bullets }) => ({ company: r.company, title: r.title, dates: dates(r), bullets })),
    leadership: rows('leadership'),
    projects: rows('project'),
    skills: on('skills').map((e) => ({ label: e.label, text: e.text })),
    order,
  }
}

// Everything that reaches the page counts for the ATS estimate.
const atsText = (r: api.Resume) => [
  r.summary,
  ...r.education.flatMap((e) => [e.school, e.degree, ...e.details]),
  ...r.experience.flatMap((x) => [x.company, x.title, ...x.bullets]),
  ...[...r.projects, ...r.leadership].flatMap((p) => [p.name, p.role, ...p.bullets]),
  ...r.skills.flatMap((l) => [l.label, l.text]),
].join('\n')

export default function Editor() {
  const [roles, setRoles] = useState<api.Role[]>([])
  const [jobText, setJobText] = useState('')
  const [jobId, setJobId] = useState<number | null>(null)
  const [name, setName] = useState('')
  const [contacts, setContacts] = useState('')
  const [summary, setSummary] = useState('')
  const [bullets, setBullets] = useState<Bullet[]>([])
  const [extras, setExtras] = useState<Extra[]>([])
  const [order, setOrder] = useState<api.SectionKey[]>(DEFAULT_ORDER)
  const [ats, setAts] = useState<api.Ats | null>(null)
  const [roleHits, setRoleHits] = useState<Record<string, number>>({})
  const [critic, setCritic] = useState<api.Critique | null>(null)
  const [criticLoading, setCriticLoading] = useState(false)
  const [html, setHtml] = useState('')
  const [fit, setFit] = useState<api.Fit>({ pages: 1, shorten: [], remove: [] })
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
    Promise.all([api.listRoles(), api.listBullets(), api.listEntries(), api.latestVersion()]).then(([rs, bs, es, v]) => {
      setRoles(rs)
      setExtras([
        ...rs.filter((r) => r.kind === 'education').map((r) => ({
          key: `role_${r.id}`, section: 'education' as const, label: r.company, sub: r.title, date: dates(r), on: true,
          text: bs.filter((b) => b.role_id === r.id).map((b) => b.text).join('\n'),
        })),
        ...es.filter((e) => e.section === 'skills').map((e) => ({ key: `entry_${e.id}`, section: 'skills' as const, label: e.label, sub: '', date: '', text: e.text, on: true })),
      ])
      if (v) {
        setName(v.content.name ?? '')
        setContacts((v.content.contacts ?? []).join('\n'))
        if (v.content.order) setOrder(v.content.order)
      }
    }).catch((e) => setError(e.message))
  }, [])

  const resume = toResume(name, contacts, summary, roles, bullets, extras, order)
  // Flags and "kept" are left out, so a re-check result doesn't trigger another re-check.
  const draftKey = JSON.stringify([resume, bullets.map((b) => [b.text, b.source_id])])

  useEffect(() => setReviewed(false), [draftKey])

  useEffect(() => {
    if (jobId === null) return
    let stale = false
    setChecking(true)
    const t = setTimeout(() => {
      const fallback = bullets.filter((b) => b.included && b.fallback).map((b) => b.text)
      // Per-role job-term hits over what each role puts on the page, like atsText.
      const roleText = Object.fromEntries(roles.filter((r) => r.kind !== 'education').map((r) => [`role_${r.id}`,
        [r.company, r.title, ...bullets.filter((b) => b.included && b.role_id === `role_${r.id}`).map((b) => b.text)].join('\n')]))
      // Both must return before the gate opens: flags and page count must come from this draft.
      Promise.all([api.check(jobId, atsText(resume), bullets, roleText), api.preview(resume, jobId, fallback)]).then(([r, p]) => {
        if (stale) return
        setAts(r.ats)
        setRoleHits(r.role_hits ?? {})
        setBullets((bs) => bs.map((b, i) => ({ ...b, flags: r.flags[i] ?? b.flags })))
        const { html, ...f } = p
        setHtml(html)
        setFit(f)
        setChecking(false)
      // Fails closed: download stays blocked until an edit retries both.
      }).catch((e) => !stale && setError(`Checking this draft failed, edit it to retry. ${e.message}`))
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
      const bs = out.bullets.map((b) => ({ ...b, included: b.included ?? true, key: nextKey++ }))
      jobRef.current = job.id
      setJobId(job.id)
      setBullets(bs)
      setCritic(null)
      runCritic(job.id, bs.filter((b) => b.included))
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
      await api.saveVersion(jobId, {
        name, contacts: lines(contacts), summary, bullets: bullets.map(({ key, kept, ...b }) => b),
        order, education: resume.education, skills: resume.skills,
      })
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
  const editExtra = (key: string, patch: Partial<Extra>) =>
    setExtras((es) => es.map((e) => (e.key === key ? { ...e, ...patch } : e)))
  const move = (i: number, by: number) => setOrder((o) => {
    const next = [...o]
    ;[next[i], next[i + by]] = [next[i + by], next[i]]
    return next
  })

  const unresolved = bullets.filter((b) => b.included && b.flags.length > 0 && !b.kept).length
  const canDownload = jobId !== null && unresolved === 0 && reviewed && !checking && !busy && fit.pages <= 1
  const clip = (t: string) => (t.length > 60 ? `${t.slice(0, 60)}...` : t)

  const groups = [
    ...roles.filter((r) => r.kind !== 'education').map((r) => ({ id: `role_${r.id}`, title: [r.company, r.title].filter(Boolean).join(' - '), dates: dates(r), cited: true })),
    { id: null, title: 'Uncited (left out of the PDF)', dates: '', cited: false },
  ].map((g) => ({ ...g, items: bullets.filter((b) => b.role_id === g.id) }))
    // Every role keeps its card (a zero-bullet role shows its header only); uncited only when it has bullets.
    .filter((g) => g.cited || g.items.length > 0)

  function renderBullet(b: Bullet, cited: boolean) {
    const n = bullets.indexOf(b) + 1
    const kinds = [...new Set(b.flags.map(kindOf))]
    return (
      <li key={b.key} className={`flex flex-col gap-2 ${b.included ? '' : 'opacity-60'}`}>
        <div className="flex items-start gap-2">
          <input type="checkbox" className="mt-3" aria-label={`Include bullet ${n}`} checked={b.included} onChange={(e) => editBullet(b.key, { included: e.target.checked })} />
          <textarea
            aria-label={`Bullet ${n}`}
            className="field font-serif leading-relaxed"
            rows={2}
            value={b.text}
            onChange={(e) => editBullet(b.key, { text: e.target.value, kept: false, fallback: false })}
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
          <div className="record">
            <h2 className="font-serif text-lg font-semibold">Section order</h2>
            <ol className="mt-3 flex flex-col gap-1">
              {order.map((k, i) => (
                <li key={k} className="flex items-center gap-2">
                  <span className="flex-1">{SECTION_NAMES[k]}</span>
                  <button type="button" className="btn btn-quiet px-2" aria-label={`Move ${SECTION_NAMES[k]} up`} disabled={i === 0} onClick={() => move(i, -1)}>
                    <ArrowUp aria-hidden size={16} />
                  </button>
                  <button type="button" className="btn btn-quiet px-2" aria-label={`Move ${SECTION_NAMES[k]} down`} disabled={i === order.length - 1} onClick={() => move(i, 1)}>
                    <ArrowDown aria-hidden size={16} />
                  </button>
                </li>
              ))}
            </ol>
          </div>
          {(['education', 'skills'] as const).map((sec) => {
            const items = extras.filter((e) => e.section === sec)
            return items.length > 0 && (
              <div key={sec} className="record">
                <h2 className="font-serif text-lg font-semibold">{SECTION_NAMES[sec]}</h2>
                <p className="text-sm text-muted">Copied as saved. Edits here apply to this draft only.</p>
                <ul className="mt-3 flex flex-col gap-4">
                  {items.map((e) => (
                    <li key={e.key} className="flex flex-col gap-2">
                      <label className="inline-flex items-center gap-2 text-sm font-medium">
                        <input type="checkbox" checked={e.on} onChange={(ev) => editExtra(e.key, { on: ev.target.checked })} />
                        Include {e.label}{e.sub && ` | ${e.sub}`}
                      </label>
                      <textarea
                        aria-label={sec === 'education' ? `${e.label} details` : `${e.label} text`}
                        className="field font-serif leading-relaxed"
                        rows={2}
                        disabled={!e.on}
                        value={e.text}
                        onChange={(ev) => editExtra(e.key, { text: ev.target.value })}
                      />
                    </li>
                  ))}
                </ul>
              </div>
            )
          })}
          {groups.map((g) => (
            <div key={g.id ?? 'uncited'} className="record">
              <h2 className="font-serif text-lg font-semibold">{g.title}</h2>
              {g.dates && <p className="text-sm text-muted">{g.dates}</p>}
              {g.id !== null && g.id in roleHits && (
                <p className="text-sm text-muted" title="local estimate">{roleHits[g.id]} job term{roleHits[g.id] === 1 ? '' : 's'}</p>
              )}
              {g.items.some((b) => b.included && b.fallback) && <p className="text-sm text-muted">Copied as saved</p>}
              {g.items.length > 0 && <ul className="mt-3 flex flex-col gap-4">{g.items.map((b) => renderBullet(b, g.cited))}</ul>}
            </div>
          ))}
          {jobId !== null && (
            <div className="record flex flex-col gap-3">
              <p className="text-sm text-muted" aria-live="polite">
                {unresolved > 0 ? `${unresolved} flagged bullet${unresolved > 1 ? 's' : ''} to fix, keep or remove.` : 'No unresolved flags.'}
              </p>
              {fit.pages > 1 && (
                <div role="status" className="rounded-lg border border-warn/50 bg-warn/10 p-3 text-sm">
                  <p className="font-semibold text-warn">This resume runs to {fit.pages} pages. Download is blocked until it fits on 1.</p>
                  {fit.shorten.length > 0 && (<>
                    <p className="mt-2 font-medium">Shorten first</p>
                    <ul className="list-disc pl-5">
                      {fit.shorten.slice(0, 5).map((s, i) => <li key={i}>{s.role}: {clip(s.text)} (last line {s.words} word{s.words === 1 ? '' : 's'})</li>)}
                    </ul>
                  </>)}
                  {fit.remove.length > 0 && (<>
                    <p className="mt-2 font-medium">Then consider removing</p>
                    <ul className="list-disc pl-5">
                      {fit.remove.slice(0, 5).map((s, i) => <li key={i}>{s.role}: {clip(s.text)}</li>)}
                    </ul>
                  </>)}
                </div>
              )}
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
          <CriticPanel critic={critic} loading={criticLoading} disabled={jobId === null} onRerun={() => jobId !== null && runCritic(jobId, bullets.filter((b) => b.included))} />
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
