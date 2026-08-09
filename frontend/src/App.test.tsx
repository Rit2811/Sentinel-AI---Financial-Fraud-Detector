import { render, screen } from '@testing-library/react'
import { expect, test } from 'vitest'

import App from './App'

test('renders the neutral operational shell', () => {
  render(<App />)

  expect(
    screen.getByRole('heading', { name: 'Sentinel AI' }),
  ).toBeInTheDocument()
  expect(screen.getByText('Infrastructure proof only')).toBeInTheDocument()
  expect(screen.getByText('Not implemented')).toBeInTheDocument()
})
