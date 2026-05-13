import { Outlet } from 'react-router-dom';
import { Sidebar } from './Sidebar';
import { MatrixBackground } from './effects/MatrixBackground';

export function Layout() {
  return (
    <div className="layout">
      <MatrixBackground />
      <div className="circuit-bg" />
      <Sidebar />
      <main className="main-content">
        <Outlet />
      </main>
    </div>
  );
}
