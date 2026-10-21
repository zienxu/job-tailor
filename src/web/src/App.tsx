import { useState } from 'react'
import { Award, BookOpen, Briefcase, FolderGit2, GraduationCap, ListChecks, Wrench, PanelLeftClose, PanelLeftOpen, PenLine, type LucideIcon } from 'lucide-react'
import Editor from './pages/Editor'
import Entries from './pages/Entries'
import Experience from './pages/Experience'
import Stories from './pages/Stories'
import Tracker from './pages/Tracker'

type Page = 'experience' | 'project' | 'education' | 'leadership' | 'skills' | 'stories' | 'editor' | 'tracker'

const PAGES: [Page, string, LucideIcon, boolean][] = [
  ['experience', 'Experience', Briefcase, true],
  ['project', 'Projects', FolderGit2, true],
  ['education', 'Education', GraduationCap, true],
  ['leadership', 'Leadership', Award, true],
  ['skills', 'Skills', Wrench, true],
  ['stories', 'Stories', BookOpen, true],
  ['editor', 'Editor', PenLine, true],
  ['tracker', 'Tracker', ListChecks, true],
]

const KEY = 'sidebar-collapsed'

function readCollapsed() {
  try {
    return localStorage.getItem(KEY) === '1'
  } catch {
    return false
  }
}

export default function App() {
  const [page, setPage] = useState<Page>('experience')
  const [collapsed, setCollapsed] = useState(readCollapsed)

  function toggle() {
    setCollapsed(!collapsed)
    try {
      localStorage.setItem(KEY, collapsed ? '0' : '1')
    } catch {
      // Private mode or blocked storage: the sidebar just won't remember.
    }
  }

  const ToggleIcon = collapsed ? PanelLeftOpen : PanelLeftClose

  return (
    <div className="flex min-h-screen font-sans">
      <nav
        aria-label="Pages"
        className={`sticky top-0 flex h-screen shrink-0 flex-col border-r border-line bg-surface px-2 py-5 transition-[width] duration-200 motion-reduce:transition-none ${collapsed ? 'w-14' : 'w-14 sm:w-56'}`}
      >
        <p className="mb-6 truncate px-2.5 font-serif text-lg font-semibold" aria-hidden>
          <span className={collapsed ? '' : 'sm:hidden'}>jt</span>
          {!collapsed && <span className="hidden sm:inline">job-tailor</span>}
        </p>
        <ul id="nav-pages" className="flex flex-col gap-1">
          {PAGES.map(([id, label, Icon, ready]) => (
            <li key={id}>
              <button
                type="button"
                disabled={!ready}
                onClick={() => setPage(id)}
                aria-current={page === id ? 'page' : undefined}
                title={label}
                className="flex w-full items-center gap-3 rounded-md px-2.5 py-2 text-sm font-medium text-muted transition-colors hover:bg-paper hover:text-ink disabled:cursor-not-allowed disabled:opacity-50 disabled:hover:bg-transparent disabled:hover:text-muted aria-[current=page]:bg-accent/10 aria-[current=page]:text-accent motion-reduce:transition-none"
              >
                <Icon aria-hidden size={18} className="shrink-0" />
                <span className={collapsed ? 'sr-only' : 'sr-only sm:not-sr-only sm:truncate'}>{label}</span>
                {!ready && !collapsed && <span aria-hidden className="ml-auto hidden text-xs font-normal sm:inline">Soon</span>}
              </button>
            </li>
          ))}
        </ul>
        <button
          type="button"
          onClick={toggle}
          aria-expanded={!collapsed}
          aria-controls="nav-pages"
          aria-label="Sidebar"
          title={collapsed ? 'Expand sidebar' : 'Collapse sidebar'}
          className="mt-auto hidden items-center rounded-md sm:flex px-2.5 py-2 text-muted hover:bg-paper hover:text-ink"
        >
          <ToggleIcon aria-hidden size={18} />
        </button>
      </nav>
      <main className="min-w-0 flex-1 px-5 py-8 sm:px-10 sm:py-12">
        {page === 'stories' ? <Stories />
          : page === 'editor' ? <Editor />
          : page === 'tracker' ? <Tracker />
          : page === 'skills' ? <Entries section={page} />
          : page === 'project' || page === 'education' || page === 'leadership' ? <Experience key={page} kind={page} />
          : <Experience />}
      </main>
    </div>
  )
}
