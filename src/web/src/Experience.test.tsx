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
  m.createRole.mockResolvedValue({ id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '' })
  m.createBullet.mockResolvedValue({ id: 10, role_id: 1, text: 'Shipped X' })
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(screen.getByText('Add role'))
  await user.type(screen.getByLabelText('Company'), 'Acme')
  await user.type(screen.getByLabelText('Title'), 'Engineer')
  await user.type(screen.getByLabelText('Bullets (one per line)'), 'Shipped X')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createBullet).toHaveBeenCalledWith({ role_id: 1, text: 'Shipped X' }))
  expect(m.createRole).toHaveBeenCalledWith({ company: 'Acme', title: 'Engineer', start_date: '', end_date: '' })
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
  const role = { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '' }
  m.listRoles.mockResolvedValue([role])
  m.listBullets.mockResolvedValue([{ id: 10, role_id: 1, text: 'A' }])
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
  const role = { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '' }
  m.listRoles.mockResolvedValue([role])
  m.listBullets.mockResolvedValue([{ id: 10, role_id: 1, text: 'A' }, { id: 11, role_id: 1, text: 'B' }])
  m.updateRole.mockResolvedValue(role)
  const user = userEvent.setup()
  render(<Experience />)

  await user.click(await screen.findByText('Edit'))
  const box = screen.getByDisplayValue(/A\s+B/)
  await user.clear(box)
  await user.type(box, 'A{Enter}C')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createBullet).toHaveBeenCalledWith({ role_id: 1, text: 'C' }))
  expect(m.deleteBullet).toHaveBeenCalledTimes(1)
  expect(m.deleteBullet).toHaveBeenCalledWith(11)
  expect(m.createBullet).toHaveBeenCalledTimes(1)
})

test('a saved role is locked until Edit; Cancel restores it, Save locks it again', async () => {
  const role = { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '' }
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
  expect(m.updateRole).toHaveBeenCalledWith(1, { company: 'Acme Corp', title: 'Engineer', start_date: '', end_date: '' })
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
