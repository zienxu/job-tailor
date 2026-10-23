export type RoleKind = 'experience' | 'project' | 'education' | 'leadership'
export type RoleFields = { company: string; title: string; start_date: string; end_date: string; kind: RoleKind }
export type Role = RoleFields & { id: number }
export type ItemFields = { role_id: number; text: string }
export type Bullet = ItemFields & { id: number; position: number }
export type Story = ItemFields & { id: number }
export type Section = 'leadership' | 'eligibility' | 'summary'
export type EntryFields = { section: Section; label: string; text: string }
export type Entry = EntryFields & { id: number }
export type SkillGroup = 'Product' | 'AI' | 'Technical'
export type SkillFields = { name: string; grp: SkillGroup; aliases: string; is_default: boolean; demote: boolean }
export type Skill = SkillFields & { id: number }

export type Status = 'saved' | 'applied' | 'interview' | 'offer' | 'rejected'
export type JobFields = { company: string; title: string; link: string; status: Status; applied_at: string; notes: string; version_id: number | null }
export type Requirement = { text: string; kind: 'must' | 'nice'; hard_gate: boolean; status: 'met' | 'partial' | 'missing'; evidence_ids: string[]; evidence: string[] }
export type Grade = { score: number; band: 'Apply' | 'Stretch' | 'Skip'; requirements: Requirement[]; keywords: { term: string; kind: 'must' | 'nice' }[]; seniority_fit?: 'under' | 'match' | 'over'; summary?: string }
export type JobMeta = { company: string; title: string; link: string }
export type Job = JobFields & { id: number; text: string; created_at?: string; versions?: { id: number; created_at: string }[]; grade?: Grade | null }
export type DraftBullet = { text: string; source_id: string | null; role_id: string | null; flags: string[]; fallback?: boolean; included?: boolean }
export type Ats = { label: string; score: number; matched: string[]; missing: string[] }
export type CriticItem = { bullet: string; problem: string; fix: string }
export type Critique = {
  items: CriticItem[]; error?: string
  readiness?: { verdict: 'ready' | 'needs_work'; reason: string } | null
}
export type SectionKey = 'summary' | 'education' | 'experience' | 'leadership' | 'projects' | 'skills'
export type Education = { school: string; degree: string; date: string; details: string[] }
export type Row = { name: string; role: string; dates: string; bullets: string[] }
export type Resume = {
  name: string; contacts: string[]; summary: string
  education: Education[]
  experience: { company: string; title: string; dates: string; bullets: string[] }[]
  leadership: Row[]
  projects: Row[]
  skills: string[] // skill names, in print order
  order: SectionKey[]
}
export type Draft = {
  name: string; contacts: string[]; summary: string; bullets: DraftBullet[]
  order?: SectionKey[]; education?: Education[]; skills?: string[]
  resume?: Resume // the exact payload sent to /pdf, so the tracker can rebuild it
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

export const listSkills = () => req<Skill[]>('GET', '/skill_pool')
export const createSkill = (s: SkillFields) => req<Skill>('POST', '/skill_pool', s)
export const updateSkill = (id: number, s: SkillFields) => req<Skill>('PUT', `/skill_pool/${id}`, s)
export const deleteSkill = (id: number) => req<void>('DELETE', `/skill_pool/${id}`)
export const swapSkills = (a: number, b: number) => req<void>('POST', `/skill_pool/${a}/swap/${b}`)

export const createJob = (text: string, meta?: JobMeta) => req<Job>('POST', '/jobs', { text, ...meta })
export const fetchJob = (url: string) => req<JobMeta & { text: string }>('POST', '/jobs/fetch', { url })
export const gradeJob = (id: number) => req<Grade>('POST', `/jobs/${id}/grade`)
export type SummaryHint = { kind: 'pm' | 'technical' | 'graduate'; domain: string; company: string; programme: string }
export const summaryHint = (id: number) => req<SummaryHint>('POST', `/jobs/${id}/summary-hint`)
export const listJobs = () => req<Job[]>('GET', '/jobs')
export const updateJob = (id: number, j: JobFields) => req<Job>('PUT', `/jobs/${id}`, j)
export const deleteJob = (id: number) => req<void>('DELETE', `/jobs/${id}`)
export const versionPdf = async (id: number) => (await send('GET', `/versions/${id}/pdf`)).blob()
export const tailor = (jobId: number) => req<{ bullets: DraftBullet[]; skills?: string[] }>('POST', `/jobs/${jobId}/tailor`)
export const check = (jobId: number, text: string, bullets: DraftBullet[], roles: Record<string, string>) =>
  req<{ ats: Ats; flags: string[][]; role_hits: Record<string, number> }>('POST', `/jobs/${jobId}/check`, { text, bullets, roles })
export const critique = (jobId: number, bullets: DraftBullet[]) => req<Critique>('POST', `/jobs/${jobId}/critique`, { bullets })
export const preview = (resume: Resume, jobId: number, fallback: string[]) =>
  req<{ html: string } & Fit>('POST', '/preview', { resume, job_id: jobId, fallback })
export const pdf = async (resume: Resume) => (await send('POST', '/pdf', { resume })).blob()
export const saveVersion = (jobId: number, content: Draft) => req<Version>('POST', `/jobs/${jobId}/versions`, { content })
export const latestVersion = () => req<Version | null>('GET', '/versions/latest')
