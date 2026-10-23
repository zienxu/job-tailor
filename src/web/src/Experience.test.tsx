import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import Experience from './pages/Experience'

vi.mock('./api')
const m = vi.mocked(api)

beforeEach(() => vi.resetAllMocks())

test('add a role and a bullet, then save', async () => {
  m.listRoles.mockResolvedValue([])
  m.listBullets.mockResolvedValue([])
  m.createRole.mockResolvedValue({ id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' })
  m.createBullet.mockResolvedValue({ id: 10, role_id: 1, text: 'Shipped X', position: 0 })
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(screen.getByText('Add role'))
  await user.type(screen.getByLabelText('Company'), 'Acme')
  await user.type(screen.getByLabelText('Title'), 'Engineer')
  await user.type(screen.getByLabelText('Bullets (one per line)'), 'Shipped X')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createBullet).toHaveBeenCalledWith({ role_id: 1, text: 'Shipped X', position: 0 }))
  expect(m.createRole).toHaveBeenCalledWith({ company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' })
})

test('a role needs a company and title', async () => {
  m.listRoles.mockResolvedValue([])
  m.listBullets.mockResolvedValue([])
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(screen.getByText('Add role'))
  await user.type(screen.getByLabelText('Company'), 'Acme')
  await user.click(screen.getByText('Save'))

  expect(await screen.findByRole('alert')).toHaveTextContent('Company and title are required')
  expect(m.createRole).not.toHaveBeenCalled()
})

test('bullets are reloaded even when a bullet call fails', async () => {
  const role = { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' as const }
  m.listRoles.mockResolvedValue([role])
  m.listBullets.mockResolvedValue([{ id: 10, role_id: 1, text: 'A', position: 0 }])
  m.updateRole.mockResolvedValue(role)
  m.deleteBullet.mockRejectedValue(new Error('DELETE /bullets/10 failed: 500'))
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(await screen.findByText('Edit'))
  await user.clear(screen.getByDisplayValue('A'))
  await user.click(screen.getByText('Save'))

  expect(await screen.findByRole('alert')).toHaveTextContent('500')
  await waitFor(() => expect(m.listBullets).toHaveBeenCalledTimes(2))
  expect(screen.getByText('Save')).toBeEnabled()
})

test('unchanged bullets keep their IDs; removed are deleted, new are created', async () => {
  const role = { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' as const }
  m.listRoles.mockResolvedValue([role])
  m.listBullets.mockResolvedValue([{ id: 10, role_id: 1, text: 'A', position: 0 }, { id: 11, role_id: 1, text: 'B', position: 1 }])
  m.updateRole.mockResolvedValue(role)
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(await screen.findByText('Edit'))
  const box = screen.getByDisplayValue(/A\s+B/)
  await user.clear(box)
  await user.type(box, 'A{Enter}C')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createBullet).toHaveBeenCalledWith({ role_id: 1, text: 'C', position: 1 }))
  expect(m.deleteBullet).toHaveBeenCalledTimes(1)
  expect(m.deleteBullet).toHaveBeenCalledWith(11)
  expect(m.createBullet).toHaveBeenCalledTimes(1)
  expect(m.updateBullet).not.toHaveBeenCalled()
})

test('reordering bullet lines keeps IDs and saves the new positions', async () => {
  const role = { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' as const }
  m.listRoles.mockResolvedValue([role])
  m.listBullets.mockResolvedValue([{ id: 10, role_id: 1, text: 'A', position: 0 }, { id: 11, role_id: 1, text: 'B', position: 1 }])
  m.updateRole.mockResolvedValue(role)
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(await screen.findByText('Edit'))
  const box = screen.getByDisplayValue(/A\s+B/)
  await user.clear(box)
  await user.type(box, 'B{Enter}A')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.updateBullet).toHaveBeenCalledTimes(2))
  expect(m.updateBullet).toHaveBeenCalledWith(11, { role_id: 1, text: 'B', position: 0 })
  expect(m.updateBullet).toHaveBeenCalledWith(10, { role_id: 1, text: 'A', position: 1 })
  expect(m.createBullet).not.toHaveBeenCalled()
  expect(m.deleteBullet).not.toHaveBeenCalled()
})

test('up/down on a project swaps it with its neighbour', async () => {
  const p = (id: number, company: string) => ({ id, company, title: 'Course Project', start_date: '', end_date: '', kind: 'project' as const })
  m.listRoles.mockResolvedValue([p(1, 'Solver'), p(2, 'Compiler')])
  m.listBullets.mockResolvedValue([])
  const user = userEvent.setup()
  render(<Experience kind="project" />)

  await screen.findByDisplayValue('Solver')
  expect(screen.getAllByLabelText('Move up')[0]).toBeDisabled()
  await user.click(screen.getAllByLabelText('Move down')[0])

  await waitFor(() => expect(m.swapRoles).toHaveBeenCalledWith(1, 2))
  await waitFor(() => expect(screen.getAllByLabelText('Project').map((e) => (e as HTMLInputElement).value)).toEqual(['Compiler', 'Solver']))
})

test('education has no move buttons', async () => {
  m.listRoles.mockResolvedValue([{ id: 1, company: 'NUS', title: 'BComp', start_date: '', end_date: '', kind: 'education' }])
  m.listBullets.mockResolvedValue([])
  render(<Experience kind="education" />)

  await screen.findByDisplayValue('NUS')
  expect(screen.queryByLabelText('Move up')).not.toBeInTheDocument()
})

test('a saved role is locked until Edit; Cancel restores it, Save locks it again', async () => {
  const role = { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' as const }
  m.listRoles.mockResolvedValue([role])
  m.listBullets.mockResolvedValue([])
  m.updateRole.mockResolvedValue({ ...role, company: 'Acme Corp' })
  const user = userEvent.setup()
  render(<Experience />)

  const company = await screen.findByDisplayValue('Acme')
  expect(company).toHaveAttribute('readonly')
  expect(screen.getByText('Save')).toBeDisabled()
  expect(screen.getByText('Delete')).toBeDisabled()

  await user.click(screen.getByText('Edit'))
  expect(company).not.toHaveAttribute('readonly')
  expect(screen.getByText('Delete')).toBeEnabled()
  await user.type(company, ' Corp')
  await user.click(screen.getByText('Cancel'))
  expect(screen.getByLabelText('Company')).toHaveValue('Acme')
  expect(screen.getByLabelText('Company')).toHaveAttribute('readonly')

  await user.click(screen.getByText('Edit'))
  await user.type(screen.getByLabelText('Company'), ' Corp')
  await user.click(screen.getByText('Save'))
  expect(await screen.findByText('Edit')).toBeInTheDocument()
  expect(screen.getByLabelText('Company')).toHaveValue('Acme Corp')
  expect(screen.getByLabelText('Company')).toHaveAttribute('readonly')
  expect(m.updateRole).toHaveBeenCalledWith(1, { company: 'Acme Corp', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' })
})

test('a new role opens unlocked, and Cancel discards it', async () => {
  m.listRoles.mockResolvedValue([])
  m.listBullets.mockResolvedValue([])
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(screen.getByText('Add role'))
  expect(screen.getByLabelText('Company')).not.toHaveAttribute('readonly')
  expect(screen.getByText('Save')).toBeEnabled()
  await user.click(screen.getByText('Cancel'))
  expect(screen.queryByLabelText('Company')).not.toBeInTheDocument()
})

test('add a project with its own labels, saved as kind project', async () => {
  m.listRoles.mockResolvedValue([{ id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' }])
  m.listBullets.mockResolvedValue([])
  m.createRole.mockResolvedValue({ id: 2, company: 'Chess AI', title: 'Course Project, NUS', start_date: '', end_date: '', kind: 'project' })
  m.createBullet.mockResolvedValue({ id: 10, role_id: 2, text: 'Built a solver', position: 0 })
  const user = userEvent.setup()
  render(<Experience kind="project" />)

  expect(screen.getByRole('heading', { name: 'Projects' })).toBeInTheDocument()
  await waitFor(() => expect(m.listRoles).toHaveBeenCalled())
  expect(screen.queryByDisplayValue('Acme')).not.toBeInTheDocument()
  await user.click(screen.getByText('Add project'))
  await user.type(screen.getByLabelText('Project'), 'Chess AI')
  await user.type(screen.getByLabelText('Subtitle'), 'Course Project, NUS')
  await user.type(screen.getByLabelText('Bullets (one per line)'), 'Built a solver')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createBullet).toHaveBeenCalledWith({ role_id: 2, text: 'Built a solver', position: 0 }))
  expect(m.createRole).toHaveBeenCalledWith({ company: 'Chess AI', title: 'Course Project, NUS', start_date: '', end_date: '', kind: 'project' })
})

test('a project saves without a subtitle', async () => {
  m.listRoles.mockResolvedValue([])
  m.listBullets.mockResolvedValue([])
  m.createRole.mockResolvedValue({ id: 2, company: 'Chess AI', title: '', start_date: '', end_date: '', kind: 'project' })
  const user = userEvent.setup()
  render(<Experience kind="project" />)

  await user.click(screen.getByText('Add project'))
  await user.type(screen.getByLabelText('Project'), 'Chess AI')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createRole).toHaveBeenCalledWith({ company: 'Chess AI', title: '', start_date: '', end_date: '', kind: 'project' }))
})

test('a leadership role saves with kind leadership and no position', async () => {
  m.listRoles.mockResolvedValue([])
  m.listBullets.mockResolvedValue([])
  m.createRole.mockResolvedValue({ id: 3, company: 'Chess Club', title: '', start_date: '', end_date: '', kind: 'leadership' })
  m.createBullet.mockResolvedValue({ id: 11, role_id: 3, text: 'Led 20 members', position: 0 })
  const user = userEvent.setup()
  render(<Experience kind="leadership" />)

  expect(screen.getByRole('heading', { name: 'Leadership' })).toBeInTheDocument()
  await user.click(screen.getByText('Add leadership'))
  await user.type(screen.getByLabelText('Organisation'), 'Chess Club')
  await user.type(screen.getByLabelText('Bullets (one per line)'), 'Led 20 members')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createBullet).toHaveBeenCalledWith({ role_id: 3, text: 'Led 20 members', position: 0 }))
  expect(m.createRole).toHaveBeenCalledWith({ company: 'Chess Club', title: '', start_date: '', end_date: '', kind: 'leadership' })
})
