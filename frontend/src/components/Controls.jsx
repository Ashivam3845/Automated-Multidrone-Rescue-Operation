import React from 'react';
import { Play, Pause, RotateCcw, Crosshair } from 'lucide-react';

const Controls = ({ isPlaying, togglePlay, step, reset, addAnomaly }) => {
  return (
    <div className="controls">
      <button className={isPlaying ? "danger" : "primary"} onClick={togglePlay}>
        {isPlaying ? <><Pause size={18} /> Pause Auto-Pilot</> : <><Play size={18} /> Start Auto-Pilot</>}
      </button>
      <button onClick={step} disabled={isPlaying}>
        Step Forward (1 tick)
      </button>
      <button onClick={reset}>
        <RotateCcw size={18} /> Reset Sim
      </button>
      <button onClick={() => addAnomaly(Math.random() * 5000, Math.random() * 5000)}>
        <Crosshair size={18} /> Random Anomaly
      </button>
    </div>
  );
};

export default Controls;
