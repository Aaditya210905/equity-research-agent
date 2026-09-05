import React, { useState, useEffect } from 'react';
import { Search } from 'lucide-react';

export default function Compare() {
  const [tickers, setTickers] = useState(['TCS', 'INFY', 'RELIANCE']);
  const [newTicker, setNewTicker] = useState('');
  const [marketDataMap, setMarketDataMap] = useState({});
  const [error, setError] = useState('');

  useEffect(() => {
    tickers.forEach(async (t) => {
      if (!marketDataMap[t]) {
        try {
          const res = await fetch(`http://localhost:8000/market/${t}`);
          if (res.ok) {
            const data = await res.json();
            setMarketDataMap(prev => ({ ...prev, [t]: data }));
          }
        } catch (e) {
          console.error(`Failed to fetch ${t}`, e);
        }
      }
    });
  }, [tickers]);

  const handleAdd = async (e) => {
    e.preventDefault();
    if (!newTicker) return;
    const t = newTicker.toUpperCase();
    if (tickers.includes(t)) {
      setNewTicker('');
      return;
    }
    
    setError('');
    try {
      const res = await fetch(`http://localhost:8000/company/${t}`);
      if (res.ok) {
        const data = await res.json();
        if (data?.profile?.company_name === 'Unknown' || data?.profile?.company_name === 'N/A') {
          setError(`Unknown Ticker: Could not find data for ${t}`);
          return;
        }
        setTickers([...tickers, t]);
        setNewTicker('');
      } else {
        setError(`Failed to verify ticker ${t}`);
      }
    } catch (e) {
      setError(`Error connecting to server`);
    }
  };

  const handleRemove = (t) => {
    setTickers(tickers.filter(ticker => ticker !== t));
  };

  const formatNumber = (num) => {
    if (!num) return 'N/A';
    if (num >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    return `${num.toLocaleString()}`;
  };

  const metricsToCompare = [
    { id: 'price', label: 'Price', getValue: (d) => d.price?.current ? `${d.currency === 'INR' ? '₹' : '$'}${d.price.current}` : 'N/A' },
    { id: 'marketCap', label: 'Market Cap', getValue: (d) => d.valuation?.market_cap ? `${d.currency === 'INR' ? '₹' : '$'}${formatNumber(d.valuation.market_cap)}` : 'N/A' },
    { id: 'pe', label: 'P/E Ratio', getValue: (d) => d.multiples?.pe_ratio ?? 'N/A' },
    { id: 'forwardPe', label: 'Forward P/E', getValue: (d) => d.multiples?.forward_pe ?? 'N/A' },
    { id: 'pb', label: 'Price to Book', getValue: (d) => d.multiples?.price_to_book ?? 'N/A' },
    { id: 'divYield', label: 'Div Yield', getValue: (d) => d.trading?.dividend_yield ? `${d.trading.dividend_yield}%` : 'N/A' },
  ];

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
        {error && <div style={{ color: 'var(--danger)', marginTop: '10px', fontSize: '0.9rem' }}>{error}</div>}
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
            {metricsToCompare.map(metric => (
              <tr key={metric.id} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                <td style={{ padding: '15px', color: 'var(--text-secondary)' }}>
                  {metric.label}
                </td>
                {tickers.map(t => (
                  <td key={`${t}-${metric.id}`} style={{ padding: '15px', fontWeight: 500 }}>
                    {marketDataMap[t] ? metric.getValue(marketDataMap[t]) : 'Loading...'}
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
          Based on the live comparative matrix, you can evaluate companies on real-time market data. Note that financial metrics like revenue growth and operating margin require parsing full quarterly reports, which can be done from the individual company dashboards.
        </p>
      </div>
    </div>
  );
}
