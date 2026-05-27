import React, { useRef, useEffect } from 'react';

const GridMap = ({ stateData }) => {
  const canvasRef = useRef(null);
  const containerRef = useRef(null);
  const prevDronesRef = useRef({});
  const animFrameRef = useRef(null);

  useEffect(() => {
    if (!stateData || !stateData.drones) return;
    
    // Initialize or cleanup drones
    const currentIds = new Set(stateData.drones.map(d => d.id));
    stateData.drones.forEach(d => {
      if (!prevDronesRef.current[d.id]) {
        // Initial spawn position
        prevDronesRef.current[d.id] = { x: d.x, y: d.y };
      }
    });
    // Remove despawned drones
    Object.keys(prevDronesRef.current).forEach(id => {
      if (!currentIds.has(id)) {
        delete prevDronesRef.current[id];
      }
    });

    const canvas = canvasRef.current;
    if (!canvas) return;
    const ctx = canvas.getContext('2d');
    
    const size = 800;
    canvas.width = size;
    canvas.height = size;
    
    const renderFrame = () => {
      // Interpolate drone positions
      stateData.drones.forEach(d => {
        let current = prevDronesRef.current[d.id];
        current.x += (d.x - current.x) * 0.1;
        current.y += (d.y - current.y) * 0.1;
      });

      const { grid, grid_size_m, obstacles, base_x, base_y } = stateData;
      const gridSize = grid.length;
      const cellPx = size / gridSize;

      // Draw Heatmap (Grid)
      for (let i = 0; i < gridSize; i++) {
        for (let j = 0; j < gridSize; j++) {
          const prob = grid[i][j];
          const isObstacle = obstacles && obstacles[i] && obstacles[i][j];
          
          if (isObstacle) {
            ctx.fillStyle = '#1e1e1e';
            ctx.fillRect(i * cellPx, j * cellPx, cellPx, cellPx);
            
            ctx.strokeStyle = '#ff003c';
            ctx.lineWidth = 1;
            ctx.beginPath();
            ctx.moveTo(i * cellPx, j * cellPx);
            ctx.lineTo((i + 1) * cellPx, (j + 1) * cellPx);
            ctx.stroke();
          } else {
            const r = Math.floor(20 + prob * 235);
            const g = Math.floor(30 + prob * 150);
            const b = Math.floor(40);
            ctx.fillStyle = `rgb(${r}, ${g}, ${b})`;
            ctx.fillRect(i * cellPx, j * cellPx, cellPx, cellPx);
          }
          
          ctx.strokeStyle = 'rgba(255,255,255,0.05)';
          ctx.strokeRect(i * cellPx, j * cellPx, cellPx, cellPx);
        }
      }

      const mToPx = (m) => (m / grid_size_m) * size;

      // Draw Base Station
      ctx.fillStyle = '#38bdf8';
      ctx.beginPath();
      ctx.arc(mToPx(base_x), mToPx(base_y), 8, 0, 2 * Math.PI);
      ctx.fill();
      ctx.strokeStyle = '#fff';
      ctx.stroke();

      // Draw Anomalies
      if (stateData.anomalies) {
        stateData.anomalies.forEach(a => {
          if (a.status !== 'active') return;
          ctx.fillStyle = '#fbbf24';
          ctx.beginPath();
          const pulse = 6 + Math.sin(Date.now() / 200) * 2;
          ctx.arc(mToPx(a.x), mToPx(a.y), pulse, 0, 2 * Math.PI);
          ctx.fill();
          ctx.strokeStyle = '#f59e0b';
          ctx.stroke();
        });
      }

      // Draw All Drones
      stateData.drones.forEach(d => {
        const current = prevDronesRef.current[d.id];
        
        if (d.type === 'recon') {
          // Recon Trail
          if (d.trail && d.trail.length > 0) {
            ctx.strokeStyle = 'rgba(57, 255, 20, 0.4)';
            ctx.lineWidth = 2;
            ctx.beginPath();
            ctx.moveTo(mToPx(d.trail[0][0]), mToPx(d.trail[0][1]));
            for (let i = 1; i < d.trail.length; i++) {
              ctx.lineTo(mToPx(d.trail[i][0]), mToPx(d.trail[i][1]));
            }
            ctx.lineTo(mToPx(current.x), mToPx(current.y));
            ctx.stroke();
          }

          // Recon Sensor Range
          ctx.strokeStyle = 'rgba(74, 222, 128, 0.3)';
          ctx.lineWidth = 1;
          ctx.beginPath();
          ctx.arc(mToPx(current.x), mToPx(current.y), mToPx(200), 0, 2 * Math.PI);
          ctx.stroke();

          // Recon Icon
          ctx.fillStyle = '#4ade80';
          ctx.beginPath();
          ctx.arc(mToPx(current.x), mToPx(current.y), 6, 0, 2 * Math.PI);
          ctx.fill();
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2;
          ctx.stroke();
          
        } else if (d.type === 'relief') {
          // Relief Supply Icon (Blue Cross)
          const px = mToPx(current.x);
          const py = mToPx(current.y);
          ctx.fillStyle = '#3b82f6';
          ctx.fillRect(px - 6, py - 6, 12, 12);
          
          ctx.strokeStyle = '#fff';
          ctx.lineWidth = 2;
          ctx.beginPath();
          ctx.moveTo(px, py - 4); ctx.lineTo(px, py + 4);
          ctx.moveTo(px - 4, py); ctx.lineTo(px + 4, py);
          ctx.stroke();
        }
        
        // Draw Label
        ctx.fillStyle = '#fff';
        ctx.font = '10px monospace';
        ctx.fillText(d.id, mToPx(current.x) + 10, mToPx(current.y) - 10);
      });

      // Continue animating
      let stillMoving = false;
      stateData.drones.forEach(d => {
        let current = prevDronesRef.current[d.id];
        if (Math.abs(d.x - current.x) > 0.1 || Math.abs(d.y - current.y) > 0.1) {
          stillMoving = true;
        }
      });
      
      if (stillMoving) {
        animFrameRef.current = requestAnimationFrame(renderFrame);
      }
    };

    animFrameRef.current = requestAnimationFrame(renderFrame);

    return () => {
      if (animFrameRef.current) cancelAnimationFrame(animFrameRef.current);
    };
  }, [stateData]);

  const handleCanvasClick = (e) => {
    const rect = canvasRef.current.getBoundingClientRect();
    const xPx = e.clientX - rect.left;
    const yPx = e.clientY - rect.top;
    
    const scaleX = canvasRef.current.width / rect.width;
    const scaleY = canvasRef.current.height / rect.height;
    
    const trueX = xPx * scaleX;
    const trueY = yPx * scaleY;

    if (stateData && window.injectAnomaly) {
      const mToPxRatio = stateData.grid_size_m / 800;
      const xM = trueX * mToPxRatio;
      const yM = trueY * mToPxRatio;
      window.injectAnomaly(xM, yM);
    }
  };

  return (
    <div className="map-container" ref={containerRef} style={{ width: '100%', height: '100%', display: 'flex', alignItems: 'center', justifyContent: 'center' }}>
      <canvas 
        ref={canvasRef} 
        onClick={handleCanvasClick}
        style={{ 
          maxWidth: '100%', 
          maxHeight: '100%',
          objectFit: 'contain'
        }}
      />
      <div style={{position: 'absolute', top: '10px', left: '20px', color: '#fff', fontSize: '12px', opacity: 0.7}}>
        Click on the map to inject a thermal anomaly
      </div>
    </div>
  );
};

export default GridMap;
