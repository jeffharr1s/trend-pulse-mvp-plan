import { useState, useEffect, useCallback } from 'react';

const API_URL = '/api/trends';
const ALERT_URL = '/api/alert';

export default function App() {
  const [trends, setTrends] = useState([]);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState(null);
  const [filter, setFilter] = useState('all');
  const [lastUpdate, setLastUpdate] = useState(null);
  const [alertsEnabled, setAlertsEnabled] = useState(false);
  const [alertStatus, setAlertStatus] = useState(null);

  const getSignal = (momentum, sentiment) => {
    if (momentum >= 70 && sentiment > 0.2) return { label: 'BUY', color: '#22c55e', bg: '#dcfce7' };
    if (momentum <= 30 || sentiment < -0.3) return { label: 'SELL', color: '#ef4444', bg: '#fee2e2' };
    if (momentum >= 50) return { label: 'WATCH', color: '#f59e0b', bg: '#fef3c7' };
    return { label: 'HOLD', color: '#6b7280', bg: '#f3f4f6' };
  };

  const getMomentumColor = (m) => {
    if (m >= 70) return '#22c55e';
    if (m >= 50) return '#f59e0b';
    if (m >= 30) return '#6b7280';
    return '#ef4444';
  };

  const fetchTrends = useCallback(async () => {
    try {
      setLoading(true);
      const res = await fetch(API_URL);
      if (!res.ok) throw new Error(`API error: ${res.status}`);
      const data = await res.json();
      const newTrends = data.trends || [];
      setTrends(newTrends);
      setLastUpdate(new Date().toLocaleTimeString());
      setError(null);
      
      // Auto-alert on strong BUY signals
      if (alertsEnabled) {
        newTrends.forEach(t => {
          const signal = getSignal(t.momentum, t.sentiment);
          if (signal.label === 'BUY' && t.momentum >= 75) {
            sendAlert(t, signal.label);
          }
        });
      }
    } catch (err) {
      setError(err.message);
    } finally {
      setLoading(false);
    }
  }, [alertsEnabled]);
  
  const sendAlert = async (trend, signal) => {
    try {
      const res = await fetch(ALERT_URL, {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          ticker: trend.ticker,
          signal,
          momentum: trend.momentum,
          sentiment: trend.sentiment,
          source: trend.source,
          channels: ['discord', 'email']
        })
      });
      const data = await res.json();
      setAlertStatus({
        ticker: trend.ticker,
        success: data.sent,
        message: data.sent ? `Alert sent for ${trend.ticker}` : data.reason || 'Not sent'
      });
      setTimeout(() => setAlertStatus(null), 3000);
    } catch (err) {
      setAlertStatus({ ticker: trend.ticker, success: false, message: err.message });
      setTimeout(() => setAlertStatus(null), 3000);
    }
  };

  useEffect(() => {
    fetchTrends();
    const interval = setInterval(fetchTrends, 60000);
    return () => clearInterval(interval);
  }, [fetchTrends]);

  const filteredTrends = trends.filter(t => 
    filter === 'all' || t.source === filter || (filter === 'multi' && t.source === 'multi')
  );

  const sources = [
    { key: 'all', label: '📊 All', enabled: true },
    { key: 'stocktwits', label: '💬 Stocktwits', enabled: true },
    { key: 'twitter', label: '𝕏 Twitter', enabled: true },
    { key: 'multi', label: '🔗 Multi-Source', enabled: true },
  ];

  return (
    <div style={{ minHeight: '100vh', background: '#0f172a', color: '#f1f5f9', fontFamily: 'system-ui, sans-serif' }}>
      {/* Header */}
      <header style={{ padding: '20px 24px', borderBottom: '1px solid #1e293b', display: 'flex', justifyContent: 'space-between', alignItems: 'center', flexWrap: 'wrap', gap: '12px' }}>
        <div>
          <h1 style={{ margin: 0, fontSize: '24px', fontWeight: 700 }}>📊 TrendPulse</h1>
          <p style={{ margin: '4px 0 0', fontSize: '14px', color: '#94a3b8' }}>
            Real-time social sentiment • Stocktwits + X
          </p>
        </div>
        <div style={{ display: 'flex', gap: '12px', alignItems: 'center' }}>
          {lastUpdate && <span style={{ fontSize: '12px', color: '#64748b' }}>Updated: {lastUpdate}</span>}
          <button 
            onClick={() => setAlertsEnabled(!alertsEnabled)}
            style={{ 
              padding: '8px 16px', 
              background: alertsEnabled ? '#22c55e' : '#334155', 
              border: 'none', 
              borderRadius: '6px', 
              color: 'white', 
              cursor: 'pointer', 
              fontSize: '14px' 
            }}
          >
            {alertsEnabled ? '🔔 Alerts ON' : '🔕 Alerts OFF'}
          </button>
          <button 
            onClick={fetchTrends} 
            disabled={loading}
            style={{ padding: '8px 16px', background: '#3b82f6', border: 'none', borderRadius: '6px', color: 'white', cursor: 'pointer', fontSize: '14px' }}
          >
            {loading ? '⏳' : '🔄'} Refresh
          </button>
        </div>
      </header>

      {/* Alert Toast */}
      {alertStatus && (
        <div style={{ 
          position: 'fixed', top: '80px', right: '24px', padding: '12px 20px', 
          background: alertStatus.success ? '#166534' : '#991b1b', 
          borderRadius: '8px', fontSize: '14px', zIndex: 50, boxShadow: '0 4px 12px rgba(0,0,0,0.3)'
        }}>
          {alertStatus.success ? '✅' : '⚠️'} {alertStatus.message}
        </div>
      )}

      {/* Filters */}
      <div style={{ padding: '16px 24px', display: 'flex', gap: '8px', flexWrap: 'wrap' }}>
        {sources.map(s => (
          <button
            key={s.key}
            onClick={() => s.enabled && setFilter(s.key)}
            style={{
              padding: '6px 14px',
              background: filter === s.key ? '#3b82f6' : '#1e293b',
              border: 'none',
              borderRadius: '20px',
              color: filter === s.key ? 'white' : '#94a3b8',
              cursor: s.enabled ? 'pointer' : 'not-allowed',
              fontSize: '13px',
              opacity: s.enabled ? 1 : 0.5
            }}
          >
            {s.label}
          </button>
        ))}
        <span style={{ marginLeft: 'auto', fontSize: '13px', color: '#64748b' }}>
          {filteredTrends.length} tickers
        </span>
      </div>

      {/* Error */}
      {error && (
        <div style={{ margin: '0 24px', padding: '12px 16px', background: '#7f1d1d', borderRadius: '8px', fontSize: '14px' }}>
          ⚠️ {error}
        </div>
      )}

      {/* Trend Cards */}
      <main style={{ padding: '8px 24px 24px', display: 'grid', gridTemplateColumns: 'repeat(auto-fill, minmax(280px, 1fr))', gap: '16px' }}>
        {loading && trends.length === 0 ? (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '60px', color: '#64748b' }}>⏳ Loading trends...</div>
        ) : filteredTrends.length === 0 ? (
          <div style={{ gridColumn: '1 / -1', textAlign: 'center', padding: '60px', color: '#64748b' }}>No trends found.</div>
        ) : (
          filteredTrends.map((t, i) => {
            const signal = getSignal(t.momentum, t.sentiment);
            return (
              <div key={`${t.ticker}-${i}`} style={{ background: '#1e293b', borderRadius: '12px', padding: '16px', border: '1px solid #334155' }}>
                {/* Header */}
                <div style={{ display: 'flex', justifyContent: 'space-between', alignItems: 'flex-start', marginBottom: '12px' }}>
                  <div>
                    <span style={{ fontSize: '20px', fontWeight: 700 }}>{t.ticker}</span>
                    <span style={{ 
                      marginLeft: '8px', fontSize: '11px', padding: '2px 6px', 
                      background: t.source === 'stocktwits' ? '#1d9bf0' : t.source === 'multi' ? '#8b5cf6' : '#ff4500',
                      borderRadius: '4px'
                    }}>
                      {t.source === 'stocktwits' ? 'ST' : t.source === 'multi' ? 'Multi' : 'X'}
                    </span>
                  </div>
                  <span style={{ padding: '4px 10px', background: signal.bg, color: signal.color, borderRadius: '6px', fontSize: '12px', fontWeight: 600 }}>
                    {signal.label}
                  </span>
                </div>

                {/* Momentum */}
                <div style={{ marginBottom: '12px' }}>
                  <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '12px', color: '#94a3b8', marginBottom: '4px' }}>
                    <span>Momentum</span>
                    <span style={{ color: getMomentumColor(t.momentum), fontWeight: 600 }}>{t.momentum}/100</span>
                  </div>
                  <div style={{ height: '6px', background: '#334155', borderRadius: '3px', overflow: 'hidden' }}>
                    <div style={{ height: '100%', width: `${t.momentum}%`, background: getMomentumColor(t.momentum), borderRadius: '3px', transition: 'width 0.3s' }} />
                  </div>
                </div>

                {/* Stats */}
                <div style={{ display: 'flex', justifyContent: 'space-between', fontSize: '13px' }}>
                  <div>
                    <span style={{ color: '#64748b' }}>Mentions: </span>
                    <span style={{ fontWeight: 500 }}>{t.mentions}</span>
                  </div>
                  <div>
                    <span style={{ color: '#64748b' }}>Sentiment: </span>
                    <span style={{ fontWeight: 500, color: t.sentiment > 0.2 ? '#22c55e' : t.sentiment < -0.2 ? '#ef4444' : '#94a3b8' }}>
                      {t.sentiment > 0 ? '+' : ''}{(t.sentiment * 100).toFixed(0)}%
                    </span>
                  </div>
                </div>

                {/* Alert Button */}
                {(signal.label === 'BUY' || signal.label === 'SELL') && (
                  <button
                    onClick={() => sendAlert(t, signal.label)}
                    style={{ marginTop: '12px', width: '100%', padding: '8px', background: '#334155', border: '1px solid #475569', borderRadius: '6px', color: '#94a3b8', cursor: 'pointer', fontSize: '12px' }}
                  >
                    🔔 Send Alert
                  </button>
                )}
              </div>
            );
          })
        )}
      </main>

      {/* Footer */}
      <footer style={{ padding: '16px 24px', borderTop: '1px solid #1e293b', textAlign: 'center', fontSize: '12px', color: '#475569' }}>
        TrendPulse MVP • Not financial advice
      </footer>
    </div>
  );
}
