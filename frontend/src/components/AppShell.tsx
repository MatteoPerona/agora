import { NavLink, Outlet, useLocation } from 'react-router-dom'

const FLOW_LINKS = [
  { to: '/start', label: '1. Compose' },
  { to: '/personas', label: '2. Select personas' },
  { to: '/simulation', label: '3. Simulation' },
]

const UTILITY_LINKS = [
  { to: '/library', label: 'Library' },
  { to: '/profile', label: 'Profile' },
]

export function AppShell() {
  const location = useLocation()

  return (
    <div className="app-shell">
      <header className="site-header">
        <div className="site-brand">
          <p className="eyebrow">Perspective Engine</p>
          <h1>Deliberation, one phase at a time.</h1>
          <p className="site-summary">
            A calmer flow for framing the decision, choosing the right panel, and watching perspectives collide in a
            dedicated simulation workspace.
          </p>
        </div>

        <div className="site-nav-block">
          <nav className="flow-nav" aria-label="Primary flow">
            {FLOW_LINKS.map((link) => {
              const active =
                link.to === '/simulation'
                  ? location.pathname.startsWith('/simulation')
                  : location.pathname === link.to
              return (
                <NavLink key={link.to} to={link.to} className={`flow-link ${active ? 'active' : ''}`}>
                  {link.label}
                </NavLink>
              )
            })}
          </nav>

          <nav className="utility-nav" aria-label="Utility navigation">
            {UTILITY_LINKS.map((link) => (
              <NavLink key={link.to} to={link.to} className="utility-link">
                {link.label}
              </NavLink>
            ))}
          </nav>
        </div>
      </header>

      <main className="route-shell">
        <Outlet />
      </main>
    </div>
  )
}

