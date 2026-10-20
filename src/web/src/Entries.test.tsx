import { render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import Entries from './pages/Entries'

vi.mock('./api')
const m = vi.mocked(api)

beforeEach(() => vi.resetAllMocks())

test.each([
  ['leadership', 'Add leadership', 'President, Chess Club', 'Ran weekly sessions'],
  ['skills', 'Add skill group', 'Languages', 'Python, TypeScript'],
] as const)('add a %s entry and save', async (section, add, label, text) => {
  m.listEntries.mockResolvedValue([])
  m.createEntry.mockResolvedValue({ id: 1, section, label, text })
  const user = userEvent.setup()
  render(<Entries section={section} />)

  await user.click(screen.getByText(add))
  await user.type(screen.getByLabelText('Label'), label)
  await user.type(screen.getByLabelText('Text'), text)
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.createEntry).toHaveBeenCalledWith({ section, label, text }))
  expect(screen.getByText('Edit')).toBeInTheDocument()
  expect(screen.getByText('Save')).toBeDisabled()
})

test('only entries of this section are listed', async () => {
  m.listEntries.mockResolvedValue([
    { id: 1, section: 'skills', label: 'Languages', text: 'Python' },
    { id: 2, section: 'leadership', label: 'President', text: 'Ran the club' },
  ])
  render(<Entries section="skills" />)

  expect(await screen.findByDisplayValue('Languages')).toBeInTheDocument()
  expect(screen.queryByDisplayValue('President')).not.toBeInTheDocument()
})

test('an entry needs a label and text', async () => {
  m.listEntries.mockResolvedValue([])
  const user = userEvent.setup()
  render(<Entries section="skills" />)

  await user.click(screen.getByText('Add skill group'))
  await user.type(screen.getByLabelText('Label'), 'Languages')
  await user.click(screen.getByText('Save'))

  expect(await screen.findByRole('alert')).toHaveTextContent('Label and text are required')
  expect(m.createEntry).not.toHaveBeenCalled()
})

test('up/down on a skills entry swaps it with its neighbour', async () => {
  m.listEntries.mockResolvedValue([
    { id: 1, section: 'skills', label: 'Languages', text: 'Python' },
    { id: 2, section: 'skills', label: 'Tools', text: 'Git' },
  ])
  const user = userEvent.setup()
  render(<Entries section="skills" />)

  await screen.findByDisplayValue('Tools')
  expect(screen.getAllByLabelText('Move down')[1]).toBeDisabled()
  await user.click(screen.getAllByLabelText('Move up')[1])

  await waitFor(() => expect(m.swapEntries).toHaveBeenCalledWith(2, 1))
  await waitFor(() => expect(screen.getAllByLabelText('Label').map((e) => (e as HTMLInputElement).value)).toEqual(['Tools', 'Languages']))
})
