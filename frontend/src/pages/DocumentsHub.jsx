import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Search, FileText, Download, CheckCircle2, RefreshCw } from 'lucide-react';

export default function DocumentsHub() {
  const { token } = useAuth();
  const [ticker, setTicker] = useState('');
  const [searchTicker, setSearchTicker] = useState('');
  const [documents, setDocuments] = useState([]);
  const [isCollecting, setIsCollecting] = useState(false);
  const [collectLogs, setCollectLogs] = useState([]);
  
  useEffect(() => {
    if (searchTicker) {
      fetchDocuments(searchTicker);
    }
  }, [searchTicker]);

  const fetchDocuments = async (t) => {
    if (!t) return;
    try {
      const res = await fetch(`http://localhost:8000/documents/${t}`);
      if (res.ok) {
        const data = await res.json();
        setDocuments(data.documents || []);
      }
    } catch (e) {
      console.error(e);
    }
  };

  const handleCollect = async (e) => {
    e.preventDefault();
    if (!ticker) return;
    
    setIsCollecting(true);
    setCollectLogs([]);
    setSearchTicker(ticker.toUpperCase());
    
    // 1. Trigger the collection on the backend
    fetch(`http://localhost:8000/documents/${ticker.toUpperCase()}/collect`, {
      method: 'POST',
      headers: { Authorization: `Bearer ${token}` }
    }).catch(console.error);

    // 2. Stream the progress
    const eventSource = new EventSource(`http://localhost:8000/documents/${ticker.toUpperCase()}/stream`);
    
    eventSource.onmessage = (event) => {
      const data = JSON.parse(event.data);
      if (data.node === 'done') {
        eventSource.close();
        setCollectLogs(prev => [...prev, { msg: 'Collection Complete!' }]);
        setIsCollecting(false);
        fetchDocuments(ticker.toUpperCase());
      } else if (data.node === 'error') {
        eventSource.close();
        setCollectLogs(prev => [...prev, { msg: `Error: ${data.data.error}` }]);
        setIsCollecting(false);
      } else {
        setCollectLogs(prev => [...prev, { msg: `Processed step: ${data.node}` }]);
      }
    };
    
    eventSource.onerror = () => {
      eventSource.close();
      setIsCollecting(false);
    };
  };

  return (
    <div>
      <div className="top-bar">
        <div>
          <h2>Documents Hub</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Ingest and manage financial documents</p>
        </div>
        <form className="search-box" onSubmit={handleCollect}>
          <Search size={18} style={{ color: 'var(--text-secondary)' }} />
          <input 
            type="text" 
            placeholder="Collect new documents (e.g. AAPL)..." 
            value={ticker}
            onChange={(e) => setTicker(e.target.value)}
          />
          <button type="submit" className="btn-primary" style={{ padding: '4px 10px', fontSize: '0.9rem' }}>
            Fetch
          </button>
        </form>
      </div>

      {isCollecting && (
        <div className="glass-card" style={{ marginBottom: '30px', borderLeft: '4px solid var(--accent)' }}>
          <h3 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
             <RefreshCw size={18} className="spin" /> Scraping & Ingesting Documents...
          </h3>
          <div style={{ background: 'rgba(0,0,0,0.5)', padding: '15px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '0.9rem', color: '#a78bfa' }}>
             {collectLogs.map((log, i) => (
                <div key={i} style={{ display: 'flex', gap: '10px', alignItems: 'center', margin: '5px 0' }}>
                   <CheckCircle2 size={14} color="var(--success)" /> {log.msg}
                </div>
             ))}
             <div className="typing-indicator" style={{ color: 'var(--text-secondary)' }}>Downloading...</div>
          </div>
        </div>
      )}

      <div className="glass-card">
        <h3 style={{ marginBottom: '20px' }}>{searchTicker ? `Repository for ${searchTicker}` : 'Document Repository'}</h3>
        {documents.length === 0 ? (
          <p style={{ color: 'var(--text-secondary)' }}>
             {searchTicker ? `No documents found for ${searchTicker}.` : 'Search for a company above to ingest and view documents.'}
          </p>
        ) : (
          <table style={{ width: '100%', borderCollapse: 'collapse', textAlign: 'left' }}>
            <thead>
              <tr style={{ borderBottom: '1px solid var(--border)' }}>
                <th style={{ padding: '15px' }}>Document</th>
                <th style={{ padding: '15px' }}>Source</th>
                <th style={{ padding: '15px' }}>Year</th>
                <th style={{ padding: '15px' }}>Type</th>
              </tr>
            </thead>
            <tbody>
              {documents.map((doc, idx) => (
                <tr key={idx} style={{ borderBottom: '1px solid rgba(255,255,255,0.05)' }}>
                  <td style={{ padding: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
                    <FileText size={16} color="var(--accent)" />
                    {doc.url ? (
                      <a href={doc.url} target="_blank" rel="noreferrer" style={{ color: 'var(--text-primary)' }}>
                        {doc.title || doc.url.split('/').pop()}
                      </a>
                    ) : (
                      <span>{doc.title || 'Unknown Document'}</span>
                    )}
                  </td>
                  <td style={{ padding: '15px', color: 'var(--text-secondary)' }}>{doc.source}</td>
                  <td style={{ padding: '15px' }}>{doc.year || 'N/A'}</td>
                  <td style={{ padding: '15px' }}>
                    <span className="badge high" style={{ textTransform: 'capitalize' }}>
                      {doc.doc_type}
                    </span>
                  </td>
                </tr>
              ))}
            </tbody>
          </table>
        )}
      </div>
    </div>
  );
}
