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
    { id: 4, company: 'Chess Club', title: 'President', start_date: '', end_date: '', kind: 'leadership' as const },
  ])
  m.listBullets.mockResolvedValue([{ id: 9, role_id: 3, text: 'GPA 4.5', position: 9 }])
  m.listEntries.mockResolvedValue([
    { id: 2, section: 'skills', label: 'Languages', text: 'Python' },
  ])
  m.latestVersion.mockResolvedValue(null)
  m.createJob.mockResolvedValue({ id: 5, text: 'job', company: '', title: '', link: '', status: 'saved', applied_at: '', notes: '', version_id: null })
  m.tailor.mockResolvedValue({ bullets: [
    { text: 'Cut build time by 40%', source_id: 'bullet_1', role_id: 'role_1', flags: [] },
    { text: 'Led 9 teams', source_id: 'bullet_2', role_id: 'role_1', flags: ['unsupported_fact'] },
    { text: 'Invented claim', source_id: null, role_id: null, flags: ['missing_citation'] },
  ] })
  m.critique.mockResolvedValue(emptyCritique)
  m.preview.mockResolvedValue({ html: '<p>preview</p>', pages: 1, shorten: [], remove: [] })
  // Stand-in for the backend: "kubernetes" is the one missing keyword, and "9" contradicts the source.
  m.check.mockImplementation(async (_id, text, bullets, roles) => ({
    ats: { label: 'local estimate', score: text.includes('kubernetes') ? 100 : 50, matched: [], missing: [] },
    role_hits: Object.fromEntries(Object.entries(roles).map(([k, t]) => [k, t.includes('kubernetes') ? 1 : 0])),
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
  const contradicts = screen.getByText('Not in your saved text')
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
  await waitFor(() => expect(screen.queryByText('Not in your saved text')).not.toBeInTheDocument())
})

test('re-run calls the critic again', async () => {
  const user = await tailored()
  await waitFor(() => expect(m.critique).toHaveBeenCalledTimes(1))
  await user.click(screen.getByRole('button', { name: /Re-run critic/ }))
  await waitFor(() => expect(m.critique).toHaveBeenCalledTimes(2))
})

test('download is blocked until flags are resolved and the draft is reviewed', async () => {
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
  expect(m.saveVersion).not.toHaveBeenCalled() // downloading never saves; only "Save in tracker" does
  expect(m.pdf.mock.calls[0][0].experience[0].bullets).toEqual(['Cut build time by 40%', 'Led 9 teams'])
})

test('"Save in tracker" uses the download gate and saves the resume payload', async () => {
  m.saveVersion.mockResolvedValue({} as api.Version)
  m.listJobs.mockResolvedValue([{ id: 5 }, { id: 2 }, { id: 1 }] as api.Job[])
  const user = await tailored()
  const save = screen.getByRole('button', { name: /Save in tracker/ })
  expect(save).toBeDisabled()

  await user.click(screen.getByLabelText('Remove bullet 3'))
  await user.click(screen.getByLabelText('Keep anyway'))
  await user.click(screen.getByLabelText("I've reviewed this draft"))
  await waitFor(() => expect(save).toBeEnabled())

  await user.click(save)
  await waitFor(() => expect(m.saveVersion).toHaveBeenCalledWith(5, expect.objectContaining({
    bullets: expect.any(Array), resume: expect.objectContaining({ experience: expect.any(Array) }),
  })))
  expect(await screen.findByText('Saved as v1 of row 3 in the tracker')).toBeInTheDocument()
  expect(m.pdf).not.toHaveBeenCalled()
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

  await waitFor(() => { release(); expect(screen.getAllByText('Not in your saved text')).toHaveLength(2) })
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

  await user.type(screen.getByLabelText('Languages text'), ', Go')
  await user.click(screen.getByLabelText('Include NUS | BComp'))
  await waitFor(() => expect(lastPreview().education).toEqual([]))
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
  expect(within(group).getByText('Not in your saved text')).toHaveAttribute('data-flag', 'contradicts')
  await waitFor(() => expect(lastPreview().projects).toEqual([
    { name: 'Tailor App', role: 'Course Project, NUS', dates: '2024', bullets: ['Built 9 parsers'] }]))
  // Acme has no bullets in this draft but keeps its header line.
  expect(lastPreview().experience).toEqual([{ company: 'Acme', title: 'Engineer', dates: '2020 - 2023', bullets: [] }])
})

test('a zero-bullet role keeps its header and fallback bullets say "Copied as saved"', async () => {
  m.tailor.mockResolvedValue({ bullets: [
    { text: 'Cut build time by 40%', source_id: 'bullet_1', role_id: 'role_1', flags: [], fallback: true },
  ] })
  await tailored()
  const acme = screen.getByRole('heading', { name: 'Acme - Engineer' }).parentElement!
  expect(within(acme).getByText('Copied as saved')).toBeInTheDocument()
  const app = screen.getByRole('heading', { name: 'Tailor App - Course Project, NUS' }).parentElement!
  expect(within(app).queryByText('Copied as saved')).toBeNull()
  // Once edited, the bullet is no longer copied as saved.
  await userEvent.setup().type(within(acme).getByLabelText('Bullet 1'), '!')
  expect(within(acme).queryByText('Copied as saved')).toBeNull()
  await waitFor(() => expect(lastPreview().projects).toEqual([
    { name: 'Tailor App', role: 'Course Project, NUS', dates: '2024', bullets: [] }]))
})

test('leadership bullets sit under their role card and reach the preview as rows', async () => {
  m.tailor.mockResolvedValue({ bullets: [
    { text: 'Led 20 members', source_id: 'bullet_7', role_id: 'role_4', flags: [], fallback: true },
  ] })
  await tailored()
  const club = screen.getByRole('heading', { name: 'Chess Club - President' }).parentElement!
  expect(within(club).getByLabelText('Bullet 1')).toHaveValue('Led 20 members')
  expect(within(club).getByText('Copied as saved')).toBeInTheDocument()
  await waitFor(() => expect(lastPreview().leadership).toEqual([
    { name: 'Chess Club', role: 'President', dates: '', bullets: ['Led 20 members'] }]))
  expect(m.check.mock.calls.at(-1)![1]).toContain('Led 20 members')
})

test('unticking a bullet removes it from the preview payload but keeps it visible', async () => {
  const user = await tailored()
  await user.click(screen.getByLabelText('Include bullet 1'))
  await waitFor(() => expect(lastPreview().experience[0].bullets).toEqual(['Led 9 teams']))
  expect(screen.getByLabelText('Bullet 1')).toHaveValue('Cut build time by 40%')
})

test('an unticked flagged bullet does not block the review gate', async () => {
  const user = await tailored()
  const download = screen.getByRole('button', { name: /Download PDF/ })
  await user.click(screen.getByLabelText('Include bullet 2'))
  await user.click(screen.getByLabelText('Include bullet 3'))
  await user.click(screen.getByLabelText("I've reviewed this draft"))
  await waitFor(() => expect(download).toBeEnabled())
})

test('only included bullets reach leadership rows and the "Copied as saved" note', async () => {
  m.tailor.mockResolvedValue({ bullets: [
    { text: 'Led 20 members', source_id: 'bullet_7', role_id: 'role_4', flags: [], fallback: true, included: true },
    { text: 'Booked venues', source_id: 'bullet_8', role_id: 'role_4', flags: [], fallback: true, included: false },
    { text: 'Cut build time by 40%', source_id: 'bullet_1', role_id: 'role_1', flags: [], fallback: true, included: false },
  ] })
  await tailored()
  expect(screen.getByLabelText('Include bullet 2')).not.toBeChecked()
  await waitFor(() => expect(lastPreview().leadership).toEqual([
    { name: 'Chess Club', role: 'President', dates: '', bullets: ['Led 20 members'] }]))
  const acme = screen.getByRole('heading', { name: 'Acme - Engineer' }).parentElement!
  expect(within(acme).queryByText('Copied as saved')).toBeNull()
})

test('over 1 page blocks download and shows shorten then remove suggestions', async () => {
  m.preview.mockResolvedValue({
    html: '<p>preview</p>', pages: 2,
    shorten: [{ section: 'experience', role: 'Acme', text: 'Cut build time by 40%', words: 1 }],
    remove: [{ section: 'leadership', role: 'Chess Club', text: 'Led 20 members' }],
  })
  const user = await tailored()
  await user.click(screen.getByLabelText('Remove bullet 3'))
  await user.click(screen.getByLabelText('Keep anyway'))
  await user.click(screen.getByLabelText("I've reviewed this draft"))
  expect(await screen.findByText(/runs to 2 pages/)).toBeInTheDocument()
  expect(screen.getByText('Acme: Cut build time by 40% (last line 1 word)')).toBeInTheDocument()
  expect(screen.getByText('Chess Club: Led 20 members')).toBeInTheDocument()
  expect(screen.getByRole('button', { name: /Download PDF/ })).toBeDisabled()
  expect(screen.getByLabelText('Bullet 1')).toHaveValue('Cut build time by 40%') // never auto-edits
})

test('each role card shows its job-term hits, leadership included', async () => {
  const user = await tailored()
  const acme = screen.getByRole('heading', { name: 'Acme - Engineer' }).parentElement!
  const club = screen.getByRole('heading', { name: 'Chess Club - President' }).parentElement!
  await waitFor(() => expect(within(acme).getByText('0 job terms')).toBeInTheDocument())
  expect(within(club).getByText('0 job terms')).toBeInTheDocument()

  await user.type(screen.getByLabelText('Bullet 1'), ' on kubernetes')
  await waitFor(() => expect(within(acme).getByText('1 job term')).toBeInTheDocument())
})

test('the readiness verdict shows and "needs_work" does not block download', async () => {
  m.critique.mockResolvedValue({ ...emptyCritique, readiness: { verdict: 'needs_work', reason: 'No kubernetes evidence' } })
  const user = await tailored()
  expect(await screen.findByText('Needs work')).toBeInTheDocument()
  expect(screen.getByText('No kubernetes evidence')).toBeInTheDocument()

  await user.click(screen.getByLabelText('Remove bullet 3'))
  await user.click(screen.getByLabelText('Keep anyway'))
  await user.click(screen.getByLabelText("I've reviewed this draft"))
  await waitFor(() => expect(screen.getByRole('button', { name: /Download PDF/ })).toBeEnabled())
})

const grade = (band: api.Grade['band'] = 'Skip', score = 2.4): api.Grade => ({
  score, band, keywords: [],
  requirements: [
    { text: 'Python', kind: 'must', hard_gate: false, status: 'met', evidence_ids: ['bullet_1'], evidence: ['Wrote Python services'] },
    { text: 'Kubernetes', kind: 'must', hard_gate: false, status: 'missing', evidence_ids: [], evidence: [] },
    { text: 'Go', kind: 'nice', hard_gate: false, status: 'missing', evidence_ids: [], evidence: [] },
  ],
})

async function gradedJob() {
  const user = userEvent.setup()
  render(<Editor />)
  await user.click(screen.getByLabelText('Job text'))
  await user.paste('Need Python and kubernetes')
  await user.click(screen.getByRole('button', { name: 'Grade fit' }))
  return user
}

test('grading a pasted job shows score, band and must-haves with evidence', async () => {
  m.gradeJob.mockResolvedValue(grade())
  await gradedJob()

  expect(await screen.findByTestId('grade-score')).toHaveTextContent('2.4 / 5')
  expect(screen.getByTestId('grade-band')).toHaveTextContent('Skip')
  const card = within(screen.getByRole('region', { name: /Fit grade/ }))
  const met = card.getByText('Python').closest('li')!
  expect(met).toHaveAttribute('data-status', 'met')
  expect(within(met).getByText('Wrote Python services')).toBeInTheDocument()
  expect(card.getByText('Kubernetes').closest('li')).toHaveAttribute('data-status', 'missing')
  expect(card.queryByText('Go')).not.toBeInTheDocument() // must-haves only
  expect(m.gradeJob).toHaveBeenCalledWith(5)
})

test('Tailor is enabled on a Skip band and reuses the graded job', async () => {
  m.gradeJob.mockResolvedValue(grade('Skip'))
  const user = await gradedJob()
  await screen.findByTestId('grade-band')

  const tailorBtn = screen.getByRole('button', { name: 'Tailor' })
  expect(tailorBtn).toBeEnabled()
  await user.click(tailorBtn)
  await screen.findByLabelText('Bullet 1')
  expect(m.createJob).toHaveBeenCalledTimes(1)
  expect(m.tailor).toHaveBeenCalledWith(5)
})

test('Re-grade calls the grade endpoint again and replaces the card', async () => {
  m.gradeJob.mockResolvedValueOnce(grade('Skip', 2.4)).mockResolvedValueOnce(grade('Apply', 4.2))
  const user = await gradedJob()
  await screen.findByText('2.4 / 5')

  await user.click(screen.getByRole('button', { name: 'Re-grade' }))
  expect(await screen.findByText('4.2 / 5')).toBeInTheDocument()
  expect(m.gradeJob).toHaveBeenCalledTimes(2)
  expect(m.gradeJob).toHaveBeenLastCalledWith(5)
  expect(m.createJob).toHaveBeenCalledTimes(1)
})

test('a grade error shows and Tailor still works', async () => {
  m.gradeJob.mockRejectedValue(new Error('POST /jobs/5/grade failed: 502'))
  const user = await gradedJob()

  expect(await screen.findByText(/Grade failed/)).toBeInTheDocument()
  const tailorBtn = screen.getByRole('button', { name: 'Tailor' })
  expect(tailorBtn).toBeEnabled()
  await user.click(tailorBtn)
  expect(await screen.findByLabelText('Bullet 1')).toBeInTheDocument()
})

test('fetching a link fills the job text and grades it', async () => {
  m.fetchJob.mockResolvedValue({ text: 'Fetched job: Python', company: 'Acme', title: 'SWE', link: 'https://boards.greenhouse.io/acme/jobs/1' })
  m.gradeJob.mockResolvedValue(grade())
  const user = userEvent.setup()
  render(<Editor />)
  await user.type(screen.getByLabelText(/Job link/), 'https://boards.greenhouse.io/acme/jobs/1')
  await user.click(screen.getByRole('button', { name: 'Fetch' }))

  expect(await screen.findByTestId('grade-band')).toHaveTextContent('Skip')
  expect(screen.getByLabelText('Job text')).toHaveValue('Fetched job: Python')
  expect(m.createJob).toHaveBeenCalledWith('Fetched job: Python', { company: 'Acme', title: 'SWE', link: 'https://boards.greenhouse.io/acme/jobs/1' })
})

test('grading after Tailor reuses the tailored job instead of making one', async () => {
  m.gradeJob.mockResolvedValue(grade())
  const user = await tailored()
  await user.click(screen.getByRole('button', { name: 'Grade fit' }))
  await screen.findByTestId('grade-band')
  expect(m.createJob).toHaveBeenCalledTimes(1)
  expect(m.gradeJob).toHaveBeenCalledWith(5)
})

test('the grade card shows the band thresholds and when a hard requirement held it at Stretch', async () => {
  m.gradeJob.mockResolvedValue({ score: 4.2, band: 'Stretch', keywords: [], requirements: [
    { text: 'Singapore Citizen or PR', kind: 'must', hard_gate: true, status: 'missing', evidence_ids: [], evidence: [] },
    { text: 'Python', kind: 'must', hard_gate: false, status: 'met', evidence_ids: ['bullet_1'], evidence: ['Wrote Python'] },
  ] })
  await gradedJob()

  expect(await screen.findByText('Apply ≥ 3.8 · Stretch 3.0–3.7 · Skip below 3.0')).toBeInTheDocument()
  expect(screen.getByTestId('grade-gated')).toHaveTextContent('Held at Stretch: a must-have is missing (Singapore Citizen or PR)')
  expect(screen.getByText('hard requirement')).toBeInTheDocument()
})

test('the grade card shows the summary and seniority fit, and old grades without them still render', async () => {
  m.gradeJob.mockResolvedValue({ ...grade('Apply', 4.1), summary: 'Strong Python match.', seniority_fit: 'over' })
  await gradedJob()
  expect(await screen.findByTestId('grade-summary')).toHaveTextContent('Strong Python match.')
  expect(screen.getByTestId('grade-seniority')).toHaveTextContent('You are more senior than the role')
})

test('an old stored Apply grade with a missing non-hard must shows no "held" note', async () => {
  m.gradeJob.mockResolvedValue({ ...grade('Apply', 4.1), requirements: [
    { text: 'Kubernetes', kind: 'must', hard_gate: false, status: 'missing', evidence_ids: [], evidence: [] }] })
  await gradedJob()
  await screen.findByTestId('grade-band')
  expect(screen.queryByTestId('grade-gated')).not.toBeInTheDocument()
  expect(screen.queryByTestId('grade-summary')).not.toBeInTheDocument()
})

test('a low score with a missing hard requirement has no "held" note', async () => {
  m.gradeJob.mockResolvedValue({ ...grade('Skip', 2.4), requirements: [
    { text: 'Singapore Citizen or PR', kind: 'must', hard_gate: true, status: 'missing', evidence_ids: [], evidence: [] }] })
  await gradedJob()
  await screen.findByTestId('grade-band')
  expect(screen.queryByTestId('grade-gated')).not.toBeInTheDocument()
})

test('eligibility facts never appear in the editor', async () => {
  m.listEntries.mockResolvedValue([
    { id: 2, section: 'skills', label: 'Languages', text: 'Python' },
    { id: 3, section: 'eligibility', label: 'Work eligibility', text: 'Singapore Citizen' },
  ])
  render(<Editor />)
  expect(await screen.findByLabelText('Languages text')).toBeInTheDocument()
  expect(screen.queryByText(/Work eligibility/)).not.toBeInTheDocument()
  expect(screen.queryByDisplayValue('Singapore Citizen')).not.toBeInTheDocument()
})
