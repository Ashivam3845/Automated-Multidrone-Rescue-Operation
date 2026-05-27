import React, { useState, useEffect, useRef } from 'react';
import GridMap from './components/GridMap';
import Controls from './components/Controls';
import { Activity, Battery, Navigation, Target } from 'lucide-react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, AreaChart, Area, ResponsiveContainer, Legend } from 'recharts';
import './index.css';

const WS_URL = 'ws://127.0.0.1:8000/ws';

function App() {
  const [stateData, setStateData] = useState(null);
  const [history, setHistory] = useState([]);
  const [isPlaying, setIsPlaying] = useState(false);
  const wsRef = useRef(null);

  useEffect(() => {
    wsRef.current = new WebSocket(WS_URL);

    wsRef.current.onmessage = (event) => {
      try {
        const payload = JSON.parse(event.data);
        if (payload.type === 'state') {
          setStateData(payload.data);
          
          setHistory(prev => {
            const recons = payload.data.drones.filter(d => d.type === 'recon');
            if (recons.length === 0) return prev;
            const primary = recons[0];
            
            const newHist = [...prev, {
              time: prev.length,
              soc: primary.soc * 100,
              Search: primary.utilities?.Search || 0,
              Investigate: Object.keys(primary.utilities || {}).filter(k => k.startsWith('Investigate')).reduce((acc, k) => Math.max(acc, primary.utilities[k]), 0),
              RTB: primary.utilities?.RTB || 0
            }];
            if (newHist.length > 50) return newHist.slice(newHist.length - 50);
            return newHist;
          });
        }
      } catch(e) { console.error(e); }
    };

    return () => {
      if (wsRef.current) wsRef.current.close();
    };
  }, []);

  const sendMessage = (msg) => {
    if (wsRef.current && wsRef.current.readyState === WebSocket.OPEN) {
      wsRef.current.send(msg);
    }
  };

  const stepSimulation = () => sendMessage(JSON.stringify({action: 'step'}));
  const resetSimulation = () => {
    setIsPlaying(false);
    setHistory([]);
    sendMessage(JSON.stringify({action: 'reset'}));
  };
  const injectAnomaly = (x, y) => {
    sendMessage(JSON.stringify({action: 'inject', x, y, priority: 0.95}));
  };

  const togglePlay = () => {
    const nextState = !isPlaying;
    setIsPlaying(nextState);
    sendMessage(JSON.stringify({action: nextState ? 'play' : 'pause'}));
  };

  useEffect(() => {
    window.injectAnomaly = injectAnomaly;
  }, []);

  const renderUtilityBars = (drone) => {
    if (!drone || !drone.utilities || Object.keys(drone.utilities).length === 0) return null;
    
    const maxVal = Math.max(...Object.values(drone.utilities), 0.1);

    return Object.entries(drone.utilities).map(([key, val]) => {
      let colorClass = 'blue';
      if (key === 'RTB') colorClass = 'red';
      if (key.includes('Investigate')) colorClass = 'yellow';

      const percent = Math.min((val / maxVal) * 100, 100);
      
      return (
        <div key={key} style={{marginBottom: '0.5rem'}}>
          <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem', color: 'var(--text-muted)'}}>
            <span>U({key})</span>
            <span>{val.toFixed(2)}</span>
          </div>
          <div className="progress-bar">
            <div className={`progress-fill ${colorClass}`} style={{width: `${percent}%`}}></div>
          </div>
        </div>
      );
    });
  };

  if (!stateData) return <div style={{padding: '2rem'}}>Connecting to Jatayu Engine via WebSockets...</div>;

  let latestRecon = null;
  if (stateData.anomalies) {
    const resolvedAnomalies = stateData.anomalies.filter(a => a.status === 'resolved' && a.image_url);
    if (resolvedAnomalies.length > 0) {
      resolvedAnomalies.sort((a, b) => (b.resolved_at || 0) - (a.resolved_at || 0));
      latestRecon = resolvedAnomalies[0];
    }
  }

  return (
    <div className="dashboard">
      <div className="panel" style={{height: '100%', overflowY: 'auto'}}>
        <h1><Activity size={24} /> Jatayu Swarm</h1>
        
        <Controls 
          isPlaying={isPlaying} 
          togglePlay={togglePlay} 
          step={stepSimulation} 
          reset={resetSimulation} 
          addAnomaly={injectAnomaly}
        />

        <div className="stat-box" style={{marginBottom: '1rem'}}>
          <div style={{fontSize: '0.85rem', color: 'var(--text-muted)'}}>
            Engine Latency: <strong style={{color: 'var(--text-main)'}}>{stateData.latency_ms.toFixed(2)} ms</strong>
          </div>
        </div>

        {stateData.drones.map(drone => {
          let batteryClass = 'green';
          if (drone.soc < 0.20) batteryClass = 'red';
          else if (drone.soc < 0.50) batteryClass = 'yellow';

          return (
            <div key={drone.id} className="stat-box" style={{borderLeft: drone.type==='recon' ? '3px solid #4ade80' : '3px solid #3b82f6'}}>
              <h2>
                <Navigation size={16} style={{marginRight: '6px', verticalAlign: 'text-bottom'}} /> 
                {drone.id} ({drone.type})
              </h2>
              
              <div style={{display: 'flex', justifyContent: 'space-between', margin: '0.5rem 0'}}>
                <span className="stat-label">Position X,Y</span>
                <span style={{fontFamily: 'monospace'}}>{Math.round(drone.x)}, {Math.round(drone.y)}</span>
              </div>
              
              <div style={{display: 'flex', justifyContent: 'space-between'}}>
                <span className="stat-label">Action</span>
                <span className={`action-badge action-${(drone.action||'').split('_')[0]}`}>
                  {drone.action}
                </span>
              </div>

              <div style={{marginTop: '10px'}}>
                <div style={{display: 'flex', justifyContent: 'space-between', fontSize: '0.8rem'}}>
                  <span>SoC</span>
                  <span>{(drone.soc * 100).toFixed(1)}%</span>
                </div>
                <div className="progress-bar" style={{height: '6px'}}>
                  <div className={`progress-fill ${batteryClass}`} style={{width: `${drone.soc * 100}%`}}></div>
                </div>
              </div>

              {drone.type === 'recon' && (
                <div style={{marginTop: '1rem'}}>
                  {renderUtilityBars(drone)}
                </div>
              )}
            </div>
          );
        })}

        <div className="stat-box">
          <h2><Activity size={16} style={{marginRight: '6px', verticalAlign: 'text-bottom'}} /> Operations Log</h2>
          <div className="log-container">
            {stateData.logs.map((log, i) => (
              <div key={i} className="log-entry">{log}</div>
            ))}
          </div>
        </div>
      </div>

      <div style={{ display: 'flex', flexDirection: 'column', overflow: 'hidden' }}>
        <div style={{ display: 'flex', gap: '1rem', flexGrow: 1 }}>
          <GridMap stateData={stateData} />
          
          <div className="panel" style={{ width: '350px', padding: '1rem', flexShrink: 0, display: 'flex', flexDirection: 'column' }}>
            <h2><Target size={16} style={{marginRight: '6px', verticalAlign: 'text-bottom'}} /> Live Recon Intel</h2>
            {latestRecon ? (
              <div style={{marginTop: '1rem'}}>
                <div className="recon-container">
                  <img src={latestRecon.image_url} className="recon-image" alt="Thermal Recon" />
                  <div className="recon-overlay"></div>
                  <div className="recon-crosshair"></div>
                  <div className="recon-text">
                    TGT ACQ: {Math.round(latestRecon.x)},{Math.round(latestRecon.y)}
                  </div>
                </div>
                <div style={{marginTop: '1rem', fontSize: '0.85rem', color: 'var(--text-muted)'}}>
                  <p><strong>STATUS:</strong> RESOLVED</p>
                  <p><strong>PROBABILITY:</strong> {(latestRecon.priority * 100).toFixed(1)}%</p>
                  <p><strong>TIMESTAMP:</strong> {new Date(latestRecon.resolved_at * 1000).toLocaleTimeString()}</p>
                </div>
              </div>
            ) : (
              <div style={{marginTop: '1rem', flexGrow: 1, display: 'flex', alignItems: 'center', justifyContent: 'center', border: '1px dashed #334155', color: '#64748b', fontSize: '0.9rem', textAlign: 'center'}}>
                AWAITING TARGET ACQUISITION...
              </div>
            )}
          </div>
        </div>
        
        <div className="charts-container">
          <div className="panel chart-wrapper" style={{ padding: '1rem' }}>
            <h2>Battery Tracking</h2>
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" hide />
                <YAxis domain={[0, 100]} stroke="#94a3b8" tick={{fontSize: 12}} width={30} />
                <Tooltip contentStyle={{backgroundColor: '#111827', border: '1px solid #1e293b'}} />
                <Line type="monotone" dataKey="soc" stroke="#39ff14" strokeWidth={2} dot={false} isAnimationActive={true} animationDuration={300} />
              </LineChart>
            </ResponsiveContainer>
          </div>
          
          <div className="panel chart-wrapper" style={{ padding: '1rem' }}>
            <h2>Utility Priorities</h2>
            <ResponsiveContainer width="100%" height="100%">
              <AreaChart data={history}>
                <CartesianGrid strokeDasharray="3 3" stroke="#1e293b" />
                <XAxis dataKey="time" hide />
                <YAxis stroke="#94a3b8" tick={{fontSize: 12}} width={30} />
                <Tooltip contentStyle={{backgroundColor: '#111827', border: '1px solid #1e293b'}} />
                <Legend iconType="circle" wrapperStyle={{ fontSize: '12px' }} />
                <Area type="monotone" dataKey="Search" stackId="1" stroke="#38bdf8" fill="#38bdf8" fillOpacity={0.3} isAnimationActive={true} animationDuration={300} />
                <Area type="monotone" dataKey="Investigate" stackId="1" stroke="#ffb000" fill="#ffb000" fillOpacity={0.3} isAnimationActive={true} animationDuration={300} />
                <Area type="monotone" dataKey="RTB" stackId="1" stroke="#ff003c" fill="#ff003c" fillOpacity={0.3} isAnimationActive={true} animationDuration={300} />
              </AreaChart>
            </ResponsiveContainer>
          </div>
        </div>
      </div>
    </div>
  );
}

export default App;
