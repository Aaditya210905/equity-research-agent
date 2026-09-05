import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ReportViewer from '../components/ReportViewer';
import MarketDataGrid from '../components/MarketDataGrid';
import { Download, RefreshCw, FileText, CheckCircle2, Bot } from 'lucide-react';

function AnalystNotes({ ticker }) {
  const { token } = useAuth();
  const [note, setNote] = useState('');
  const [savedNotes, setSavedNotes] = useState([]);

  useEffect(() => {
    fetchNotes();
  }, [ticker]);

  const fetchNotes = async () => {
    try {
      const res = await fetch(`http://localhost:8000/workspace/notes/${ticker}`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setSavedNotes(data);
      }
    } catch (e) { console.error(e); }
  };

  const handleSave = async () => {
    if (!note) return;
    try {
      const res = await fetch(`http://localhost:8000/workspace/notes/${ticker}`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify({ content: note })
      });
      if (res.ok) {
        setNote('');
        fetchNotes();
      }
    } catch (e) { console.error(e); }
  };

  const handleDelete = async (id) => {
    try {
      await fetch(`http://localhost:8000/workspace/notes/${id}`, {
        method: 'DELETE',
        headers: { Authorization: `Bearer ${token}` }
      });
      fetchNotes();
    } catch (e) { console.error(e); }
  };

  return (
    <div className="glass-card" style={{ display: 'flex', flexDirection: 'column', height: '100%' }}>
      <h4>Analyst Notes</h4>
      
      <div style={{ flex: 1, overflowY: 'auto', marginBottom: '15px', minHeight: '400px' }}>
        {savedNotes.map(n => (
          <div key={n.id} style={{ background: 'rgba(255,255,255,0.05)', padding: '10px', borderRadius: '8px', marginBottom: '10px' }}>
            <p style={{ fontSize: '0.9rem', marginBottom: '5px' }}>{n.content}</p>
            <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-secondary)' }}>
              <span>{new Date(n.created_at).toLocaleDateString()}</span>
              <button onClick={() => handleDelete(n.id)} style={{ background: 'none', border: 'none', color: 'var(--danger)', cursor: 'pointer' }}>Delete</button>
            </div>
          </div>
        ))}
      </div>

      <textarea 
        value={note}
        onChange={(e) => setNote(e.target.value)}
        style={{ width: '100%', height: '150px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '8px', color: 'white', padding: '10px', fontFamily: 'inherit', resize: 'vertical' }} 
        placeholder="Jot down your thesis or observations..."
      ></textarea>
      <button className="btn-primary" onClick={handleSave} style={{ width: '100%', marginTop: '10px' }}>Save Note</button>
    </div>
  );
}

