import { useEffect, useState } from 'react'
import { Plus } from 'lucide-react'
import * as api from '../api'

type Form = { id?: number; tmp?: number; label: string; text: string; editing?: boolean; orig?: Form }
let nextTmp = 0 // stable React key for unsaved forms

const LABELS: Record<api.Section, { heading: string; lede: string; add: string }> = {
  leadership: { heading: 'Leadership', lede: 'Leadership and activities, copied to the resume as saved.', add: 'Add leadership' },
  skills: { heading: 'Skills', lede: 'Skill groups, copied to the resume as saved.', add: 'Add skill group' },
}

export default function Entries({ section }: { section: api.Section }) {
  const L = LABELS[section]
  const [forms, setForms] = useState<Form[]>([])
  const [error, setError] = useState('')
  const [saving, setSaving] = useState(false)

  useEffect(() => {
    api.listEntries().then((es) => setForms(es.filter((e) => e.section === section))).catch((e) => setError(e.message))
  }, [section])

  const edit = (i: number, patch: Partial<Form>) =>
    setForms((fs) => fs.map((f, j) => (j === i ? { ...f, ...patch } : f)))

  async function save(i: number) {
    const { id, label, text } = forms[i]
    if (!label.trim() || !text.trim()) return setError('Label and text are required')
    setSaving(true)
    setError('')
    try {
      const fields = { section, label, text }
      const e = id ? await api.updateEntry(id, fields) : await api.createEntry(fields)
      edit(i, { id: e.id, editing: false, orig: undefined })
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
      if (id) await api.deleteEntry(id)
      setForms((fs) => fs.filter((_, j) => j !== i))
    } catch (e) {
      setError((e as Error).message)
    }
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
            <label className="label">Label<input className="field" readOnly={!f.editing} value={f.label} onChange={(e) => edit(i, { label: e.target.value })} /></label>
            <label className="label mt-4">Text<textarea className="field font-serif leading-relaxed" rows={3} readOnly={!f.editing} value={f.text} onChange={(e) => edit(i, { text: e.target.value })} /></label>
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
      <button className="btn btn-secondary mt-5" onClick={() => setForms((fs) => [...fs, { tmp: nextTmp++, label: '', text: '', editing: true }])}>
        <Plus aria-hidden size={16} />{L.add}
      </button>
    </section>
  )
}
