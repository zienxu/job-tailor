import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import Stories from './pages/Stories'

vi.mock('./api')
const m = vi.mocked(api)

beforeEach(() => vi.resetAllMocks())

test('link a story to a role and save', async () => {
  m.listRoles.mockResolvedValue([{ id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' as const }])
  m.listStories.mockResolvedValue([])
  m.createStory.mockResolvedValue({ id: 5, role_id: 1, text: 'Fixed the outage' })
  const user = userEvent.setup()
  render(<Stories />)

  await user.click(screen.getByText('Add story'))
  await user.selectOptions(screen.getByLabelText('Role'), await screen.findByText('Acme - Engineer'))
  await user.type(screen.getByLabelText('Story'), 'Fixed the outage')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createStory).toHaveBeenCalledWith({ role_id: 1, text: 'Fixed the outage' }))
})

test('saving without a role is refused', async () => {
  m.listRoles.mockResolvedValue([])
  m.listStories.mockResolvedValue([])
  const user = userEvent.setup()
  render(<Stories />)

  await user.click(screen.getByText('Add story'))
  await user.click(screen.getByText('Save'))

  expect(await screen.findByRole('alert')).toHaveTextContent('Pick a role')
  expect(m.createStory).not.toHaveBeenCalled()
})

test('a saved story is locked until Edit, and a failed save stays unlocked', async () => {
  m.listRoles.mockResolvedValue([{ id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' as const }])
  m.listStories.mockResolvedValue([{ id: 5, role_id: 1, text: 'Fixed the outage' }])
  m.updateStory.mockRejectedValue(new Error('PUT /stories/5 failed: 500'))
  const user = userEvent.setup()
  render(<Stories />)

  const story = await screen.findByDisplayValue('Fixed the outage')
  expect(story).toHaveAttribute('readonly')
  expect(screen.getByLabelText('Role')).toBeDisabled()
  expect(screen.getByText('Save')).toBeDisabled()

  await user.click(screen.getByText('Edit'))
  expect(screen.getByLabelText('Role')).toBeEnabled()
  await user.type(story, ' twice')
  await user.click(screen.getByText('Save'))

  expect(await screen.findByRole('alert')).toHaveTextContent('500')
  expect(screen.getByText('Cancel')).toBeInTheDocument()
  expect(story).not.toHaveAttribute('readonly')
})

test('education roles are hidden from the picker unless a story already uses one', async () => {
  m.listRoles.mockResolvedValue([
    { id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '', kind: 'experience' },
    { id: 2, company: 'NUS', title: 'BComp', start_date: '', end_date: '', kind: 'education' },
  ])
  m.listStories.mockResolvedValue([{ id: 5, role_id: 2, text: 'Old story' }])
  const user = userEvent.setup()
  render(<Stories />)

  expect(await screen.findByRole('option', { name: 'NUS - BComp' })).toBeInTheDocument()
  await user.click(screen.getByText('Add story'))
  const [, fresh] = screen.getAllByLabelText('Role')
  expect(within(fresh).queryByRole('option', { name: 'NUS - BComp' })).not.toBeInTheDocument()
  expect(within(fresh).getByRole('option', { name: 'Acme - Engineer' })).toBeInTheDocument()
})

test('a story can be linked to a leadership role', async () => {
  m.listRoles.mockResolvedValue([{ id: 4, company: 'Chess Club', title: '', start_date: '', end_date: '', kind: 'leadership' }])
  m.listStories.mockResolvedValue([])
  m.createStory.mockResolvedValue({ id: 6, role_id: 4, text: 'Grew the club' })
  const user = userEvent.setup()
  render(<Stories />)

  await user.click(screen.getByText('Add story'))
  await user.selectOptions(screen.getByLabelText('Role'), await screen.findByText('Chess Club'))
  await user.type(screen.getByLabelText('Story'), 'Grew the club')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createStory).toHaveBeenCalledWith({ role_id: 4, text: 'Grew the club' }))
})
