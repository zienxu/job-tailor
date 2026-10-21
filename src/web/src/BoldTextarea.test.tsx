import { useState } from 'react'
import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { expect, test } from 'vitest'
import BoldTextarea from './components/BoldTextarea'

function Box({ readOnly = false }: { readOnly?: boolean }) {
  const [v, setV] = useState('hello world')
  return <label>Note<BoldTextarea readOnly={readOnly} value={v} onChange={(e) => setV(e.target.value)} /></label>
}

const select = (el: HTMLElement, a: number, b: number) => (el as HTMLTextAreaElement).setSelectionRange(a, b)

test('Ctrl+B wraps the selection', async () => {
  const user = userEvent.setup()
  render(<Box />)
  const ta = screen.getByLabelText('Note')
  ta.focus(); select(ta, 0, 5)
  await user.keyboard('{Control>}b{/Control}')
  expect(ta).toHaveValue('**hello** world')
})

test('the B button wraps the selection', async () => {
  const user = userEvent.setup()
  render(<Box />)
  const ta = screen.getByLabelText('Note')
  select(ta, 6, 11)
  await user.click(screen.getByRole('button', { name: 'Bold' }))
  expect(ta).toHaveValue('hello **world**')
})

test('read-only text cannot be bolded', async () => {
  const user = userEvent.setup()
  render(<Box readOnly />)
  expect(screen.getByRole('button', { name: 'Bold' })).toBeDisabled()
  const ta = screen.getByLabelText('Note')
  ta.focus(); select(ta, 0, 5)
  await user.keyboard('{Control>}b{/Control}')
  expect(ta).toHaveValue('hello world')
})

test('an empty selection inserts nothing', async () => {
  const user = userEvent.setup()
  render(<Box />)
  const ta = screen.getByLabelText('Note')
  ta.focus(); select(ta, 3, 3)
  await user.keyboard('{Control>}b{/Control}')
  expect(ta).toHaveValue('hello world')
})
