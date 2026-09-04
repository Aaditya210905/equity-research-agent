import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Bot } from 'lucide-react';
import Chatbot from '../components/Chatbot';
import { useAuth } from '../context/AuthContext';

export default function ResearchAssistant() {
  const { ticker } = useParams();
  const { token } = useAuth();
  const [companyInfo, setCompanyInfo] = useState(null);

  useEffect(() => {
    const fetchCompanyData = async () => {
      try {
        const compRes = await fetch(`http://localhost:8000/company/${ticker}`);
        if (compRes.ok) setCompanyInfo(await compRes.json());
      } catch (e) { console.error(e); }
    };
    fetchCompanyData();
  }, [ticker]);

  return (
    <div className="research-assistant-page" style={{ height: 'calc(100vh - 40px)', display: 'flex', flexDirection: 'column' }}>
      <div className="top-bar" style={{ marginBottom: '20px', display: 'flex', justifyContent: 'space-between', alignItems: 'center' }}>
        <div>
          <h2 style={{ display: 'flex', alignItems: 'center', gap: '15px' }}>
            <Bot size={28} style={{ color: 'var(--accent)' }} />
            Research Assistant
            <span style={{ fontSize: '1.2rem', color: 'var(--text-secondary)' }}>{ticker}</span>
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginTop: '5px' }}>
            {companyInfo?.profile ? companyInfo.profile.company_name : `Ask questions about ${ticker}'s ingested filings`}
          </p>
        </div>
        <div>
          <Link to={`/company/${ticker}`} className="btn-primary" style={{ display: 'flex', alignItems: 'center', gap: '8px', textDecoration: 'none', background: 'transparent', border: '1px solid var(--border)' }}>
            <ArrowLeft size={16} /> Back to Dashboard
          </Link>
        </div>
      </div>
      
      <div className="assistant-container" style={{ flex: 1, overflow: 'hidden', display: 'flex' }}>
         <div style={{ flex: 1, maxWidth: '1000px', margin: '0 auto', width: '100%', height: '100%' }}>
            <Chatbot ticker={ticker} />
         </div>
      </div>
    </div>
  );
}
