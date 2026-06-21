import { Suspense } from 'react'
import React from 'react'
import ReactDOM from 'react-dom/client'
import { App } from './App'

const fontLink = document.createElement('link')
fontLink.rel = 'stylesheet'
fontLink.href = 'https://chinese-fonts-cdn.deno.dev/packages/lxgwwenkai/dist/LXGWWenKaiTC/result.css'
document.head.appendChild(fontLink)

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <Suspense fallback={null}>
      <App />
    </Suspense>
  </React.StrictMode>,
)
