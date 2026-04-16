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
  // Town boundary colours, cycled by town.id
  const TOWN_COLORS = [
    '#6a8aff','#6affa0','#ffa06a','#ff6a9a','#a06aff',
    '#6affff','#ffff6a','#ff9a6a','#6aff8a','#9a6aff',
  ];

  let canvas, ctx, s;
  // Cached camera position for helpers called without args
  let _camX = 0, _camY = 0, _vpW = 0, _vpH = 0;

  function init(c, st) {
    canvas = c; ctx = c.getContext('2d'); s = st;
    resize();
    window.addEventListener('resize', resize);
  }

  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
    draw(); // immediately redraw — prevents black flash during window drag
  }

  function draw() {
    if (!s.player) return;
    const W = canvas.width, H = canvas.height;
    ctx.clearRect(0, 0, W, H);

    _camX = s.player.x * T - W/2 + T/2;
    _camY = s.player.y * T - H/2 + T/2;
    _vpW = W; _vpH = H;

    ctx.save();
    ctx.translate(-_camX, -_camY);

    _drawTiles(_camX, _camY, W, H);
    _drawTowns();
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

    const wx = s.world ? s.world.w : 1000;
    const wy = s.world ? s.world.h : 1000;
    const sx = Math.max(0,       Math.floor(camX / T));
    const sy = Math.max(0,       Math.floor(camY / T));
    const ex = Math.min(wx - 1,  Math.ceil((camX + W) / T));
    const ey = Math.min(wy - 1,  Math.ceil((camY + H) / T));

    for (let ty = sy; ty <= ey; ty++) {
      for (let tx = sx; tx <= ex; tx++) {
        const h = (tx * 7 + ty * 13) & 0xff;
        const base = (tx + ty) % 2 === 0 ? 74 : 80;
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

  function _drawTowns() {
    for (const town of (s.towns || [])) {
      const poly = town.boundary;
      if (!poly || poly.length < 3) continue;
      const col       = TOWN_COLORS[town.id % TOWN_COLORS.length];
      const isCurrent = s.currentTownId === town.id;

      ctx.beginPath();
      ctx.moveTo(poly[0].x * T + T/2, poly[0].y * T + T/2);
      for (let i = 1; i < poly.length; i++) {
        ctx.lineTo(poly[i].x * T + T/2, poly[i].y * T + T/2);
      }
      ctx.closePath();

      // Very faint interior fill
      ctx.globalAlpha = isCurrent ? 0.07 : 0.03;
      ctx.fillStyle = col;
      ctx.fill();

      // Boundary line — all towns are drawn; Voronoi-clipped polygons never
      // overlap so adjacent borders share the same edge (no crossing lines).
      ctx.globalAlpha = isCurrent ? 0.50 : 0.18;
      ctx.strokeStyle = col;
      ctx.lineWidth   = isCurrent ? 2.5 : 1.0;
      ctx.stroke();
      ctx.globalAlpha = 1.0;

      // Town name near centre (only if in viewport)
      const cnx = town.center_x * T + T/2;
      const cny = town.center_y * T + T/2;
      if (cnx > _camX - 300 && cnx < _camX + _vpW + 300 &&
          cny > _camY - 300 && cny < _camY + _vpH + 300) {
        ctx.globalAlpha = isCurrent ? 0.85 : 0.45;
        ctx.fillStyle = col;
        ctx.font = isCurrent ? 'bold 13px monospace' : '11px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(town.name, cnx, cny - 12);
        ctx.globalAlpha = 1.0;
      }
    }
  }

  function _drawParcels() {
    if (!s.player) return;
    const px = s.player.x, py = s.player.y;
    // Visible tile range
    const tileLeft   = Math.floor(_camX / T) - 1;
    const tileRight  = Math.ceil((_camX + _vpW) / T) + 1;
    const tileTop    = Math.floor(_camY / T) - 1;
    const tileBottom = Math.ceil((_camY + _vpH) / T) + 1;

    for (const p of (s.world_parcels || [])) {
      // Viewport cull (AABB in tile space)
      if (p.x + p.w < tileLeft || p.x > tileRight ||
          p.y + p.h < tileTop  || p.y > tileBottom) continue;

      const ox = p.x * T, oy = p.y * T;
      const pw = p.w * T, ph = p.h * T;
      const isMine    = s.player && p.owner_id === s.player.id;
      const isPreview = s.parcelPreview === p.id;
      const isCurrent = (px >= p.x && px < p.x + p.w &&
                         py >= p.y && py < p.y + p.h);

      // Background fill
      if (isPreview) {
        ctx.fillStyle = 'rgba(255,220,50,0.18)';
        ctx.fillRect(ox, oy, pw, ph);
      } else if (isMine) {
        ctx.fillStyle = 'rgba(100,200,100,0.10)';
        ctx.fillRect(ox, oy, pw, ph);
      } else if (isCurrent && !p.owner_id) {
        ctx.fillStyle = 'rgba(255,255,200,0.07)';
        ctx.fillRect(ox, oy, pw, ph);
      }

      // Border
      if (isPreview) {
        ctx.strokeStyle = 'rgba(255,220,50,0.92)';
        ctx.lineWidth = 2.5;
      } else if (isMine) {
        ctx.strokeStyle = 'rgba(100,220,100,0.55)';
        ctx.lineWidth = 1;
      } else if (isCurrent) {
        ctx.strokeStyle = 'rgba(255,255,255,0.50)';
        ctx.lineWidth = 1.5;
      } else if (p.owner_id) {
        ctx.strokeStyle = 'rgba(200,120,100,0.22)';
        ctx.lineWidth = 0.5;
      } else {
        ctx.strokeStyle = 'rgba(180,180,100,0.18)';
        ctx.lineWidth = 0.5;
      }
      ctx.strokeRect(ox + 0.5, oy + 0.5, pw - 1, ph - 1);

      // Label
      if (isPreview) {
        ctx.fillStyle = 'rgba(255,220,50,0.95)';
        ctx.font = 'bold 10px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(`${p.price}c`, ox + pw/2, oy + ph/2 - 3);
        if (pw >= 64 && ph >= 32) {
          ctx.font = '9px monospace';
          ctx.fillText('B to confirm', ox + pw/2, oy + ph/2 + 9);
        }
      } else if (isMine && pw >= 32 && ph >= 24) {
        ctx.fillStyle = 'rgba(100,220,100,0.75)';
        ctx.font = '9px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(p.owner_name || '', ox + pw/2, oy + ph/2 + 3);
      } else if (p.owner_id && isCurrent && pw >= 32) {
        ctx.fillStyle = 'rgba(220,150,100,0.80)';
        ctx.font = '9px monospace';
        ctx.textAlign = 'center';
        ctx.fillText(p.owner_name || '?', ox + pw/2, oy + ph/2 + 3);
      }
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
      const label = pile.sell_price != null
        ? `${pile.resource_type[0].toUpperCase()} ${pile.sell_price}c`
        : pile.resource_type[0].toUpperCase();
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

      if (node.is_town_hall) {
        ctx.fillStyle = '#4a3a1a';
        ctx.fillRect(nx + 1, ny + 1, T - 2, T - 2);
        ctx.strokeStyle = '#d4a830';
        ctx.lineWidth = 2;
        ctx.strokeRect(nx + 1, ny + 1, T - 2, T - 2);
        ctx.fillStyle = '#f5c842';
        ctx.font = 'bold 7px monospace';
        ctx.textAlign = 'center';
        ctx.fillText('HALL', nx + T/2, ny + T/2 + 3);
        if (node.owner_name) {
          ctx.fillStyle = 'rgba(245,200,66,0.8)';
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
    ctx.fillStyle = color;
    ctx.fillRect(px + 6, py + 8, T - 12, T - 18);

    ctx.beginPath();
    ctx.arc(px + T/2, py + T - 5, 5, 0, Math.PI * 2);
    ctx.fillStyle = flatTire ? '#e06060' : '#222';
    ctx.fill();
    if (flatTire) {
      ctx.strokeStyle = '#e06060';
      ctx.lineWidth = 1;
      ctx.stroke();
    }

    ctx.strokeStyle = color;
    ctx.lineWidth = 2;
    ctx.beginPath();
    ctx.moveTo(px + 4,   py + 10); ctx.lineTo(px + 4,   py + T - 4);
    ctx.moveTo(px + T-4, py + 10); ctx.lineTo(px + T-4, py + T - 4);
    ctx.stroke();

    ctx.fillStyle = '#fff';
    ctx.font = '9px monospace';
    ctx.textAlign = 'center';
    ctx.fillText(label || '', px + T/2, py + 7);
  }

  return { init, draw };
})();
