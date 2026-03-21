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
          <div className="site-label-row">
            <p className="eyebrow">Perspective Engine</p>
            <span className="site-badge">Modern debate workspace</span>
          </div>
          <h1>Structured deliberation without the UI noise.</h1>
          <p className="site-summary">
            Frame the decision, assemble a panel, and track how the room moves in a cleaner three-step workspace.
          </p>
        </div>

        <div className="site-nav-block">
          <div className="nav-group">
            <p className="eyebrow">Flow</p>
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
          </div>

          <div className="nav-group nav-group-utility">
            <p className="eyebrow">Reference</p>
            <nav className="utility-nav" aria-label="Utility navigation">
              {UTILITY_LINKS.map((link) => (
                <NavLink key={link.to} to={link.to} className="utility-link">
                  {link.label}
                </NavLink>
              ))}
            </nav>
          </div>
        </div>
      </header>

      <main className="route-shell">
        <Outlet />
      </main>
    </div>
  )
}
