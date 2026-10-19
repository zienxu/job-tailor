import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import Stories from './pages/Stories'

vi.mock('./api')
const m = vi.mocked(api)

beforeEach(() => vi.resetAllMocks())

test('link a story to a role and save', async () => {
  m.listRoles.mockResolvedValue([{ id: 1, company: 'Acme', title: 'Engineer', start_date: '', end_date: '' }])
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
