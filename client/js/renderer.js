const Renderer = (() => {
  const T = 32; // tile size px

  const NODE_COLORS = {
    manure:  '#6b3a2a',
    gravel:  '#888',
    topsoil: '#3d2b1a',
    compost: '#2d5020',
  };
  const NODE_LABELS = {
    manure: 'M', gravel: 'G', topsoil: 'T', compost: 'C',
  };

  let canvas, ctx, state;

  function init(c, s) {
    canvas = c;
    ctx    = c.getContext('2d');
    state  = s;
    resize();
    window.addEventListener('resize', resize);
  }

  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
  }

  function draw() {
    if (!state.player) return;

    const pw = canvas.width;
    const ph = canvas.height;
    ctx.clearRect(0, 0, pw, ph);

    // Camera: center on local player
    const camX = state.player.x * T - pw / 2 + T / 2;
    const camY = state.player.y * T - ph / 2 + T / 2;

    ctx.save();
    ctx.translate(-camX, -camY);

    // --- World background ---
    const startTX = Math.max(0, Math.floor(camX / T));
    const startTY = Math.max(0, Math.floor(camY / T));
    const endTX   = Math.min(state.world.w - 1, Math.ceil((camX + pw) / T));
    const endTY   = Math.min(state.world.h - 1, Math.ceil((camY + ph) / T));

    for (let ty = startTY; ty <= endTY; ty++) {
      for (let tx = startTX; tx <= endTX; tx++) {
        const checker = (tx + ty) % 2 === 0;
        ctx.fillStyle = checker ? '#4a7c3f' : '#507a44';
        ctx.fillRect(tx * T, ty * T, T, T);
      }
    }

    // --- Market tile ---
    if (state.market) {
      const mx = state.market.x * T;
      const my = state.market.y * T;
      ctx.fillStyle = '#b8860b';
      ctx.fillRect(mx, my, T, T);
      ctx.fillStyle = '#ffe066';
      ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText('MARKET', mx + T / 2, my + T / 2 + 4);
    }

    // --- Resource nodes ---
    for (const node of state.nodes) {
      const nx = node.x * T;
      const ny = node.y * T;
      ctx.fillStyle = NODE_COLORS[node.type] || '#999';
      ctx.fillRect(nx + 2, ny + 2, T - 4, T - 4);
      // fill indicator bar
      const fillPct = Math.min(1, node.amount / (node.max || 100));
      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.fillRect(nx + 2, ny + T - 7, T - 4, 5);
      ctx.fillStyle = '#7ee87e';
      ctx.fillRect(nx + 2, ny + T - 7, (T - 4) * fillPct, 5);
      // label
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 12px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(NODE_LABELS[node.type] || '?', nx + T / 2, ny + T / 2 + 4);
    }

    // --- Other players ---
    for (const p of state.players) {
      if (p.id === state.player.id) continue;
      _drawWheelbarrow(p.x * T, p.y * T, '#6ab0e8', p.username);
    }

    // --- Local player ---
    _drawWheelbarrow(state.player.x * T, state.player.y * T, '#f5c842', state.player.username);

    ctx.restore();
  }

  function _drawWheelbarrow(px, py, color, label) {
    // Bucket body
    ctx.fillStyle = color;
    ctx.fillRect(px + 6, py + 8, T - 12, T - 18);
    // Wheel
    ctx.beginPath();
    ctx.arc(px + T / 2, py + T - 5, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#222';
    ctx.fill();
    // Handles
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px + 4,  py + 10); ctx.lineTo(px + 4,  py + T - 4);
    ctx.moveTo(px + T - 4, py + 10); ctx.lineTo(px + T - 4, py + T - 4);
    ctx.stroke();
    // Name
    ctx.fillStyle = '#fff';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(label, px + T / 2, py + 6);
  }

  return { init, draw };
})();
