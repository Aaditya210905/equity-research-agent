import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Link, useNavigate } from 'react-router-dom';
import { Search, Plus, Trash2, ArrowRight } from 'lucide-react';

export default function Dashboard() {
  const { token, user } = useAuth();
  const [watchlist, setWatchlist] = useState([]);
  const [ticker, setTicker] = useState('');
  const navigate = useNavigate();

  useEffect(() => {
    fetchWatchlist();
  }, [token]);

  const fetchWatchlist = async () => {
    try {
      const res = await fetch('http://localhost:8000/workspace/watchlist', {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setWatchlist(data);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSearch = (e) => {
    e.preventDefault();
    if (ticker) navigate(`/company/${ticker.toUpperCase()}`);
  };

  const addToWatchlist = async (e) => {
    e.preventDefault();
    if (!ticker) return;
    try {
      const res = await fetch(`http://localhost:8000/workspace/watchlist/${ticker}`, {
        method: 'POST',
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        setTicker('');
        fetchWatchlist();
      }
    } catch (e) {
      console.error(e);
    }
  };

  const removeFromWatchlist = async (t) => {
    try {
      await fetch(`http://localhost:8000/workspace/watchlist/${t}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchWatchlist();
    } catch (e) {
      console.error(e);
    }
  };

  return (
    <div>
      <div className="top-bar">
        <h2>Welcome, {user?.username}</h2>
        <form className="search-box" onSubmit={handleSearch}>
          <Search size={18} style={{ color: 'var(--text-secondary)' }} />
          <input 
            type="text" 
            placeholder="Search company ticker (e.g., AAPL, RELIANCE.NS)" 
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
          />
          <button type="submit" className="btn-primary" style={{ padding: '4px 10px', fontSize: '0.9rem' }}>
            Analyze
          </button>
        </form>
      </div>

      <div style={{ display: 'flex', gap: '30px', marginTop: '40px' }}>
        <div style={{ flex: 1 }}>
          <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
            <h3>Your Watchlist</h3>
            <button className="btn-primary" onClick={addToWatchlist} style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
              <Plus size={16} /> Add {ticker || 'Ticker'}
            </button>
          </div>
          
          <div className="grid-container" style={{ marginTop: 0 }}>
            {watchlist.map(item => (
              <div className="glass-card" key={item.ticker}>
                <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                  <h4>{item.ticker}</h4>
                  <Trash2 size={16} style={{ cursor: 'pointer', color: 'var(--danger)' }} onClick={() => removeFromWatchlist(item.ticker)} />
                </div>
                <div className="value" style={{ fontSize: '1.2rem', margin: '15px 0' }}>
                  {item.company_name || 'Active Coverage'}
                </div>
                <Link to={`/company/${item.ticker}`} style={{ color: 'var(--accent)', textDecoration: 'none', display: 'flex', alignItems: 'center', gap: '5px', fontSize: '0.9rem' }}>
                  Open Workspace <ArrowRight size={14} />
                </Link>
              </div>
            ))}
            {watchlist.length === 0 && (
              <div style={{ color: 'var(--text-secondary)' }}>Your watchlist is empty.</div>
            )}
          </div>
        </div>
      </div>
    </div>
  );
}
