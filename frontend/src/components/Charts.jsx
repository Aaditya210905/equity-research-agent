import React from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer } from 'recharts';

export function RevenueChart({ data }) {
  if (!data || !data.labels) return null;
  const chartData = data.labels.map((label, i) => ({
    name: label,
    Revenue: data.revenue[i]
  }));

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis dataKey="name" stroke="#94a3b8" />
          <YAxis stroke="#94a3b8" tickFormatter={(v) => `$${(v/1e9).toFixed(1)}B`} />
          <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }} />
          <Legend />
          <Line type="monotone" dataKey="Revenue" stroke="#3b82f6" strokeWidth={3} dot={{ r: 4 }} activeDot={{ r: 8 }} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}

export function MarginChart({ data }) {
  if (!data || !data.labels) return null;
  const chartData = data.labels.map((label, i) => ({
    name: label,
    'Net Margin': data.net_margin[i],
    'Op Margin': data.op_margin[i]
  }));

  return (
    <div style={{ width: '100%', height: 300 }}>
      <ResponsiveContainer>
        <LineChart data={chartData}>
          <CartesianGrid strokeDasharray="3 3" stroke="rgba(255,255,255,0.1)" />
          <XAxis dataKey="name" stroke="#94a3b8" />
          <YAxis stroke="#94a3b8" tickFormatter={(v) => `${v}%`} />
          <Tooltip contentStyle={{ backgroundColor: '#1e293b', border: 'none', borderRadius: '8px', color: '#fff' }} />
          <Legend />
          <Line type="monotone" dataKey="Net Margin" stroke="#10b981" strokeWidth={3} />
          <Line type="monotone" dataKey="Op Margin" stroke="#f59e0b" strokeWidth={3} />
        </LineChart>
      </ResponsiveContainer>
    </div>
  );
}
