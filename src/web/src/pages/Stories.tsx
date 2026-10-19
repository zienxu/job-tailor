import { useEffect, useState } from 'react'
import * as api from '../api'

type Form = { id?: number; tmp?: number; role_id: number | ''; text: string }
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
      edit(i, { id: s.id })
    } catch (e) {
      setError((e as Error).message)
    }
    setSaving(false)
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
    <section>
      <h1>Stories</h1>
      {error && <p role="alert">{error}</p>}
      {forms.map((f, i) => (
        <form key={f.id ?? `new-${f.tmp}`} onSubmit={(e) => { e.preventDefault(); save(i) }}>
          <label>Role
            <select value={f.role_id} onChange={(e) => edit(i, { role_id: e.target.value ? Number(e.target.value) : '' })}>
              <option value="">Pick a role</option>
              {roles.map((r) => <option key={r.id} value={r.id}>{r.company} - {r.title}</option>)}
            </select>
          </label>
          <label>Story <textarea rows={5} value={f.text} onChange={(e) => edit(i, { text: e.target.value })} /></label>
          <button type="submit" disabled={saving}>Save</button>
          <button type="button" onClick={() => remove(i)}>Delete</button>
        </form>
      ))}
      <button onClick={() => setForms((fs) => [...fs, { tmp: nextTmp++, role_id: '', text: '' }])}>Add story</button>
    </section>
  )
}
