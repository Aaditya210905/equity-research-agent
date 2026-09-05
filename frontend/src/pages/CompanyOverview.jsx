import React, { useState } from 'react';
import { Search, Building2 } from 'lucide-react';
import MarketDataGrid from '../components/MarketDataGrid';

export default function CompanyOverview() {
  const [ticker, setTicker] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [companyInfo, setCompanyInfo] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState('');

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!searchQuery) return;
    
    setTicker(searchQuery.toUpperCase());
    setLoading(true);
    setError('');
    setCompanyInfo(null);
    setMarketData(null);

    try {
      const compRes = await fetch(`http://localhost:8000/company/${searchQuery}`);
      if (compRes.ok) {
        setCompanyInfo(await compRes.json());
      } else {
        setError('Company not found.');
      }
      
      const marketRes = await fetch(`http://localhost:8000/market/${searchQuery}`);
      if (marketRes.ok) {
        setMarketData(await marketRes.json());
      }
    } catch (e) {
      console.error(e);
      setError('Failed to fetch data.');
    } finally {
      setLoading(false);
    }
  };

  const formatNumber = (num) => {
    if (!num) return 'N/A';
    if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    return `$${num.toLocaleString()}`;
  };

  return (
    <div>
      <div className="top-bar" style={{ marginBottom: '30px' }}>
        <div>
          <h2>Company Overview</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Search for any global ticker to view its profile and live market data</p>
        </div>
      </div>

      <div className="glass-card" style={{ marginBottom: '30px' }}>
        <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px' }}>
          <input 
            type="text" 
            placeholder="Search ticker (e.g. AAPL, TSLA)..." 
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
            style={{ flex: 1, padding: '12px', borderRadius: '8px', border: '1px solid var(--border)', background: 'rgba(0,0,0,0.2)', color: 'white', fontFamily: 'inherit', fontSize: '1rem' }}
          />
          <button type="submit" className="btn-primary" style={{ padding: '0 20px', display: 'flex', alignItems: 'center', gap: '8px' }}>
            <Search size={18} /> Search
          </button>
        </form>
      </div>

      {loading && <div style={{ color: 'var(--text-secondary)' }}>Fetching data for {searchQuery.toUpperCase()}...</div>}
      {error && <div style={{ color: 'var(--danger)' }}>{error}</div>}

      {!loading && companyInfo?.profile && (
        <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
          <div className="glass-card" style={{ padding: '30px' }}>
            <div style={{ display: 'flex', alignItems: 'center', gap: '15px', marginBottom: '20px' }}>
              <div style={{ background: 'rgba(255,255,255,0.1)', padding: '15px', borderRadius: '12px' }}>
                <Building2 size={32} color="var(--accent)" />
              </div>
              <div>
                <h2 style={{ margin: '0 0 5px 0' }}>{companyInfo.profile.company_name} <span style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', fontWeight: 'normal' }}>{companyInfo.profile.ticker}</span></h2>
                <span style={{ color: 'var(--accent)' }}>{companyInfo.profile.sector} • {companyInfo.profile.industry}</span>
              </div>
            </div>

            <div style={{ display: 'flex', gap: '40px', marginBottom: '20px', borderTop: '1px solid var(--border)', borderBottom: '1px solid var(--border)', padding: '20px 0' }}>
              <div><strong style={{ color: 'var(--text-secondary)', display: 'block', marginBottom: '5px' }}>Exchange</strong> {companyInfo.profile.exchange}</div>
              <div><strong style={{ color: 'var(--text-secondary)', display: 'block', marginBottom: '5px' }}>Country</strong> {companyInfo.profile.country}</div>
              <div><strong style={{ color: 'var(--text-secondary)', display: 'block', marginBottom: '5px' }}>Currency</strong> {companyInfo.profile.currency}</div>
              <div><strong style={{ color: 'var(--text-secondary)', display: 'block', marginBottom: '5px' }}>Employees</strong> {companyInfo.profile.employees?.toLocaleString() || 'N/A'}</div>
              <div><strong style={{ color: 'var(--text-secondary)', display: 'block', marginBottom: '5px' }}>Website</strong> <a href={companyInfo.profile.website} target="_blank" rel="noreferrer" style={{ color: 'var(--text-primary)' }}>{companyInfo.profile.website}</a></div>
            </div>

            <div>
              <h4 style={{ marginBottom: '10px' }}>About {companyInfo.profile.company_name}</h4>
              <p style={{ lineHeight: '1.6', color: 'var(--text-secondary)' }}>{companyInfo.profile.description}</p>
            </div>
          </div>

          {marketData && (
            <div>
              <h3 style={{ marginBottom: '15px' }}>Live Market Data</h3>
              <MarketDataGrid marketData={marketData} />
            </div>
          )}
        </div>
      )}
    </div>
  );
}
