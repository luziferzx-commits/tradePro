import { useEffect, useState } from 'react';
import './index.css';

interface SummaryData {
  acceptance_pct: number;
  total_signals: number;
  total_trades: number;
  total_profit: number;
}

interface Signal {
  timestamp: string;
  symbol: string;
  direction: string;
  conviction: number;
  threshold: number;
  decision: string;
}

export default function App() {
  const [summary, setSummary] = useState<SummaryData | null>(null);
  const [signals, setSignals] = useState<Signal[]>([]);

  const fetchData = async () => {
    try {
      const sumRes = await fetch('http://localhost:8000/api/summary');
      setSummary(await sumRes.json());
      const sigRes = await fetch('http://localhost:8000/api/recent_signals?limit=10');
      setSignals(await sigRes.json());
    } catch (e) {
      console.error("Failed to fetch API", e);
    }
  };

  useEffect(() => {
    fetchData();
    const interval = setInterval(fetchData, 5000);
    return () => clearInterval(interval);
  }, []);

  return (
    <div className="dashboard-container">
      <header className="header">
        <h1>GQOS Command Center</h1>
        <div className="header-status">
          <div className="pulse-dot"></div>
          Live Sync
        </div>
      </header>

      <main>
        <div className="grid">
          <div className="glass-panel">
            <h2>Today's Profit (Shadow)</h2>
            <div className={`stat-value ${summary?.total_profit && summary.total_profit < 0 ? 'negative' : 'positive'}`}>
              ${summary?.total_profit?.toFixed(2) || '0.00'}
            </div>
          </div>
          
          <div className="glass-panel">
            <h2>Total Trades (Shadow)</h2>
            <div className="stat-value">{summary?.total_trades || 0}</div>
          </div>

          <div className="glass-panel">
            <h2>AI Acceptance Rate</h2>
            <div className="stat-value">{summary?.acceptance_pct || 0}%</div>
            <div style={{color: 'var(--text-secondary)', fontSize: '0.875rem'}}>
              Signals Generated: {summary?.total_signals || 0}
            </div>
          </div>
        </div>

        <div className="glass-panel">
          <h2>Recent AI Signals (Live)</h2>
          <div className="table-container">
            <table>
              <thead>
                <tr>
                  <th>Time</th>
                  <th>Symbol</th>
                  <th>Direction</th>
                  <th>Conviction</th>
                  <th>Threshold</th>
                  <th>Decision</th>
                </tr>
              </thead>
              <tbody>
                {signals.map((sig, i) => (
                  <tr key={i}>
                    <td>{new Date(sig.timestamp).toLocaleTimeString()}</td>
                    <td style={{fontWeight: 'bold'}}>{sig.symbol}</td>
                    <td>
                      <span className={`badge ${sig.direction === 'BUY' ? 'badge-buy' : 'badge-sell'}`}>
                        {sig.direction}
                      </span>
                    </td>
                    <td>{(sig.conviction * 100).toFixed(1)}%</td>
                    <td>{(sig.threshold * 100).toFixed(1)}%</td>
                    <td>
                      <span className={`badge ${sig.decision === 'ACCEPT' ? 'badge-accept' : 'badge-reject'}`}>
                        {sig.decision}
                      </span>
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        </div>
      </main>
    </div>
  );
}
