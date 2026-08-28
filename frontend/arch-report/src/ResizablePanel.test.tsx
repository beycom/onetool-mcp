// @vitest-environment jsdom

import { cleanup, fireEvent, render, screen } from '@testing-library/react'
import { afterEach, expect, test, vi } from 'vitest'

import { ResizablePanel } from './ResizablePanel'

afterEach(cleanup)

test('a collapsed dock uses an accessible icon rail and reopens from it', () => {
  const onChange = vi.fn()
  render(<ResizablePanel className="view-dock" label="View" layout={{ collapsed: true, size: 280 }} name="view" onChange={onChange}><p>Content</p></ResizablePanel>)

  const reopen = screen.getByRole('button', { name: 'Open View dock' })
  expect(reopen.textContent).toBe('')
  expect(screen.queryByText('Open View dock')).toBeNull()
  fireEvent.click(reopen)
  expect(onChange).toHaveBeenCalledWith({ collapsed: false, size: 280 })
})
