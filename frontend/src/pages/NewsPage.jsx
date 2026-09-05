import React, { useState } from 'react';
import { Search, Newspaper, ExternalLink, Clock, Globe } from 'lucide-react';

export default function NewsPage() {
  const [activeTab, setActiveTab] = useState('company');
  const [ticker, setTicker] = useState('');
  const [searchQuery, setSearchQuery] = useState('');
  const [market, setMarket] = useState('IN');
  const [news, setNews] = useState([]);
  const [loading, setLoading] = useState(false);
  const [searched, setSearched] = useState(false);

  const handleCompanySearch = async (e) => {
    e.preventDefault();
    if (!searchQuery) return;
    setTicker(searchQuery.toUpperCase());
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch(`http://localhost:8000/news/${searchQuery}`);
      if (res.ok) {
        const data = await res.json();
        setNews(data.items || []);
      } else {
        setNews([]);
      }
    } catch (e) {
      console.error(e);
      setNews([]);
    } finally {
      setLoading(false);
    }
  };

  const handleMarketFetch = async (mkt) => {
    setMarket(mkt);
    setLoading(true);
    setSearched(true);
    try {
      const res = await fetch(`http://localhost:8000/news/market/${mkt}`);
      if (res.ok) {
        const data = await res.json();
        setNews(data.items || []);
      } else {
        setNews([]);
      }
    } catch (e) {
      console.error(e);
      setNews([]);
    } finally {
      setLoading(false);
    }
  };

  const formatDate = (dateStr) => {
    if (!dateStr) return '';
    try {
      const d = new Date(dateStr);
      const now = new Date();
      const diffMs = now - d;
      const diffHrs = Math.floor(diffMs / (1000 * 60 * 60));
      if (diffHrs < 1) return 'Just now';
      if (diffHrs < 24) return `${diffHrs}h ago`;
      const diffDays = Math.floor(diffHrs / 24);
      if (diffDays === 1) return 'Yesterday';
      if (diffDays < 7) return `${diffDays}d ago`;
      return d.toLocaleDateString('en-US', { month: 'short', day: 'numeric', year: 'numeric' });
    } catch {
      return '';
    }
  };

  const originLabel = (origin) => {
    const map = { 'google-news': 'Google News', 'yahoo': 'Yahoo Finance', 'bing': 'Bing News' };
    return map[origin] || origin;
  };

  const originColor = (origin) => {
    const map = { 'google-news': '#4285f4', 'yahoo': '#7b1fa2', 'bing': '#00897b' };
    return map[origin] || 'var(--accent)';
  };

  return (
    <div>
      <div className="top-bar" style={{ flexWrap: 'wrap', gap: '15px' }}>
        <h2 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          <Newspaper size={24} /> News Feed
        </h2>

        {/* Tabs */}
        <div style={{ display: 'flex', gap: '5px', background: 'var(--bg-card)', borderRadius: '12px', padding: '4px', border: '1px solid var(--border)' }}>
          <button
            onClick={() => { setActiveTab('company'); setNews([]); setSearched(false); }}
            style={{
              padding: '8px 18px', borderRadius: '10px', border: 'none', cursor: 'pointer',
              background: activeTab === 'company' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'company' ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600, fontSize: '0.9rem', transition: 'all 0.2s'
            }}
          >
            Company News
          </button>
          <button
            onClick={() => { setActiveTab('market'); setNews([]); setSearched(false); handleMarketFetch(market); }}
            style={{
              padding: '8px 18px', borderRadius: '10px', border: 'none', cursor: 'pointer',
              background: activeTab === 'market' ? 'var(--accent)' : 'transparent',
              color: activeTab === 'market' ? '#fff' : 'var(--text-secondary)',
              fontWeight: 600, fontSize: '0.9rem', transition: 'all 0.2s'
            }}
          >
            Market News
          </button>
        </div>
      </div>

      {/* Company search bar */}
      {activeTab === 'company' && (
        <form className="search-box" onSubmit={handleCompanySearch} style={{ marginBottom: '30px', maxWidth: '500px' }}>
          <Search size={18} style={{ color: 'var(--text-secondary)' }} />
          <input
            type="text"
            placeholder="Enter ticker (e.g. TCS, AAPL, RELIANCE)..."
            value={searchQuery}
            onChange={(e) => setSearchQuery(e.target.value)}
          />
          <button type="submit" className="btn-primary" style={{ padding: '6px 16px', fontSize: '0.9rem' }}>
            Search
          </button>
        </form>
      )}

      {/* Market toggle */}
      {activeTab === 'market' && (
        <div style={{ display: 'flex', gap: '10px', marginBottom: '30px' }}>
          {['IN', 'US'].map(mkt => (
            <button
              key={mkt}
              onClick={() => handleMarketFetch(mkt)}
              className="btn-primary"
              style={{
                background: market === mkt ? 'var(--accent)' : 'transparent',
                border: '1px solid var(--border)',
                padding: '8px 20px',
                display: 'flex', alignItems: 'center', gap: '8px'
              }}
            >
              <Globe size={16} /> {mkt === 'IN' ? '🇮🇳 India' : '🇺🇸 United States'}
            </button>
          ))}
        </div>
      )}

      {/* Loading */}
      {loading && (
        <div style={{ textAlign: 'center', padding: '60px', color: 'var(--text-secondary)' }}>
          <div className="spin" style={{ display: 'inline-block', width: '30px', height: '30px', border: '3px solid var(--border)', borderTopColor: 'var(--accent)', borderRadius: '50%', marginBottom: '15px' }}></div>
          <p>Fetching news from multiple sources...</p>
        </div>
      )}

      {/* Empty state */}
      {!loading && searched && news.length === 0 && (
        <div className="glass-card" style={{ textAlign: 'center', padding: '60px', color: 'var(--text-secondary)' }}>
          <Newspaper size={48} style={{ opacity: 0.2, marginBottom: '15px' }} />
          <h3>No News Found</h3>
          <p>No articles found{activeTab === 'company' ? ` for ${ticker}` : ` for ${market} market`}. Try a different search.</p>
        </div>
      )}

      {/* Initial state */}
      {!loading && !searched && activeTab === 'company' && (
        <div className="glass-card" style={{ textAlign: 'center', padding: '60px', color: 'var(--text-secondary)' }}>
          <Newspaper size={48} style={{ opacity: 0.2, marginBottom: '15px' }} />
          <h3>Search for Company News</h3>
          <p>Enter a stock ticker above to fetch the latest news from Google, Bing, and Yahoo.</p>
        </div>
      )}

      {/* News grid */}
      {!loading && news.length > 0 && (
        <div>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '20px', fontSize: '0.9rem' }}>
            {news.length} article{news.length !== 1 ? 's' : ''} found
            {activeTab === 'company' ? ` for ${ticker}` : ` for ${market === 'IN' ? 'Indian' : 'US'} markets`}
          </p>
          <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(340px, 1fr))', gap: '20px' }}>
            {news.map((item, idx) => (
              <a
                key={item.id || idx}
                href={item.url}
                target="_blank"
                rel="noreferrer"
                style={{ textDecoration: 'none', color: 'inherit' }}
              >
                <div className="glass-card" style={{
                  padding: '20px', cursor: 'pointer', height: '100%',
                  display: 'flex', flexDirection: 'column', gap: '12px',
                  transition: 'transform 0.2s, border-color 0.2s',
                  borderLeft: `3px solid ${originColor(item.origin)}`
                }}
                  onMouseEnter={(e) => { e.currentTarget.style.transform = 'translateY(-2px)'; }}
                  onMouseLeave={(e) => { e.currentTarget.style.transform = 'translateY(0)'; }}
                >
                  {/* Thumbnail */}
                  {item.thumbnail && (
                    <div style={{ borderRadius: '8px', overflow: 'hidden', height: '160px', marginBottom: '5px' }}>
                      <img src={item.thumbnail} alt="" style={{ width: '100%', height: '100%', objectFit: 'cover' }} onError={(e) => e.target.style.display = 'none'} />
                    </div>
                  )}

                  {/* Title */}
                  <h4 style={{ fontSize: '1rem', lineHeight: '1.4', margin: 0, color: 'var(--text-primary)' }}>
                    {item.title}
                  </h4>

                  {/* Snippet */}
                  {item.snippet && (
                    <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', lineHeight: '1.5', margin: 0, flex: 1 }}>
                      {item.snippet.length > 180 ? item.snippet.slice(0, 180) + '...' : item.snippet}
                    </p>
                  )}

                  {/* Footer */}
                  <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginTop: 'auto' }}>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '8px' }}>
                      <span style={{
                        fontSize: '0.75rem', padding: '3px 8px', borderRadius: '6px',
                        background: `${originColor(item.origin)}20`, color: originColor(item.origin),
                        fontWeight: 600
                      }}>
                        {originLabel(item.origin)}
                      </span>
                      <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
                        {item.source}
                      </span>
                    </div>
                    <div style={{ display: 'flex', alignItems: 'center', gap: '5px' }}>
                      {item.publishedAt && (
                        <span style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '3px' }}>
                          <Clock size={12} /> {formatDate(item.publishedAt)}
                        </span>
                      )}
                      <ExternalLink size={14} style={{ color: 'var(--text-secondary)' }} />
                    </div>
                  </div>
                </div>
              </a>
            ))}
          </div>
        </div>
      )}
    </div>
  );
}
