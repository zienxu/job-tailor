import { useEffect, useState } from 'react'
import * as api from '../api'

type Form = api.RoleFields & { id?: number; tmp?: number; bullets: string }
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
    try {
      const role = id ? await api.updateRole(id, fields) : await api.createRole(fields)
      edit(i, { id: role.id })
      // Match by text so unchanged bullets keep the IDs the tailor cites; an edited line is a new bullet.
      const lines = new Set(text.split('\n').map((l) => l.trim()).filter(Boolean))
      const old = bullets.filter((b) => b.role_id === role.id)
      const oldTexts = new Set(old.map((b) => b.text))
      for (const b of old) if (!lines.has(b.text)) await api.deleteBullet(b.id)
      for (const t of lines) if (!oldTexts.has(t)) await api.createBullet({ role_id: role.id, text: t })
    } catch (e) {
      setError((e as Error).message)
    }
    // Refresh even after a partial failure, so the next diff isn't against already-deleted IDs.
    await api.listBullets().then(setBullets, () => {})
    setSaving(false)
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
    <section>
      <h1>Experience</h1>
      {error && <p role="alert">{error}</p>}
      {forms.map((f, i) => (
        <form key={f.id ?? `new-${f.tmp}`} onSubmit={(e) => { e.preventDefault(); save(i) }}>
          {FIELDS.map(([k, label]) => (
            <label key={k}>{label} <input value={f[k]} onChange={(e) => edit(i, { [k]: e.target.value })} /></label>
          ))}
          <label>Bullets (one per line)
            <textarea rows={6} value={f.bullets} onChange={(e) => edit(i, { bullets: e.target.value })} />
          </label>
          <button type="submit" disabled={saving}>Save</button>
          <button type="button" onClick={() => remove(i)}>Delete</button>
        </form>
      ))}
      <button onClick={() => setForms((fs) => [...fs, { tmp: nextTmp++, company: '', title: '', start_date: '', end_date: '', bullets: '' }])}>
        Add role
      </button>
    </section>
  )
}