export default function Company() {
  const { ticker } = useParams();
  const { token } = useAuth();
  
  const [report, setReport] = useState(null);
  const [companyInfo, setCompanyInfo] = useState(null);
  const [marketData, setMarketData] = useState(null);
  const [loading, setLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateLogs, setGenerateLogs] = useState([]);
  const [showNoDocsModal, setShowNoDocsModal] = useState(false);
  const [showUnknownTickerModal, setShowUnknownTickerModal] = useState(false);

  useEffect(() => {
    fetchLatestReport();
    fetchCompanyData();
  }, [ticker]);

  const fetchCompanyData = async () => {
    try {
      const compRes = await fetch(`http://localhost:8000/company/${ticker}`);
      if (compRes.ok) {
        const data = await compRes.json();
        if (data?.profile?.company_name === 'Unknown' || data?.profile?.company_name === 'N/A') {
          setShowUnknownTickerModal(true);
        }
        setCompanyInfo(data);
      }
      
      const marketRes = await fetch(`http://localhost:8000/market/${ticker}`);
      if (marketRes.ok) setMarketData(await marketRes.json());
    } catch (e) { console.error(e); }
  };

  const fetchLatestReport = async () => {
    try {
      setLoading(true);
      const res = await fetch(`http://localhost:8000/workspace/report/${ticker}/latest`, {
        headers: { Authorization: `Bearer ${token}` }
      });
      if (res.ok) {
        const data = await res.json();
        setReport(data);
      } else {
        setReport(null);
      }
    } catch (e) {
      console.error(e);
    } finally {
      setLoading(false);
    }
  };

  const handleGenerate = async () => {
    try {
      const docRes = await fetch(`http://localhost:8000/documents/${ticker}`);
      if (docRes.ok) {
        const docData = await docRes.json();
        if (!docData.documents || docData.documents.length === 0) {
          setShowNoDocsModal(true);
          return;
        }
      }
    } catch (e) {
      console.error("Error checking documents:", e);
    }

    setIsGenerating(true);
    setGenerateLogs([]);
    
    const eventSource = new EventSource(`http://localhost:8000/research/${ticker}/stream`);
    let lastState = null;
    
    eventSource.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      if (data.node === 'done') {
        eventSource.close();
        setGenerateLogs(prev => [...prev, { node: 'done', msg: 'Verification complete. Assembling 12-section report...' }]);
        if (lastState) {
          try {
            const res = await fetch(`http://localhost:8000/workspace/report/${ticker}/format_and_save`, {
              method: 'POST',
              headers: { 'Content-Type': 'application/json', Authorization: `Bearer ${token}` },
              body: JSON.stringify(lastState)
            });
            if (res.ok) await fetchLatestReport();
          } catch (e) { console.error("Format save error", e); }
        }
        setIsGenerating(false);
      } else if (data.node === 'error') {
        eventSource.close();
        setGenerateLogs(prev => [...prev, { node: 'error', msg: `Error: ${data.data.error}` }]);
        setIsGenerating(false);
      } else {
        setGenerateLogs(prev => [...prev, { node: data.node, msg: `Completed node: ${data.node}` }]);
        lastState = data.data; 
      }
    };
    eventSource.onerror = () => { eventSource.close(); setIsGenerating(false); };
  };

  const handleExport = (format) => {
    window.open(`http://localhost:8000/workspace/report/${ticker}/export/${format}?token=${token}`, '_blank');
  };

  const formatNumber = (num) => {
    if (!num) return 'N/A';
    if (num >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    return `${num.toLocaleString()}`;
  };

  if (loading && !companyInfo) return <div>Loading workspace...</div>;

  return (
    <div className="company-workspace">
      <div className="top-bar" style={{ 
        position: 'sticky',
        top: -50,
        zIndex: 50,
        background: 'rgba(15, 23, 42, 0.85)',
        backdropFilter: 'blur(12px)',
        margin: '-30px -30px 20px -30px',
        padding: '30px 30px 15px 30px',
        borderBottom: '1px solid rgba(255, 255, 255, 0.1)'
      }}>
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            {companyInfo?.profile ? companyInfo.profile.company_name : ticker} 
            <span style={{ fontSize: '1.2rem', color: 'var(--text-secondary)' }}>{ticker}</span>
          </h2>
          <p style={{ color: 'var(--text-secondary)' }}>
            {companyInfo?.profile ? `${companyInfo.profile.sector} • ${companyInfo.profile.industry}` : 'Advanced AI Research Dashboard'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px', alignItems: 'flex-end' }}>
          <Link to={`/company/${ticker}/chat`} className="btn-primary" style={{ display: 'flex', gap: '8px', alignItems: 'center', background: 'var(--accent)', color: '#fff', textDecoration: 'none' }}>
            <Bot size={16} /> Research Assistant
          </Link>
          {!isGenerating && (
            <div style={{ display: 'flex', flexDirection: 'column', alignItems: 'flex-end', gap: '8px' }}>
              
              <button className="btn-primary" onClick={handleGenerate} style={{ display: 'flex', gap: '8px', alignItems: 'center', width: '100%', justifyContent: 'center' }}>
                <RefreshCw size={16} /> Generate AI Report
              </button>
            </div>
          )}
          {report && (
            <div className="export-bar" style={{ display: 'flex', gap: '5px' }}>
              <button onClick={() => handleExport('pdf')} className="btn-primary" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} title="Export PDF"><Download size={16}/></button>
              <button onClick={() => handleExport('docx')} className="btn-primary" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>DOCX</button>
            </div>
          )}
        </div>
      </div>

      {/* Market Data KPI Grid */}
      <div style={{ marginBottom: '40px' }}>
        {marketData && <MarketDataGrid marketData={marketData} />}
      </div>
      
      {isGenerating && (
        <div className="glass-card" style={{ marginBottom: '30px', borderLeft: '4px solid var(--accent)' }}>
          <h3 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
             <RefreshCw size={18} className="spin" /> Generating AI Report...
          </h3>
          <div style={{ background: 'rgba(0,0,0,0.5)', padding: '15px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '0.9rem', color: '#a78bfa' }}>
            {generateLogs.map((log, idx) => (
              <div key={idx} style={{ marginBottom: '5px' }}>
                <span style={{ color: '#34d399' }}>[{new Date().toLocaleTimeString()}]</span> {log.msg}
              </div>
            ))}
          </div>
        </div>
      )}
      
      {report ? (
        <div style={{ display: 'flex', gap: '30px' }}>
          <div style={{ flex: 3 }}>
             <ReportViewer report={report} ticker={ticker} />
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', position: 'sticky', top: '80px', height: 'calc(100vh - 120px)' }}>
             <AnalystNotes ticker={ticker} />
          </div>
        </div>
      ) : (
        !isGenerating && (
          <div className="glass-card" style={{ padding: '40px', textAlign: 'center', color: 'var(--text-secondary)' }}>
            <FileText size={48} style={{ opacity: 0.2, marginBottom: '20px' }} />
            <h3>No Report Available</h3>
            <p>Click "Generate AI Report" to create a new research report for this company.</p>
          </div>
        )
      )}

      {showNoDocsModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="glass-card" style={{ padding: '30px', maxWidth: '400px', width: '90%', textAlign: 'center' }}>
            <div style={{ color: '#fbbf24', marginBottom: '15px', display: 'flex', justifyContent: 'center' }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><path d="m21.73 18-8-14a2 2 0 0 0-3.48 0l-8 14A2 2 0 0 0 4 21h16a2 2 0 0 0 1.73-3Z"></path><line x1="12" y1="9" x2="12" y2="13"></line><line x1="12" y1="17" x2="12.01" y2="17"></line></svg>
            </div>
            <h3 style={{ marginBottom: '15px', color: 'var(--text-primary)' }}>No Documents Ingested</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '25px', lineHeight: '1.5' }}>
              You need to ingest financial documents for <b>{ticker}</b> before generating an AI report. The AI needs source material to analyze.
            </p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <button onClick={() => setShowNoDocsModal(false)} className="btn-primary" style={{ background: 'transparent', border: '1px solid var(--border)' }}>
                Cancel
              </button>
              <Link to="/documents" className="btn-primary" style={{ textDecoration: 'none' }}>
                Go to Documents
              </Link>
            </div>
          </div>
        </div>
      )}

      {showUnknownTickerModal && (
        <div style={{
          position: 'fixed', top: 0, left: 0, right: 0, bottom: 0,
          backgroundColor: 'rgba(0,0,0,0.7)', backdropFilter: 'blur(4px)',
          display: 'flex', alignItems: 'center', justifyContent: 'center', zIndex: 1000
        }}>
          <div className="glass-card" style={{ padding: '30px', maxWidth: '400px', width: '90%', textAlign: 'center' }}>
            <div style={{ color: '#ef4444', marginBottom: '15px', display: 'flex', justifyContent: 'center' }}>
              <svg xmlns="http://www.w3.org/2000/svg" width="48" height="48" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2" strokeLinecap="round" strokeLinejoin="round"><circle cx="12" cy="12" r="10"></circle><line x1="12" y1="8" x2="12" y2="12"></line><line x1="12" y1="16" x2="12.01" y2="16"></line></svg>
            </div>
            <h3 style={{ marginBottom: '15px', color: 'var(--text-primary)' }}>Unknown Ticker</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '25px', lineHeight: '1.5' }}>
              We couldn't find any financial data for the ticker <b>{ticker}</b>. Please check the symbol and try again.
            </p>
            <div style={{ display: 'flex', gap: '10px', justifyContent: 'center' }}>
              <Link to="/" className="btn-primary" style={{ textDecoration: 'none' }}>
                Go to Dashboard
              </Link>
            </div>
          </div>
        </div>
      )}
    </div>
  );
}
