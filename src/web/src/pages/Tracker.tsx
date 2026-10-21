import { Fragment, useEffect, useState } from 'react'
import { ChevronDown, ChevronRight, Download, ExternalLink } from 'lucide-react'
import * as api from '../api'

const STATUSES: api.Status[] = ['saved', 'applied', 'interview', 'offer', 'rejected']
// SQLite CURRENT_TIMESTAMP is UTC with no zone marker.
const when = (utc: string) => new Date(utc.replace(' ', 'T') + 'Z').toLocaleString()
const today = () => new Date().toLocaleDateString('en-CA') // local YYYY-MM-DD; toISOString would give the UTC date

export default function Tracker() {
  const [jobs, setJobs] = useState<api.Job[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState<number | null>(null) // id of the job being saved
  const [open, setOpen] = useState<number | null>(null) // job whose detail row is expanded

  useEffect(() => {
    api.listJobs().then(setJobs).catch((e) => setError(e.message))
  }, [])

  const edit = (id: number, patch: Partial<api.Job>) =>
    setJobs((js) => js.map((j) => (j.id === id ? { ...j, ...patch } : j)))

  function setStatus(j: api.Job, status: api.Status) {
    // Applying records what was sent: default to the newest version and today.
    if (status === 'applied') {
      return edit(j.id, { status, version_id: j.version_id ?? j.versions?.at(-1)?.id ?? null, applied_at: j.applied_at || today() })
    }
    edit(j.id, { status })
  }

  async function save(j: api.Job) {
    setSaving(j.id)
    setError('')
    try {
      const { company, title, link, status, applied_at, notes, version_id } = j
      const saved = await api.updateJob(j.id, { company, title, link, status, applied_at, notes, version_id })
      edit(j.id, saved)
    } catch (e) {
      setError((e as Error).message)
    }
    setSaving(null)
  }

  async function remove(j: api.Job) {
    if (!confirm(`Delete this job and its ${j.versions?.length ?? 0} saved versions?`)) return
    try {
      await api.deleteJob(j.id)
      setJobs((js) => js.filter((x) => x.id !== j.id))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  async function download(id: number) {
    setError('')
    try {
      const url = URL.createObjectURL(await api.versionPdf(id))
      const a = document.createElement('a')
      a.href = url
      a.download = 'resume.pdf'
      a.click()
      setTimeout(() => URL.revokeObjectURL(url), 0) // revoking during click() can cancel the download
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const cell = 'field px-2 py-1 text-sm'
  // The row the Editor's last "Save in tracker" went to.
  const latest = Math.max(0, ...jobs.flatMap((j) => (j.versions ?? []).map((v) => v.id)))

  return (
    <section>
      <header className="mb-8">
        <h1 className="page-title">Tracker</h1>
        <p className="page-lede">Jobs you saved from the Editor, their status and the resume version you sent.</p>
      </header>
      {error && <p role="alert" className="alert">{error}</p>}
      {jobs.length === 0 ? <p className="text-muted">No saved jobs yet. Use Save in tracker in the Editor.</p> : (
        <div className="overflow-x-auto rounded-xl border border-line bg-surface">
          <table className="w-full min-w-[56rem] text-left text-sm">
            <thead className="border-b border-line text-muted">
              <tr>
                <th className="w-8 px-2 py-2"><span className="sr-only">Details</span></th>
                <th className="px-2 py-2 font-medium">#</th>
                {['Company', 'Role', 'Status', 'Date applied', 'Version sent', 'Link'].map((h) => <th key={h} className="px-2 py-2 font-medium">{h}</th>)}
                <th className="px-2 py-2"><span className="sr-only">Actions</span></th>
              </tr>
            </thead>
            <tbody>
              {jobs.map((j, i) => {
                const row = jobs.length - i // oldest saved job is row 1; closes up after a delete
                const versions = j.versions ?? []
                const vName = (id: number) => `v${versions.findIndex((v) => v.id === id) + 1}`
                const expanded = open === j.id
                const Chevron = expanded ? ChevronDown : ChevronRight
                return (
                  <Fragment key={j.id}>
                    <tr className="border-b border-line align-middle last:border-0">
                      <td className="px-2 py-2">
                        <button type="button" className="rounded p-1 text-muted hover:text-ink" aria-expanded={expanded} aria-controls={`job-${j.id}`}
                          aria-label={`Details for ${j.company || `job ${row}`}`} onClick={() => setOpen(expanded ? null : j.id)}>
                          <Chevron aria-hidden size={16} />
                        </button>
                      </td>
                      <td className="whitespace-nowrap px-2 py-2">
                        {row}
                        {versions.some((v) => v.id === latest) && <span className="ml-2 rounded border border-accent/50 px-1.5 text-xs text-accent">latest save</span>}
                      </td>
                      <td className="px-2 py-2"><input className={cell} aria-label="Company" placeholder={`Job ${row}`} value={j.company} onChange={(e) => edit(j.id, { company: e.target.value })} /></td>
                      <td className="px-2 py-2"><input className={cell} aria-label="Role" value={j.title} onChange={(e) => edit(j.id, { title: e.target.value })} /></td>
                      <td className="px-2 py-2">
                        <select className={cell} aria-label="Status" value={j.status} onChange={(e) => setStatus(j, e.target.value as api.Status)}>
                          {STATUSES.map((s) => <option key={s} value={s}>{s}</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-2"><input className={cell} type="date" aria-label="Date applied" value={j.applied_at} onChange={(e) => edit(j.id, { applied_at: e.target.value })} /></td>
                      <td className="px-2 py-2">
                        <select className={cell} aria-label="Version sent" value={j.version_id ?? ''} onChange={(e) => edit(j.id, { version_id: e.target.value ? Number(e.target.value) : null })}>
                          <option value="">None</option>
                          {versions.map((v) => <option key={v.id} value={v.id}>{vName(v.id)}</option>)}
                        </select>
                      </td>
                      <td className="px-2 py-2">
                        <span className="flex items-center gap-1">
                          <input className={cell} type="url" aria-label="Link" value={j.link} onChange={(e) => edit(j.id, { link: e.target.value })} />
                          {/^https?:\/\//.test(j.link) && <a href={j.link} target="_blank" rel="noreferrer" aria-label="Open link" className="text-muted hover:text-accent"><ExternalLink aria-hidden size={16} /></a>}
                        </span>
                      </td>
                      <td className="px-2 py-2">
                        <span className="flex gap-1">
                          <button type="button" className="btn btn-primary px-3 py-1" disabled={saving === j.id} onClick={() => save(j)}>Save</button>
                          <button type="button" className="btn btn-quiet px-3 py-1" onClick={() => remove(j)}>Delete</button>
                        </span>
                      </td>
                    </tr>
                    {expanded && (
                      <tr id={`job-${j.id}`} className="border-b border-line bg-paper last:border-0">
                        <td colSpan={9} className="px-4 py-4">
                          <div className="grid gap-4 md:grid-cols-2">
                            <label className="label">Notes<textarea className="field" rows={3} value={j.notes} onChange={(e) => edit(j.id, { notes: e.target.value })} /></label>
                            <div>
                              <p className="text-sm font-medium text-muted">Versions</p>
                              <ul className="mt-1 flex flex-col gap-1">
                                {versions.map((v) => (
                                  <li key={v.id} className="flex items-center gap-3 text-sm">
                                    <span>{vName(v.id)} · {when(v.created_at)}</span>
                                    {v.id === j.version_id && <span className="rounded border border-accent/50 px-1.5 text-xs text-accent">sent</span>}
                                    <button type="button" className="btn btn-secondary ml-auto px-2 py-1" aria-label={`Download ${vName(v.id)} PDF`} onClick={() => download(v.id)}>
                                      <Download aria-hidden size={14} />PDF
                                    </button>
                                  </li>
                                ))}
                              </ul>
                            </div>
                          </div>
                          <details className="mt-4 text-sm">
                            <summary className="cursor-pointer text-muted">Job text</summary>
                            <p className="mt-2 whitespace-pre-wrap">{j.text}</p>
                          </details>
                        </td>
                      </tr>
                    )}
                  </Fragment>
                )
              })}
            </tbody>
          </table>
        </div>
      )}
    </section>
  )
}
