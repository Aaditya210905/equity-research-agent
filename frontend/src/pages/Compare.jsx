import React, { useState } from 'react';
import { Search } from 'lucide-react';

export default function Compare() {
  const [tickers, setTickers] = useState(['TCS', 'INFY', 'HCLTECH']);
  const [newTicker, setNewTicker] = useState('');

  const handleAdd = (e) => {
    e.preventDefault();
    if (newTicker && !tickers.includes(newTicker.toUpperCase())) {
      setTickers([...tickers, newTicker.toUpperCase()]);
      setNewTicker('');
    }
  };

  const handleRemove = (t) => {
    setTickers(tickers.filter(ticker => ticker !== t));
  };

  // Dummy mock data since comparison backend endpoint is minimal in this phase
  const mockData = {
    'TCS': { price: 3800, pe: 32.5, revGrowth: '8.4%', opMargin: '24.5%', roe: '45.2%' },
    'INFY': { price: 1450, pe: 24.1, revGrowth: '5.2%', opMargin: '21.0%', roe: '32.1%' },
    'HCLTECH': { price: 1320, pe: 21.8, revGrowth: '10.5%', opMargin: '19.8%', roe: '28.4%' },
  };

  return (
    <div>
      <div className="top-bar">
        <h2>Peer Comparison</h2>
        <form className="search-box" onSubmit={handleAdd}>
          <Search size={18} style={{ color: 'var(--text-secondary)' }} />
          <input 
            type="text" 
            placeholder="Add ticker to compare..." 
            value={newTicker}
            onChange={(e) => setNewTicker(e.target.value)}
          />
          <button type="submit" className="btn-primary" style={{ padding: '4px 10px', fontSize: '0.9rem' }}>
            Add
          </button>
        </form>
      </div>

      <div className="glass-card" style={{ overflowX: 'auto' }}>
        <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
          <thead>
            <tr style={{ borderBottom: '1px solid var(--border)' }}>
              <th style={{ padding: '15px' }}>Metric</th>
              {tickers.map(t => (
                <th key={t} style={{ padding: '15px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between' }}>
                    {t}
                    <button onClick={() => handleRemove(t)} style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}>✕</button>
                  </div>
                </th>
              ))}
            </tr>
          </thead>
          <tbody>
            {['price', 'pe', 'revGrowth', 'opMargin', 'roe'].map(metric => (
              <tr key={metric} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '15px', textTransform: 'capitalize', color: 'var(--text-secondary)' }}>
                  {metric.replace(/([A-Z])/g, ' $1').trim()}
                </td>
                {tickers.map(t => (
                  <td key={`${t}-${metric}`} style={{ padding: '15px', fontWeight: 500 }}>
                    {mockData[t] ? mockData[t][metric] || '-' : 'N/A'}
                  </td>
                ))}
              </tr>
            ))}
          </tbody>
        </table>
      </div>

      <div className="glass-card" style={{ marginTop: '20px' }}>
        <h3 style={{ color: 'var(--accent)', marginBottom: '15px' }}>AI Comparison Synthesis</h3>
        <p style={{ color: 'var(--text-secondary)', lineHeight: 1.6 }}>
          Based on the comparative matrix, <b>TCS</b> maintains a premium valuation (P/E 32.5) justified by its industry-leading operating margin of 24.5% and superior ROE. 
          However, <b>HCLTECH</b> shows the strongest topline momentum with 10.5% Revenue Growth, potentially signaling a shift in market share.
        </p>
      </div>
    </div>
  );
}
