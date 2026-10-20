import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Plus } from 'lucide-react'
import * as api from '../api'

type Form = api.RoleFields & { id?: number; tmp?: number; bullets: string; editing?: boolean; orig?: Form }
let nextTmp = 0 // stable React key for unsaved forms

const LABELS: Record<api.RoleKind, { heading: string; lede: string; company: string; title: string; bullets: string; add: string; noun: string }> = {
  experience: {
    heading: 'Experience', lede: 'Your roles and the bullets the tailor is allowed to cite.',
    company: 'Company', title: 'Title', bullets: 'Bullets (one per line)', add: 'Add role', noun: 'role',
  },
  project: {
    heading: 'Projects', lede: 'Your projects and the bullets the tailor is allowed to cite.',
    company: 'Project', title: 'Subtitle', bullets: 'Bullets (one per line)', add: 'Add project', noun: 'project',
  },
  education: {
    heading: 'Education', lede: 'Schools and degrees, copied to the resume as saved. Never sent to the tailor.',
    company: 'School', title: 'Degree', bullets: 'Details (one per line)', add: 'Add education', noun: 'entry',
  },
}

export default function Experience({ kind = 'experience' }: { kind?: api.RoleKind }) {
  const L = LABELS[kind]
  const FIELDS: [keyof api.RoleFields, string][] = [
    ['company', L.company], ['title', L.title], ['start_date', 'Start date'], ['end_date', 'End date'],
  ]
  const [forms, setForms] = useState<Form[]>([])
  const [bullets, setBullets] = useState<api.Bullet[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([api.listRoles(), api.listBullets()]).then(([roles, bs]) => {
      setBullets(bs)
      setForms(roles.filter((r) => r.kind === kind).map((r) => ({
        ...r, bullets: bs.filter((b) => b.role_id === r.id).map((b) => b.text).join('\n'),
      })))
    }).catch((e) => setError(e.message))
  }, [kind])

  const edit = (i: number, patch: Partial<Form>) =>
    setForms((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)))

  async function save(i: number) {
    const { id, bullets: text, company, title, start_date, end_date } = forms[i]
    const fields = { company, title, start_date, end_date, kind }
    if (!company.trim() || !title.trim()) return setError(`${L.company} and ${L.title.toLowerCase()} are required`)
    setSaving(true)
    setError('')
    let ok = false
    try {
      const role = id ? await api.updateRole(id, fields) : await api.createRole(fields)
      edit(i, { id: role.id })
      // Match by text so unchanged bullets keep the IDs the tailor cites; an edited line is a new bullet.
      // Line order is bullet order: each bullet's position is its line index.
      const lines = [...new Set(text.split('\n').map((l) => l.trim()).filter(Boolean))]
      const old = bullets.filter((b) => b.role_id === role.id)
      const byText = new Map(old.map((b) => [b.text, b]))
      for (const b of old) if (!lines.includes(b.text)) await api.deleteBullet(b.id)
      for (const [position, t] of lines.entries()) {
        const b = byText.get(t)
        if (!b) await api.createBullet({ role_id: role.id, text: t, position })
        else if (b.position !== position) await api.updateBullet(b.id, { role_id: role.id, text: t, position })
      }
      ok = true
    } catch (e) {
      setError((e as Error).message)
    }
    // Refresh even after a partial failure, so the next diff isn't against already-deleted IDs.
    await api.listBullets().then(setBullets, () => {})
    setSaving(false)
    if (ok) edit(i, { editing: false, orig: undefined })
  }

  function cancel(i: number) {
    const f = forms[i]
    setError('')
    if (!f.id) return setForms((fs) => fs.filter((_, j) => j !== i))
    setForms((fs) => fs.map((x, j) => (j === i ? { ...(f.orig ?? f), editing: false, orig: undefined } : x)))
  }

  async function move(i: number, d: -1 | 1) {
    try {
      await api.swapRoles(forms[i].id!, forms[i + d].id!)
    } catch (e) {
      return setError((e as Error).message)
    }
    setForms((fs) => fs.map((f, j) => (j === i ? fs[i + d] : j === i + d ? fs[i] : f)))
  }

  async function remove(i: number) {
    const { id, company } = forms[i]
    if (id) {
      if (!confirm(`Delete ${company || `this ${L.noun}`} and all its bullets and stories?`)) return
      try {
        await api.deleteRole(id)
      } catch (e) {
        return setError((e as Error).message)
      }
    }
    setForms((fs) => fs.filter((_, j) => j !== i))
  }

  return (
    <section className="max-w-3xl">
      <header className="mb-8">
        <h1 className="page-title">{L.heading}</h1>
        <p className="page-lede">{L.lede}</p>
      </header>
      {error && <p role="alert" className="alert">{error}</p>}
      <div className="flex flex-col gap-5">
        {forms.map((f, i) => (
          <form key={f.id ?? `new-${f.tmp}`} className="record" onSubmit={(e) => { e.preventDefault(); if (f.editing) save(i) }}>
            <div className="grid gap-4 sm:grid-cols-2">
              {FIELDS.map(([k, label]) => (
                <label key={k} className="label">{label}<input className="field" readOnly={!f.editing} value={f[k]} onChange={(e) => edit(i, { [k]: e.target.value })} /></label>
              ))}
            </div>
            <label className="label mt-4">{L.bullets}
              <textarea className="field ruled font-serif" rows={6} readOnly={!f.editing} value={f.bullets} onChange={(e) => edit(i, { bullets: e.target.value })} />
            </label>
            <div className="mt-4 flex items-center justify-between gap-2">
              <button type="button" className="btn btn-quiet" disabled={!f.editing} onClick={() => remove(i)}>Delete</button>
              <div className="flex gap-2">
                {kind !== 'education' && <> {/* education keeps creation order */}
                  <button type="button" className="btn btn-quiet" aria-label="Move up" disabled={!f.id || !forms[i - 1]?.id} onClick={() => move(i, -1)}><ArrowUp aria-hidden size={16} /></button>
                  <button type="button" className="btn btn-quiet" aria-label="Move down" disabled={!f.id || !forms[i + 1]?.id} onClick={() => move(i, 1)}><ArrowDown aria-hidden size={16} /></button>
                </>}
                {f.editing
                  ? <button type="button" className="btn btn-secondary" onClick={() => cancel(i)}>Cancel</button>
                  : <button type="button" className="btn btn-secondary" onClick={() => edit(i, { editing: true, orig: f })}>Edit</button>}
                <button type="submit" className="btn btn-primary" disabled={!f.editing || saving}>Save</button>
              </div>
            </div>
          </form>
        ))}
      </div>
      <button className="btn btn-secondary mt-5" onClick={() => setForms((fs) => [...fs, { tmp: nextTmp++, company: '', title: '', start_date: '', end_date: '', kind, bullets: '', editing: true }])}>
        <Plus aria-hidden size={16} />{L.add}
      </button>
    </section>
  )
}
