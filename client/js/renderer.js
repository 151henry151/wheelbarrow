const Renderer = (() => {
  const T = 32;   // tile size in pixels

  const NODE_COLORS = {
    manure:'#6b3a2a', gravel:'#777', topsoil:'#3d2b1a', compost:'#2d5020',
    wood:'#5a3a1a',   stone:'#5a5a6a', clay:'#8a6a4a', dirt:'#7a5a3a',
    wheat:'#c8a830',  unknown:'#555',
  };
  const NODE_KEYS = {
    manure:'M', gravel:'G', topsoil:'T', compost:'C',
    wood:'W',   stone:'S',  clay:'Cl',   dirt:'D',
    wheat:'Wh', unknown:'?',
  };
  const STRUCT_BORDER = '#c8e88a';
  const SEASON_TILE_TINT = {
    spring: null,
    summer: 'rgba(255,230,0,0.04)',
    fall:   'rgba(200,100,0,0.06)',
    winter: 'rgba(180,220,255,0.08)',
  };

  let canvas, ctx, s;

  function init(c, st) {
    canvas = c; ctx = c.getContext('2d'); s = st;
    resize();
    window.addEventListener('resize', resize);
  }

  function resize() { canvas.width = window.innerWidth; canvas.height = window.innerHeight; }

  function draw() {
    if (!s.player) return;
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    const camX = s.player.x * T - W/2 + T/2;
    const camY = s.player.y * T - H/2 + T/2;
    ctx.save();
    ctx.translate(-camX, -camY);

    _drawTiles(camX, camY, W, H);
    _drawParcels();
    _drawMarket();
    _drawNpcShops();
    _drawPiles();
    _drawCrops();
    _drawNodes();
    _drawPlayers();

    ctx.restore();
  }

  function _drawTiles(camX, camY, W, H) {
    const seasonName = s.season ? s.season.name : 'spring';
    const tint = SEASON_TILE_TINT[seasonName];

    const sx = Math.max(0,               Math.floor(camX / T));
    const sy = Math.max(0,               Math.floor(camY / T));
    const ex = Math.min(s.world.w - 1,   Math.ceil((camX + W) / T));
    const ey = Math.min(s.world.h - 1,   Math.ceil((camY + H) / T));

    for (let ty = sy; ty <= ey; ty++) {
      for (let tx = sx; tx <= ex; tx++) {
        // Subtle colour variation using a simple hash
        const h = (tx * 7 + ty * 13) & 0xff;
        const base = (tx + ty) % 2 === 0 ? 74 : 80;  // two shades of green
        const r = 50 + ((h & 0x0f) >> 1);
        const g = base + ((h >> 4) & 0x07);
        const b = 45;
        ctx.fillStyle = `rgb(${r},${g},${b})`;
        ctx.fillRect(tx * T, ty * T, T, T);
      }
    }

    if (tint) {
      ctx.fillStyle = tint;
      ctx.fillRect(camX, camY, W, H);
    }
  }

  function _drawParcels() {
    const PARCEL_SIZE = 10;
    for (const p of s.parcels) {
      const ox  = p.px * PARCEL_SIZE * T;
      const oy  = p.py * PARCEL_SIZE * T;
      const sz  = PARCEL_SIZE * T;
      const own = s.player && p.owner_id === s.player.id;

      ctx.fillStyle = own ? 'rgba(100,200,100,0.08)' : 'rgba(200,200,100,0.06)';
      ctx.fillRect(ox, oy, sz, sz);

      ctx.strokeStyle = own ? 'rgba(100,220,100,0.35)' : 'rgba(200,200,100,0.25)';
      ctx.lineWidth = 1;
      ctx.strokeRect(ox + 0.5, oy + 0.5, sz - 1, sz - 1);

      ctx.fillStyle = own ? 'rgba(100,200,100,0.55)' : 'rgba(200,200,100,0.40)';
      ctx.font = '9px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(p.owner_name, ox + sz/2, oy + sz/2);
    }

    ctx.strokeStyle = 'rgba(255,255,255,0.04)';
    ctx.lineWidth = 1;
    for (let gx = 0; gx <= s.world.w; gx += PARCEL_SIZE) {
      ctx.beginPath(); ctx.moveTo(gx*T, 0); ctx.lineTo(gx*T, s.world.h*T); ctx.stroke();
    }
    for (let gy = 0; gy <= s.world.h; gy += PARCEL_SIZE) {
      ctx.beginPath(); ctx.moveTo(0, gy*T); ctx.lineTo(s.world.w*T, gy*T); ctx.stroke();
    }
  }

  function _drawMarket() {
    if (!s.market) return;
    const mx = s.market.x * T, my = s.market.y * T;
    ctx.fillStyle = '#7a6000';
    ctx.fillRect(mx, my, T, T);
    ctx.fillStyle = '#f5c842';
    ctx.font = 'bold 8px monospace';
    ctx.textAlign = 'center';
    ctx.fillText('MARKET', mx + T/2, my + T/2 + 3);
  }

  function _drawNpcShops() {
    for (const shop of (s.npc_shops || [])) {
      const sx = shop.x * T, sy = shop.y * T;
      ctx.fillStyle = '#2a2a6a';
      ctx.fillRect(sx, sy, T, T);
      ctx.strokeStyle = '#6a6aff';
      ctx.lineWidth = 1.5;
      ctx.strokeRect(sx + 1, sy + 1, T - 2, T - 2);
      ctx.fillStyle = '#aaaaff';
      ctx.font = 'bold 7px monospace';
      ctx.textAlign = 'center';
      const shortName = shop.label.replace(' Shop','').replace(' Store','');
      ctx.fillText(shortName, sx + T/2, sy + T/2 + 3);
    }
  }

  function _drawPiles() {
    for (const pile of (s.piles || [])) {
      const px = pile.x * T, py = pile.y * T;
      ctx.fillStyle = NODE_COLORS[pile.resource_type] || '#555';
      ctx.globalAlpha = 0.5;
      ctx.fillRect(px + 8, py + 8, T - 16, T - 16);
      ctx.globalAlpha = 1.0;

      ctx.fillStyle = pile.sell_price != null ? '#f5c842' : '#aaa';
      ctx.font = '7px monospace';
      ctx.textAlign = 'center';
      const label = pile.sell_price != null ? `${pile.resource_type[0].toUpperCase()} ${pile.sell_price}c` : pile.resource_type[0].toUpperCase();
      ctx.fillText(label, px + T/2, py + T - 4);
    }
  }

  function _drawCrops() {
    for (const crop of (s.crops || [])) {
      const cx = crop.x * T, cy = crop.y * T;
      ctx.fillStyle = crop.ready ? '#c8a830' : (crop.fertilized ? '#80c040' : '#a0a040');
      ctx.globalAlpha = 0.65;
      ctx.fillRect(cx + 4, cy + 4, T - 8, T - 8);
      ctx.globalAlpha = 1.0;
      ctx.fillStyle = '#fff';
      ctx.font = '8px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(crop.ready ? '✓' : '~', cx + T/2, cy + T/2 + 3);
    }
  }

  function _drawNodes() {
    for (const node of s.nodes) {
      const nx = node.x * T, ny = node.y * T;

      if (node.is_market) {
        // Player market
        ctx.fillStyle = '#603060';
        ctx.fillRect(nx + 2, ny + 2, T - 4, T - 4);
        ctx.strokeStyle = '#c060c0';
        ctx.lineWidth = 1.5;
        ctx.strokeRect(nx + 2, ny + 2, T - 4, T - 4);
        ctx.fillStyle = '#e0a0e0';
        ctx.font = 'bold 7px monospace';
        ctx.textAlign = 'center';
        ctx.fillText('MKT', nx + T/2, ny + T/2 + 3);
        if (node.owner_name) {
          ctx.fillStyle = 'rgba(200,160,200,0.8)';
          ctx.font = '7px monospace';
          ctx.fillText(node.owner_name, nx + T/2, ny + 9);
        }
        continue;
      }

      ctx.fillStyle = NODE_COLORS[node.type] || NODE_COLORS.unknown;
      ctx.fillRect(nx + 2, ny + 2, T - 4, T - 4);

      if (node.is_structure) {
        ctx.strokeStyle = STRUCT_BORDER;
        ctx.lineWidth = 1.5;
        ctx.strokeRect(nx + 2, ny + 2, T - 4, T - 4);
      }

      // Fill bar
      const pct = Math.min(1, node.amount / (node.max || 100));
      ctx.fillStyle = 'rgba(0,0,0,0.4)';
      ctx.fillRect(nx + 2, ny + T - 7, T - 4, 5);
      ctx.fillStyle = pct > 0.4 ? '#7ee87e' : '#e07e40';
      ctx.fillRect(nx + 2, ny + T - 7, (T-4)*pct, 5);

      // Label
      ctx.fillStyle = '#fff';
      ctx.font = 'bold 11px monospace';
      ctx.textAlign = 'center';
      ctx.fillText(NODE_KEYS[node.type] || '?', nx + T/2, ny + T/2 + 4);

      if (node.is_structure && node.owner_name) {
        ctx.fillStyle = 'rgba(200,232,138,0.8)';
        ctx.font = '7px monospace';
        ctx.fillText(node.owner_name, nx + T/2, ny + 9);
      }
    }
  }

  function _drawPlayers() {
    for (const p of s.players) {
      if (!s.player || p.id === s.player.id) continue;
      _wheelbarrow(p.x * T, p.y * T, '#6ab0e8', p.username, p.flat_tire);
    }
    if (s.player) {
      _wheelbarrow(s.player.x * T, s.player.y * T, '#f5c842', s.player.username, s.player.flat_tire);
    }
  }

  function _wheelbarrow(px, py, color, label, flatTire) {
    // Bucket (body)
    ctx.fillStyle = color;
    ctx.fillRect(px + 6, py + 8, T - 12, T - 18);

    // Wheel
    ctx.beginPath();
    ctx.arc(px + T/2, py + T - 5, 5, 0, Math.PI * 2);
    ctx.fillStyle = flatTire ? '#e06060' : '#222';
    ctx.fill();
    if (flatTire) {
      ctx.strokeStyle = '#e06060';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    // Handles
    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px + 4,   py + 10); ctx.lineTo(px + 4,   py + T - 4);
    ctx.moveTo(px + T-4, py + 10); ctx.lineTo(px + T-4, py + T - 4);
    ctx.stroke();

    // Name label
    ctx.fillStyle = '#fff';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(label, px + T/2, py + 7);
  }

  return { init, draw };
})();
