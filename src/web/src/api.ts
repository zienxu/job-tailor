export type RoleKind = 'experience' | 'project' | 'education' | 'leadership'
export type RoleFields = { company: string; title: string; start_date: string; end_date: string; kind: RoleKind }
export type Role = RoleFields & { id: number }
export type ItemFields = { role_id: number; text: string }
export type Bullet = ItemFields & { id: number; position: number }
export type Story = ItemFields & { id: number }
export type Section = 'leadership' | 'skills'
export type EntryFields = { section: Section; label: string; text: string }
export type Entry = EntryFields & { id: number }

export type Job = { id: number; text: string; company: string; title: string; link: string }
export type DraftBullet = { text: string; source_id: string | null; role_id: string | null; flags: string[]; fallback?: boolean; included?: boolean }
export type Ats = { label: string; score: number; matched: string[]; missing: string[] }
export type Note = { text: string; reason: string }
export type Critique = {
  unmet_must_haves: string[]; weak_bullets: Note[]; missing_keywords: string[]; overstated_claims: Note[]; error?: string
  readiness?: { verdict: 'ready' | 'needs_work'; reason: string } | null
}
export type SectionKey = 'summary' | 'education' | 'experience' | 'leadership' | 'projects' | 'skills'
export type LabelText = { label: string; text: string }
export type Education = { school: string; degree: string; date: string; details: string[] }
export type Row = { name: string; role: string; dates: string; bullets: string[] }
export type Resume = {
  name: string; contacts: string[]; summary: string
  education: Education[]
  experience: { company: string; title: string; dates: string; bullets: string[] }[]
  leadership: Row[]
  projects: Row[]
  skills: LabelText[]
  order: SectionKey[]
}
export type Draft = {
  name: string; contacts: string[]; summary: string; bullets: DraftBullet[]
  order?: SectionKey[]; education?: Education[]; skills?: LabelText[]
}
export type Suggestion = { section: string; role: string; text: string; words?: number }
export type Fit = { pages: number; shorten: Suggestion[]; remove: Suggestion[] }
export type Version = { id: number; job_id: number; content: Draft; created_at: string }

async function send(method: string, path: string, body?: unknown): Promise<Response> {
  const res = await fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status} ${await res.text()}`)
  return res
}

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await send(method, path, body)
  return (res.status === 204 ? undefined : await res.json()) as T
}

export const listRoles = () => req<Role[]>('GET', '/roles')
export const createRole = (r: RoleFields) => req<Role>('POST', '/roles', r)
export const updateRole = (id: number, r: RoleFields) => req<Role>('PUT', `/roles/${id}`, r)
export const deleteRole = (id: number) => req<void>('DELETE', `/roles/${id}`)
export const swapRoles = (a: number, b: number) => req<void>('POST', `/roles/${a}/swap/${b}`)

export const listBullets = () => req<Bullet[]>('GET', '/bullets')
export const createBullet = (b: ItemFields & { position?: number }) => req<Bullet>('POST', '/bullets', b)
export const updateBullet = (id: number, b: ItemFields & { position: number }) => req<Bullet>('PUT', `/bullets/${id}`, b)
export const deleteBullet = (id: number) => req<void>('DELETE', `/bullets/${id}`)

export const listStories = () => req<Story[]>('GET', '/stories')
export const createStory = (s: ItemFields) => req<Story>('POST', '/stories', s)
export const updateStory = (id: number, s: ItemFields) => req<Story>('PUT', `/stories/${id}`, s)
export const deleteStory = (id: number) => req<void>('DELETE', `/stories/${id}`)

export const listEntries = () => req<Entry[]>('GET', '/entries')
export const createEntry = (e: EntryFields) => req<Entry>('POST', '/entries', e)
export const updateEntry = (id: number, e: EntryFields) => req<Entry>('PUT', `/entries/${id}`, e)
export const deleteEntry = (id: number) => req<void>('DELETE', `/entries/${id}`)
export const swapEntries = (a: number, b: number) => req<void>('POST', `/entries/${a}/swap/${b}`)

export const createJob = (text: string) => req<Job>('POST', '/jobs', { text })
export const tailor = (jobId: number) => req<{ bullets: DraftBullet[] }>('POST', `/jobs/${jobId}/tailor`)
export const check = (jobId: number, text: string, bullets: DraftBullet[], roles: Record<string, string>) =>
  req<{ ats: Ats; flags: string[][]; role_hits: Record<string, number> }>('POST', `/jobs/${jobId}/check`, { text, bullets, roles })
export const critique = (jobId: number, bullets: DraftBullet[]) => req<Critique>('POST', `/jobs/${jobId}/critique`, { bullets })
export const preview = (resume: Resume, jobId: number, fallback: string[]) =>
  req<{ html: string } & Fit>('POST', '/preview', { resume, job_id: jobId, fallback })
export const pdf = async (resume: Resume) => (await send('POST', '/pdf', { resume })).blob()
export const saveVersion = (jobId: number, content: Draft) => req<Version>('POST', `/jobs/${jobId}/versions`, { content })
export const latestVersion = () => req<Version | null>('GET', '/versions/latest')
