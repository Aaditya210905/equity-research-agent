import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Search, Download, FileText, Globe, Folder, FolderOpen } from 'lucide-react';

export default function BseScreener() {
  const { token } = useAuth();
  const [query, setQuery] = useState('');
  const [searchResults, setSearchResults] = useState([]);
  const [fetchedFolders, setFetchedFolders] = useState([]);
  const [activeScripCodes, setActiveScripCodes] = useState([]);
  const [loading, setLoading] = useState(false);
  const [selectedPdf, setSelectedPdf] = useState(null);
  const [expandedCategories, setExpandedCategories] = useState({});

  const toggleCategory = (scripCode, kind) => {
    const key = `${scripCode}-${kind}`;
    setExpandedCategories(prev => ({ ...prev, [key]: !prev[key] }));
  };

  useEffect(() => {
    fetchFolders();
  }, []);

  const fetchFolders = async () => {
    try {
      const res = await fetch('http://localhost:8000/bse/filings');
      if (res.ok) {
        setFetchedFolders(await res.json());
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleSearch = async (e) => {
    e.preventDefault();
    if (!query || query.length < 2) return;
    setLoading(true);
    try {
      const res = await fetch(`http://localhost:8000/bse/search?query=${query}`);
      if (res.ok) setSearchResults(await res.json());
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleFetch = async (company) => {
    setLoading(true);
    if (!activeScripCodes.includes(company.scripCode)) {
      setActiveScripCodes(prev => [company.scripCode, ...prev]);
    }
    try {
      const res = await fetch(`http://localhost:8000/bse/filings/fetch`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify({
          scripCode: company.scripCode,
          name: company.name
        })
      });
      if (res.ok) {
        fetchFolders();
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  return (
    <div>
      <div className="top-bar">
        <div>
          <h2>BSE India Screener</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Search and download filings from the Bombay Stock Exchange</p>
        </div>
      </div>

      <div style={{ display: 'flex', gap: '30px' }}>
        {/* Left panel: Search & Results */}
        <div style={{ flex: 1 }}>
          <div className="glass-card">
            <form onSubmit={handleSearch} style={{ display: 'flex', gap: '10px', marginBottom: '20px' }}>
              <input 
                type="text" 
                placeholder="Search company (e.g. WIPRO, TCS)..." 
                value={query}
                onChange={(e) => setQuery(e.target.value)}
                style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid var(--border)', background: 'rgba(0,0,0,0.2)', color: 'white', fontFamily: 'inherit' }}
              />
              <button type="submit" className="btn-primary">Search</button>
            </form>
            
            {loading && <div style={{ color: 'var(--text-secondary)' }}>Searching...</div>}

            <div style={{ maxHeight: '400px', overflowY: 'auto' }}>
              {searchResults.map((res, i) => (
                <div key={i} style={{ padding: '15px', background: 'rgba(255,255,255,0.05)', borderRadius: '8px', marginBottom: '10px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
                  <div>
                    <h4 style={{ margin: 0 }}>{res.name}</h4>
                    <span style={{ fontSize: '0.8rem', color: 'var(--accent)' }}>Scrip: {res.scripCode} | {res.symbol}</span>
                  </div>
                  <button onClick={() => handleFetch(res)} className="btn-primary" style={{ padding: '5px 10px', fontSize: '0.8rem', display: 'flex', alignItems: 'center', gap: '5px' }}>
                    <Download size={14} /> Fetch Filings
                  </button>
                </div>
              ))}
            </div>
          </div>
        </div>

        {/* Right panel: Downloaded Folders & Viewer */}
        <div style={{ flex: 2 }}>
          {selectedPdf ? (
            <div className="glass-card" style={{ height: '700px', display: 'flex', flexDirection: 'column' }}>
              <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '15px' }}>
                <h4 style={{ display: 'flex', alignItems: 'center', gap: '10px' }}><FileText size={18} color="var(--accent)"/> PDF Viewer</h4>
                <button onClick={() => setSelectedPdf(null)} style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}>Close Viewer</button>
              </div>
              <iframe 
                src={selectedPdf} 
                style={{ flex: 1, width: '100%', border: 'none', borderRadius: '8px', background: 'white' }} 
                title="PDF Viewer"
              />
            </div>
          ) : (
            <div className="glass-card">
              <h3 style={{ marginBottom: '20px' }}><Globe size={20} style={{ verticalAlign: 'middle', marginRight: '10px' }}/> Fetched Documents</h3>
              
              {fetchedFolders.filter(f => activeScripCodes.includes(f.scripCode)).length === 0 ? (
                <p style={{ color: 'var(--text-secondary)' }}>No filings fetched yet. Search for a company and click "Fetch Filings" to view documents here.</p>
              ) : (
                <div style={{ display: 'flex', flexDirection: 'column', gap: '20px' }}>
                  {fetchedFolders.filter(f => activeScripCodes.includes(f.scripCode)).map((folder, i) => {
                    const groupedFiles = folder.files.reduce((acc, file) => {
                      const kind = file.kind || 'other';
                      if (!acc[kind]) acc[kind] = [];
                      acc[kind].push(file);
                      return acc;
                    }, {});

                    return (
                      <div key={i} style={{ border: '1px solid var(--border)', borderRadius: '8px', padding: '15px' }}>
                        <h4 style={{ marginBottom: '15px', color: 'var(--text-primary)' }}>{folder.name} <span style={{ fontSize: '0.8rem', color: 'var(--accent)', fontWeight: 'normal', marginLeft: '10px' }}>{folder.scripCode}</span></h4>
                        
                        <div style={{ display: 'flex', flexDirection: 'column', gap: '10px' }}>
                          {Object.entries(groupedFiles).map(([kind, files]) => {
                            const catKey = `${folder.scripCode}-${kind}`;
                            const isExpanded = expandedCategories[catKey];
                            
                            return (
                              <div key={kind}>
                                <button 
                                  onClick={() => toggleCategory(folder.scripCode, kind)}
                                  style={{ display: 'flex', alignItems: 'center', gap: '8px', background: 'none', border: 'none', color: 'var(--text-primary)', cursor: 'pointer', fontSize: '1rem', padding: '5px 0' }}
                                >
                                  {isExpanded ? <FolderOpen size={18} color="var(--accent)" /> : <Folder size={18} color="var(--accent)" />}
                                  <span style={{ textTransform: 'capitalize' }}>{kind.replace(/[_-]/g, ' ')} ({files.length})</span>
                                </button>
                                
                                {isExpanded && (
                                  <ul style={{ listStyle: 'none', padding: '10px 0 10px 25px', margin: 0, borderLeft: '1px solid rgba(255,255,255,0.1)', marginLeft: '8px' }}>
                                    {files.map((file, j) => (
                                      <li key={j} style={{ padding: '6px 0' }}>
                                        <button 
                                          onClick={() => setSelectedPdf(`http://localhost:8000/bse/file/${encodeURIComponent(file.relativePath)}`)}
                                          style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer', textAlign: 'left', display: 'flex', alignItems: 'flex-start', gap: '10px', fontSize: '0.9rem' }}
                                        >
                                          <FileText size={14} color="var(--danger)" style={{ marginTop: '2px', flexShrink: 0 }} /> 
                                          <span>{(file.headline && file.headline !== 'Filing') ? file.headline : file.fileName}</span>
                                        </button>
                                      </li>
                                    ))}
                                  </ul>
                                )}
                              </div>
                            );
                          })}
                        </div>
                      </div>
                    );
                  })}
                </div>
              )}
            </div>
          )}
        </div>
      </div>
    </div>
  );
}
