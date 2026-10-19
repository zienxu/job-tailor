import { useState } from 'react'
import Experience from './pages/Experience'
import Stories from './pages/Stories'

export default function App() {
  const [tab, setTab] = useState<'experience' | 'stories'>('experience')
  return (
    <main>
      <nav>
        <button onClick={() => setTab('experience')} aria-pressed={tab === 'experience'}>Experience</button>
        <button onClick={() => setTab('stories')} aria-pressed={tab === 'stories'}>Stories</button>
      </nav>
      {tab === 'experience' ? <Experience /> : <Stories />}
    </main>
  )
}
