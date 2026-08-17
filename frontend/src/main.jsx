import { StrictMode } from 'react'
import { createRoot } from 'react-dom/client'

import App from './App'
import { applyTheme } from './theme'
import './styles/global.css'
import './styles/components.css'
import './styles/dashboard.css'

const rootElement = document.getElementById('root')

if (!rootElement) {
  throw new Error('Root element not found')
}

applyTheme()

createRoot(rootElement).render(
  <StrictMode>
    <App />
  </StrictMode>,
)
