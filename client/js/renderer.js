const Renderer = (() => {
  const T = 32;

  const NODE_COLORS = { manure:'#6b3a2a', gravel:'#777', topsoil:'#3d2b1a', compost:'#2d5020', unknown:'#555' };
  const NODE_KEYS   = { manure:'M', gravel:'G', topsoil:'T', compost:'C', unknown:'?' };
  const STRUCT_BORDER = '#c8e88a';

  let canvas, ctx, state;

  function init(c, s) {
    canvas = c; ctx = c.getContext('2d'); state = s;
    resize();
    window.addEventListener('resize', resize);
  }

  function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }

  function draw() {
    if (!state.player) return;
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const camX = state.player.x * T - W / 2 + T / 2;
    const camY = state.player.y * T - H / 2 + T / 2;
    ctx.save();
    ctx.translate(-camX, -camY);

    _drawTiles(camX, camY, W, H);
    _drawParcels();
    _drawMarket();
    _drawNodes();
    _drawPlayers();

    ctx.restore();
  }

  function _drawTiles(camX, camY, W, H) {
    const sx = Math.max(0,  Math.floor(camX / T));
    const sy = Math.max(0,  Math.floor(camY / T));
    const ex = Math.min(state.world.w - 1, Math.ceil((camX + W) / T));
    const ey = Math.min(state.world.h - 1, Math.ceil((camY + H) / T));
    for (let ty = sy; ty <= ey; ty++) {
      for (let tx = sx; tx <= ex; tx++) {
        ctx.fillStyle = (tx + ty) % 2 === 0 ? '#4a7c3f' : '#507a44';
        ctx.fillRect(tx * T, ty * T, T, T);
      }
    }
  }

  function _drawParcels() {
    const PARCEL_SIZE = 10;
    for (const p of state.parcels) {
      const ox = p.px * PARCEL_SIZE * T;
      const oy = p.py * PARCEL_SIZE * T;
      const sz = PARCEL_SIZE * T;

      const isOwn = state.player && p.owner_id === state.player.id;
      ctx.fillStyle = isOwn ? 'rgba(100,200,100,0.08)' : 'rgba(200,200,100,0.06)';
      ctx.fillRect(ox, oy, sz, sz);

      ctx.strokeStyle = isOwn ? 'rgba(100,220,100,0.35)' : 'rgba(200,200,100,0.25)';
      ctx.lineWidth = 1;
      ctx.strokeRect(ox + 0.5, oy + 0.5, sz - 1, sz - 1);

      ctx.fillStyle = isOwn ? 'rgba(100,200,100,0.6)' : 'rgba(200,200,100,0.45)';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(p.owner_name, ox + sz / 2, oy + sz / 2);
    }

    // Faint parcel grid lines over the whole world
    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let gx = 0; gx <= state.world.w; gx += PARCEL_SIZE) {
      ctx.beginPath();
      ctx.moveTo(gx * T, 0);
      ctx.lineTo(gx * T, state.world.h * T);
      ctx.stroke();
    }
    for (let gy = 0; gy <= state.world.h; gy += PARCEL_SIZE) {
      ctx.beginPath();
      ctx.moveTo(0, gy * T);
      ctx.lineTo(state.world.w * T, gy * T);
      ctx.stroke();
    }
  }

  function _drawMarket() {
    if (!state.market) return;
    const mx = state.market.x * T, my = state.market.y * T;
    ctx.fillStyle = '#7a6000';
    ctx.fillRect(mx, my, T, T);
    ctx.fillStyle = '#f5c842';
    ctx.font = 'bold 9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('MARKET', mx + T / 2, my + T / 2 + 3);
  }

  function _drawNodes() {
    for (const node of state.nodes) {
      const nx = node.x * T, ny = node.y * T;
      ctx.fillStyle = NODE_COLORS[node.type] || NODE_COLORS.unknown;
      ctx.fillRect(nx + 2, ny + 2, T - 4, T - 4);

      // Structure border
      if (node.is_structure) {
        ctx.strokeStyle = STRUCT_BORDER;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(nx + 2, ny + 2, T - 4, T - 4);
      }

      // Fill bar
      const pct = Math.min(1, node.amount / (node.max || 100));
      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.fillRect(nx + 2, ny + T - 7, T - 4, 5);
      ctx.fillStyle = '#7ee87e';
      ctx.fillRect(nx + 2, ny + T - 7, (T - 4) * pct, 5);

      // Label
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(NODE_KEYS[node.type] || '?', nx + T / 2, ny + T / 2 + 4);

      // Owner name for structures
      if (node.is_structure && node.owner_name) {
        ctx.fillStyle = 'rgba(200,232,138,0.8)';
        ctx.font = '7px monospace';
        ctx.fillText(node.owner_name, nx + T / 2, ny + 10);
      }
    }
  }

  function _drawPlayers() {
    for (const p of state.players) {
      if (!state.player || p.id === state.player.id) continue;
      _wheelbarrow(p.x * T, p.y * T, '#6ab0e8', p.username);
    }
    if (state.player) {
      _wheelbarrow(state.player.x * T, state.player.y * T, '#f5c842', state.player.username);
    }
  }

  function _wheelbarrow(px, py, color, label) {
    ctx.fillStyle = color;
    ctx.fillRect(px + 6, py + 8, T - 12, T - 18);
    ctx.beginPath();
    ctx.arc(px + T / 2, py + T - 5, 5, 0, Math.PI * 2);
    ctx.fillStyle = '#222';
    ctx.fill();
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px + 4, py + 10); ctx.lineTo(px + 4, py + T - 4);
    ctx.moveTo(px + T - 4, py + 10); ctx.lineTo(px + T - 4, py + T - 4);
    ctx.stroke();
    ctx.fillStyle = '#fff';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(label, px + T / 2, py + 7);
  }

  return { init, draw };
})();
