import { useEffect, useState } from 'react'
import { ArrowDown, ArrowUp, Plus } from 'lucide-react'
import * as api from '../api'

type Form = api.SkillFields & { id?: number; tmp?: number; editing?: boolean; orig?: Form }
let nextTmp = 0 // stable React key for unsaved forms
const GROUPS: api.SkillGroup[] = ['Product', 'AI', 'Technical']

export default function Skills() {
  const [forms, setForms] = useState<Form[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.listSkills().then((ss) => setForms(ss.map((s) => ({ ...s, is_default: !!s.is_default, demote: !!s.demote })))).catch((e) => setError(e.message))
  }, [])

  const edit = (i: number, patch: Partial<Form>) =>
    setForms((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)))

  async function save(i: number) {
    const { id, name, grp, aliases, is_default, demote } = forms[i]
    if (!name.trim()) return setError('Name is required')
    setSaving(true)
    setError('')
    try {
      const fields = { name, grp, aliases, is_default, demote }
      const s = id ? await api.updateSkill(id, fields) : await api.createSkill(fields)
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

  async function move(i: number, d: -1 | 1) {
    try {
      await api.swapSkills(forms[i].id!, forms[i + d].id!)
    } catch (e) {
      return setError((e as Error).message)
    }
    setForms((fs) => fs.map((f, j) => (j === i ? fs[i + d] : j === i + d ? fs[i] : f)))
  }

  async function remove(i: number) {
    const { id } = forms[i]
    try {
      if (id) await api.deleteSkill(id)
      setForms((fs) => fs.filter((_, j) => j !== i))
    } catch (e) {
      setError((e as Error).message)
    }
  }

  const defaults = forms.filter((f) => f.is_default).length
  return (
    <section className="max-w-3xl">
      <header className="mb-8">
        <h1 className="page-title">Skills</h1>
        <p className="page-lede">
          Your pool of skills you can defend. The tailor picks up to 14 per job and the resume prints them as one line, exactly as named here.
          Defaults are what shows with no job (aim for 12 to 14; now {defaults}).
        </p>
      </header>
      {error && <p role="alert" className="alert">{error}</p>}
      <div className="flex flex-col gap-5">
        {forms.map((f, i) => (
          <form key={f.id ?? `new-${f.tmp}`} className="record" onSubmit={(e) => { e.preventDefault(); if (f.editing) save(i) }}>
            <div className="grid gap-4 sm:grid-cols-[1fr_10rem]">
              <label className="label">Name<input className="field" readOnly={!f.editing} value={f.name} onChange={(e) => edit(i, { name: e.target.value })} /></label>
              <label className="label">Group
                <select className="field" disabled={!f.editing} value={f.grp} onChange={(e) => edit(i, { grp: e.target.value as api.SkillGroup })}>
                  {GROUPS.map((g) => <option key={g}>{g}</option>)}
                </select>
              </label>
            </div>
            <label className="label mt-4">Also matches (comma separated)
              <input className="field" readOnly={!f.editing} value={f.aliases} onChange={(e) => edit(i, { aliases: e.target.value })} />
            </label>
            <div className="mt-4 flex flex-wrap gap-4 text-sm font-medium">
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" disabled={!f.editing} checked={f.is_default} onChange={(e) => edit(i, { is_default: e.target.checked })} />Default
              </label>
              <label className="inline-flex items-center gap-2">
                <input type="checkbox" disabled={!f.editing} checked={f.demote} onChange={(e) => edit(i, { demote: e.target.checked })} />Not in the first five unless the job requires it
              </label>
            </div>
            <div className="mt-4 flex items-center justify-between gap-2">
              <button type="button" className="btn btn-quiet" disabled={!f.editing} onClick={() => remove(i)}>Delete</button>
              <div className="flex gap-2">
                <button type="button" className="btn btn-quiet" aria-label="Move up" disabled={!f.id || !forms[i - 1]?.id} onClick={() => move(i, -1)}><ArrowUp aria-hidden size={16} /></button>
                <button type="button" className="btn btn-quiet" aria-label="Move down" disabled={!f.id || !forms[i + 1]?.id} onClick={() => move(i, 1)}><ArrowDown aria-hidden size={16} /></button>
                {f.editing
                  ? <button type="button" className="btn btn-secondary" onClick={() => cancel(i)}>Cancel</button>
                  : <button type="button" className="btn btn-secondary" onClick={() => edit(i, { editing: true, orig: f })}>Edit</button>}
                <button type="submit" className="btn btn-primary" disabled={!f.editing || saving}>Save</button>
              </div>
            </div>
          </form>
        ))}
      </div>
      <button className="btn btn-secondary mt-5" onClick={() => setForms((fs) => [...fs, { tmp: nextTmp++, name: '', grp: 'Technical', aliases: '', is_default: false, demote: false, editing: true }])}>
        <Plus aria-hidden size={16} />Add skill
      </button>
    </section>
  )
}
