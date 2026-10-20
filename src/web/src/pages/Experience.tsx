import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import * as api from '../api'

type Form = api.RoleFields & { id?: number; tmp?: number; bullets: string; editing?: boolean; orig?: Form }
let nextTmp = 0 // stable React key for unsaved forms

const FIELDS: [keyof api.RoleFields, string][] = [
  ['company', 'Company'], ['title', 'Title'], ['start_date', 'Start date'], ['end_date', 'End date'],
]

export default function Experience() {
  const [forms, setForms] = useState<Form[]>([])
  const [bullets, setBullets] = useState<api.Bullet[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([api.listRoles(), api.listBullets()]).then(([roles, bs]) => {
      setBullets(bs)
      setForms(roles.map((r) => ({
        ...r, bullets: bs.filter((b) => b.role_id === r.id).map((b) => b.text).join('\n'),
      })))
    }).catch((e) => setError(e.message))
  }, [])

  const edit = (i: number, patch: Partial<Form>) =>
    setForms((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)))

  async function save(i: number) {
    const { id, bullets: text, company, title, start_date, end_date } = forms[i]
    const fields = { company, title, start_date, end_date }
    if (!company.trim() || !title.trim()) return setError('Company and title are required')
    setSaving(true)
    setError('')
    let ok = false
    try {
      const role = id ? await api.updateRole(id, fields) : await api.createRole(fields)
      edit(i, { id: role.id })
      // Match by text so unchanged bullets keep the IDs the tailor cites; an edited line is a new bullet.
      const lines = new Set(text.split('\n').map((l) => l.trim()).filter(Boolean))
      const old = bullets.filter((b) => b.role_id === role.id)
      const oldTexts = new Set(old.map((b) => b.text))
      for (const b of old) if (!lines.has(b.text)) await api.deleteBullet(b.id)
      for (const t of lines) if (!oldTexts.has(t)) await api.createBullet({ role_id: role.id, text: t })
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

  async function remove(i: number) {
    const { id, company } = forms[i]
    if (id) {
      if (!confirm(`Delete ${company || 'this role'} and all its bullets and stories?`)) return
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
        <h1 className="page-title">Experience</h1>
        <p className="page-lede">Your roles and the bullets the tailor is allowed to cite.</p>
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
            <label className="label mt-4">Bullets (one per line)
              <textarea className="field ruled font-serif" rows={6} readOnly={!f.editing} value={f.bullets} onChange={(e) => edit(i, { bullets: e.target.value })} />
            </label>
            <div className="mt-4 flex items-center justify-between gap-2">
              <button type="button" className="btn btn-quiet" disabled={!f.editing} onClick={() => remove(i)}>Delete</button>
              <div className="flex gap-2">
                {f.editing
                  ? <button type="button" className="btn btn-secondary" onClick={() => cancel(i)}>Cancel</button>
                  : <button type="button" className="btn btn-secondary" onClick={() => edit(i, { editing: true, orig: f })}>Edit</button>}
                <button type="submit" className="btn btn-primary" disabled={!f.editing || saving}>Save</button>
              </div>
            </div>
          </form>
        ))}
      </div>
      <button className="btn btn-secondary mt-5" onClick={() => setForms((fs) => [...fs, { tmp: nextTmp++, company: '', title: '', start_date: '', end_date: '', bullets: '', editing: true }])}>
        <Plus aria-hidden size={16} />Add role
      </button>
    </section>
  )
}
