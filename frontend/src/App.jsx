import React from 'react';
import { BrowserRouter, Routes, Route, Navigate, Link, useLocation } from 'react-router-dom';
import { AuthProvider, useAuth } from './context/AuthContext';
import { LayoutDashboard, Building2, GitCompare, FolderOpen, Globe, Info, Newspaper } from 'lucide-react';
import logo from './assets/logo.png';
import Auth from './pages/Auth';
import Dashboard from './pages/Dashboard';
import Company from './pages/Company';
import Compare from './pages/Compare';
import DocumentsHub from './pages/DocumentsHub';
import BseScreener from './pages/BseScreener';
import CompanyOverview from './pages/CompanyOverview';
import ResearchAssistant from './pages/ResearchAssistant';
import AboutUs from './pages/AboutUs';
import NewsPage from './pages/NewsPage';

function PrivateRoute({ children }) {
  const { token } = useAuth();
  return token ? children : <Navigate to="/login" />;
}

function Sidebar() {
  const location = useLocation();
  const { logout, user, token } = useAuth();
  const [watchlist, setWatchlist] = React.useState([]);

  React.useEffect(() => {
    if (token) {
      fetch('http://localhost:8000/workspace/watchlist', {
        headers: { Authorization: `Bearer ${token}` }
      })
      .then(res => res.json())
      .then(data => {
         if (Array.isArray(data)) setWatchlist(data);
      })
      .catch(console.error);
    }
  }, [token, location.pathname]);

  return (
    <div className="sidebar">
      <div style={{ display: 'flex', alignItems: 'center', marginBottom: '15px', padding: '0px 0px' }}>
        <img src={logo} alt="EQUITYLENS Logo" style={{ width: '165px', height: 'auto', objectFit: 'contain' }} />
      </div>
      <h3>Menu</h3>
      <Link to="/" className={`nav-link ${location.pathname === '/' ? 'active' : ''}`}>
        <LayoutDashboard size={18} /> Dashboard
      </Link>
      <Link to="/overview" className={`nav-link ${location.pathname === '/overview' ? 'active' : ''}`}>
        <Building2 size={18} /> Company Overview
      </Link>
      <Link to="/documents" className={`nav-link ${location.pathname === '/documents' ? 'active' : ''}`}>
        <FolderOpen size={18} /> Documents
      </Link>
      <Link to="/bse" className={`nav-link ${location.pathname === '/bse' ? 'active' : ''}`}>
        <Globe size={18} /> BSE India
      </Link>
      <Link to="/compare" className={`nav-link ${location.pathname === '/compare' ? 'active' : ''}`}>
        <GitCompare size={18} /> Compare
      </Link>
      <Link to="/news" className={`nav-link ${location.pathname === '/news' ? 'active' : ''}`}>
        <Newspaper size={18} /> News
      </Link>
      <Link to="/about" className={`nav-link ${location.pathname === '/about' ? 'active' : ''}`}>
        <Info size={18} /> About Us
      </Link>
      
      {watchlist.length > 0 && <h3 style={{ marginTop: '20px' }}>Workspaces</h3>}
      {watchlist.map(item => (
        <Link key={item.ticker} to={`/company/${item.ticker}`} className={`nav-link ${location.pathname === `/company/${item.ticker}` ? 'active' : ''}`}>
          <Building2 size={18} /> {item.ticker}
        </Link>
      ))}
      
      <div style={{ 
        marginTop: 'auto', 
        position: 'sticky', 
        bottom: '-20px', 
        background: 'rgba(15, 23, 42, 0.95)',
        backdropFilter: 'blur(10px)',
        margin: 'auto -20px -20px -20px', 
        padding: '15px 20px 20px 20px',
        borderTop: '1px solid var(--border)',
        zIndex: 10
      }}>
        {user && (
          <div>
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
      <div className="main-content" style={{ display: 'flex', flexDirection: 'column' }}>
        <div style={{ flex: 1 }}>
          {children}
        </div>
        <footer style={{ 
          marginTop: '40px', 
          padding: '0px', 
          textAlign: 'center', 
          fontSize: '0.8rem', 
          color: 'var(--text-secondary)', 
          borderTop: '1px solid var(--border)' 
        }}>
          ⚠️ EQITYLENS provides AI-generated financial research for educational and informational purposes only. Not investment advice.
        </footer>
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
          <Route path="/overview" element={<PrivateRoute><CompanyOverview /></PrivateRoute>} />
          <Route path="/documents" element={<PrivateRoute><DocumentsHub /></PrivateRoute>} />
          <Route path="/bse" element={<PrivateRoute><BseScreener /></PrivateRoute>} />
          <Route path="/company/:ticker" element={<PrivateRoute><Company /></PrivateRoute>} />
          <Route path="/company/:ticker/chat" element={<PrivateRoute><ResearchAssistant /></PrivateRoute>} />
          <Route path="/compare" element={<PrivateRoute><Compare /></PrivateRoute>} />
          <Route path="/news" element={<PrivateRoute><NewsPage /></PrivateRoute>} />
          <Route path="/about" element={<PrivateRoute><AboutUs /></PrivateRoute>} />
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
