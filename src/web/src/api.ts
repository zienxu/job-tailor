export type RoleFields = { company: string; title: string; start_date: string; end_date: string }
export type Role = RoleFields & { id: number }
export type ItemFields = { role_id: number; text: string }
export type Bullet = ItemFields & { id: number }
export type Story = ItemFields & { id: number }

async function req<T>(method: string, path: string, body?: unknown): Promise<T> {
  const res = await fetch('/api' + path, {
    method,
    headers: body ? { 'Content-Type': 'application/json' } : undefined,
    body: body ? JSON.stringify(body) : undefined,
  })
  if (!res.ok) throw new Error(`${method} ${path} failed: ${res.status} ${await res.text()}`)
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
