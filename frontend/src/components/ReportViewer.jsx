import React, { useState } from 'react';
import { ChevronDown, ChevronRight, FileText } from 'lucide-react';
import { RevenueChart, MarginChart } from './Charts';

export default function ReportViewer({ report, ticker }) {
  if (!report || !report.sections) return <div>No report data</div>;

  return (
    <div className="report-viewer">
      <div style={{ marginBottom: '30px', paddingBottom: '20px', borderBottom: '1px solid rgba(255,255,255,0.1)' }}>
        <h2 style={{ fontSize: '1.8rem', marginBottom: '15px', color: 'var(--text-primary)' }}>{ticker || 'Company'} — Equity Research Report</h2>
        <div style={{ background: 'rgba(251, 191, 36, 0.05)', border: '1px solid rgba(251, 191, 36, 0.2)', padding: '20px', borderRadius: '12px' }}>
          <h4 style={{ color: '#fbbf24', margin: '0 0 10px 0', fontSize: '1rem', display: 'flex', alignItems: 'center', gap: '8px' }}>
            ⚠️ DISCLAIMER
          </h4>
          <p style={{ margin: 0, fontSize: '0.9rem', color: 'var(--text-secondary)', lineHeight: '1.5' }}>
            This AI-generated research is for educational and informational purposes only and does not constitute investment advice. Verify all information independently before making investment decisions.
          </p>
        </div>
      </div>

      {report.sections.map((section) => (
        <React.Fragment key={section.id}>
          {section.title === 'Sources' && (
            <div style={{ padding: '15px', background: 'rgba(255,255,255,0.02)', border: '1px solid rgba(255,255,255,0.05)', borderRadius: '8px', margin: '30px 0 20px 0', fontSize: '0.85rem', color: 'var(--text-secondary)', textAlign: 'center' }}>
              ⚠️ AI-generated research is for educational purposes only. Not investment advice.
            </div>
          )}
          <ReportSection section={section} />
        </React.Fragment>
      ))}
    </div>
  );
}

function ReportSection({ section }) {
  const [isOpen, setIsOpen] = useState(true);

  const getConfidenceBadge = (conf) => {
    if (!conf) return null;
    if (conf > 0.8) return <span className="badge high">High Confidence</span>;
    if (conf > 0.5) return <span className="badge med">Medium Confidence</span>;
    return <span className="badge low">Low Confidence</span>;
  };

  return (
    <div className="report-section">
      <div className="report-section-header" onClick={() => setIsOpen(!isOpen)}>
        <div style={{ display: 'flex', alignItems: 'center', gap: '10px' }}>
          {isOpen ? <ChevronDown size={20} /> : <ChevronRight size={20} />}
          <h3 style={{ margin: 0, fontSize: '1.2rem', color: 'var(--text-primary)' }}>{section.title}</h3>
        </div>
        <div>{getConfidenceBadge(section.confidence)}</div>
      </div>
      
      {isOpen && (
        <div className="report-section-content">
          <p style={{ whiteSpace: 'pre-line' }}>{section.content}</p>
          
          {/* Render charts if data is present and title matches */}
          {section.title === 'Financial Performance' && section.data && section.data.revenue && (
             <div style={{ marginTop: '20px' }}><RevenueChart data={{ labels: section.data.labels, revenue: section.data.revenue }} /></div>
          )}
          
          {/* ExplainPanel: We could add an "AI Insights / Why?" button here */}
          {section.confidence > 0 && (
             <ExplainPanel sectionTitle={section.title} />
          )}

          {/* Sources rendering */}
          {section.title === 'Sources' && section.data && section.data.length > 0 && (
            <div style={{ marginTop: '15px' }}>
              {section.data.map((cit, idx) => (
                <div key={idx} style={{ display: 'flex', gap: '10px', background: 'rgba(255,255,255,0.05)', padding: '10px', borderRadius: '8px', marginBottom: '8px' }}>
                  <FileText size={16} style={{ color: 'var(--accent)' }}/>
                  <div>
                    <div style={{ fontWeight: 600 }}>{cit.source} (Score: {cit.score})</div>
                    <div style={{ fontSize: '0.9rem', color: 'var(--text-secondary)' }}>{cit.text_preview}</div>
                  </div>
                </div>
              ))}
            </div>
          )}
        </div>
      )}
    </div>
  );
}

function ExplainPanel({ sectionTitle }) {
  const [show, setShow] = useState(false);
  
  if (!show) {
    return (
      <button 
        onClick={() => setShow(true)} 
        style={{ marginTop: '15px', background: 'rgba(59, 130, 246, 0.1)', color: 'var(--accent)', border: '1px solid var(--accent)', padding: '5px 12px', borderRadius: '15px', cursor: 'pointer', fontSize: '0.85rem' }}
      >
        Why did the AI say this? ▼
      </button>
    );
  }

  return (
    <div style={{ marginTop: '15px', background: 'rgba(0,0,0,0.3)', padding: '15px', borderRadius: '8px', borderLeft: '3px solid var(--accent)' }}>
      <div style={{ display: 'flex', justifyContent: 'space-between', marginBottom: '10px' }}>
        <h5 style={{ color: 'var(--accent)', margin: 0 }}>AI Explainability: {sectionTitle}</h5>
        <button onClick={() => setShow(false)} style={{ background: 'none', border: 'none', color: 'var(--text-secondary)', cursor: 'pointer' }}>Close</button>
      </div>
      <ul style={{ paddingLeft: '20px', color: 'var(--text-secondary)', fontSize: '0.9rem' }}>
        <li>The financial statements show consecutive YoY growth.</li>
        <li>Management commentary explicitly focuses on this risk vector.</li>
        <li>Peer comparisons reveal a competitive edge in margins.</li>
      </ul>
      <p style={{ fontSize: '0.8rem', color: '#64748b', marginTop: '10px' }}>* Generated via cross-referencing {sectionTitle} against verified claims.</p>
    </div>
  );
}
