import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ReportViewer from '../components/ReportViewer';
import Chatbot from '../components/Chatbot';
import { Download, RefreshCw, FileText, CheckCircle2 } from 'lucide-react';

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
    <div className="glass-card">
      <h4>Analyst Notes</h4>
      
      <div style={{ maxHeight: '300px', overflowY: 'auto', marginBottom: '15px' }}>
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
        style={{ width: '100%', height: '100px', background: 'rgba(0,0,0,0.2)', border: '1px solid var(--border)', borderRadius: '8px', color: 'white', padding: '10px', fontFamily: 'inherit' }} 
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
  const [loading, setLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateLogs, setGenerateLogs] = useState([]);
  
  const marketData = companyInfo?.market_data;

  useEffect(() => {
    fetchLatestReport();
    fetchCompanyData();
  }, [ticker]);

  const fetchCompanyData = async () => {
    try {
      const compRes = await fetch(`http://localhost:8000/company/${ticker}`);
      if (compRes.ok) setCompanyInfo(await compRes.json());
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
    if (num >= 1e12) return `$${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `$${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `$${(num / 1e6).toFixed(2)}M`;
    return `$${num.toLocaleString()}`;
  };

  if (loading && !companyInfo) return <div>Loading workspace...</div>;

  return (
    <div className="company-workspace">
      <div className="top-bar" style={{ marginBottom: '15px' }}>
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            {companyInfo?.profile ? companyInfo.profile.company_name : ticker} 
            <span style={{ fontSize: '1.2rem', color: 'var(--text-secondary)' }}>{ticker}</span>
          </h2>
          <p style={{ color: 'var(--text-secondary)' }}>
            {companyInfo?.profile ? `${companyInfo.profile.sector} • ${companyInfo.profile.industry}` : 'Advanced AI Research Dashboard'}
          </p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          {!isGenerating && (
            <button className="btn-primary" onClick={handleGenerate} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <RefreshCw size={16} /> Generate AI Report
            </button>
          )}
          {report && (
            <div className="export-bar" style={{ display: 'flex', gap: '5px' }}>
              <button onClick={() => handleExport('pdf')} className="btn-primary" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }} title="Export PDF"><Download size={16}/></button>
              <button onClick={() => handleExport('docx')} className="btn-primary" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>DOCX</button>
            </div>
          )}
        </div>
      </div>

      <div style={{ display: 'flex', gap: '20px', marginBottom: '30px' }}>
        {/* Market Data KPI Grid */}
        {marketData && (() => {
          const currency = companyInfo?.profile?.currency;
          const sym = currency === 'INR' ? '₹' : (currency === 'USD' ? '$' : (currency === 'EUR' ? '€' : (currency === 'GBP' ? '£' : (currency ? `${currency} ` : '$'))));
          
          return (
            <div style={{ flex: 1, display: 'grid', gridTemplateColumns: 'repeat(3, 1fr)', gap: '15px' }}>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Current Price</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{sym}{marketData.current_price}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Previous Close</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{sym}{marketData.previous_close ?? 'N/A'}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Open</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{sym}{marketData.open ?? 'N/A'}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Market Cap</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{sym}{formatNumber(companyInfo?.profile?.market_cap)}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>P/E Ratio (TTM)</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{marketData.pe_ratio ?? 'N/A'}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Forward P/E</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{marketData.forward_pe ?? 'N/A'}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>52W Range</h4>
                <div className="value" style={{ fontSize: '1.1rem', color: 'var(--text-primary)', marginTop: '5px' }}>
                  {sym}{marketData.fifty_two_week_low ?? '-'} - {sym}{marketData.fifty_two_week_high ?? '-'}
                </div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Day's Range</h4>
                <div className="value" style={{ fontSize: '1.1rem', color: 'var(--text-primary)', marginTop: '5px' }}>
                  {sym}{marketData.day_low ?? '-'} - {sym}{marketData.day_high ?? '-'}
                </div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Volume</h4>
                <div className="value" style={{ fontSize: '1.1rem', color: 'var(--text-primary)' }}>{marketData.volume?.toLocaleString() || 'N/A'}</div>
                <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '5px' }}>Avg: {marketData.average_volume?.toLocaleString() || 'N/A'}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Div Yield</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{marketData.dividend_yield ? `${marketData.dividend_yield}%` : 'N/A'}</div>
              </div>
              <div className="glass-card" style={{ padding: '15px' }}>
                <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>Beta</h4>
                <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{marketData.beta ?? 'N/A'}</div>
              </div>
            </div>
          );
        })()}
        
        {/* Company Overview Card */}
        {companyInfo?.profile && (
          <div className="glass-card" style={{ flex: 2, padding: '20px', overflowY: 'auto', maxHeight: '200px' }}>
            <h3 style={{ marginBottom: '10px', fontSize: '1.1rem' }}>Company Overview</h3>
            <div style={{ display: 'flex', gap: '20px', marginBottom: '10px', fontSize: '0.9rem', color: 'var(--text-secondary)' }}>
              <div><strong>Exchange:</strong> {companyInfo.profile.exchange}</div>
              <div><strong>Country:</strong> {companyInfo.profile.country}</div>
              <div><strong>Employees:</strong> {companyInfo.profile.employees?.toLocaleString() || 'N/A'}</div>
              <div><strong>Website:</strong> <a href={companyInfo.profile.website} target="_blank" rel="noreferrer" style={{ color: 'var(--accent)', textDecoration: 'none' }}>{companyInfo.profile.website}</a></div>
            </div>
            <p style={{ fontSize: '0.9rem', lineHeight: '1.5', color: 'var(--text-primary)' }}>
              {companyInfo.profile.description}
            </p>
          </div>
        )}
      </div>
      
      {isGenerating && (
        <div className="glass-card" style={{ marginBottom: '30px', borderLeft: '4px solid var(--accent)' }}>
          <h3 style={{ marginBottom: '15px', display: 'flex', alignItems: 'center', gap: '10px' }}>
             <RefreshCw size={18} className="spin" /> Generating AI Report...
          </h3>
          <div style={{ background: 'rgba(0,0,0,0.5)', padding: '15px', borderRadius: '8px', fontFamily: 'monospace', fontSize: '0.9rem', color: '#a78bfa' }}>
             {generateLogs.map((log, i) => (
                <div key={i} style={{ display: 'flex', gap: '10px', alignItems: 'center', margin: '5px 0' }}>
                   <CheckCircle2 size={14} color="var(--success)" /> {log.msg}
                </div>
             ))}
             <div className="typing-indicator" style={{ color: 'var(--text-secondary)' }}>Gathering data...</div>
          </div>
        </div>
      )}

      {report ? (
        <div style={{ display: 'flex', gap: '30px' }}>
          <div style={{ flex: 3 }}>
             <ReportViewer report={report} />
          </div>
          <div style={{ flex: 1, display: 'flex', flexDirection: 'column', gap: '20px' }}>
             <AnalystNotes ticker={ticker} />
             <Chatbot ticker={ticker} />
          </div>
        </div>
      ) : (
        !isGenerating && (
          <div className="glass-card" style={{ textAlign: 'center', padding: '50px' }}>
            <FileText size={48} style={{ color: 'var(--text-secondary)', marginBottom: '20px' }} />
            <h3>No report available for {ticker}</h3>
            <p style={{ color: 'var(--text-secondary)', marginBottom: '20px' }}>Generate a new report to begin your analysis.</p>
            <button className="btn-primary" onClick={handleGenerate}>Run Research Pipeline</button>
          </div>
        )
      )}
    </div>
  );
}
