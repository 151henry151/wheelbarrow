const Renderer = (() => {
  const T = 32;   // tile size in pixels

  const SEASON_TILE_TINT = {
    spring: null,
    summer: 'rgba(255,230,0,0.04)',
    fall:   'rgba(200,100,0,0.06)',
    winter: 'rgba(180,220,255,0.08)',
  };
  const TOWN_COLORS = [
    '#6a8aff','#6affa0','#ffa06a','#ff6a9a','#a06aff',
    '#6affff','#ffff6a','#ff9a6a','#6aff8a','#9a6aff',
  ];

  let canvas, ctx, s;
  let _camX = 0, _camY = 0, _vpW = 0, _vpH = 0;

  function init(c, st) {
    canvas = c; ctx = c.getContext('2d'); s = st;
    resize();
    window.addEventListener('resize', resize);
  }

  function resize() {
    canvas.width  = window.innerWidth;
    canvas.height = window.innerHeight;
    draw();
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
    _drawWater();
    _drawBridges();
    _drawTowns();
    _drawParcels();
    _drawRoads();
    _drawSoilFurrows();
    _drawNpcMarkets();
    _drawNpcShops();
    _drawPiles();
    _drawCrops();
    _drawNodes();
    _drawPlayers();
    ctx.restore();
  }

  // ── Ground tiles ────────────────────────────────────────────────────────────
  function _drawTiles(camX, camY, W, H) {
    const seasonName = s.season ? s.season.name : 'spring';
    const tint = SEASON_TILE_TINT[seasonName];
    const wx = s.world ? s.world.w : 1000;
    const wy = s.world ? s.world.h : 1000;
    const sx = Math.max(0, Math.floor(camX / T));
    const sy = Math.max(0, Math.floor(camY / T));
    const ex = Math.min(wx - 1, Math.ceil((camX + W) / T));
    const ey = Math.min(wy - 1, Math.ceil((camY + H) / T));
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

  function _drawWater() {
    for (const w of (s.water_tiles || [])) {
      const ox = w.x * T, oy = w.y * T;
      if (ox < _camX - T || ox > _camX + _vpW + T || oy < _camY - T || oy > _camY + _vpH + T) continue;
      ctx.fillStyle = 'rgba(28, 92, 160, 0.5)';
      ctx.fillRect(ox, oy, T, T);
      ctx.strokeStyle = 'rgba(18, 60, 110, 0.35)';
      ctx.lineWidth = 1;
      ctx.strokeRect(ox + 0.5, oy + 0.5, T - 1, T - 1);
    }
  }

  function _drawBridges() {
    for (const b of (s.bridge_tiles || [])) {
      const ox = b.x * T, oy = b.y * T;
      if (ox < _camX - T || ox > _camX + _vpW + T || oy < _camY - T || oy > _camY + _vpH + T) continue;
      ctx.fillStyle = 'rgba(110, 82, 52, 0.9)';
      ctx.fillRect(ox + 1, oy + 5, T - 2, T - 10);
      ctx.strokeStyle = 'rgba(60, 44, 28, 0.95)';
      ctx.lineWidth = 1;
      for (let i = 0; i < 5; i++) {
        ctx.beginPath();
        ctx.moveTo(ox + 4 + i * 6, oy + 7);
        ctx.lineTo(ox + 4 + i * 6, oy + T - 7);
        ctx.stroke();
      }
    }
  }

  function _drawSoilFurrows() {
    const crops = s.crops || [];
    const atCrop = (x, y) => crops.some(c => c.x === x && c.y === y);
    for (const st of (s.soil_tiles || [])) {
      if (!st.tilled || atCrop(st.x, st.y)) continue;
      const ox = st.x * T, oy = st.y * T;
      ctx.strokeStyle = 'rgba(95, 65, 40, 0.22)';
      ctx.lineWidth = 1;
      for (let i = 0; i < 4; i++) {
        ctx.beginPath();
        ctx.moveTo(ox + 5 + i * 7, oy + 5);
        ctx.lineTo(ox + 4 + i * 7, oy + T - 5);
        ctx.stroke();
      }
    }
  }

  function _drawRoads() {
    for (const r of (s.roads || [])) {
      const x = r.x * T;
      const y = r.y * T;
      if (x < _camX - T || x > _camX + _vpW + T || y < _camY - T || y > _camY + _vpH + T) continue;
      ctx.fillStyle = 'rgba(95, 72, 48, 0.38)';
      ctx.fillRect(x + 1, y + 1, T - 2, T - 2);
      ctx.strokeStyle = 'rgba(60, 48, 32, 0.22)';
      ctx.lineWidth = 1;
      ctx.strokeRect(x + 2.5, y + 2.5, T - 5, T - 5);
    }
  }

  // ── Town boundaries ─────────────────────────────────────────────────────────
  function _drawTowns() {
    for (const town of (s.towns || [])) {
      const poly = town.boundary;
      if (!poly || poly.length < 3) continue;
      const col = TOWN_COLORS[town.id % TOWN_COLORS.length];
      const isCurrent = s.currentTownId === town.id;
      ctx.beginPath();
      ctx.moveTo(poly[0].x * T + T/2, poly[0].y * T + T/2);
      for (let i = 1; i < poly.length; i++) {
        ctx.lineTo(poly[i].x * T + T/2, poly[i].y * T + T/2);
      }
      ctx.closePath();
      ctx.globalAlpha = isCurrent ? 0.07 : 0.03;
      ctx.fillStyle = col;
      ctx.fill();
      ctx.globalAlpha = isCurrent ? 0.50 : 0.18;
      ctx.strokeStyle = col;
      ctx.lineWidth = isCurrent ? 2.5 : 1.0;
      ctx.stroke();
      ctx.globalAlpha = 1.0;
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

  // ── Land parcels ─────────────────────────────────────────────────────────────
  function _drawParcels() {
    if (!s.player) return;
    const px = s.player.x, py = s.player.y;
    const tileLeft   = Math.floor(_camX / T) - 1;
    const tileRight  = Math.ceil((_camX + _vpW) / T) + 1;
    const tileTop    = Math.floor(_camY / T) - 1;
    const tileBottom = Math.ceil((_camY + _vpH) / T) + 1;
    for (const p of (s.world_parcels || [])) {
      if (p.x + p.w < tileLeft || p.x > tileRight ||
          p.y + p.h < tileTop  || p.y > tileBottom) continue;
      const ox = p.x * T, oy = p.y * T;
      const pw = p.w * T, ph = p.h * T;
      const isMine    = s.player && p.owner_id === s.player.id;
      const isPreview = s.parcelPreview === p.id;
      const isCurrent = (px >= p.x && px < p.x + p.w && py >= p.y && py < p.y + p.h);
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
      if (isPreview) {
        ctx.strokeStyle = 'rgba(255,220,50,0.92)'; ctx.lineWidth = 2.5;
      } else if (isMine) {
        ctx.strokeStyle = 'rgba(100,220,100,0.55)'; ctx.lineWidth = 1;
      } else if (isCurrent) {
        ctx.strokeStyle = 'rgba(255,255,255,0.50)'; ctx.lineWidth = 1.5;
      } else if (p.owner_id) {
        ctx.strokeStyle = 'rgba(200,120,100,0.22)'; ctx.lineWidth = 0.5;
      } else {
        ctx.strokeStyle = 'rgba(180,180,100,0.18)'; ctx.lineWidth = 0.5;
      }
      ctx.strokeRect(ox + 0.5, oy + 0.5, pw - 1, ph - 1);
      if (isPreview) {
        ctx.fillStyle = 'rgba(255,220,50,0.95)';
        ctx.font = 'bold 10px monospace'; ctx.textAlign = 'center';
        ctx.fillText(`${p.price}c`, ox + pw/2, oy + ph/2 - 3);
        if (pw >= 64 && ph >= 32) {
          ctx.font = '9px monospace';
          ctx.fillText('B to confirm', ox + pw/2, oy + ph/2 + 9);
        }
      } else if (isMine && pw >= 32 && ph >= 24) {
        ctx.fillStyle = 'rgba(100,220,100,0.75)';
        ctx.font = '9px monospace'; ctx.textAlign = 'center';
        ctx.fillText(p.owner_name || '', ox + pw/2, oy + ph/2 + 3);
      } else if (p.owner_id && isCurrent && pw >= 32) {
        ctx.fillStyle = 'rgba(220,150,100,0.80)';
        ctx.font = '9px monospace'; ctx.textAlign = 'center';
        ctx.fillText(p.owner_name || '?', ox + pw/2, oy + ph/2 + 3);
      }
    }
  }

  // ── NPC primary markets (one per town) ───────────────────────────────────────
  function _drawNpcMarkets() {
    const mks = s.npc_markets || [];
    for (const m of mks) {
      const x = m.x * T, y = m.y * T;
      if (x < _camX - 100 || x > _camX + _vpW + 100 || y < _camY - 100 || y > _camY + _vpH + 100) {
        continue;
      }
      _marketStall(x, y, '#b89010', '#f0d050');
      _label(x + T/2, y - 3, 'Market', '#ffe080', 'bold 8px monospace');
    }
  }

  // ── NPC shops ───────────────────────────────────────────────────────────────
  function _drawNpcShops() {
    for (const shop of (s.npc_shops || [])) {
      const x = shop.x * T, y = shop.y * T;
      if (x < _camX - 100 || x > _camX + _vpW + 100 || y < _camY - 100 || y > _camY + _vpH + 100) {
        continue;
      }
      if      (shop.label.includes('Seed'))    _seedShop(x, y);
      else if (shop.label.includes('General')) _generalStore(x, y);
      else if (shop.label.includes('Repair'))  _repairShop(x, y);
      const shortName = shop.label.replace(' Shop','').replace(' Store','');
      _label(x + T/2, y - 3, shortName, '#ccccff', '8px monospace');
    }
  }

  // ── Resource piles ──────────────────────────────────────────────────────────
  function _drawPiles() {
    for (const pile of (s.piles || [])) {
      const px = pile.x * T, py = pile.y * T;
      _drawPileIcon(px, py, pile.resource_type);
      if (pile.sell_price != null) {
        _label(px + T/2, py + T + 8, `${pile.sell_price}c`, '#f5c842', 'bold 8px monospace');
      }
    }
  }

  // ── Crops ───────────────────────────────────────────────────────────────────
  function _wheatFrostKilled(nx, ny) {
    ctx.lineCap = 'round';
    for (const st of [{x:8,h:7},{x:16,h:5},{x:24,h:6}]) {
      ctx.strokeStyle = '#6a6055';
      ctx.lineWidth = 1.2;
      ctx.beginPath();
      ctx.moveTo(nx + st.x, ny + 27);
      ctx.quadraticCurveTo(nx + st.x + 4, ny + 22 - st.h, nx + st.x + 2, ny + 18);
      ctx.stroke();
      ctx.fillStyle = 'rgba(100, 85, 70, 0.45)';
      ctx.beginPath();
      ctx.ellipse(nx + st.x + 1, ny + 16, 3, 2, 0.4, 0, Math.PI * 2);
      ctx.fill();
    }
    ctx.fillStyle = 'rgba(180, 200, 220, 0.15)';
    ctx.fillRect(nx + 3, ny + 8, T - 6, T - 10);
    ctx.lineCap = 'butt';
  }

  function _drawCrops() {
    for (const crop of (s.crops || [])) {
      const cx = crop.x * T, cy = crop.y * T;
      if (crop.winter_dead)     _wheatFrostKilled(cx, cy);
      else if (crop.ready)      _wheatReady(cx, cy);
      else if (crop.fertilized) _wheatGrowing(cx, cy, '#50c030', '#3a9020');
      else                      _wheatGrowing(cx, cy, '#88a030', '#607020');
    }
  }

  // ── Resource nodes ──────────────────────────────────────────────────────────
  function _drawNodes() {
    for (const node of s.nodes) {
      const nx = node.x * T, ny = node.y * T;

      if (node.construction_active) {
        _constructionSite(nx, ny);
        _label(nx + T/2, ny - 3, 'Building…', '#aab0c8', '7px monospace');
        const cons = node.construction;
        if (cons) {
          const parts = [];
          for (const [k, v] of Object.entries(cons.foundation_remaining || {})) {
            if (v > 0) parts.push(`${k} ${(+v).toFixed(1)}`);
          }
          for (const [k, v] of Object.entries(cons.building_remaining || {})) {
            if (v > 0) parts.push(`${k} ${(+v).toFixed(1)}`);
          }
          if (parts.length) {
            const line = parts.length > 4 ? parts.slice(0, 4).join(', ') + '…' : parts.join(', ');
            _label(nx + T/2, ny + T - 20, 'Need: ' + line, '#8a9aac', '6px monospace');
          }
        }
        continue;
      }
      if (node.is_market) {
        _marketStall(nx, ny, '#602060', '#a040a0');
        _label(nx + T/2, ny - 3, node.owner_name || 'Market', '#d890d8', '7px monospace');
        continue;
      }
      if (node.is_town_hall) {
        _townHall(nx, ny);
        if (node.owner_name) _label(nx + T/2, ny - 3, node.owner_name, 'rgba(245,200,66,0.9)', '7px monospace');
        continue;
      }

      if (node.is_structure) {
        if (node.is_silo) _siloBuilding(nx, ny, node);
        else _drawStructure(nx, ny, node.type);
        if (node.owner_name) _label(nx + T/2, ny - 3, node.owner_name, 'rgba(200,232,138,0.9)', '7px monospace');
      } else {
        _drawWildNode(nx, ny, node);
      }

      // Amount fill bar
      const pct = Math.min(1, node.amount / (node.max || 100));
      ctx.fillStyle = 'rgba(0,0,0,0.55)';
      ctx.fillRect(nx + 3, ny + T - 5, T - 6, 3);
      ctx.fillStyle = pct > 0.4 ? '#60d860' : '#e07030';
      ctx.fillRect(nx + 3, ny + T - 5, (T - 6) * pct, 3);
    }
  }

  function _drawWildNode(nx, ny, node) {
    const type = node.type;
    switch (type) {
      case 'wood':    _woodTreeWild(nx, ny, node.tree_variant); break;
      case 'stone':   _stone(nx, ny);   break;
      case 'gravel':  _gravel(nx, ny);  break;
      case 'clay':    _clay(nx, ny);    break;
      case 'dirt':    _dirt(nx, ny);    break;
      case 'topsoil': _topsoil(nx, ny); break;
      default:
        ctx.fillStyle = '#555';
        ctx.fillRect(nx + 4, ny + 4, T - 8, T - 12);
    }
  }

  function _constructionSite(nx, ny) {
    ctx.fillStyle = '#6a6050';
    ctx.fillRect(nx + 2, ny + T - 8, T - 4, 6);
    ctx.fillStyle = '#c9b090';
    ctx.fillRect(nx + 6, ny + 8, T - 12, T - 18);
    ctx.strokeStyle = 'rgba(0,0,0,0.35)';
    ctx.strokeRect(nx + 6, ny + 8, T - 12, T - 18);
    ctx.fillStyle = '#e07030';
    ctx.fillRect(nx + T / 2 - 3, ny + 4, 6, 5);
  }

  function _siloBuilding(nx, ny, node) {
    const cylW = T - 10;
    const cylH = T - 12;
    const cx = nx + T / 2;
    const topY = ny + 7;
    ctx.fillStyle = '#b8c0d0';
    ctx.beginPath();
    ctx.ellipse(cx, topY, cylW / 2, 5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#9aa8b8';
    ctx.fillRect(nx + 5, topY, cylW, cylH);
    ctx.fillStyle = '#b8c0d0';
    ctx.beginPath();
    ctx.ellipse(cx, topY + cylH, cylW / 2, 5, 0, 0, Math.PI * 2);
    ctx.fill();
    ctx.strokeStyle = 'rgba(40,50,60,0.4)';
    ctx.strokeRect(nx + 5, topY, cylW, cylH);
    const cap = node.silo_capacity || 5000;
    const w = node.silo_wheat || 0;
    const pct = cap > 0 ? Math.min(1, w / cap) : 0;
    const innerTop = topY + 5;
    const innerH = cylH - 10;
    const innerW = cylW - 8;
    ctx.fillStyle = 'rgba(0,0,0,0.45)';
    ctx.fillRect(nx + 9, innerTop, innerW, innerH);
    const fillH = innerH * pct;
    ctx.fillStyle = pct > 0.5 ? '#d8c060' : '#a89040';
    ctx.fillRect(nx + 9, innerTop + innerH - fillH, innerW, fillH);
  }

  function _drawStructure(nx, ny, type) {
    switch (type) {
      case 'manure':  _stable(nx, ny);       break;
      case 'gravel':  _gravelPit(nx, ny);    break;
      case 'compost': _compostHeap(nx, ny);  break;
      case 'topsoil': _topsoilMound(nx, ny); break;
      default:
        ctx.fillStyle = '#5a5a4a';
        ctx.fillRect(nx + 3, ny + 5, T - 6, T - 9);
    }
  }

  // ── Wild resource icons ─────────────────────────────────────────────────────

  /** Wild wood nodes: standing trees (variant 0–7 deciduous, 8–15 conifer). */
  function _woodTreeWild(nx, ny, variant) {
    const v = ((variant == null ? 0 : variant) | 0) & 15;
    if (v >= 8) _coniferSprite(nx, ny, v - 8);
    else _deciduousSprite(nx, ny, v);
  }

  function _deciduousSprite(nx, ny, sub) {
    const cx = nx + 16;
    const trunk = (w, h, xo = 0) => {
      ctx.fillStyle = '#4a3220';
      ctx.fillRect(cx - w / 2 + xo, ny + 32 - h, w, h);
      ctx.strokeStyle = 'rgba(0,0,0,0.2)';
      ctx.strokeRect(cx - w / 2 + xo, ny + 32 - h, w, h);
    };
    ctx.lineWidth = 1;
    switch (sub) {
      case 0: // round lollipop
        trunk(4, 11);
        ctx.fillStyle = '#2f7a32';
        ctx.beginPath(); ctx.arc(cx, ny + 14, 10, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#3fa040';
        ctx.beginPath(); ctx.arc(cx - 3, ny + 12, 4, 0, Math.PI * 2); ctx.fill();
        break;
      case 1: // wide oval crown
        trunk(4, 9);
        ctx.fillStyle = '#2d6828';
        ctx.beginPath(); ctx.ellipse(cx, ny + 13, 12, 8, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#3a8a36';
        ctx.beginPath(); ctx.ellipse(cx + 2, ny + 11, 5, 4, 0.2, 0, Math.PI * 2); ctx.fill();
        break;
      case 2: // twin round crowns
        trunk(5, 8);
        for (const ox of [-5, 5]) {
          ctx.fillStyle = ox < 0 ? '#2a6a28' : '#358a32';
          ctx.beginPath(); ctx.arc(cx + ox, ny + 13, 7, 0, Math.PI * 2); ctx.fill();
        }
        break;
      case 3: // tall narrow
        trunk(3, 16);
        ctx.fillStyle = '#327030';
        ctx.beginPath(); ctx.arc(cx, ny + 10, 6, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#3d8840';
        ctx.beginPath(); ctx.arc(cx, ny + 7, 3.5, 0, Math.PI * 2); ctx.fill();
        break;
      case 4: // short trunk, broad low crown
        trunk(5, 6);
        ctx.fillStyle = '#2a6828';
        ctx.beginPath(); ctx.ellipse(cx, ny + 12, 13, 9, 0, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#4a9a48';
        ctx.beginPath(); ctx.ellipse(cx - 4, ny + 11, 5, 4, 0, 0, Math.PI * 2); ctx.fill();
        break;
      case 5: // triple blob
        trunk(4, 10);
        const blobs = [[0, 12], [-6, 15], [5, 16]];
        blobs.forEach(([ox, oy], i) => {
          ctx.fillStyle = i === 0 ? '#2e7030' : '#3a8c38';
          ctx.beginPath(); ctx.arc(cx + ox, ny + oy, 5, 0, Math.PI * 2); ctx.fill();
        });
        break;
      case 6: // tilted ellipse crown
        trunk(4, 10);
        ctx.save();
        ctx.translate(cx, ny + 13);
        ctx.rotate(0.35);
        ctx.fillStyle = '#2f682c';
        ctx.beginPath(); ctx.ellipse(0, 0, 11, 7, 0, 0, Math.PI * 2); ctx.fill();
        ctx.restore();
        break;
      default: // 7 — autumn mix
        trunk(4, 9);
        ctx.fillStyle = '#6a7a28';
        ctx.beginPath(); ctx.arc(cx, ny + 13, 9, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#a86820';
        ctx.beginPath(); ctx.arc(cx + 4, ny + 14, 4, 0, Math.PI * 2); ctx.fill();
        ctx.fillStyle = '#2d6028';
        ctx.beginPath(); ctx.arc(cx - 3, ny + 11, 4, 0, Math.PI * 2); ctx.fill();
        break;
    }
  }

  function _coniferSprite(nx, ny, sub) {
    const cx = nx + 16;
    const tri = (y0, w, h, col) => {
      ctx.fillStyle = col;
      ctx.beginPath();
      ctx.moveTo(cx, y0 - h);
      ctx.lineTo(cx - w / 2, y0);
      ctx.lineTo(cx + w / 2, y0);
      ctx.closePath();
      ctx.fill();
    };
    ctx.lineWidth = 1;
    switch (sub) {
      case 0: // three stacked
        ctx.fillStyle = '#3a2818';
        ctx.fillRect(cx - 2, ny + 18, 4, 14);
        tri(ny + 22, 18, 9, '#1d5020');
        tri(ny + 17, 14, 8, '#25662a');
        tri(ny + 12, 10, 7, '#2f7a34');
        break;
      case 1: // one tall triangle
        ctx.fillStyle = '#352818';
        ctx.fillRect(cx - 1.5, ny + 12, 3, 20);
        tri(ny + 14, 12, 16, '#1a5530');
        break;
      case 2: // four tight layers
        ctx.fillStyle = '#3a2818';
        ctx.fillRect(cx - 2, ny + 20, 4, 12);
        tri(ny + 24, 20, 6, '#174018');
        tri(ny + 20, 17, 6, '#1f5520');
        tri(ny + 16, 13, 6, '#276628');
        tri(ny + 12, 9, 5, '#2f7830');
        break;
      case 3: // wide base
        ctx.fillStyle = '#3a2818';
        ctx.fillRect(cx - 2.5, ny + 19, 5, 13);
        tri(ny + 22, 22, 8, '#1a4820');
        tri(ny + 16, 16, 9, '#24702a');
        break;
      case 4: // leaning stack (draw in local space so trunk + foliage stay aligned)
        ctx.save();
        ctx.translate(cx + 2, 0);
        ctx.rotate(-0.12);
        ctx.fillStyle = '#3a2818';
        ctx.fillRect(-2, ny + 18, 4, 14);
        ctx.fillStyle = '#1d5020';
        ctx.beginPath();
        ctx.moveTo(0, ny + 14); ctx.lineTo(-8, ny + 22); ctx.lineTo(8, ny + 22); ctx.closePath(); ctx.fill();
        ctx.fillStyle = '#276628';
        ctx.beginPath();
        ctx.moveTo(0, ny + 9); ctx.lineTo(-6, ny + 16); ctx.lineTo(6, ny + 16); ctx.closePath(); ctx.fill();
        ctx.restore();
        break;
      case 5: // shaded facets
        ctx.fillStyle = '#3a2818';
        ctx.fillRect(cx - 2, ny + 19, 4, 13);
        tri(ny + 22, 18, 9, '#143818');
        tri(ny + 17, 14, 8, '#1f5520');
        ctx.fillStyle = 'rgba(80,120,80,0.35)';
        ctx.beginPath();
        ctx.moveTo(cx - 5, ny + 17); ctx.lineTo(cx - 9, ny + 22); ctx.lineTo(cx - 2, ny + 22);
        ctx.closePath(); ctx.fill();
        break;
      case 6: // sparse tall
        ctx.fillStyle = '#302418';
        ctx.fillRect(cx - 1.5, ny + 14, 3, 18);
        tri(ny + 16, 8, 12, '#1a5024');
        tri(ny + 11, 6, 8, '#246030');
        break;
      default: // 7 — short bushy
        ctx.fillStyle = '#3a2818';
        ctx.fillRect(cx - 2.5, ny + 21, 5, 11);
        tri(ny + 24, 22, 6, '#174018');
        tri(ny + 20, 18, 7, '#226024');
        tri(ny + 16, 12, 6, '#2c702c');
        break;
    }
  }

  function _stone(nx, ny) {
    // Large boulder with highlight + small companion stone
    ctx.beginPath();
    ctx.moveTo(nx+7, ny+21); ctx.lineTo(nx+9, ny+10);
    ctx.lineTo(nx+18, ny+8); ctx.lineTo(nx+25, ny+13);
    ctx.lineTo(nx+24, ny+23); ctx.lineTo(nx+14, ny+27); ctx.closePath();
    ctx.fillStyle = '#8a8a9a'; ctx.fill();
    // Top highlight face
    ctx.beginPath();
    ctx.moveTo(nx+10, ny+11); ctx.lineTo(nx+18, ny+9);
    ctx.lineTo(nx+21, ny+15); ctx.lineTo(nx+12, ny+16); ctx.closePath();
    ctx.fillStyle = '#aaaabb'; ctx.fill();
    // Edge shadow
    ctx.strokeStyle = '#505060'; ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(nx+24, ny+23); ctx.lineTo(nx+14, ny+27); ctx.lineTo(nx+7, ny+21);
    ctx.stroke();
    // Small stone
    ctx.beginPath();
    ctx.moveTo(nx+4, ny+14); ctx.lineTo(nx+5, ny+9);
    ctx.lineTo(nx+10, ny+10); ctx.lineTo(nx+9, ny+15); ctx.closePath();
    ctx.fillStyle = '#7a7a8a'; ctx.fill();
    ctx.beginPath();
    ctx.moveTo(nx+5, ny+10); ctx.lineTo(nx+8, ny+9); ctx.lineTo(nx+9, ny+11); ctx.closePath();
    ctx.fillStyle = '#9898a8'; ctx.fill();
  }

  function _gravel(nx, ny) {
    const pebbles = [
      {x:7,y:9,rx:2.8,ry:2.0,a:0.4},{x:13,y:7,rx:2.2,ry:1.6,a:1.1},
      {x:20,y:9,rx:2.5,ry:1.8,a:0.2},{x:25,y:8,rx:1.8,ry:1.4,a:0.8},
      {x:9,y:15,rx:2.3,ry:1.7,a:0.5},{x:16,y:14,rx:2.6,ry:1.9,a:1.3},
      {x:22,y:16,rx:2.0,ry:1.5,a:0.1},{x:6,y:21,rx:2.4,ry:1.8,a:0.9},
      {x:12,y:22,rx:2.0,ry:1.5,a:0.3},{x:19,y:21,rx:2.5,ry:1.8,a:1.0},
      {x:25,y:22,rx:1.8,ry:1.3,a:0.6},{x:15,y:18,rx:1.8,ry:1.3,a:0.7},
    ];
    for (const p of pebbles) {
      const v = (p.x * 17 + p.y * 11) % 3;
      ctx.fillStyle = ['#8e8e8e','#727272','#a0a0a0'][v];
      ctx.beginPath();
      ctx.ellipse(nx+p.x, ny+p.y, p.rx, p.ry, p.a, 0, Math.PI*2);
      ctx.fill();
      ctx.strokeStyle = ['#666','#555','#888'][v];
      ctx.lineWidth = 0.4; ctx.stroke();
    }
  }

  function _clay(nx, ny) {
    ctx.beginPath();
    ctx.moveTo(nx+5, ny+20);
    ctx.bezierCurveTo(nx+3,  ny+11, nx+8,  ny+6,  nx+16, ny+6);
    ctx.bezierCurveTo(nx+25, ny+6,  nx+29, ny+13, nx+27, ny+21);
    ctx.bezierCurveTo(nx+25, ny+27, nx+7,  ny+28, nx+5,  ny+20);
    ctx.fillStyle = '#9a4a26'; ctx.fill();
    // Highlight dome
    ctx.beginPath();
    ctx.ellipse(nx+14, ny+14, 8, 5, -0.35, 0, Math.PI*2);
    ctx.fillStyle = '#c46838'; ctx.fill();
    // Wet sheen
    ctx.beginPath();
    ctx.ellipse(nx+12, ny+12, 4, 2.5, -0.6, 0, Math.PI*2);
    ctx.fillStyle = 'rgba(200,130,90,0.35)'; ctx.fill();
    ctx.strokeStyle = '#6a2e10'; ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(nx+5, ny+20);
    ctx.bezierCurveTo(nx+3,  ny+11, nx+8,  ny+6,  nx+16, ny+6);
    ctx.bezierCurveTo(nx+25, ny+6,  nx+29, ny+13, nx+27, ny+21);
    ctx.stroke();
  }

  function _dirt(nx, ny) {
    ctx.beginPath();
    ctx.moveTo(nx+5, ny+14);
    ctx.bezierCurveTo(nx+6, ny+7, nx+14, ny+5, nx+22, ny+8);
    ctx.bezierCurveTo(nx+28, ny+10, nx+27, ny+20, nx+22, ny+24);
    ctx.bezierCurveTo(nx+16, ny+28, nx+6,  ny+25, nx+5,  ny+14);
    ctx.fillStyle = '#7a5030'; ctx.fill();
    // Clod shadows
    for (const c of [{x:10,y:13,rx:4,ry:3,a:0.5},{x:19,y:17,rx:3,ry:2,a:-0.3},{x:14,y:21,rx:3.5,ry:2.5,a:0.2}]) {
      ctx.beginPath(); ctx.ellipse(nx+c.x, ny+c.y, c.rx, c.ry, c.a, 0, Math.PI*2);
      ctx.fillStyle = '#604020'; ctx.fill();
    }
  }

  function _topsoil(nx, ny) {
    ctx.beginPath();
    ctx.moveTo(nx+4, ny+16);
    ctx.bezierCurveTo(nx+5, ny+7, nx+12, ny+4, nx+16, ny+4);
    ctx.bezierCurveTo(nx+22, ny+4, nx+28, ny+9, nx+28, ny+17);
    ctx.bezierCurveTo(nx+28, ny+26, nx+20, ny+29, nx+16, ny+29);
    ctx.bezierCurveTo(nx+8,  ny+29, nx+4,  ny+25, nx+4,  ny+16);
    ctx.fillStyle = '#3a2010'; ctx.fill();
    // Rich dark core
    ctx.beginPath();
    ctx.ellipse(nx+16, ny+17, 7, 5.5, 0, 0, Math.PI*2);
    ctx.fillStyle = '#221208'; ctx.fill();
    // Texture marks
    ctx.strokeStyle = 'rgba(80,50,20,0.5)'; ctx.lineWidth = 0.6;
    ctx.beginPath();
    ctx.moveTo(nx+9,  ny+14); ctx.lineTo(nx+14, ny+17);
    ctx.moveTo(nx+18, ny+12); ctx.lineTo(nx+22, ny+16);
    ctx.moveTo(nx+11, ny+21); ctx.lineTo(nx+15, ny+23);
    ctx.stroke();
  }

  // ── Structure icons ─────────────────────────────────────────────────────────

  function _stable(nx, ny) {
    // Barn building (top-down)
    ctx.fillStyle = '#8b5a2b'; ctx.fillRect(nx+3, ny+5, T-6, T-9);
    // Darker roof area
    ctx.fillStyle = '#6a3e1c'; ctx.fillRect(nx+3, ny+5, T-6, 6);
    // Roof ridge
    ctx.strokeStyle = '#4a2810'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.moveTo(nx+T/2, ny+5); ctx.lineTo(nx+T/2, ny+11); ctx.stroke();
    // Stall dividers
    ctx.strokeStyle = '#5a3018'; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(nx+T/2, ny+13); ctx.lineTo(nx+T/2, ny+T-4);
    ctx.moveTo(nx+3,   ny+T/2+1); ctx.lineTo(nx+T-3, ny+T/2+1);
    ctx.stroke();
    // Hay bales in each stall
    ctx.fillStyle = '#d4a820';
    ctx.fillRect(nx+5,    ny+14, 7, 4);
    ctx.fillRect(nx+T-12, ny+14, 7, 4);
    // Hay stripe texture
    ctx.strokeStyle = '#a07810'; ctx.lineWidth = 0.5;
    for (let i = 1; i < 3; i++) {
      ctx.beginPath(); ctx.moveTo(nx+5+i*2, ny+14); ctx.lineTo(nx+5+i*2, ny+18); ctx.stroke();
      ctx.beginPath(); ctx.moveTo(nx+T-12+i*2, ny+14); ctx.lineTo(nx+T-12+i*2, ny+18); ctx.stroke();
    }
    // Door
    ctx.fillStyle = '#2a1008'; ctx.fillRect(nx+T/2-4, ny+T-8, 8, 6);
    ctx.strokeStyle = '#4a2810'; ctx.lineWidth = 1;
    ctx.strokeRect(nx+3, ny+5, T-6, T-9);
  }

  function _gravelPit(nx, ny) {
    // Circular pit with rim and gravel inside
    ctx.beginPath(); ctx.ellipse(nx+T/2, ny+T/2, 13, 11, 0, 0, Math.PI*2);
    ctx.fillStyle = '#585848'; ctx.fill();
    ctx.beginPath(); ctx.ellipse(nx+T/2, ny+T/2+1, 10, 8, 0, 0, Math.PI*2);
    ctx.fillStyle = '#2e2e1e'; ctx.fill();
    // Gravel chips inside
    for (const c of [{x:-5,y:-2,rx:2.5,a:0.2},{x:0,y:-4,rx:2,a:1.0},{x:5,y:-1,rx:2.5,a:0.5},
                     {x:-3,y:3,rx:2,a:0.8},{x:3,y:4,rx:2.5,a:0.3},{x:0,y:1,rx:1.8,a:0.6}]) {
      ctx.fillStyle = '#909090';
      ctx.beginPath(); ctx.ellipse(nx+T/2+c.x, ny+T/2+c.y, c.rx, c.rx*0.65, c.a, 0, Math.PI*2);
      ctx.fill();
    }
    // Rim highlight
    ctx.strokeStyle = '#707060'; ctx.lineWidth = 1.5;
    ctx.beginPath(); ctx.ellipse(nx+T/2, ny+T/2, 13, 11, 0, Math.PI*0.9, Math.PI*1.9); ctx.stroke();
    ctx.strokeStyle = '#3a3a2a'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.ellipse(nx+T/2, ny+T/2, 13, 11, 0, Math.PI*1.9, Math.PI*2.9); ctx.stroke();
  }

  function _compostHeap(nx, ny) {
    // Organic mound
    ctx.beginPath();
    ctx.moveTo(nx+4, ny+18);
    ctx.bezierCurveTo(nx+3, ny+10, nx+10, ny+6, nx+16, ny+6);
    ctx.bezierCurveTo(nx+23, ny+6, nx+29, ny+11, nx+28, ny+19);
    ctx.bezierCurveTo(nx+26, ny+27, nx+8,  ny+28, nx+4,  ny+18);
    ctx.fillStyle = '#283e12'; ctx.fill();
    // Decomposing bits
    const bits = [{x:9,y:14,c:'#58800e'},{x:15,y:11,c:'#486818'},{x:21,y:14,c:'#62900c'},
                  {x:12,y:19,c:'#7a4a20'},{x:20,y:20,c:'#547022'},{x:16,y:17,c:'#385212'}];
    for (const b of bits) {
      ctx.beginPath(); ctx.ellipse(nx+b.x, ny+b.y, 3, 2, (b.x*0.2)%Math.PI, 0, Math.PI*2);
      ctx.fillStyle = b.c; ctx.fill();
    }
    // Steam wisps
    ctx.strokeStyle = 'rgba(180,220,100,0.3)'; ctx.lineWidth = 1;
    ctx.beginPath();
    ctx.moveTo(nx+12, ny+9);
    ctx.bezierCurveTo(nx+10, ny+6, nx+13, ny+4, nx+11, ny+1);
    ctx.moveTo(nx+19, ny+9);
    ctx.bezierCurveTo(nx+21, ny+6, nx+18, ny+3, nx+20, ny+1);
    ctx.stroke();
  }

  function _topsoilMound(nx, ny) {
    // Neat soil mound, darker and denser than wild topsoil
    ctx.beginPath();
    ctx.arc(nx+T/2, ny+T/2+3, 13, Math.PI, 0);
    ctx.bezierCurveTo(nx+T/2+13, ny+T/2+8, nx+T/2-13, ny+T/2+8, nx+T/2-13, ny+T/2+3);
    ctx.fillStyle = '#3a2010'; ctx.fill();
    ctx.beginPath(); ctx.ellipse(nx+T/2, ny+T/2+6, 11, 5, 0, 0, Math.PI*2);
    ctx.fillStyle = '#1e0e06'; ctx.fill();
    ctx.beginPath(); ctx.ellipse(nx+T/2-2, ny+T/2-1, 6, 4, -0.3, 0, Math.PI*2);
    ctx.fillStyle = '#4a2e18'; ctx.fill();
  }

  // ── NPC shop buildings ──────────────────────────────────────────────────────

  function _shopBase(nx, ny, wallColor, roofColor) {
    // Gabled roof area (top third)
    ctx.fillStyle = roofColor;
    ctx.fillRect(nx+2, ny+2, T-4, 12);
    ctx.strokeStyle = _shade(roofColor, -40); ctx.lineWidth = 1;
    ctx.beginPath(); ctx.moveTo(nx+T/2, ny+2); ctx.lineTo(nx+T/2, ny+14); ctx.stroke();
    // Walls
    ctx.fillStyle = wallColor;
    ctx.fillRect(nx+2, ny+14, T-4, T-16);
    // Door
    ctx.fillStyle = _shade(wallColor, -50);
    ctx.fillRect(nx+T/2-4, ny+T-9, 8, 8);
    ctx.beginPath(); ctx.arc(nx+T/2, ny+T-9, 4, Math.PI, 0); ctx.fill();
    // Building outline
    ctx.strokeStyle = _shade(wallColor, -50); ctx.lineWidth = 1;
    ctx.strokeRect(nx+2, ny+2, T-4, T-4);
  }

  function _seedShop(nx, ny) {
    _shopBase(nx, ny, '#2a6a1a', '#1e8a28');
    // Sprout icon on wall
    ctx.strokeStyle = '#80ef40'; ctx.lineWidth = 2; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(nx+22, ny+25); ctx.lineTo(nx+22, ny+16);
    ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(nx+22, ny+22);
    ctx.bezierCurveTo(nx+16, ny+19, nx+15, ny+15, nx+19, ny+14);
    ctx.strokeStyle = '#60cf20'; ctx.fill(); ctx.stroke();
    ctx.beginPath();
    ctx.moveTo(nx+22, ny+19);
    ctx.bezierCurveTo(nx+28, ny+16, nx+29, ny+13, nx+25, ny+12);
    ctx.stroke();
    ctx.lineCap = 'butt';
  }

  function _generalStore(nx, ny) {
    _shopBase(nx, ny, '#7a5020', '#9a6a30');
    // Barrel icon on wall
    ctx.fillStyle = '#6a3e10';
    ctx.beginPath(); ctx.ellipse(nx+22, ny+22, 5, 6, 0, 0, Math.PI*2); ctx.fill();
    ctx.strokeStyle = '#4a2808'; ctx.lineWidth = 1;
    ctx.beginPath(); ctx.ellipse(nx+22, ny+22, 5, 6, 0, 0, Math.PI*2); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(nx+22, ny+19, 5, 2, 0, 0, Math.PI*2); ctx.stroke();
    ctx.beginPath(); ctx.ellipse(nx+22, ny+25, 5, 2, 0, 0, Math.PI*2); ctx.stroke();
  }

  function _repairShop(nx, ny) {
    _shopBase(nx, ny, '#484858', '#383848');
    // Wrench icon on wall
    ctx.strokeStyle = '#b0b0c8'; ctx.lineWidth = 2; ctx.lineCap = 'round';
    ctx.beginPath(); ctx.moveTo(nx+19, ny+26); ctx.lineTo(nx+26, ny+17); ctx.stroke();
    ctx.beginPath(); ctx.arc(nx+26, ny+17, 3.5, 0, Math.PI*2);
    ctx.strokeStyle = '#b0b0c8'; ctx.lineWidth = 1.5; ctx.stroke();
    ctx.beginPath(); ctx.arc(nx+19, ny+26, 3, 0, Math.PI*2); ctx.stroke();
    ctx.lineCap = 'butt';
  }

  // ── Player market stall ─────────────────────────────────────────────────────
  function _marketStall(nx, ny, awningDark, awningLight) {
    // Counter
    ctx.fillStyle = '#6a4810'; ctx.fillRect(nx+2, ny+16, T-4, T-18);
    ctx.fillStyle = '#8a6020'; ctx.fillRect(nx+2, ny+16, T-4, 3);
    // Striped awning
    const sw = (T-4) / 4;
    for (let i = 0; i < 4; i++) {
      ctx.fillStyle = i % 2 === 0 ? awningDark : awningLight;
      ctx.fillRect(nx+2+i*sw, ny+5, sw, 11);
    }
    ctx.fillStyle = awningDark; ctx.fillRect(nx+2, ny+5, T-4, 2);
    // Scalloped awning bottom
    for (let i = 0; i < 4; i++) {
      ctx.fillStyle = awningDark;
      ctx.beginPath(); ctx.arc(nx+2+(i+0.5)*sw, ny+16, sw/2, 0, Math.PI); ctx.fill();
    }
    // Coins on counter
    for (let i = 0; i < 3; i++) {
      ctx.beginPath(); ctx.ellipse(nx+T/2, ny+22-i*2, 5, 1.8, 0, 0, Math.PI*2);
      ctx.fillStyle = i === 0 ? '#e8c040' : '#c09820'; ctx.fill();
      ctx.strokeStyle = '#907010'; ctx.lineWidth = 0.5; ctx.stroke();
    }
  }

  // ── Town hall ───────────────────────────────────────────────────────────────
  function _townHall(nx, ny) {
    // Base building
    ctx.fillStyle = '#4a3818'; ctx.fillRect(nx+2, ny+10, T-4, T-12);
    // Pediment (triangular gable)
    ctx.beginPath();
    ctx.moveTo(nx+2, ny+16); ctx.lineTo(nx+T/2, ny+5); ctx.lineTo(nx+T-2, ny+16);
    ctx.closePath();
    ctx.fillStyle = '#c8a030'; ctx.fill();
    ctx.strokeStyle = '#907010'; ctx.lineWidth = 1; ctx.stroke();
    // Columns (four pillars)
    ctx.fillStyle = '#d4b860';
    for (const cx of [5, 11, 21, 27]) {
      ctx.fillRect(nx+cx, ny+16, 3, T-18);
    }
    // Entablature (beam across columns)
    ctx.fillStyle = '#c0a040'; ctx.fillRect(nx+2, ny+15, T-4, 3);
    // Dome
    ctx.fillStyle = '#d8b838';
    ctx.beginPath(); ctx.ellipse(nx+T/2, ny+10, 7, 5, 0, Math.PI, 0); ctx.fill();
    ctx.strokeStyle = '#908020'; ctx.lineWidth = 0.8; ctx.stroke();
    // Door arch
    ctx.fillStyle = '#201408';
    ctx.fillRect(nx+T/2-4, ny+T-9, 8, 9);
    ctx.beginPath(); ctx.arc(nx+T/2, ny+T-9, 4, Math.PI, 0); ctx.fill();
    // Steps
    ctx.fillStyle = '#c0a458'; ctx.fillRect(nx+4, ny+T-4, T-8, 3);
    ctx.fillStyle = '#b09040'; ctx.fillRect(nx+6, ny+T-7, T-12, 3);
    ctx.strokeStyle = '#4a3010'; ctx.lineWidth = 1;
    ctx.strokeRect(nx+2, ny+10, T-4, T-12);
  }

  // ── Crop growth stages ──────────────────────────────────────────────────────
  function _wheatGrowing(nx, ny, leafColor, stemColor) {
    ctx.lineCap = 'round';
    for (const st of [{x:8,h:11},{x:16,h:13},{x:24,h:10}]) {
      ctx.strokeStyle = stemColor; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(nx+st.x, ny+27); ctx.lineTo(nx+st.x, ny+27-st.h); ctx.stroke();
      ctx.beginPath();
      ctx.moveTo(nx+st.x, ny+27-st.h*0.55);
      ctx.bezierCurveTo(nx+st.x+7, ny+27-st.h*0.75, nx+st.x+6, ny+27-st.h*0.3, nx+st.x, ny+27-st.h*0.3);
      ctx.fillStyle = leafColor; ctx.fill();
    }
    ctx.lineCap = 'butt';
  }

  function _wheatReady(nx, ny) {
    ctx.lineCap = 'round';
    for (const s of [{x:7,h:16},{x:13,h:18},{x:19,h:17},{x:25,h:15}]) {
      ctx.strokeStyle = '#9a7e18'; ctx.lineWidth = 1.5;
      ctx.beginPath(); ctx.moveTo(nx+s.x, ny+28); ctx.lineTo(nx+s.x, ny+28-s.h); ctx.stroke();
      ctx.fillStyle = '#e8c040';
      ctx.beginPath(); ctx.ellipse(nx+s.x, ny+28-s.h, 2.5, 5.5, 0, 0, Math.PI*2); ctx.fill();
      ctx.strokeStyle = '#c0a020'; ctx.lineWidth = 0.5;
      for (const w of [-1, 0, 1]) {
        ctx.beginPath();
        ctx.moveTo(nx+s.x+w, ny+28-s.h-3);
        ctx.lineTo(nx+s.x+w*3.5, ny+28-s.h-9);
        ctx.stroke();
      }
    }
    ctx.lineCap = 'butt';
  }

  // ── Pile icon ───────────────────────────────────────────────────────────────
  function _woodLogsPile(px, py) {
    // Cut log ends (same language as the old wild wood icon — good for *piles*, not standing trees)
    const logs = [{ x: 9, y: 19, r: 5.5 }, { x: 17, y: 21, r: 4.5 }, { x: 12, y: 24, r: 3.8 }];
    for (const log of logs) {
      ctx.beginPath(); ctx.arc(px + log.x, py + log.y, log.r, 0, Math.PI * 2);
      ctx.fillStyle = '#3d1f08'; ctx.fill();
      ctx.beginPath(); ctx.arc(px + log.x, py + log.y, log.r - 1.2, 0, Math.PI * 2);
      ctx.fillStyle = '#7a4218'; ctx.fill();
      ctx.beginPath(); ctx.arc(px + log.x, py + log.y, log.r - 2.8, 0, Math.PI * 2);
      ctx.fillStyle = '#9a5828'; ctx.fill();
      ctx.beginPath(); ctx.arc(px + log.x, py + log.y, log.r - 2, 0, Math.PI * 2);
      ctx.strokeStyle = 'rgba(50,22,5,0.45)'; ctx.lineWidth = 0.5; ctx.stroke();
      ctx.beginPath(); ctx.arc(px + log.x, py + log.y, 1.5, 0, Math.PI * 2);
      ctx.fillStyle = '#5a2e0e'; ctx.fill();
    }
  }

  function _drawPileIcon(px, py, type) {
    if (type === 'wood') {
      _woodLogsPile(px, py);
      return;
    }
    const cols = {
      manure:'#5a3020', fertilizer:'#2a6a1a', gravel:'#888', topsoil:'#3a2010', compost:'#2a4015',
      wood:'#5a3a1a', stone:'#606070', clay:'#8a5030', dirt:'#704828', wheat:'#c0a028',
    };
    const col = cols[type] || '#555';
    // Three overlapping blobs for "pile" appearance
    ctx.globalAlpha = 0.9;
    ctx.fillStyle = _shade(col, -25); ctx.beginPath(); ctx.ellipse(px+11, py+14, 7, 5, 0.3, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = col;              ctx.beginPath(); ctx.ellipse(px+17, py+17, 7, 5, -0.2, 0, Math.PI*2); ctx.fill();
    ctx.fillStyle = _shade(col,  25); ctx.beginPath(); ctx.ellipse(px+12, py+21, 6, 4, 0.1, 0, Math.PI*2); ctx.fill();
    ctx.globalAlpha = 1.0;
  }

  // ── Helpers ─────────────────────────────────────────────────────────────────

  function _shade(hex, amount) {
    if (!hex.startsWith('#')) return hex;
    const n = parseInt(hex.slice(1), 16);
    const r = Math.max(0, Math.min(255, ((n >> 16) & 0xff) + amount));
    const g = Math.max(0, Math.min(255, ((n >>  8) & 0xff) + amount));
    const b = Math.max(0, Math.min(255, ( n        & 0xff) + amount));
    return `rgb(${r},${g},${b})`;
  }

  /** 0 = paint like new (100), 1 = badly worn — for tub tint + wear overlay. */
  function _paintDistress(wbPaint) {
    const p = wbPaint != null ? Number(wbPaint) : 100;
    if (Number.isNaN(p) || p >= 78) return 0;
    const t = (78 - p) / 78;
    return Math.min(1, t * t * 1.15);
  }

  /** Dingy / sun-faded tub when paint condition is poor. */
  function _weatherTubColor(baseHex, distress) {
    if (distress < 0.04 || !baseHex.startsWith('#')) return baseHex;
    return _shade(baseHex, -48 * distress - 8 * distress * distress);
  }

  /** Scratches / rust streaks on the bucket (after tub is drawn). */
  function _wheelbarrowPaintWear(px, py, facing, distress) {
    if (distress < 0.06) return;
    const a = 0.1 + 0.55 * distress;
    ctx.save();
    ctx.strokeStyle = `rgba(95, 48, 28, ${a})`;
    ctx.lineWidth = 0.85;
    ctx.lineCap = 'round';
    const cx = px + T / 2;
    const f = facing || 'down';
    const n = 4 + Math.floor(distress * 5);
    const seed = (px + py * 17) % 1000;
    if (f === 'up') {
      for (let i = 0; i < n; i++) {
        const j = (seed + i * 31) % 17;
        ctx.beginPath();
        ctx.moveTo(px + 9 + (j % 5), py + 9 + (i % 3));
        ctx.lineTo(px + 14 + (i % 4), py + 16 + ((i + j) % 4));
        ctx.stroke();
      }
      ctx.strokeStyle = `rgba(55, 35, 22, ${a * 0.65})`;
      ctx.lineWidth = 0.45;
      ctx.beginPath();
      ctx.moveTo(px + 11, py + 11);
      ctx.lineTo(px + T - 13, py + 12);
      ctx.stroke();
    } else if (f === 'down') {
      for (let i = 0; i < n; i++) {
        const j = (seed + i * 29) % 19;
        ctx.beginPath();
        ctx.moveTo(px + 8 + (j % 6), py + 9 + (i % 4));
        ctx.lineTo(px + 15 + (i % 5), py + 18 + ((i + j) % 3));
        ctx.stroke();
      }
      ctx.strokeStyle = `rgba(55, 35, 22, ${a * 0.65})`;
      ctx.lineWidth = 0.45;
      ctx.beginPath();
      ctx.moveTo(px + 10, py + 10);
      ctx.lineTo(px + T - 11, py + 11);
      ctx.stroke();
    } else {
      const flip = f === 'right';
      const off = flip ? (x) => px + T - (x - px) : (x) => x;
      for (let i = 0; i < n; i++) {
        const j = (seed + i * 23) % 15;
        ctx.beginPath();
        ctx.moveTo(off(px + 18 + (j % 4)), py + 10 + (i % 3));
        ctx.lineTo(off(px + 24 + (i % 3)), py + 17 + ((i + j) % 4));
        ctx.stroke();
      }
      ctx.strokeStyle = `rgba(55, 35, 22, ${a * 0.65})`;
      ctx.lineWidth = 0.45;
      ctx.beginPath();
      ctx.moveTo(off(px + 19), py + 11);
      ctx.lineTo(off(px + 27), py + 12);
      ctx.stroke();
    }
    ctx.restore();
  }

  function _label(cx, cy, text, color, font) {
    ctx.font        = font || '8px monospace';
    ctx.textAlign   = 'center';
    ctx.shadowColor = 'rgba(0,0,0,0.9)';
    ctx.shadowBlur  = 3;
    ctx.fillStyle   = color || '#fff';
    ctx.fillText(text, cx, cy);
    ctx.shadowBlur  = 0;
  }

  // ── Players / Wheelbarrows ──────────────────────────────────────────────────
  function _drawPlayers() {
    for (const p of (s.players || [])) {
      if (!p || p.id == null || !s.player || p.id === s.player.id) continue;
      const face = s._otherFacing[p.id] || 'down';
      _wheelbarrow(p.x * T, p.y * T, '#6ab0e8', p.username, p.flat_tire, 0, face, true, p.wb_paint);
    }
    if (s.player) {
      const bucket = s.player.bucket || {};
      const total  = Object.values(bucket).reduce((a, b) => a + b, 0);
      const cap    = s.player.bucket_cap_effective != null ? s.player.bucket_cap_effective : (s.player.bucket_cap || 10);
      const face   = s.facing || 'down';
      _wheelbarrow(s.player.x * T, s.player.y * T, '#f5c842', s.player.username,
                   s.player.flat_tire, Math.min(1, total / cap), face, false, s.player.wb_paint);
    }
  }

  function _wbWheel(cx, cy, wr, flatTire) {
    ctx.beginPath(); ctx.arc(cx, cy, wr, 0, Math.PI * 2);
    ctx.fillStyle = flatTire ? '#882020' : '#1c1c1c'; ctx.fill();
    ctx.strokeStyle = flatTire ? '#cc4040' : '#404040';
    ctx.lineWidth = flatTire ? 2 : 1.5; ctx.stroke();
    ctx.strokeStyle = flatTire ? '#993030' : '#555'; ctx.lineWidth = 0.8;
    ctx.beginPath();
    ctx.moveTo(cx - wr + 0.5, cy); ctx.lineTo(cx + wr - 0.5, cy);
    ctx.moveTo(cx, cy - wr + 0.5); ctx.lineTo(cx, cy + wr - 0.5);
    ctx.stroke();
    ctx.beginPath(); ctx.arc(cx, cy, 1.5, 0, Math.PI * 2);
    ctx.fillStyle = flatTire ? '#bb3030' : '#888'; ctx.fill();
  }

  /** Moving world −y (toward top of screen): back view — flat rim away, curved bowl toward viewer, handles at bottom. */
  function _wheelbarrowUp(px, py, color, flatTire, loadFrac) {
    const cx  = px + T / 2;
    const dim = _shade(color, -45);
    const wood = '#4a3020';

    // Wheel first (drawn under frame; tub occludes upper half)
    ctx.save();
    ctx.beginPath();
    ctx.rect(px + 3, py + 26, T - 6, 7);
    ctx.clip();
    _wbWheel(cx, py + 24.5, 5.5, flatTire);
    ctx.restore();

    ctx.strokeStyle = wood; ctx.lineWidth = 2.2; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(cx - 8, py + 19); ctx.lineTo(cx - 5, py + 26);
    ctx.moveTo(cx + 8, py + 19); ctx.lineTo(cx + 5, py + 26);
    ctx.stroke();

    // Tub: flat opening on top (−y), curved bottom bulge toward +y (near handles)
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(px + 8, py + 8);
    ctx.lineTo(px + T - 8, py + 8);
    ctx.lineTo(px + T - 5, py + 14);
    ctx.bezierCurveTo(px + T - 2, py + 21, px + 2, py + 21, px + 5, py + 14);
    ctx.lineTo(px + 8, py + 8);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = _shade(color, 28);
    ctx.beginPath();
    ctx.moveTo(px + 10, py + 9);
    ctx.lineTo(px + T - 10, py + 9);
    ctx.lineTo(px + T - 7, py + 14);
    ctx.quadraticCurveTo(cx, py + 20, px + 7, py + 14);
    ctx.lineTo(px + 10, py + 9);
    ctx.closePath();
    ctx.fill();

    if (loadFrac > 0.02) {
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(px + 10, py + 9);
      ctx.lineTo(px + T - 10, py + 9);
      ctx.lineTo(px + T - 7, py + 14);
      ctx.quadraticCurveTo(cx, py + 20, px + 7, py + 14);
      ctx.lineTo(px + 10, py + 9);
      ctx.closePath();
      ctx.clip();
      const fh = 11 * loadFrac;
      ctx.fillStyle = 'rgba(140,210,90,0.58)';
      ctx.fillRect(px + 8, py + 19 - fh, 16, fh);
      ctx.restore();
    }

    ctx.strokeStyle = 'rgba(0,0,0,0.35)'; ctx.lineWidth = 0.85;
    ctx.beginPath();
    ctx.moveTo(px + 8, py + 8);
    ctx.lineTo(px + T - 8, py + 8);
    ctx.lineTo(px + T - 5, py + 14);
    ctx.bezierCurveTo(px + T - 2, py + 21, px + 2, py + 21, px + 5, py + 14);
    ctx.lineTo(px + 8, py + 8);
    ctx.stroke();

    ctx.strokeStyle = dim; ctx.lineWidth = 1.25;
    ctx.beginPath();
    ctx.moveTo(px + 7, py + 8.5); ctx.lineTo(px + T - 7, py + 8.5);
    ctx.stroke();

    ctx.strokeStyle = dim; ctx.lineWidth = 2.5; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(px + 9, py + 23); ctx.lineTo(px + 9, py + 28);
    ctx.moveTo(px + T - 9, py + 23); ctx.lineTo(px + T - 9, py + 28);
    ctx.moveTo(px + 9, py + 28); ctx.lineTo(px + T - 9, py + 28);
    ctx.stroke();
    ctx.lineCap = 'butt';
  }

  /** Moving world +y (toward bottom): front view — full wheel, opening toward viewer, wood handles stick into tile above. */
  function _wheelbarrowDown(px, py, color, flatTire, loadFrac) {
    const cx  = px + T / 2;
    const dim = _shade(color, -45);
    const wood = '#4a3020';
    const hWood = '#5a3a22';

    _wbWheel(cx, py + 27.5, 6, flatTire);

    ctx.strokeStyle = wood; ctx.lineWidth = 2.2; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(cx - 7, py + 21); ctx.lineTo(cx - 3.5, py + 24);
    ctx.moveTo(cx + 7, py + 21); ctx.lineTo(cx + 3.5, py + 24);
    ctx.stroke();

    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(px + 7, py + 7);
    ctx.lineTo(px + T - 7, py + 7);
    ctx.lineTo(px + T - 5, py + 21);
    ctx.lineTo(px + 5, py + 21);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = _shade(color, 26);
    ctx.beginPath();
    ctx.moveTo(px + 9, py + 8);
    ctx.lineTo(px + T - 9, py + 8);
    ctx.lineTo(px + T - 7, py + 20);
    ctx.lineTo(px + 7, py + 20);
    ctx.closePath();
    ctx.fill();

    if (loadFrac > 0.02) {
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(px + 9, py + 8);
      ctx.lineTo(px + T - 9, py + 8);
      ctx.lineTo(px + T - 7, py + 20);
      ctx.lineTo(px + 7, py + 20);
      ctx.closePath();
      ctx.clip();
      const fh = 11 * loadFrac;
      ctx.fillStyle = 'rgba(140,210,90,0.55)';
      ctx.fillRect(px + 6, py + 20 - fh, 20, fh);
      ctx.restore();
    }

    ctx.strokeStyle = 'rgba(0,0,0,0.32)'; ctx.lineWidth = 0.85;
    ctx.beginPath();
    ctx.moveTo(px + 7, py + 7);
    ctx.lineTo(px + T - 7, py + 7);
    ctx.lineTo(px + T - 5, py + 21);
    ctx.lineTo(px + 5, py + 21);
    ctx.closePath();
    ctx.stroke();

    // Wood handles: vertical sticks from top rim of barrow into the tile above
    ctx.strokeStyle = hWood; ctx.lineWidth = 2.8; ctx.lineCap = 'round'; ctx.lineJoin = 'round';
    ctx.beginPath();
    ctx.moveTo(px + 10, py + 6); ctx.lineTo(px + 10, py - 5);
    ctx.moveTo(px + T - 10, py + 6); ctx.lineTo(px + T - 10, py - 5);
    ctx.stroke();
    ctx.lineWidth = 2.4;
    ctx.beginPath();
    ctx.moveTo(px + 7, py - 2); ctx.lineTo(px + T - 7, py - 2);
    ctx.stroke();
    ctx.lineCap = 'butt';
  }

  /** Side profile; flip = true for moving east (+x). Wheel + obvious tub depth. */
  function _wheelbarrowSide(px, py, color, flatTire, loadFrac, flip) {
    const wood = '#4a3020';
    const hWood = '#5a3a22';
    const off = flip ? (x) => px + T - (x - px) : (x) => x;

    _wbWheel(off(px + 9), py + 26.5, 5.2, flatTire);

    ctx.strokeStyle = wood; ctx.lineWidth = 2.2; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(off(px + 13), py + 21); ctx.lineTo(off(px + 11), py + 25);
    ctx.stroke();

    // Bucket: wide trapezoid so the barrow reads in profile (wheel at left, bowl to the right)
    ctx.fillStyle = color;
    ctx.beginPath();
    ctx.moveTo(off(px + 17), py + 7);
    ctx.lineTo(off(px + 29), py + 8);
    ctx.lineTo(off(px + 30), py + 20);
    ctx.quadraticCurveTo(off(px + 22), py + 24, off(px + 12), py + 20);
    ctx.lineTo(off(px + 14), py + 9);
    ctx.closePath();
    ctx.fill();

    ctx.fillStyle = _shade(color, 24);
    ctx.beginPath();
    ctx.moveTo(off(px + 19), py + 9);
    ctx.lineTo(off(px + 28), py + 10);
    ctx.lineTo(off(px + 28.5), py + 18);
    ctx.quadraticCurveTo(off(px + 22), py + 21, off(px + 15), py + 18);
    ctx.lineTo(off(px + 16), py + 10);
    ctx.closePath();
    ctx.fill();

    if (loadFrac > 0.02) {
      ctx.save();
      ctx.beginPath();
      ctx.moveTo(off(px + 19), py + 9);
      ctx.lineTo(off(px + 28), py + 10);
      ctx.lineTo(off(px + 28.5), py + 18);
      ctx.quadraticCurveTo(off(px + 22), py + 21, off(px + 15), py + 18);
      ctx.lineTo(off(px + 16), py + 10);
      ctx.closePath();
      ctx.clip();
      const fh = 11 * loadFrac;
      ctx.fillStyle = 'rgba(140,210,90,0.55)';
      ctx.fillRect(off(px + 11), py + 19 - fh, 20, fh);
      ctx.restore();
    }

    ctx.strokeStyle = 'rgba(0,0,0,0.32)'; ctx.lineWidth = 0.85;
    ctx.beginPath();
    ctx.moveTo(off(px + 17), py + 7);
    ctx.lineTo(off(px + 29), py + 8);
    ctx.lineTo(off(px + 30), py + 20);
    ctx.quadraticCurveTo(off(px + 22), py + 24, off(px + 12), py + 20);
    ctx.lineTo(off(px + 14), py + 9);
    ctx.closePath();
    ctx.stroke();

    // Handles at back (far from wheel)
    ctx.strokeStyle = hWood; ctx.lineWidth = 2.3; ctx.lineCap = 'round';
    ctx.beginPath();
    ctx.moveTo(off(px + 26), py + 4); ctx.lineTo(off(px + 26), py + 9);
    ctx.moveTo(off(px + 30), py + 4); ctx.lineTo(off(px + 30), py + 9);
    ctx.moveTo(off(px + 26), py + 4); ctx.lineTo(off(px + 30), py + 4);
    ctx.stroke();
    ctx.lineCap = 'butt';
  }

  function _wheelbarrow(px, py, color, label, flatTire, loadFrac, facing, showLabel, wbPaint) {
    const cx = px + T / 2;
    loadFrac = loadFrac || 0;
    const f = facing || 'down';
    const distress = _paintDistress(wbPaint);
    const tubColor = _weatherTubColor(color, distress);
    if (f === 'up') _wheelbarrowUp(px, py, tubColor, flatTire, loadFrac);
    else if (f === 'down') _wheelbarrowDown(px, py, tubColor, flatTire, loadFrac);
    else if (f === 'left') _wheelbarrowSide(px, py, tubColor, flatTire, loadFrac, false);
    else _wheelbarrowSide(px, py, tubColor, flatTire, loadFrac, true);
    _wheelbarrowPaintWear(px, py, f, distress);

    if (showLabel && label) _label(cx, py + 1, label, '#ffffff', 'bold 9px monospace');
  }

  return { init, draw };
})();
