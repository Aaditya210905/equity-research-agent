import React, { useState, useEffect } from 'react';
import { useParams } from 'react-router-dom';
import { useAuth } from '../context/AuthContext';
import ReportViewer from '../components/ReportViewer';
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
  const [loading, setLoading] = useState(true);
  const [isGenerating, setIsGenerating] = useState(false);
  const [generateLogs, setGenerateLogs] = useState([]);
  
  useEffect(() => {
    fetchLatestReport();
  }, [ticker]);

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
    
    // Connect to SSE stream
    const eventSource = new EventSource(`http://localhost:8000/research/${ticker}/stream`);
    
    let lastState = null;
    
    eventSource.onmessage = async (event) => {
      const data = JSON.parse(event.data);
      
      if (data.node === 'done') {
        eventSource.close();
        setGenerateLogs(prev => [...prev, { node: 'done', msg: 'Verification complete. Assembling 12-section report...' }]);
        
        // After stream is done, POST to format_and_save using the last State
        if (lastState) {
          try {
            const res = await fetch(`http://localhost:8000/workspace/report/${ticker}/format_and_save`, {
              method: 'POST',
              headers: { 
                'Content-Type': 'application/json',
                Authorization: `Bearer ${token}` 
              },
              body: JSON.stringify(lastState)
            });
            
            if (res.ok) {
              await fetchLatestReport();
            }
          } catch (e) {
             console.error("Format save error", e);
          }
        }
        setIsGenerating(false);
      } else if (data.node === 'error') {
        eventSource.close();
        setGenerateLogs(prev => [...prev, { node: 'error', msg: `Error: ${data.data.error}` }]);
        setIsGenerating(false);
      } else {
        setGenerateLogs(prev => [...prev, { node: data.node, msg: `Completed node: ${data.node}` }]);
        lastState = data.data; // Capture state as it flows
      }
    };
    
    eventSource.onerror = (e) => {
      eventSource.close();
      setIsGenerating(false);
    };
  };

  const handleExport = (format) => {
    window.open(`http://localhost:8000/workspace/report/${ticker}/export/${format}?token=${token}`, '_blank');
  };

  if (loading) return <div>Loading workspace...</div>;

  return (
    <div className="company-workspace">
      <div className="top-bar">
        <div>
          <h2>{report ? report.metadata.company : ticker} Workspace</h2>
          <p style={{ color: 'var(--text-secondary)' }}>Advanced AI Research Dashboard</p>
        </div>
        <div style={{ display: 'flex', gap: '10px' }}>
          {!isGenerating && (
            <button className="btn-primary" onClick={handleGenerate} style={{ display: 'flex', gap: '8px', alignItems: 'center' }}>
              <RefreshCw size={16} /> Generate New Report
            </button>
          )}
          {report && (
            <div className="export-bar" style={{ display: 'flex', gap: '5px' }}>
              <button onClick={() => handleExport('pdf')} className="btn-primary" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}><Download size={16}/></button>
              <button onClick={() => handleExport('docx')} className="btn-primary" style={{ background: 'var(--bg-card)', border: '1px solid var(--border)' }}>DOCX</button>
            </div>
          )}
        </div>
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
          <div style={{ flex: 1 }}>
             <AnalystNotes ticker={ticker} />
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
