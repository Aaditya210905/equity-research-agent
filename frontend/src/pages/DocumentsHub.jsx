import React, { useState, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Search, FileText, Download, CheckCircle2, RefreshCw, Folder, FolderOpen, ChevronRight, ChevronDown } from 'lucide-react';

export default function DocumentsHub() {
  const { token } = useAuth();
  const [ticker, setTicker] = useState('');
  const [searchTicker, setSearchTicker] = useState('');
  const [documents, setDocuments] = useState([]);
  const [isCollecting, setIsCollecting] = useState(false);
  const [collectLogs, setCollectLogs] = useState([]);
  const [openFolders, setOpenFolders] = useState({});

  const toggleFolder = (type) => {
    setOpenFolders(prev => ({ ...prev, [type]: !prev[type] }));
  };

  const groupedDocuments = documents.reduce((acc, doc) => {
    const type = doc.doc_type || 'uncategorized';
    if (!acc[type]) acc[type] = [];
    acc[type].push(doc);
    return acc;
  }, {});
  
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

  const downloadDocument = (documentId) => {
    if (!documentId) return;
    const downloadUrl = `http://localhost:8000/documents/${documentId}/download`;
    // Opening in a new tab will natively trigger the download from our backend endpoint
    window.open(downloadUrl, '_blank');
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
        <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', marginBottom: '20px' }}>
          <h3>{searchTicker ? `Repository for ${searchTicker}` : 'Document Repository'}</h3>
        </div>
        {documents.length === 0 ? (
          <p style={{ color: 'var(--text-secondary)' }}>
             {searchTicker ? `No documents found for ${searchTicker}.` : 'Search for a company above to ingest and view documents.'}
          </p>
        ) : (
          <div style={{ display: 'flex', flexDirection: 'column', gap: '5px' }}>
            {Object.entries(groupedDocuments).map(([type, docs]) => {
              const isOpen = openFolders[type];
              return (
                <div key={type}>
                  <div 
                    onClick={() => toggleFolder(type)}
                    style={{ display: 'flex', alignItems: 'center', gap: '8px', padding: '10px', cursor: 'pointer', background: isOpen ? 'rgba(255,255,255,0.05)' : 'transparent', borderRadius: '6px', userSelect: 'none', transition: 'background 0.2s' }}
                    onMouseOver={(e) => { if(!isOpen) e.currentTarget.style.background = 'rgba(255,255,255,0.02)'; }}
                    onMouseOut={(e) => { if(!isOpen) e.currentTarget.style.background = 'transparent'; }}
                  >
                    {isOpen ? <ChevronDown size={18} /> : <ChevronRight size={18} />}
                    {isOpen ? <FolderOpen size={18} color="var(--accent)" /> : <Folder size={18} color="var(--accent)" />}
                    <span style={{ textTransform: 'capitalize', fontWeight: '500', fontSize: '1rem' }}>{type.replace(/_/g, ' ')}</span>
                    <span style={{ color: 'var(--text-secondary)', fontSize: '0.85rem', marginLeft: '10px' }}>({docs.length})</span>
                  </div>
                  
                  {isOpen && (
                    <div style={{ display: 'flex', flexDirection: 'column', paddingLeft: '35px', marginTop: '5px', marginBottom: '10px', gap: '5px' }}>
                      {docs.map((doc, idx) => (
                        <div key={idx} style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'center', padding: '10px 15px', background: 'rgba(255,255,255,0.02)', borderRadius: '6px', borderLeft: '2px solid rgba(255,255,255,0.1)' }}>
                          <div style={{ display: 'flex', alignItems: 'center', gap: '12px' }}>
                            <FileText size={16} color="var(--text-secondary)" />
                            {doc.document_id ? (
                              <a href={`http://localhost:8000/documents/${doc.document_id}/download`} target="_blank" rel="noreferrer" style={{ color: 'var(--text-primary)', textDecoration: 'none', fontWeight: '500' }}>
                                {(doc.title === 'Filing' ? (doc.doc_type || 'Filing').split('_').map(w => w.charAt(0).toUpperCase() + w.slice(1)).join(' ') : doc.title) || doc.document_id}
                              </a>
                            ) : (
                              <span style={{ fontWeight: '500' }}>{doc.title || 'Unknown Document'}</span>
                            )}
                            <span style={{ fontSize: '0.8rem', color: 'var(--text-secondary)', marginLeft: '10px', background: 'rgba(0,0,0,0.3)', padding: '2px 8px', borderRadius: '12px' }}>
                              {doc.year ? `${doc.year} • ` : ''}{doc.source}
                            </span>
                          </div>
                          {doc.document_id && (
                            <button 
                              onClick={() => downloadDocument(doc.document_id)}
                              style={{ background: 'var(--bg-card)', border: '1px solid var(--border)', color: 'var(--text-primary)', cursor: 'pointer', display: 'flex', alignItems: 'center', padding: '6px', borderRadius: '6px', transition: 'all 0.2s' }}
                              title="Download File"
                              onMouseOver={(e) => { e.currentTarget.style.color = 'var(--accent)'; e.currentTarget.style.borderColor = 'var(--accent)'; }}
                              onMouseOut={(e) => { e.currentTarget.style.color = 'var(--text-primary)'; e.currentTarget.style.borderColor = 'var(--border)'; }}
                            >
                              <Download size={16} />
                            </button>
                          )}
                        </div>
                      ))}
                    </div>
                  )}
                </div>
              );
            })}
          </div>
        )}
      </div>
    </div>
  );
}
