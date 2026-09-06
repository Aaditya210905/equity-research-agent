import React from 'react';
import { Shield, BrainCircuit, Activity, Database, FileText, Bot, Target, Globe, Landmark, Newspaper, GitCompare } from 'lucide-react';
import logo from '../assets/logo.png';

export default function AboutUs() {
  const features = [
    { icon: <Database size={24} />, title: "Comprehensive Data", desc: "Real-time market snapshots, historical price trends, and deep company fundamentals." },
    { icon: <Globe size={24} />, title: "BSE India Integration", desc: "Direct fetching of annual reports, quarterly results, and announcements from the Bombay Stock Exchange." },
    { icon: <Landmark size={24} />, title: "SEC EDGAR Filings", desc: "Seamless access to US 10-K and 10-Q filings for complete fundamental research." },
    { icon: <Newspaper size={24} />, title: "Live News Aggregation", desc: "Curated, real-time financial news aggregated across Yahoo Finance, Google News, and Bing." },
    { icon: <GitCompare size={24} />, title: "Company Comparison", desc: "Side-by-side analysis of financial metrics, valuations, and performance across peers." },
    { icon: <Bot size={24} />, title: "AI Research Assistant", desc: "LangGraph-powered AI using RAG to query complex reports and synthesize exact insights." }
  ];

  const goals = [
    "Democratize access to institutional-grade financial data",
    "Automate the extraction of relevant information from lengthy reports",
    "Provide a unified workspace for cross-market (US & India) equity research",
    "Compare peer companies dynamically across multiple fundamental dimensions",
    "Trace all AI-generated insights back to their original SEC/BSE source documents"
  ];

  return (
    <div style={{ maxWidth: '1100px', margin: '0 auto', padding: '40px 20px', color: 'var(--text-primary)' }}>
      {/* Hero Section */}
      <div style={{ textAlign: 'center', marginBottom: '60px' }}>
        <img src={logo} alt="EQUAILENS Logo" style={{ height: '90px', marginBottom: '20px' }} />
        <h1 style={{ fontSize: '2.8rem', marginBottom: '15px', background: 'linear-gradient(90deg, #3b82f6, #8b5cf6)', WebkitBackgroundClip: 'text', WebkitTextFillColor: 'transparent' }}>
          Welcome to EquAiLens
        </h1>
        <p style={{ fontSize: '1.2rem', color: 'var(--text-secondary)', maxWidth: '750px', margin: '0 auto', lineHeight: '1.6' }}>
          <b>EQUAILENS</b> is an autonomous, AI-powered equity research platform designed to help investors, analysts, and researchers cut through the noise of financial markets.
        </p>
      </div>

      {/* Intro text */}
      <div className="glass-card" style={{ padding: '30px', marginBottom: '50px', fontSize: '1.1rem', lineHeight: '1.7', borderLeft: '4px solid var(--accent)' }}>
        <p style={{ margin: 0 }}>
          Unlike standard AI chatbots, EQUAILENS is built on a specialized <b>Agentic Workflow (LangGraph)</b>. It actively reaches out to external APIs, fetches multi-market financial data (US & India), parses native SEC/BSE filings, aggregates global news, and uses Retrieval-Augmented Generation (RAG) to ground every piece of analysis in absolute fact.
        </p>
      </div>

      {/* Features Grid */}
      <div style={{ marginBottom: '70px' }}>
        <h2 style={{ fontSize: '1.8rem', marginBottom: '30px', display: 'flex', alignItems: 'center', gap: '10px', justifyContent: 'center' }}>
          <BrainCircuit color="var(--accent)" /> Powerful Features Under the Hood
        </h2>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(300px, 1fr))', gap: '25px' }}>
          {features.map((feature, idx) => (
            <div key={idx} className="glass-card" style={{ padding: '25px', display: 'flex', gap: '20px', alignItems: 'flex-start', transition: 'transform 0.2s', cursor: 'default' }} onMouseOver={e => e.currentTarget.style.transform = 'translateY(-5px)'} onMouseOut={e => e.currentTarget.style.transform = 'none'}>
              <div style={{ color: 'var(--accent)', background: 'rgba(59, 130, 246, 0.1)', padding: '12px', borderRadius: '12px' }}>
                {feature.icon}
              </div>
              <div>
                <h4 style={{ marginBottom: '8px', fontSize: '1.1rem', color: 'var(--text-primary)' }}>{feature.title}</h4>
                <p style={{ fontSize: '0.9rem', color: 'var(--text-secondary)', margin: 0, lineHeight: '1.5' }}>{feature.desc}</p>
              </div>
            </div>
          ))}
        </div>
      </div>

      {/* Our Goal & Responsible AI */}
      <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(400px, 1fr))', gap: '30px', marginBottom: '60px' }}>
        <div className="glass-card" style={{ padding: '40px' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '25px', display: 'flex', alignItems: 'center', gap: '10px' }}>
            <Target color="var(--accent)" /> Our Mission
          </h2>
          <p style={{ color: 'var(--text-secondary)', marginBottom: '25px', lineHeight: '1.6' }}>
            Our mission is to make advanced equity research <b>more accessible, transparent, and significantly faster</b> by combining traditional financial models with state-of-the-art AI parsing.
          </p>
          <ul style={{ paddingLeft: '20px', color: 'var(--text-primary)', lineHeight: '1.8' }}>
            {goals.map((goal, idx) => (
              <li key={idx} style={{ marginBottom: '10px' }}>{goal}</li>
            ))}
          </ul>
        </div>

        <div className="glass-card" style={{ padding: '40px', background: 'linear-gradient(135deg, rgba(15,23,42,0.9) 0%, rgba(30,41,59,0.9) 100%)', border: '1px solid rgba(16, 185, 129, 0.2)' }}>
          <h2 style={{ fontSize: '1.5rem', marginBottom: '25px', display: 'flex', alignItems: 'center', gap: '10px', color: '#10b981' }}>
            <Shield color="#10b981" /> Built with Responsible AI
          </h2>
          <p style={{ color: 'var(--text-secondary)', lineHeight: '1.7', marginBottom: '20px' }}>
            EQUAILENS is designed with an uncompromising emphasis on <b>accuracy, transparency, and verifiability</b>. Every piece of analysis is tied to the raw filings downloaded directly from government or exchange servers.
          </p>
          <p style={{ color: 'var(--text-secondary)', lineHeight: '1.7' }}>
            However, LLM hallucinations and data delays can still occur. <b>We encourage all users to independently verify information</b> by checking the source documents provided in the platform before making any financial decisions.
          </p>
        </div>
      </div>

      {/* Disclaimer */}
      <div style={{ background: 'rgba(251, 191, 36, 0.05)', border: '1px solid rgba(251, 191, 36, 0.3)', padding: '30px', borderRadius: '12px', textAlign: 'center' }}>
        <h3 style={{ color: '#fbbf24', margin: '0 0 15px 0', fontSize: '1.3rem', display: 'flex', alignItems: 'center', justifyContent: 'center', gap: '10px' }}>
          ⚠️ Important Disclaimer
        </h3>
        <p style={{ color: 'var(--text-secondary)', lineHeight: '1.6', marginBottom: '15px', maxWidth: '800px', margin: '0 auto 15px auto' }}>
          EQUAILENS provides AI-generated financial research for <b>educational and informational purposes only</b>. It does not constitute investment, financial, or personalized advice, nor does it constitute a recommendation to buy, sell, or hold any security.
        </p>
        <p style={{ color: 'var(--text-primary)', fontWeight: 'bold', margin: 0 }}>
          Investments are subject to market risks, including the possible loss of principal. Past performance does not guarantee future results.
        </p>
      </div>

      {/* Footer Tagline */}
      <div style={{ textAlign: 'center', marginTop: '60px', paddingBottom: '40px', color: 'var(--text-secondary)', fontSize: '1.1rem' }}>
        <p><b>EQUAILENS</b> — Research smarter. Verify the evidence. Decide for yourself.</p>
      </div>

    </div>
  );
}
