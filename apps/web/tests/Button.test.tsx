import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { Button } from '@/components/ui/Button'

describe('Button', () => {
  it('renders the label and handles keyboard activation', async () => {
    const onClick = vi.fn()
    render(<Button onClick={onClick}>Save note</Button>)
    const button = screen.getByRole('button', { name: 'Save note' })
    button.focus()
    await userEvent.keyboard('{Enter}')
    expect(onClick).toHaveBeenCalledTimes(1)
  })

  it('swaps the label while loading and blocks clicks', () => {
    render(<Button loading>Save note</Button>)
    const button = screen.getByRole('button')
    expect(button).toHaveTextContent('Saving...')
    expect(button).toBeDisabled()
  })

  it('never uses a rounded class', () => {
    render(<Button variant="primary">Go</Button>)
    expect(screen.getByRole('button').className).not.toMatch(/rounded/)
  })
})
