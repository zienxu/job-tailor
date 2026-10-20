export type RoleFields = { company: string; title: string; start_date: string; end_date: string }
export type Role = RoleFields & { id: number }
export type ItemFields = { role_id: number; text: string }
export type Bullet = ItemFields & { id: number }
export type Story = ItemFields & { id: number }

export type Job = { id: number; text: string; company: string; title: string; link: string }
export type DraftBullet = { text: string; source_id: string | null; role_id: string | null; flags: string[] }
export type Ats = { label: string; score: number; matched: string[]; missing: string[] }
export type Note = { text: string; reason: string }
export type Critique = {
  unmet_must_haves: string[]; weak_bullets: Note[]; missing_keywords: string[]; overstated_claims: Note[]; error?: string
}
export type Resume = {
  name: string; contacts: string[]; summary: string
  experience: { company: string; title: string; dates: string; bullets: string[] }[]
}
export type Draft = { name: string; contacts: string[]; summary: string; bullets: DraftBullet[] }
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

export const listBullets = () => req<Bullet[]>('GET', '/bullets')
export const createBullet = (b: ItemFields) => req<Bullet>('POST', '/bullets', b)
export const deleteBullet = (id: number) => req<void>('DELETE', `/bullets/${id}`)

export const listStories = () => req<Story[]>('GET', '/stories')
export const createStory = (s: ItemFields) => req<Story>('POST', '/stories', s)
export const updateStory = (id: number, s: ItemFields) => req<Story>('PUT', `/stories/${id}`, s)
export const deleteStory = (id: number) => req<void>('DELETE', `/stories/${id}`)

export const createJob = (text: string) => req<Job>('POST', '/jobs', { text })
export const tailor = (jobId: number) => req<{ bullets: DraftBullet[] }>('POST', `/jobs/${jobId}/tailor`)
export const check = (jobId: number, text: string, bullets: DraftBullet[]) =>
  req<{ ats: Ats; flags: string[][] }>('POST', `/jobs/${jobId}/check`, { text, bullets })
export const critique = (jobId: number, bullets: DraftBullet[]) => req<Critique>('POST', `/jobs/${jobId}/critique`, { bullets })
export const preview = async (resume: Resume) => (await send('POST', '/preview', { resume })).text()
export const pdf = async (resume: Resume) => (await send('POST', '/pdf', { resume })).blob()
export const saveVersion = (jobId: number, content: Draft) => req<Version>('POST', `/jobs/${jobId}/versions`, { content })
export const latestVersion = () => req<Version | null>('GET', '/versions/latest')
