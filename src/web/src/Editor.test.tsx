import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import Editor from './pages/Editor'

vi.mock('./api')
const m = vi.mocked(api)

const emptyCritique = { unmet_must_haves: [], weak_bullets: [], missing_keywords: [], overstated_claims: [] }

beforeEach(() => {
  vi.resetAllMocks()
  m.listRoles.mockResolvedValue([
    { id: 1, company: 'Acme', title: 'Engineer', start_date: '2020', end_date: '2023', kind: 'experience' as const },
    { id: 2, company: 'Tailor App', title: 'Course Project, NUS', start_date: '2024', end_date: '', kind: 'project' as const },
    { id: 3, company: 'NUS', title: 'BComp', start_date: '', end_date: '2025', kind: 'education' as const },
  ])
  m.listBullets.mockResolvedValue([{ id: 9, role_id: 3, text: 'GPA 4.5', position: 9 }])
  m.listEntries.mockResolvedValue([
    { id: 1, section: 'leadership', label: 'Chess Club', text: 'Led 20 members' },
    { id: 2, section: 'skills', label: 'Languages', text: 'Python' },
  ])
  m.latestVersion.mockResolvedValue(null)
  m.createJob.mockResolvedValue({ id: 5, text: 'job', company: '', title: '', link: '' })
  m.tailor.mockResolvedValue({ bullets: [
    { text: 'Cut build time by 40%', source_id: 'bullet_1', role_id: 'role_1', flags: [] },
    { text: 'Led 9 teams', source_id: 'bullet_2', role_id: 'role_1', flags: ['unsupported_fact'] },
    { text: 'Invented claim', source_id: null, role_id: null, flags: ['missing_citation'] },
  ] })
  m.critique.mockResolvedValue(emptyCritique)
  m.preview.mockResolvedValue('<p>preview</p>')
  // Stand-in for the backend: "kubernetes" is the one missing keyword, and "9" contradicts the source.
  m.check.mockImplementation(async (_id, text, bullets) => ({
    ats: { label: 'local estimate', score: text.includes('kubernetes') ? 100 : 50, matched: [], missing: [] },
    flags: bullets.map((b) => (!b.source_id ? ['missing_citation'] : b.text.includes('9') ? ['unsupported_fact'] : [])),
  }))
})

async function tailored() {
  const user = userEvent.setup()
  render(<Editor />)
  await user.type(screen.getByLabelText('Job text'), 'Need kubernetes')
  await user.click(screen.getByRole('button', { name: 'Tailor' }))
  await screen.findByLabelText('Bullet 1')
  return user
}

test('typing a missing keyword raises the score', async () => {
  const user = await tailored()
  await waitFor(() => expect(screen.getByTestId('ats-score')).toHaveTextContent('50%'))
  expect(screen.getByText(/local estimate/)).toBeInTheDocument()

  await user.type(screen.getByLabelText('Bullet 1'), ' on kubernetes')

  await waitFor(() => expect(screen.getByTestId('ats-score')).toHaveTextContent('100%'))
})

test('missing citation and contradicts source flags look different', async () => {
  await tailored()
  const contradicts = screen.getByText('Contradicts source')
  const missing = screen.getByText('Missing citation')
  expect(contradicts).toHaveAttribute('data-flag', 'contradicts')
  expect(missing).toHaveAttribute('data-flag', 'missing')
  expect(contradicts.className).toContain('text-danger')
  expect(missing.className).toContain('text-warn')
  expect(contradicts.className).not.toContain('text-warn')
})

test('fixing a bullet clears its flag', async () => {
  const user = await tailored()
  await user.clear(screen.getByLabelText('Bullet 2'))
  await user.type(screen.getByLabelText('Bullet 2'), 'Led 2 teams')
  await waitFor(() => expect(screen.queryByText('Contradicts source')).not.toBeInTheDocument())
})

test('re-run calls the critic again', async () => {
  const user = await tailored()
  await waitFor(() => expect(m.critique).toHaveBeenCalledTimes(1))
  await user.click(screen.getByRole('button', { name: /Re-run critic/ }))
  await waitFor(() => expect(m.critique).toHaveBeenCalledTimes(2))
})

