import React, { useState } from 'react';
import { useAuth } from '../context/AuthContext';
import { useNavigate } from 'react-router-dom';
import { CheckSquare, Square } from 'lucide-react';
import logo from '../assets/logo.png';

export default function Auth() {
  const [isLogin, setIsLogin] = useState(true);
  const [username, setUsername] = useState('');
  const [password, setPassword] = useState('');
  const [error, setError] = useState('');
  const [rememberMe, setRememberMe] = useState(false);
  const { login, register, token } = useAuth();
  const navigate = useNavigate();

  React.useEffect(() => {
    if (token) {
      navigate('/');
    }
  }, [token, navigate]);

  const handleSubmit = async (e) => {
    e.preventDefault();
    setError('');
    
    if (isLogin) {
      const success = await login(username, password);
      if (success) navigate('/');
      else setError('Invalid credentials');
    } else {
      const success = await register(username, password);
      if (success) {
        await login(username, password);
        navigate('/');
      } else {
        setError('Registration failed. Username might exist.');
      }
    }
  };

  return (
    <div className="auth-page-wrapper">
      {/* Decorative floating shapes in background */}
      <div className="shape shape-1"></div>
      <div className="shape shape-2"></div>
      <div className="shape shape-3"></div>
      <div className="shape shape-4"></div>

      <div className={`split-auth-card ${isLogin ? '' : 'is-register'}`}>
        
        {/* LEFT PANE - Form */}
        <div className="auth-left">
          <div className="auth-form-container">
            <div className="auth-header">
              <div style={{ marginBottom: '15px', transform: 'translateX(-10px)' }}>
                <img src={logo} alt="EQUITYLENS Logo" style={{ height: '60px', objectFit: 'contain' }} />
              </div>
              <h2 className="auth-title">{isLogin ? 'LOGIN' : 'REGISTER'}</h2>
            </div>
            
            {error && <div className="error-message">{error}</div>}
            
            <form onSubmit={handleSubmit} className="auth-form">
              <div className="input-group">
                <input 
                  type="text" 
                  placeholder="Username / Email Address" 
                  value={username}
                  onChange={(e) => setUsername(e.target.value)}
                  required
                />
              </div>
              
              <div className="input-group">
                <input 
                  type="password" 
                  placeholder="Password" 
                  value={password}
                  onChange={(e) => setPassword(e.target.value)}
                  required
                />
              </div>

              {isLogin && (
                <div className="form-actions-row">
                  <label className="remember-me" onClick={() => setRememberMe(!rememberMe)}>
                    {rememberMe ? <CheckSquare size={16} color="#8b5cf6" /> : <Square size={16} color="var(--text-secondary)" />}
                    <span>Remember me</span>
                  </label>
                  <a href="#" className="forgot-password">Forgot your password?</a>
                </div>
              )}

              <button type="submit" className="auth-submit-btn">
                {isLogin ? 'LOGIN' : 'CREATE ACCOUNT'}
              </button>
            </form>
          </div>
        </div>

        {/* RIGHT PANE - Welcome & Gradient */}
        <div className="auth-right">
          <div className="auth-right-content">
            <h2 className="welcome-title">{isLogin ? 'Welcome' : 'Hello there'}</h2>
            <p className="welcome-text">
              {isLogin 
                ? "Don't have an account? Create your account, it takes less than a minute" 
                : "Already have an account? Login with your existing credentials"}
            </p>
            <button 
              type="button" 
              className="toggle-mode-btn"
              onClick={() => {
                setIsLogin(!isLogin);
                setError('');
              }}
            >
              {isLogin ? 'Register Now' : 'Login Now'}
            </button>
          </div>
          
          {/* Decorative elements for right pane */}
          <div className="dots-pattern"></div>
          <div className="circle-pattern small"></div>
          <div className="circle-pattern large"></div>
          <div className="wave-bg">
            <svg viewBox="0 0 1440 320" preserveAspectRatio="none" style={{ width: '100%', height: '100%' }}>
              <path fill="rgba(255,255,255,0.05)" d="M0,192L48,197.3C96,203,192,213,288,229.3C384,245,480,267,576,250.7C672,235,768,181,864,181.3C960,181,1056,235,1152,234.7C1248,235,1344,181,1392,154.7L1440,128L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path>
              <path fill="rgba(255,255,255,0.1)" d="M0,64L48,80C96,96,192,128,288,128C384,128,480,96,576,85.3C672,75,768,85,864,112C960,139,1056,181,1152,197.3C1248,213,1344,203,1392,197.3L1440,192L1440,320L1392,320C1344,320,1248,320,1152,320C1056,320,960,320,864,320C768,320,672,320,576,320C480,320,384,320,288,320C192,320,96,320,48,320L0,320Z"></path>
            </svg>
          </div>
        </div>

      </div>
    </div>
  );
}
