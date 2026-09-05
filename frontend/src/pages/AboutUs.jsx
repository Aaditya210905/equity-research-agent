import React from 'react';
import { Shield, BrainCircuit, Activity, Database, FileText, Bot, Target } from 'lucide-react';
import logo from '../assets/logo.png';

export default function AboutUs() {
  const steps = [
    { icon: <Database size={24} />, title: "Data Collection", desc: "Gathering financial data and market metrics" },
    { icon: <FileText size={24} />, title: "Document Processing", desc: "Parsing complex reports and filings" },
    { icon: <BrainCircuit size={24} />, title: "RAG Retrieval", desc: "Semantic search for exact context" },
    { icon: <Activity size={24} />, title: "Financial Analysis", desc: "Deterministic financial calculations" },
    { icon: <Bot size={24} />, title: "AI Research", desc: "Context-aware reasoning and synthesis" }
  ];

  const goals = [
    "Understand complex financial information",
    "Explore company fundamentals",
    "Discover relevant information from lengthy reports",
    "Compare companies and financial metrics",
    "Identify important risks and opportunities",
    "Trace AI-generated insights back to their sources"
  ];

  return (
    <div style={{ maxWidth: '1000px', margin: '0 auto', padding: '40px 20px', color: 'var(--text-primary)' }}>
      {/* Hero Section */}
      <div style={{ textAlign: 'center', marginBottom: '60px' }}>
        <img src={logo} alt="EQUITYLENS Logo" style={{ height: '80px', marginBottom: '20px' }} />
        <h1 style={{ fontSize: '2.5rem', marginBottom: '15px', background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          AI-Powered Equity Research
        </h1>
        <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', maxWidth: '700px', margin: '0 auto', lineHeight: '1.6' }}>
          <b>EQUITYLENS</b> is an AI-powered equity research platform designed to help users explore companies, understand financial performance, and analyze publicly available financial information through an automated research workflow.
        </p>
      </div>

      {/* Intro text */}
      <div className="glass-card" style={{ padding: '30px', marginBottom: '40px', fontSize: '1.05rem', lineHeight: '1.7' }}>
        <p style={{ margin: 0 }}>
          Instead of simply generating answers from an AI model, EQUITYLENS combines <b>financial data, document-based research, semantic retrieval, deterministic financial calculations, and AI-driven analysis</b> to produce structured and evidence-grounded research reports.
        </p>
      </div>

      {/* How it Works */}
      <div style={{ marginBottom: '60px' }}>
        <h2 style={{ fontSize: '1.8rem', marginBottom: '30px', display: 'flex', alignItems: 'center', gap: '10px' }}>
          <BrainCircuit color="var(--accent)" /> How EQUITYLENS Works
        </h2>
        <p style={{ marginBottom: '25px', color: 'var(--text-secondary)' }}>EQUITYLENS follows an autonomous research workflow:</p>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(180px, 1fr))', gap: '20px' }}>
          {steps.map((step, idx) => (
            <div key={idx} className="glass-card" style={{ padding: '20px', textAlign: 'center', borderTop: '2px solid var(--accent)' }}>
              <div style={{ color: 'var(--accent)', marginBottom: '15px', display: 'flex', justifyContent: 'center' }}>{step.icon}</div>
              <h4 style={{ marginBottom: '10px', fontSize: '1rem' }}>{step.title}</h4>
              <p style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', margin: 0 }}>{step.desc}</p>
            </div>
          ))}
        </div>
      </div>

      {/* Our Goal & Responsible AI */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(350px, 1fr))', gap: '30px', marginBottom: '50px' }}>
        <div className="glass-card" style={{ padding: '30px' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Target color="var(--accent)" /> Our Goal
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '20px', lineHeight: '1.6' }}>
            Our goal is to make equity research <b>more accessible, transparent, and efficient</b> by combining traditional financial analysis with modern AI technologies.
          </p>
          <ul style={{ paddingLeft: '20px', color: 'var(--text-primary)', lineHeight: '1.8' }}>
            {goals.map((goal, idx) => (
              <li key={idx} style={{ marginBottom: '5px' }}>{goal}</li>
            ))}
          </ul>
        </div>

        <div className="glass-card" style={{ padding: '30px', background: 'linear-gradient(135deg, rgba(15,23,42,0.9) 0%, rgba(30,41,59,0.9) 100%)' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '20px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Shield color="#10b981" /> Built with Responsible AI
          </h2>
          <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '15px' }}>
            EQUITYLENS is designed with an emphasis on <b>accuracy, transparency, and verification</b>. The platform uses source citations and automated verification mechanisms to reduce unsupported AI-generated claims.
          </p>
          <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6' }}>
            However, AI systems and financial data sources can contain errors, omissions, delays, or inaccuracies. <b>Users should independently verify important information before relying on it.</b>
          </p>
        </div>
      </div>

      {/* Disclaimer */}
      <div style={{ background: 'rgba(251, 191, 36, 0.05)', border: '1px solid rgba(251, 191, 36, 0.3)', padding: '30px', borderRadius: '12px' }}>
        <h3 style={{ color: '#fbbf24', margin: '0 0 15px 0', fontSize: '1.3rem', display: 'flex', alignItems: 'center', gap: '10px' }}>
          ⚠️ Important Disclaimer
        </h3>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '15px' }}>
          EQUITYLENS provides AI-generated financial research for <b>educational and informational purposes only</b>. It does not constitute investment, financial, or personalized advice, nor does it constitute a recommendation to buy, sell, or hold any security.
        </p>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '15px' }}>
          EQUITYLENS does not assess an individual's financial circumstances, investment objectives, or risk tolerance. Users are responsible for their own investment decisions and should consult a qualified financial professional when personalized advice is required.
        </p>
        <p style={{ color: 'var(--text-primary)', fontWeight: 'bold', margin: 0 }}>
          Investments are subject to market risks, including the possible loss of principal. Past performance does not guarantee future results.
        </p>
      </div>

      {/* Footer Tagline */}
      <div style={{ textAlign: 'center', marginTop: '60px', color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
        <p><b>EQUITYLENS</b> — Research smarter. Verify the evidence. Decide for yourself.</p>
      </div>

    </div>
  );
}
