import { Outlet, NavLink, useLocation } from 'react-router-dom'
import { MessageCircle, BookOpen, Wrench, Settings } from 'lucide-react'
import clsx from 'clsx'

const navItems = [
  { path: '/chat', icon: MessageCircle, label: '聊天' },
  { path: '/knowledge', icon: BookOpen, label: '知识库' },
  { path: '/skills', icon: Wrench, label: '技能' },
  { path: '/settings', icon: Settings, label: '设置' },
]

export default function Layout() {
  const location = useLocation()

  return (
    <div className="flex h-full">
      {/* Sidebar */}
      <aside className="w-16 md:w-56 bg-surface border-r border-border flex flex-col">
        {/* Logo */}
        <div className="h-14 flex items-center px-4 border-b border-border">
          <div className="w-8 h-8 bg-gradient-to-br from-primary to-primary-light rounded-lg flex items-center justify-center text-white font-bold">
            H
          </div>
          <span className="hidden md:block ml-3 font-semibold">Hermes</span>
        </div>

        {/* Nav */}
        <nav className="flex-1 py-2">
          {navItems.map(({ path, icon: Icon, label }) => (
            <NavLink
              key={path}
              to={path}
              className={({ isActive }) =>
                clsx(
                  'flex items-center mx-2 px-3 py-2 rounded-lg transition-colors',
                  isActive
                    ? 'bg-primary/20 text-primary'
                    : 'text-text-secondary hover:bg-surface-light hover:text-text-primary'
                )
              }
            >
              <Icon size={20} />
              <span className="hidden md:block ml-3 text-sm">{label}</span>
            </NavLink>
          ))}
        </nav>

        {/* Status */}
        <div className="p-4 border-t border-border">
          <div className="flex items-center text-xs text-text-secondary">
            <span className="w-2 h-2 bg-success rounded-full mr-2 animate-pulse" />
            在线
          </div>
        </div>
      </aside>

      {/* Main Content */}
      <main className="flex-1 flex flex-col overflow-hidden">
        <Outlet />
      </main>
    </div>
  )
}
