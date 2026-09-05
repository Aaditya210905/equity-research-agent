import React, { useState, useEffect } from 'react';
import { useParams, Link } from 'react-router-dom';
import { ArrowLeft, Bot } from 'lucide-react';
import Chatbot from '../components/Chatbot';
import { useAuth } from '../context/AuthContext';

export default function ResearchAssistant() {
  const { ticker } = useParams();
  const { token } = useAuth();
  const [companyInfo, setCompanyInfo] = useState(null);
  const [showUnknownTickerModal, setShowUnknownTickerModal] = useState(false);

  useEffect(() => {
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
