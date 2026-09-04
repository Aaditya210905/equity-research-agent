import React, { useState, useRef, useEffect } from 'react';
import { useAuth } from '../context/AuthContext';
import { Send, Bot, User, Loader2 } from 'lucide-react';

export default function Chatbot({ ticker }) {
  const { token } = useAuth();
  const [messages, setMessages] = useState([]);
  const [input, setInput] = useState('');
  const [isTyping, setIsTyping] = useState(false);
  const messagesEndRef = useRef(null);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isTyping]);

  const handleSend = async (e) => {
    e.preventDefault();
    if (!input.trim()) return;

    const userMsg = input;
    setInput('');
    setMessages(prev => [...prev, { role: 'user', text: userMsg }]);
    setIsTyping(true);

    try {
      const res = await fetch(`http://localhost:8000/ask/stream`, {
        method: 'POST',
        headers: { 
          'Content-Type': 'application/json',
          Authorization: `Bearer ${token}` 
        },
        body: JSON.stringify({
          question: userMsg,
          company: ticker,
          year: 0,
          doc_type: "string",
          top_k: 5,
          rewrite_query: true
        })
      });

      if (!res.ok) throw new Error("Failed to connect to AI");

      const reader = res.body.getReader();
      const decoder = new TextDecoder('utf-8');
      
      let aiResponseText = "";
      
      // Add empty AI message first
      setMessages(prev => [...prev, { role: 'assistant', text: '' }]);

      while (true) {
        const { value, done } = await reader.read();
        if (done) break;
        
        const chunk = decoder.decode(value);
        const lines = chunk.split('\n');
        
        for (let line of lines) {
          if (line.startsWith('data: ')) {
            const dataStr = line.substring(6);
            if (dataStr === '[DONE]') break;
            
            try {
              const dataObj = JSON.parse(dataStr);
              if (dataObj.node === "error") {
                aiResponseText = "Error: " + (dataObj.data?.error || "Unknown error occurred.");
              } else if (dataObj.node === "done") {
                // stream finished
              } else if (dataObj.data) {
                // If the state update contains the answer, use it
                if (dataObj.data.answer) {
                  aiResponseText = dataObj.data.answer;
                } else if (!aiResponseText) {
                  // Show intermediate status if answer is not yet generated
                  const statusMap = {
                    classify: "Understanding question...",
                    expand: "Formulating search queries...",
                    retrieve: "Searching documents...",
                    build_context: "Reading sources...",
                    build_prompt: "Preparing response...",
                    generate_answer: "Generating answer...",
                    compute_confidence: "Verifying...",
                    respond_insufficient: "Not enough information found.",
                    respond: "Finalizing response..."
                  };
                  if (statusMap[dataObj.node]) {
                    aiResponseText = `*${statusMap[dataObj.node]}*`;
                  }
                }
              }

              // Update the last message if we have text to show
              if (aiResponseText) {
                setMessages(prev => {
                  const newMsgs = [...prev];
                  newMsgs[newMsgs.length - 1].text = aiResponseText;
                  return newMsgs;
                });
              }
            } catch (e) { console.error("Parse error", e); }
          }
        }
      }
    } catch (e) {
      console.error(e);
      setMessages(prev => [...prev, { role: 'assistant', text: 'Error connecting to the Research Assistant.' }]);
    } finally {
      setIsTyping(false);
    }
  };

  return (
    <div className="glass-card" style={{ height: '500px', display: 'flex', flexDirection: 'column', padding: 0, overflow: 'hidden' }}>
      <div style={{ padding: '15px 20px', borderBottom: '1px solid var(--border)', background: 'rgba(255,255,255,0.02)' }}>
        <h3 style={{ display: 'flex', alignItems: 'center', gap: '10px', margin: 0 }}>
          <Bot size={20} color="var(--accent)" /> {ticker} Research Assistant
        </h3>
        <p style={{ margin: 0, fontSize: '0.8rem', color: 'var(--text-secondary)' }}>Ask factual questions based on ingested documents.</p>
      </div>
      
      <div style={{ flex: 1, overflowY: 'auto', padding: '20px', display: 'flex', flexDirection: 'column', gap: '15px' }}>
        {messages.length === 0 && (
          <div style={{ margin: 'auto', color: 'var(--text-secondary)', textAlign: 'center' }}>
            <Bot size={40} style={{ opacity: 0.2, marginBottom: '10px' }} />
            <p>Ask anything about {ticker}'s financials, risks, or performance.</p>
          </div>
        )}
        
        {messages.map((msg, idx) => (
          <div key={idx} style={{ 
            alignSelf: msg.role === 'user' ? 'flex-end' : 'flex-start',
            maxWidth: '80%',
            background: msg.role === 'user' ? 'var(--accent)' : 'rgba(255,255,255,0.1)',
            padding: '10px 15px',
            borderRadius: '12px',
            borderBottomRightRadius: msg.role === 'user' ? 0 : '12px',
            borderBottomLeftRadius: msg.role === 'assistant' ? 0 : '12px',
            color: msg.role === 'user' ? 'white' : 'var(--text-primary)',
            lineHeight: 1.5
          }}>
            {msg.role === 'assistant' && <Bot size={14} style={{ marginBottom: '5px', opacity: 0.5 }} />}
            {msg.role === 'user' && <User size={14} style={{ marginBottom: '5px', opacity: 0.5 }} />}
            <div>{msg.text}</div>
          </div>
        ))}
        {isTyping && (
          <div style={{ alignSelf: 'flex-start', color: 'var(--text-secondary)', display: 'flex', alignItems: 'center', gap: '5px' }}>
             <Loader2 size={14} className="spin" /> Thinking...
          </div>
        )}
        <div ref={messagesEndRef} />
      </div>

      <div style={{ padding: '15px', borderTop: '1px solid var(--border)', background: 'rgba(0,0,0,0.2)' }}>
        <form onSubmit={handleSend} style={{ display: 'flex', gap: '10px' }}>
          <input
            type="text"
            value={input}
            onChange={(e) => setInput(e.target.value)}
            placeholder={`Ask about ${ticker}...`}
            style={{ flex: 1, padding: '10px', borderRadius: '8px', border: '1px solid var(--border)', background: 'rgba(255,255,255,0.05)', color: 'white' }}
            disabled={isTyping}
          />
          <button type="submit" className="btn-primary" disabled={isTyping} style={{ padding: '10px 15px' }}>
            <Send size={18} />
          </button>
        </form>
      </div>
    </div>
  );
}
