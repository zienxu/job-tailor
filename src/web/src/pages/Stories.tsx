import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import * as api from '../api'

type Form = { id?: number; tmp?: number; role_id: number | ''; text: string; editing?: boolean; orig?: Form }
let nextTmp = 0 // stable React key for unsaved forms

export default function Stories() {
  const [forms, setForms] = useState<Form[]>([])
  const [roles, setRoles] = useState<api.Role[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    Promise.all([api.listRoles(), api.listStories()]).then(([rs, ss]) => {
      setRoles(rs)
      setForms(ss)
    }).catch((e) => setError(e.message))
  }, [])

  const edit = (i: number, patch: Partial<Form>) =>
    setForms((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)))

  async function save(i: number) {
    const { id, role_id, text } = forms[i]
    if (role_id === '') return setError('Pick a role for this story')
    setSaving(true)
    setError('')
    try {
      const s = id ? await api.updateStory(id, { role_id, text }) : await api.createStory({ role_id, text })
      edit(i, { id: s.id, editing: false, orig: undefined })
    } catch (e) {
      setError((e as Error).message)
    }
    setSaving(false)
  }

  function cancel(i: number) {
    const f = forms[i]
    setError('')
    if (!f.id) return setForms((fs) => fs.filter((_, j) => j !== i))
    setForms((fs) => fs.map((x, j) => (j === i ? { ...(f.orig ?? f), editing: false, orig: undefined } : x)))
  }

  async function remove(i: number) {
    const { id } = forms[i]
    try {
      if (id) await api.deleteStory(id)
      setForms((fs) => fs.filter((_, j) => j !== i))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  return (
    <section className="max-w-3xl">
      <header className="mb-8">
        <h1 className="page-title">Stories</h1>
        <p className="page-lede">Longer accounts of your work, each tied to a role. The tailor can draw new bullets from them.</p>
      </header>
      {error && <p role="alert" className="alert">{error}</p>}
      <div className="flex flex-col gap-5">
        {forms.map((f, i) => (
          <form key={f.id ?? `new-${f.tmp}`} className="record" onSubmit={(e) => { e.preventDefault(); if (f.editing) save(i) }}>
            <label className="label">Role
              <select className="field" disabled={!f.editing} value={f.role_id} onChange={(e) => edit(i, { role_id: e.target.value ? Number(e.target.value) : '' })}>
                <option value="">Pick a role</option>
                {roles.map((r) => <option key={r.id} value={r.id}>{r.company} - {r.title}</option>)}
              </select>
            </label>
            <label className="label mt-4">Story<textarea className="field font-serif leading-relaxed" rows={5} readOnly={!f.editing} value={f.text} onChange={(e) => edit(i, { text: e.target.value })} /></label>
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
      <button className="btn btn-secondary mt-5" onClick={() => setForms((fs) => [...fs, { tmp: nextTmp++, role_id: '', text: '', editing: true }])}>
        <Plus aria-hidden size={16} />Add story
      </button>
    </section>
  )
}