test('download is blocked until flags are resolved and the draft is reviewed', async () => {
  m.saveVersion.mockResolvedValue({} as api.Version)
  m.pdf.mockResolvedValue(new Blob(['%PDF']))
  URL.createObjectURL = vi.fn(() => 'blob:x')
  URL.revokeObjectURL = vi.fn()
  const user = await tailored()
  const download = screen.getByRole('button', { name: /Download PDF/ })

  await user.click(screen.getByLabelText("I've reviewed this draft"))
  expect(download).toBeDisabled()

  await user.click(screen.getByLabelText('Remove bullet 3'))
  await user.click(screen.getByLabelText('Keep anyway'))
  expect(download).toBeDisabled() // removing a bullet changed the draft, so review again
  await user.click(screen.getByLabelText("I've reviewed this draft"))
  await waitFor(() => expect(download).toBeEnabled()) // once the re-check of the edited draft returns

  await user.click(download)
  await waitFor(() => expect(m.pdf).toHaveBeenCalled())
  expect(m.saveVersion).toHaveBeenCalledWith(5, expect.objectContaining({ bullets: expect.any(Array) }))
  expect(m.pdf.mock.calls[0][0].experience[0].bullets).toEqual(['Cut build time by 40%', 'Led 9 teams'])
})

test('download waits for the fact check of the latest edit', async () => {
  let release = () => {}
  const user = await tailored()
  await user.click(screen.getByLabelText('Remove bullet 3'))
  await user.click(screen.getByLabelText('Keep anyway'))
  await waitFor(() => expect(screen.getByText('No unresolved flags.')).toBeInTheDocument())

  const realCheck = m.check.getMockImplementation()!
  m.check.mockImplementation((...args) => new Promise((ok) => { release = () => ok(realCheck(...args)) }))
  await user.type(screen.getByLabelText('Bullet 1'), ' by 9x')
  await user.click(screen.getByLabelText("I've reviewed this draft"))
  const download = screen.getByRole('button', { name: /Download PDF/ })
  expect(download).toBeDisabled()

  await waitFor(() => { release(); expect(screen.getAllByText('Contradicts source')).toHaveLength(2) })
  expect(download).toBeDisabled() // the late check found a new flag, so the gate still holds
})

test('Open full size shows the preview in a dialog', async () => {
  HTMLDialogElement.prototype.showModal = vi.fn(function (this: HTMLDialogElement) { this.open = true }) // jsdom lacks it
  const user = await tailored()
  await user.click(await screen.findByRole('button', { name: /Open full size/ }))
  expect(screen.getByRole('dialog', { name: 'Full size preview' })).toBeVisible()
  expect(screen.getByTitle('Resume preview, full size')).toHaveAttribute('width', '816')
})

const lastPreview = () => m.preview.mock.calls.at(-1)![0]

test('moving a section changes the order in the preview request', async () => {
  const user = await tailored()
  await waitFor(() => expect(m.preview).toHaveBeenCalled())
  expect(lastPreview().order).toEqual(['summary', 'education', 'experience', 'leadership', 'projects', 'skills'])
  await user.click(screen.getByLabelText('Move Projects up'))
  await waitFor(() => expect(lastPreview().order).toEqual(['summary', 'education', 'experience', 'projects', 'leadership', 'skills']))
  expect(screen.getByLabelText('Move Summary up')).toBeDisabled()
})

test('copied sections are pre-filled, and unticking an entry removes it from the resume', async () => {
  const user = await tailored()
  await waitFor(() => expect(m.preview).toHaveBeenCalled())
  expect(lastPreview().education).toEqual([{ school: 'NUS', degree: 'BComp', date: '2025', details: ['GPA 4.5'] }])
  expect(lastPreview().leadership).toEqual([{ label: 'Chess Club', text: 'Led 20 members' }])

  await user.type(screen.getByLabelText('Languages text'), ', Go')
  await user.click(screen.getByLabelText('Include Chess Club'))
  await waitFor(() => expect(lastPreview().leadership).toEqual([]))
  expect(lastPreview().skills).toEqual([{ label: 'Languages', text: 'Python, Go' }])
  expect(m.updateEntry).not.toHaveBeenCalled()
  expect(m.check.mock.calls.at(-1)![1]).toContain('Python, Go') // ATS sees every included section
})

test('a flagged project bullet shows its flag under its project', async () => {
  m.tailor.mockResolvedValue({ bullets: [
    { text: 'Built 9 parsers', source_id: 'bullet_5', role_id: 'role_2', flags: ['unsupported_fact'] },
  ] })
  await tailored()
  const group = screen.getByRole('heading', { name: 'Tailor App - Course Project, NUS' }).parentElement!
  expect(within(group).getByText('Contradicts source')).toHaveAttribute('data-flag', 'contradicts')
  await waitFor(() => expect(lastPreview().projects).toEqual([
    { name: 'Tailor App', role: 'Course Project, NUS', dates: '2024', bullets: ['Built 9 parsers'] }]))
  expect(lastPreview().experience).toEqual([])
})
