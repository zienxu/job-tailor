import { render, screen, waitFor, within } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import Tracker from './pages/Tracker'

vi.mock('./api')
const m = vi.mocked(api)

const job = (patch: Partial<api.Job> = {}): api.Job => ({
  id: 1, text: 'Need Python', company: 'Acme', title: 'SWE', link: '', status: 'saved', applied_at: '', notes: '',
  version_id: null, versions: [{ id: 7, created_at: '2026-10-20 10:00:00' }, { id: 9, created_at: '2026-10-21 10:00:00' }],
  ...patch,
})

beforeEach(() => vi.resetAllMocks())

test('list shows status and the version sent', async () => {
  m.listJobs.mockResolvedValue([job({ status: 'applied', version_id: 7, applied_at: '2026-10-20' })])
  render(<Tracker />)

  expect(await screen.findByDisplayValue('Acme')).toBeInTheDocument()
  expect(screen.getByLabelText('Status')).toHaveValue('applied')
  expect(screen.getByLabelText('Version sent')).toHaveDisplayValue('v1') // visible in the row, no expand needed
  expect(screen.queryByText('sent')).not.toBeInTheDocument()

  await userEvent.setup().click(screen.getByRole('button', { name: 'Details for Acme' }))
  const sent = screen.getByText('sent').closest('li')!
  expect(within(sent).getByText(/^v1 ·/)).toBeInTheDocument()
})

test('marking applied sends the latest version and today', async () => {
  m.listJobs.mockResolvedValue([job()])
  m.updateJob.mockImplementation(async (id, j) => ({ ...job(), ...j, id }))
  const user = userEvent.setup()
  render(<Tracker />)

  await user.selectOptions(await screen.findByLabelText('Status'), 'applied')
  await user.click(screen.getByText('Save'))

  await waitFor(() => expect(m.updateJob).toHaveBeenCalledWith(1, expect.objectContaining({
    status: 'applied', version_id: 9, applied_at: new Date().toLocaleDateString('en-CA'),
  })))
})

test('delete removes the job after confirm', async () => {
  m.listJobs.mockResolvedValue([job()])
  m.deleteJob.mockResolvedValue()
  vi.spyOn(window, 'confirm').mockReturnValue(true)
  const user = userEvent.setup()
  render(<Tracker />)

  await user.click(await screen.findByText('Delete'))
  await waitFor(() => expect(m.deleteJob).toHaveBeenCalledWith(1))
  expect(screen.queryByDisplayValue('Acme')).not.toBeInTheDocument()
})

test('the row of the latest save is marked with its job number', async () => {
  m.listJobs.mockResolvedValue([job({ id: 5, company: '', versions: [{ id: 12, created_at: '2026-10-21 10:00:00' }] }), job()])
  render(<Tracker />)

  const row = (await screen.findByText('latest save')).closest('tr')!
  expect(within(row).getByText('2')).toBeInTheDocument() // newest-first list of 2, so this is row 2
  expect(screen.getAllByText('latest save')).toHaveLength(1)
})

test('each row shows its band, blank when ungraded, and the stored grade without a new call', async () => {
  const grade: api.Grade = { score: 3.4, band: 'Stretch', keywords: [], requirements: [
    { text: 'Python', kind: 'must', hard_gate: false, status: 'met', evidence_ids: ['bullet_1'], evidence: ['Wrote Python services'] }] }
  m.listJobs.mockResolvedValue([job({ id: 2, company: 'Graded', grade }), job({ company: 'Plain', grade: null })])
  render(<Tracker />)

  const [graded, plain] = await screen.findAllByTestId('fit')
  expect(graded).toHaveTextContent('Stretch')
  expect(plain).toHaveTextContent(/^$/)

  await userEvent.setup().click(screen.getByRole('button', { name: 'Details for Graded' }))
  expect(screen.getByText('3.4 / 5')).toBeInTheDocument()
  expect(screen.getByText('Wrote Python services')).toBeInTheDocument()
  expect(m.gradeJob).not.toHaveBeenCalled()
})
