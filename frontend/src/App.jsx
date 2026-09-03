import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LayoutDashboard, Building2, GitCompare } from 'lucide-react';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import Company from './pages/Company';
import Compare from './pages/Compare';

function PrivateRoute({ children }) {
  const { user } = useAuth();
  return user ? children : <Navigate to="/login" />;
}

function Sidebar() {
  const location = useLocation();
  const { logout, user } = useAuth();

  return (
    <div className="sidebar">
      <h2>Research Agent</h2>
      <h3>Menu</h3>
      <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
        <LayoutDashboard size={18} /> Dashboard
      </Link>
      <Link to="/company/AAPL" className={`nav-link ${location.pathname.startsWith('/company') ? 'active' : ''}`}>
        <Building2 size={18} /> Workspace
      </Link>
      <Link to="/compare" className={`nav-link ${location.pathname === '/compare' ? 'active' : ''}`}>
        <GitCompare size={18} /> Compare
      </Link>
      
      <div style={{ marginTop: 'auto' }}>
        {user && (
          <div style={{ padding: '15px 0' }}>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '10px' }}>Logged in as <b>{user.username}</b></p>
            <button onClick={logout} className="btn-primary" style={{ width: '100%', background: 'transparent', border: '1px solid var(--border)' }}>
              Logout
            </button>
          </div>
        )}
      </div>
    </div>
  );
}

function AppLayout({ children }) {
  const { user } = useAuth();
  if (!user) return children;
  
  return (
    <div className="app-layout">
      <Sidebar />
      <div className="main-content">
        {children}
      </div>
    </div>
  );
}

function AppRoutes() {
  return (
    <BrowserRouter>
      <AppLayout>
        <Routes>
          <Route path="/login" element={<Auth />} />
          <Route path="/" element={<PrivateRoute><Dashboard /></PrivateRoute>} />
          <Route path="/company/:ticker" element={<PrivateRoute><Company /></PrivateRoute>} />
          <Route path="/compare" element={<PrivateRoute><Compare /></PrivateRoute>} />
        </Routes>
      </AppLayout>
    </BrowserRouter>
  );
}

function App() {
  return (
    <AuthProvider>
      <AppRoutes />
    </AuthProvider>
  );
}

export default App;
