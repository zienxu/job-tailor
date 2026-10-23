import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import Skills from './pages/Skills'

vi.mock('./api')
const m = vi.mocked(api)

beforeEach(() => vi.resetAllMocks())

test('add a skill with an alias, default and demote flags, and save', async () => {
  m.listSkills.mockResolvedValue([])
  m.createSkill.mockResolvedValue({ id: 1, name: 'SQL', grp: 'Technical', aliases: 'Postgres', is_default: true, demote: true })
  const user = userEvent.setup()
  render(<Skills />)

  await user.click(await screen.findByText('Add skill'))
  await user.type(screen.getByLabelText('Name'), 'SQL')
  await user.type(screen.getByLabelText('Also matches (comma separated)'), 'Postgres')
  await user.click(screen.getByLabelText('Default'))
  await user.click(screen.getByLabelText('Not in the first five unless the job requires it'))
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createSkill).toHaveBeenCalledWith({ name: 'SQL', grp: 'Technical', aliases: 'Postgres', is_default: true, demote: true }))
  expect(screen.getByText('Edit')).toBeInTheDocument()
})

test('a skill needs a name', async () => {
  m.listSkills.mockResolvedValue([])
  const user = userEvent.setup()
  render(<Skills />)

  await user.click(await screen.findByText('Add skill'))
  await user.click(screen.getByText('Save'))

  expect(await screen.findByRole('alert')).toHaveTextContent('Name is required')
  expect(m.createSkill).not.toHaveBeenCalled()
})

test('up/down swaps a skill with its neighbour', async () => {
  const s = (id: number, name: string) => ({ id, name, grp: 'Technical' as const, aliases: '', is_default: false, demote: false })
  m.listSkills.mockResolvedValue([s(1, 'Python'), s(2, 'Flask')])
  const user = userEvent.setup()
  render(<Skills />)

  await screen.findByDisplayValue('Flask')
  await user.click(screen.getAllByLabelText('Move up')[1])

  await waitFor(() => expect(m.swapSkills).toHaveBeenCalledWith(2, 1))
  await waitFor(() => expect(screen.getAllByLabelText('Name').map((e) => (e as HTMLInputElement).value)).toEqual(['Flask', 'Python']))
})

test('edit a saved skill, then delete one', async () => {
  const s = (id: number, name: string) => ({ id, name, grp: 'Technical' as const, aliases: '', is_default: false, demote: false })
  m.listSkills.mockResolvedValue([s(1, 'Python'), s(2, 'Flask')])
  m.updateSkill.mockResolvedValue({ ...s(1, 'Python'), aliases: 'py' })
  m.deleteSkill.mockResolvedValue(undefined)
  const user = userEvent.setup()
  render(<Skills />)

  await screen.findByDisplayValue('Flask')
  expect(screen.getAllByText('Delete')[0]).toBeDisabled() // read-only until Edit
  await user.click(screen.getAllByText('Edit')[0])
  await user.type(screen.getAllByLabelText('Also matches (comma separated)')[0], 'py')
  await user.selectOptions(screen.getAllByLabelText('Group')[0], 'AI')
  await user.click(screen.getAllByText('Save')[0])
  await waitFor(() => expect(m.updateSkill).toHaveBeenCalledWith(1, { name: 'Python', grp: 'AI', aliases: 'py', is_default: false, demote: false }))

  await user.click(screen.getAllByText('Edit')[1])
  await user.click(screen.getAllByText('Delete')[1])
  await waitFor(() => expect(m.deleteSkill).toHaveBeenCalledWith(2))
  expect(screen.queryByDisplayValue('Flask')).not.toBeInTheDocument()
})
