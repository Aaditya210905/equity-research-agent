import React from 'react';

export default function MarketDataGrid({ marketData }) {
  if (!marketData) return null;

  const currency = marketData.currency;
  const sym = currency === 'INR' ? '₹' : (currency === 'USD' ? '$' : (currency === 'EUR' ? '€' : (currency === 'GBP' ? '£' : (currency ? `${currency} ` : '$'))));

  const formatNumber = (num) => {
    if (num === null || num === undefined) return 'N/A';
    if (num >= 1e12) return `${(num / 1e12).toFixed(2)}T`;
    if (num >= 1e9) return `${(num / 1e9).toFixed(2)}B`;
    if (num >= 1e6) return `${(num / 1e6).toFixed(2)}M`;
    return `${num.toLocaleString()}`;
  };

  const formatDecimal = (num) => {
    if (num === null || num === undefined) return 'N/A';
    return Number(num).toFixed(2);
  };

  const { price, valuation, multiples, trading } = marketData;

  const Card = ({ title, value, subtext }) => (
    <div className="glass-card" style={{ padding: '15px' }}>
      <h4 style={{ fontSize: '0.85rem', color: 'var(--text-secondary)', marginBottom: '5px' }}>{title}</h4>
      <div className="value" style={{ fontSize: '1.2rem', color: 'var(--text-primary)' }}>{value !== null && value !== undefined ? value : 'N/A'}</div>
      {subtext && <div style={{ fontSize: '0.75rem', color: 'var(--text-secondary)', marginTop: '5px' }}>{subtext}</div>}
    </div>
  );

  return (
    <div style={{ display: 'flex', flexDirection: 'column', gap: '20px', flex: 1 }}>
      
      <div>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '10px' }}>Price & Trading</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '15px' }}>
          <Card title="Current Price" value={price.current ? `${sym}${formatDecimal(price.current)}` : 'N/A'} />
          <Card title="Previous Close" value={price.previous_close ? `${sym}${formatDecimal(price.previous_close)}` : 'N/A'} />
          <Card title="Open" value={price.open ? `${sym}${formatDecimal(price.open)}` : 'N/A'} />
          <Card title="Day's Range" value={price.low && price.high ? `${sym}${formatDecimal(price.low)} - ${sym}${formatDecimal(price.high)}` : 'N/A'} />
          <Card title="52W Range" value={trading.fifty_two_week_low && trading.fifty_two_week_high ? `${sym}${formatDecimal(trading.fifty_two_week_low)} - ${sym}${formatDecimal(trading.fifty_two_week_high)}` : 'N/A'} />
          <Card title="Volume" value={trading.volume ? trading.volume.toLocaleString() : 'N/A'} subtext={`Avg: ${trading.average_volume?.toLocaleString() || 'N/A'}`} />
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '10px' }}>Valuation</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '15px' }}>
          <Card title="Market Cap" value={valuation.market_cap ? `${sym}${formatNumber(valuation.market_cap)}` : 'N/A'} />
          <Card title="Enterprise Value" value={valuation.enterprise_value ? `${sym}${formatNumber(valuation.enterprise_value)}` : 'N/A'} />
          <Card title="Shares Outstanding" value={valuation.shares_outstanding ? formatNumber(valuation.shares_outstanding) : 'N/A'} />
        </div>
      </div>

      <div>
        <h3 style={{ fontSize: '1.1rem', marginBottom: '10px' }}>Multiples & Returns</h3>
        <div style={{ display: 'grid', gridTemplateColumns: 'repeat(auto-fit, minmax(140px, 1fr))', gap: '15px' }}>
          <Card title="P/E Ratio (TTM)" value={formatDecimal(multiples.pe_ratio)} />
          <Card title="Forward P/E" value={formatDecimal(multiples.forward_pe)} />
          <Card title="PEG Ratio" value={formatDecimal(multiples.peg_ratio)} />
          <Card title="Price to Book" value={formatDecimal(multiples.price_to_book)} />
          <Card title="EPS (TTM)" value={multiples.eps ? `${sym}${formatDecimal(multiples.eps)}` : 'N/A'} />
          <Card title="Div Yield" value={trading.dividend_yield ? `${formatDecimal(trading.dividend_yield)}%` : 'N/A'} />
          <Card title="Beta" value={formatDecimal(trading.beta)} />
        </div>
      </div>

    </div>
  );
}
