import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, beforeEach, expect, test, vi } from 'vitest'
import * as api from './api'
import App from './App'

vi.mock('./api')
const m = vi.mocked(api)

beforeEach(() => {
  vi.resetAllMocks()
  localStorage.clear()
  m.listRoles.mockResolvedValue([])
  m.listBullets.mockResolvedValue([])
  m.listStories.mockResolvedValue([])
})

afterEach(() => vi.restoreAllMocks())

const sidebarToggle = () => screen.getByRole('button', { name: 'Sidebar' })

test('nav switches between Experience and Stories', async () => {
  const user = userEvent.setup()
  render(<App />)

  expect(screen.getByRole('heading', { name: 'Experience' })).toBeInTheDocument()
  await user.click(screen.getByRole('button', { name: 'Stories' }))
  expect(screen.getByRole('heading', { name: 'Stories' })).toBeInTheDocument()
  expect(screen.getByRole('button', { name: 'Stories' })).toHaveAttribute('aria-current', 'page')
  expect(screen.getByRole('button', { name: 'Experience' })).not.toHaveAttribute('aria-current')
})

test('Editor and Tracker cannot be opened yet', async () => {
  const user = userEvent.setup()
  render(<App />)

  for (const name of ['Editor', 'Tracker']) {
    const item = screen.getByRole('button', { name })
    expect(item).toBeDisabled()
    await user.click(item)
    expect(item).not.toHaveAttribute('aria-current')
  }
  expect(screen.getByRole('heading', { name: 'Experience' })).toBeInTheDocument()
})

test('collapsed sidebar is remembered after a remount', async () => {
  const user = userEvent.setup()
  const { unmount } = render(<App />)

  expect(sidebarToggle()).toHaveAttribute('aria-expanded', 'true')
  await user.click(sidebarToggle())
  expect(sidebarToggle()).toHaveAttribute('aria-expanded', 'false')
  unmount()

  render(<App />)
  expect(sidebarToggle()).toHaveAttribute('aria-expanded', 'false')
  expect(screen.getByRole('button', { name: 'Stories' })).toBeInTheDocument()
})

test('sidebar still works when storage is blocked', async () => {
  vi.spyOn(Storage.prototype, 'getItem').mockImplementation(() => { throw new Error('blocked') })
  vi.spyOn(Storage.prototype, 'setItem').mockImplementation(() => { throw new Error('blocked') })
  const user = userEvent.setup()
  render(<App />)

  await user.click(sidebarToggle())
  expect(sidebarToggle()).toHaveAttribute('aria-expanded', 'false')
})
