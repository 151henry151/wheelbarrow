// Mirrored from server/game/constants.py
const WB_BARROW_MATERIAL_NAMES = { 1: 'plastic', 2: 'steel',    3: 'aluminium' };
const WB_TIRE_TYPE_NAMES        = { 1: 'regular', 2: 'tubeless', 3: 'heavy-duty' };
const WB_HANDLE_MATERIAL_NAMES  = { 1: 'wood',    2: 'steel',    3: 'fiberglass' };

// Chassis weights added to load weight for speed calculation.
// Positive = heavier = slower; negative = lighter = faster than plastic/wood.
const WB_BARROW_CHASSIS_WEIGHT = { 1:  0.0, 2:  5.0, 3: -2.0 };
const WB_HANDLE_CHASSIS_WEIGHT = { 1:  0.0, 2:  1.5, 3: -0.5 };

const RESOURCE_WEIGHTS = {
  wood:    0.5,
  wheat:   0.6,
  compost: 0.7,
  manure:  0.8,
  topsoil: 1.2,
  dirt:    1.5,
  clay:    1.8,
  stone:   2.0,
  gravel:  2.5,
};
const RESOURCE_WEIGHT_DEFAULT  = 1.0;
const RESOURCE_WEIGHT_MAX_UNIT = 2.5;   // gravel — used to normalize speed

// Mirrored from server constants for UI display
const STRUCTURE_DEFS = {
  stable:        { label: 'Horse Stable',    cost: '200c',                      produces: 'manure'  },
  gravel_pit:    { label: 'Gravel Pit',      cost: '300c + 20 gravel',          produces: 'gravel'  },
  compost_heap:  { label: 'Compost Heap',    cost: '150c + 10 manure',          produces: 'compost' },
  topsoil_mound: { label: 'Topsoil Mound',   cost: '250c + 20 topsoil',         produces: 'topsoil' },
  market:        { label: 'Player Market',   cost: '2000c + 50 wood + 30 stone', produces: null     },
  town_hall:     { label: 'Town Hall',       cost: '5000c + 50 stone + 50 wood + 100 dirt', produces: null },
};
const STRUCT_KEYS = Object.keys(STRUCTURE_DEFS);

const SEED_SHOP = {
  wheat_seed: { label: 'Wheat Seeds ×10', cost: 25 },
  fertilizer: { label: 'Fertilizer ×5',  cost: 20 },
};
const REPAIR_OPTIONS = [
  { key: 'paint',  label: 'Repair Paint  (30c per 10%)' },
  { key: 'tire',   label: 'Repair Tire   (50c per 10%)' },
  { key: 'handle', label: 'Repair Handle (60c per 10%)' },
  { key: 'barrow', label: 'Repair Barrow (45c per 10%)' },
  { key: 'flat',   label: 'Fix Flat Tire (40c flat)'    },
];
const UPGRADE_LABELS = {
  bucket: 'Barrow capacity',
  tire:   'Tire type',
  handle: 'Handle material',
  barrow: 'Barrow material',
};
const UPGRADE_COSTS = {
  bucket: {2:600,  3:1800,  4:5500,  5:16000, 6:45000},
  tire:   {2:400,  3:4000},
  handle: {2:500,  3:4500},
  barrow: {2:700,  3:6000},
};

function _upgradeLevelLabel(comp, level) {
  if (comp === 'barrow') return WB_BARROW_MATERIAL_NAMES[level] || `L${level}`;
  if (comp === 'tire')   return WB_TIRE_TYPE_NAMES[level]        || `L${level}`;
  if (comp === 'handle') return WB_HANDLE_MATERIAL_NAMES[level]  || `L${level}`;
  return `L${level}`;
}

const state = {
  player:       null,
  players:      [],
  nodes:        [],
  world_parcels: [],   // all parcels (received once at init, updated on purchase)
  towns:        [],    // all towns (received once at init)
  piles:        [],
  crops:        [],
  market:       null,
  npc_shops:    [],
  prices:       {},
  season:       null,
  world:        { w: 1000, h: 1000 },

  // UI state
  buildMenuOpen: false,
  shopMenuOpen:  false,
  shopType:      null,
  pileMenuOpen:  false,
  townMenuOpen:  false,
  hudVisible:    false,
  parcelPreview: null,   // parcel id being previewed for purchase, or null
  currentTownId: null,   // id of town player is currently in
  _townMenuTown: null,   // scratch ref used by town menu key handler
  _townMenuOpts: [],     // ordered option list for town menu
};

// ---------------------------------------------------------------- helpers

function _parcelAt(x, y) {
  for (const p of state.world_parcels) {
    if (x >= p.x && x < p.x + p.w && y >= p.y && y < p.y + p.h) return p;
  }
  return null;
}

function _pointInPolygon(x, y, poly) {
  let inside = false;
  let j = poly.length - 1;
  for (let i = 0; i < poly.length; i++) {
    const xi = poly[i].x, yi = poly[i].y;
    const xj = poly[j].x, yj = poly[j].y;
    if (((yi > y) !== (yj > y)) && (x < (xj - xi) * (y - yi) / (yj - yi + 1e-9) + xi)) {
      inside = !inside;
    }
    j = i;
  }
  return inside;
}

function _townAt(x, y) {
  for (const town of state.towns) {
    if (_pointInPolygon(x, y, town.boundary)) return town;
  }
  return null;
}

// ---------------------------------------------------------------- notice bar
let noticeTimer = null;
function showNotice(msg) {
  const bar = document.getElementById('notice-bar');
  bar.textContent = msg;
  bar.style.display = 'block';
  bar.style.opacity = '1';
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => {
    bar.style.opacity = '0';
    setTimeout(() => bar.style.display = 'none', 400);
  }, 3500);
}

// ---------------------------------------------------------------- load speed
function _loadSpeedMult(player) {
  const bucket = player.bucket || {};
  const cap    = player.bucket_cap || 10;
  let totalWeight = 0;
  for (const [rtype, amount] of Object.entries(bucket)) {
    totalWeight += (RESOURCE_WEIGHTS[rtype] ?? RESOURCE_WEIGHT_DEFAULT) * amount;
  }
  // Add chassis material weights (steel barrow/handle heavier; aluminium/fiberglass lighter)
  totalWeight += WB_BARROW_CHASSIS_WEIGHT[player.wb_barrow_level] ?? 0;
  totalWeight += WB_HANDLE_CHASSIS_WEIGHT[player.wb_handle_level] ?? 0;
  // 1.0 (empty plastic+wood) → ~3.0 (full of gravel with steel chassis)
  const maxWeight = cap * RESOURCE_WEIGHT_MAX_UNIT;
  return Math.max(0.5, 1.0 + (totalWeight / maxWeight) * 2.0);
}

// ---------------------------------------------------------------- town crossing
function _checkTownCrossing() {
  if (!state.player) return;
  const p = state.player;
  const town = _townAt(p.x, p.y);
  const newId = town ? town.id : null;
  if (newId !== state.currentTownId) {
    state.currentTownId = newId;
    const townInfo = document.getElementById('town-info');
    if (town) {
      const taxPct = Math.round((town.tax_rate || 0) * 100);
      townInfo.textContent = `in: ${town.name}${taxPct > 0 ? ` (${taxPct}% tax)` : ''}`;
      townInfo.style.display = 'block';
      showNotice(`Entering ${town.name}${taxPct > 0 ? ` — ${taxPct}% sales tax` : ''}`);
    } else {
      townInfo.style.display = 'none';
    }
  }
}

// ---------------------------------------------------------------- HUD update
function updateHud() {
  if (!state.player) return;
  if (!state.hudVisible) return;

  if (state.season) {
    const mins = Math.ceil(state.season.remaining_s / 60);
    document.getElementById('hud-season').textContent =
      `Season: ${state.season.name}  (${mins}m left)`;
  }

  document.getElementById('hud-coins-val').textContent = state.player.coins;

  const bucket = state.player.bucket || {};
  const total  = Object.values(bucket).reduce((a,b) => a+b, 0);
  const cap    = state.player.bucket_cap || 10;
  const lines  = Object.entries(bucket).filter(([,v]) => v > 0).map(([k,v]) => `${k}: ${v}`);
  document.getElementById('hud-bucket-contents').textContent = lines.length ? lines.join('\n') : 'empty';
  document.getElementById('hud-bucket-fill').style.width = `${Math.min(100, (total/cap)*100)}%`;

  const pocket = state.player.pocket || {};
  const pLines = Object.entries(pocket).filter(([,v]) => v > 0).map(([k,v]) => `${k}: ${v}`);
  document.getElementById('hud-pocket').textContent = pLines.length ? 'pocket: ' + pLines.join('  ') : '';

  // Prices only visible when standing at/near a market
  const px = state.player.x, py = state.player.y;
  const nearNpcMarket = state.market && Math.abs(px - state.market.x) <= 1 && Math.abs(py - state.market.y) <= 1;
  const nearPlayerMarket = state.nodes.some(n => n.is_market && Math.abs(n.x - px) <= 1 && Math.abs(n.y - py) <= 1);
  if (nearNpcMarket || nearPlayerMarket) {
    document.getElementById('hud-prices').textContent =
      Object.entries(state.prices).map(([k,v]) => `${k[0].toUpperCase()}${k.slice(1)}: ${v}c`).join('  ');
  } else {
    document.getElementById('hud-prices').textContent = '';
  }

  _updateWbHud();
  _updateHint();
}

function _updateWbHud() {
  const p = state.player;
  const comps = [
    { key: 'paint',  barId: 'wb-paint-bar',  valId: 'wb-paint-val'  },
    { key: 'tire',   barId: 'wb-tire-bar',   valId: 'wb-tire-val'   },
    { key: 'handle', barId: 'wb-handle-bar', valId: 'wb-handle-val' },
    { key: 'barrow', barId: 'wb-barrow-bar', valId: 'wb-barrow-val' },
  ];
  for (const c of comps) {
    const v   = Math.round(p[`wb_${c.key}`] ?? 100);
    const bar = document.getElementById(c.barId);
    bar.style.width = `${v}%`;
    bar.className   = 'wb-bar' + (v < 25 ? ' low' : v < 50 ? ' med' : '');
    document.getElementById(c.valId).textContent = v;
  }
  document.getElementById('wb-flat-ind').textContent = p.flat_tire ? ' FLAT' : '';
  // RUST indicator only relevant for steel barrows — plastic and aluminium don't rust
  const isSteel = (p.wb_barrow_level ?? 1) === 2;
  document.getElementById('wb-rust-ind').textContent = isSteel && (p.wb_paint ?? 100) < 50 ? ' RUST' : '';
  const barrowName = WB_BARROW_MATERIAL_NAMES[p.wb_barrow_level] || `L${p.wb_barrow_level}`;
  const tireName   = WB_TIRE_TYPE_NAMES[p.wb_tire_level]         || `L${p.wb_tire_level}`;
  const handleName = WB_HANDLE_MATERIAL_NAMES[p.wb_handle_level] || `L${p.wb_handle_level}`;
  document.getElementById('wb-upgrades').textContent =
    `${barrowName}  ${tireName}  ${handleName}  cap L${p.wb_bucket_level}`;
}

function _updateHint() {
  const hint = document.getElementById('hud-hint');
  if (state.buildMenuOpen || state.shopMenuOpen || state.pileMenuOpen || state.townMenuOpen) {
    hint.textContent = '';
    return;
  }
  const p   = state.player;
  const px  = p.x, py = p.y;
  const hints = [];

  const atMarket = state.market && px === state.market.x && py === state.market.y;
  const total    = Object.values(p.bucket || {}).reduce((a,b) => a+b, 0);
  if (atMarket && total > 0) hints.push('[Space] sell all at NPC market');

  const nearShop = state.npc_shops.find(s => Math.abs(s.x - px) <= 1 && Math.abs(s.y - py) <= 1);
  if (nearShop) hints.push(`[E] open ${nearShop.label}`);

  const nearHall = state.nodes.find(n => n.is_town_hall && Math.abs(n.x-px) <= 1 && Math.abs(n.y-py) <= 1);
  if (nearHall) hints.push('[E] town hall');

  const parcel = _parcelAt(px, py);
  if (parcel) {
    if (parcel.owner_id === p.id) {
      if (total > 0) hints.push('[U] unload to pile');
      hints.push('[P] build menu');
      hints.push('[F] farm');
    } else if (!parcel.owner_id) {
      if (state.parcelPreview === parcel.id) {
        hints.push(`[B] confirm purchase: ${parcel.price}c`);
        hints.push('[Esc] cancel');
      } else {
        hints.push(`[B] preview parcel (${parcel.price}c)`);
      }
    } else {
      hints.push(`land: ${parcel.owner_name}`);
    }
  }

  const pilesHere = state.piles.filter(p2 => p2.x === px && p2.y === py);
  if (pilesHere.length) {
    const ownPiles   = pilesHere.filter(p2 => p2.owner_id === p.id);
    const otherPiles = pilesHere.filter(p2 => p2.owner_id !== p.id && p2.sell_price != null);
    if (ownPiles.length)   hints.push('[E] manage pile prices');
    if (otherPiles.length) hints.push('[E] buy from pile');
  }

  const near = state.nodes.find(n => !n.is_structure && Math.abs(n.x-px)<=1 && Math.abs(n.y-py)<=1 && n.amount > 0);
  if (near) hints.push(`Collecting ${near.type}...`);

  const crop = state.crops.find(c => c.x === px && c.y === py);
  if (crop) hints.push(crop.ready ? '[F] harvest crop' : '[F] fertilize/check crop');

  const nearMarket = state.nodes.find(n => n.is_market && Math.abs(n.x-px)<=1 && Math.abs(n.y-py)<=1);
  if (nearMarket) hints.push('[E] trade at player market');

  hint.textContent = hints.join('\n');
}

// ------------------------------------------------------------ build menu
function openBuildMenu() {
  closeAllMenus();
  state.buildMenuOpen = true;
  const menu  = document.getElementById('build-menu');
  const items = document.getElementById('build-menu-items');
  items.innerHTML = '';
  STRUCT_KEYS.forEach((type, i) => {
    const def = STRUCTURE_DEFS[type];
    const div = document.createElement('div');
    div.className = 'build-option affordable';
    div.innerHTML = `<span class="key">[${i+1}]</span> ${def.label} — ${def.cost}` +
                    (def.produces ? ` → ${def.produces}` : '');
    items.appendChild(div);
  });
  menu.style.display = 'block';
}

// ------------------------------------------------------------ shop menu
function openShopMenu(shopKey) {
  closeAllMenus();
  state.shopMenuOpen = true;
  state.shopType     = shopKey;
  const menu  = document.getElementById('shop-menu');
  const title = document.getElementById('shop-menu-title');
  const items = document.getElementById('shop-menu-items');
  items.innerHTML = '';

  if (shopKey === 'seed_shop') {
    title.textContent = 'Seed Shop';
    Object.entries(SEED_SHOP).forEach(([k, def], i) => {
      const div = document.createElement('div');
      div.className = 'build-option affordable';
      div.innerHTML = `<span class="key">[${i+1}]</span> ${def.label} — ${def.cost}c`;
      items.appendChild(div);
    });
  } else if (shopKey === 'repair_shop') {
    title.textContent = 'Repair Shop';
    REPAIR_OPTIONS.forEach((opt, i) => {
      const div = document.createElement('div');
      div.className = 'build-option affordable';
      div.innerHTML = `<span class="key">[${i+1}]</span> ${opt.label}`;
      items.appendChild(div);
    });
  } else if (shopKey === 'general_store') {
    title.textContent = 'General Store — Upgrades';
    const p = state.player;
    const entries = [];
    for (const [comp, costs] of Object.entries(UPGRADE_COSTS)) {
      const cur  = p[`wb_${comp}_level`] || 1;
      const next = cur + 1;
      if (costs[next] !== undefined) entries.push({ comp, level: next, cost: costs[next] });
    }
    if (!entries.length) {
      const div = document.createElement('div');
      div.style.color = '#888';
      div.textContent = 'All upgrades maxed!';
      items.appendChild(div);
    } else {
      entries.forEach((e, i) => {
        const div = document.createElement('div');
        const affordable = (p.coins || 0) >= e.cost;
        div.className = `build-option ${affordable ? 'affordable' : 'unaffordable'}`;
        div.innerHTML = `<span class="key">[${i+1}]</span> ${UPGRADE_LABELS[e.comp]} → ${_upgradeLevelLabel(e.comp, e.level)} — ${e.cost}c`;
        items.appendChild(div);
      });
    }
  }
  menu.style.display = 'block';
}

// ------------------------------------------------------------ pile menu
function openPileMenu() {
  const p  = state.player;
  const pilesHere = state.piles.filter(pl => pl.x === p.x && pl.y === p.y);
  if (!pilesHere.length) return;
  closeAllMenus();
  state.pileMenuOpen = true;
  const menu  = document.getElementById('pile-menu');
  const items = document.getElementById('pile-menu-items');
  items.innerHTML = '';
  pilesHere.forEach((pile, i) => {
    const div = document.createElement('div');
    div.className = 'build-option affordable';
    const isOwn  = pile.owner_id === p.id;
    const priceStr = pile.sell_price != null ? `${pile.sell_price}c/unit` : 'not for sale';
    if (isOwn) {
      div.innerHTML = `<span class="key">[${i+1}]</span> ${pile.resource_type}: ${pile.amount} — ${priceStr} (set price)`;
    } else {
      div.innerHTML = `<span class="key">[${i+1}]</span> Buy ${pile.resource_type}: ${pile.amount} @ ${priceStr}`;
    }
    items.appendChild(div);
  });
  menu.style.display = 'block';
}

// ------------------------------------------------------------ town menu
function openTownMenu(hallNode) {
  closeAllMenus();
  state.townMenuOpen = true;
  const p    = state.player;
  const town = _townAt(hallNode.x, hallNode.y);
  state._townMenuTown = town;

  const menu  = document.getElementById('town-menu');
  const title = document.getElementById('town-menu-title');
  const items = document.getElementById('town-menu-items');
  items.innerHTML = '';

  if (!town) {
    title.textContent = 'Town Hall';
    const div = document.createElement('div');
    div.style.color = '#888';
    div.textContent = 'No town data found.';
    items.appendChild(div);
    menu.style.display = 'block';
    return;
  }

  title.textContent = town.name;

  const taxPct = Math.round((town.tax_rate || 0) * 100);
  const leaderEntry = state.players.find(pl => pl.id === town.leader_id);
  const leaderName  = leaderEntry ? leaderEntry.username : (town.leader_id ? `#${town.leader_id}` : 'none');

  const infoDiv = document.createElement('div');
  infoDiv.style.cssText = 'color:#888;font-size:0.76rem;margin-bottom:8px;';
  infoDiv.textContent = `Tax: ${taxPct}%  |  Treasury: ${town.treasury || 0}c  |  Leader: ${leaderName}`;
  items.appendChild(infoDiv);

  const isLeader  = p.id === town.leader_id;
  const isFounder = p.id === town.founder_id;
  // Build sequential option list so key numbers match display order
  const menuOpts = [];
  if (isLeader) {
    menuOpts.push({ action: 'set_tax',  label: `Set tax rate (current: ${taxPct}%)` });
    menuOpts.push({ action: 'withdraw', label: 'Withdraw from treasury' });
  }
  // Only show rename if founder and town hasn't been renamed yet (name === raw_name means no custom name)
  if (isFounder && town.name === town.raw_name) {
    menuOpts.push({ action: 'rename', label: 'Rename town (one time)' });
  }

  if (menuOpts.length === 0) {
    const div = document.createElement('div');
    div.style.color = '#666';
    div.style.fontSize = '0.76rem';
    div.textContent = 'Only the leader/founder can govern this town.';
    items.appendChild(div);
  } else {
    menuOpts.forEach((opt, i) => _addMenuItem(items, i + 1, opt.label));
  }
  state._townMenuOpts = menuOpts;

  menu.style.display = 'block';
}

function _addMenuItem(container, num, label) {
  const div = document.createElement('div');
  div.className = 'build-option affordable';
  div.innerHTML = `<span class="key">[${num}]</span> ${label}`;
  container.appendChild(div);
}

// ------------------------------------------------------------ close menus
function closeAllMenus() {
  state.buildMenuOpen = false;
  state.shopMenuOpen  = false;
  state.shopType      = null;
  state.pileMenuOpen  = false;
  state.townMenuOpen  = false;
  state._townMenuTown = null;
  state._townMenuOpts = [];
  document.getElementById('build-menu').style.display = 'none';
  document.getElementById('shop-menu').style.display  = 'none';
  document.getElementById('pile-menu').style.display  = 'none';
  document.getElementById('town-menu').style.display  = 'none';
}

// ------------------------------------------------------------ HUD toggle
function toggleHud() {
  state.hudVisible = !state.hudVisible;
  const show = state.hudVisible;
  document.getElementById('hud').style.display    = show ? 'block' : 'none';
  document.getElementById('hud-wb').style.display = show ? 'block' : 'none';
  document.getElementById('hud-toggle').textContent = show ? '[H] close hud' : '[H] hud';
}

// --------------------------------------------------------------- key handler
function handleKey(key) {
  // Escape: cancel parcel preview or close menus
  if (key === 'Escape') {
    if (state.parcelPreview !== null) {
      state.parcelPreview = null;
      return;
    }
    closeAllMenus();
    return;
  }

  // ---- Build menu ----
  if (state.buildMenuOpen) {
    const idx = parseInt(key) - 1;
    if (idx >= 0 && idx < STRUCT_KEYS.length) {
      WS.send({ type: 'build', structure_type: STRUCT_KEYS[idx] });
      closeAllMenus();
    }
    return;
  }

  // ---- Shop menu ----
  if (state.shopMenuOpen) {
    const idx = parseInt(key) - 1;
    if (idx < 0) return;
    if (state.shopType === 'seed_shop') {
      const itemKeys = Object.keys(SEED_SHOP);
      if (idx < itemKeys.length) {
        WS.send({ type: 'npc_shop_buy', shop: 'seed_shop', item: itemKeys[idx] });
        closeAllMenus();
      }
    } else if (state.shopType === 'repair_shop') {
      if (idx < REPAIR_OPTIONS.length) {
        WS.send({ type: 'npc_shop_buy', shop: 'repair_shop', item: REPAIR_OPTIONS[idx].key });
        closeAllMenus();
      }
    } else if (state.shopType === 'general_store') {
      const p = state.player;
      const entries = [];
      for (const [comp, costs] of Object.entries(UPGRADE_COSTS)) {
        const cur = p[`wb_${comp}_level`] || 1;
        if (costs[cur + 1] !== undefined) entries.push({ comp });
      }
      if (idx < entries.length) {
        WS.send({ type: 'upgrade_wb', component: entries[idx].comp });
        closeAllMenus();
      }
    }
    return;
  }

  // ---- Pile menu ----
  if (state.pileMenuOpen) {
    const idx = parseInt(key) - 1;
    const p   = state.player;
    const pilesHere = state.piles.filter(pl => pl.x === p.x && pl.y === p.y);
    if (idx < 0 || idx >= pilesHere.length) return;
    const pile = pilesHere[idx];
    if (pile.owner_id === p.id) {
      const priceStr = prompt(`Set sell price per unit for ${pile.resource_type} (blank = not for sale):`);
      if (priceStr === null) { closeAllMenus(); return; }
      const price = priceStr.trim() === '' ? null : parseFloat(priceStr);
      if (priceStr.trim() !== '' && isNaN(price)) { closeAllMenus(); return; }
      WS.send({ type: 'set_pile_price', resource_type: pile.resource_type, price });
    } else if (pile.sell_price != null) {
      const maxAfford = Math.floor(p.coins / pile.sell_price);
      const space     = (p.bucket_cap || 10) - Object.values(p.bucket || {}).reduce((a,b)=>a+b,0);
      const maxBuy    = Math.min(pile.amount, space, maxAfford);
      if (maxBuy <= 0) { showNotice('Cannot afford or no bucket space.'); closeAllMenus(); return; }
      WS.send({ type: 'buy_pile', resource_type: pile.resource_type, amount: maxBuy });
    }
    closeAllMenus();
    return;
  }

  // ---- Town menu ----
  if (state.townMenuOpen) {
    const town = state._townMenuTown;
    const opts = state._townMenuOpts || [];
    if (town && opts.length) {
      const idx = parseInt(key) - 1;
      if (idx >= 0 && idx < opts.length) {
        const opt = opts[idx];
        if (opt.action === 'set_tax') {
          const rateStr = prompt('Set tax rate 0–30 (enter a number, e.g. 10 for 10%):');
          if (rateStr !== null) {
            const rate = parseFloat(rateStr) / 100;
            if (!isNaN(rate) && rate >= 0 && rate <= 0.30) {
              WS.send({ type: 'town_action', action: 'set_tax', town_id: town.id, rate });
            } else {
              showNotice('Invalid rate — enter 0 to 30.');
            }
          }
        } else if (opt.action === 'withdraw') {
          const amt = parseInt(prompt('Withdraw how many coins?') || '0');
          if (amt > 0) WS.send({ type: 'town_action', action: 'withdraw', town_id: town.id, amount: amt });
        } else if (opt.action === 'rename') {
          const newName = prompt('New town name (max 32 chars):');
          if (newName && newName.trim()) {
            WS.send({ type: 'town_action', action: 'rename', town_id: town.id, name: newName.trim().slice(0,32) });
          }
        }
      }
    }
    closeAllMenus();
    return;
  }

  // ---- Normal keys ----
  const lk = key.toLowerCase();
  if (lk === 'h')  { toggleHud(); return; }
  if (key === ' ') { WS.send({ type: 'sell' }); return; }
  if (lk === 'b')  { _handleBuyParcel(); return; }
  if (lk === 'p')  { openBuildMenu(); return; }
  if (lk === 'u')  { WS.send({ type: 'unload' }); return; }
  if (lk === 'f')  { WS.send({ type: 'farm' }); return; }
  if (lk === 'e')  { _contextInteract(); return; }
}

function _handleBuyParcel() {
  const p      = state.player;
  const parcel = _parcelAt(p.x, p.y);

  if (!parcel) {
    showNotice('No parcel here to buy.');
    return;
  }
  if (parcel.owner_id === p.id) {
    showNotice('You already own this parcel.');
    return;
  }
  if (parcel.owner_id) {
    showNotice(`This land belongs to ${parcel.owner_name}.`);
    return;
  }

  if (state.parcelPreview === parcel.id) {
    // Second press: send purchase
    WS.send({ type: 'buy_parcel', parcel_id: parcel.id });
    state.parcelPreview = null;
  } else {
    // First press: enter preview
    state.parcelPreview = parcel.id;
    showNotice(`Parcel: ${parcel.w}×${parcel.h} tiles — ${parcel.price}c. Press B again to buy, Esc to cancel.`);
  }
}

function _contextInteract() {
  const p  = state.player;
  const px = p.x, py = p.y;

  // Town hall?
  const nearHall = state.nodes.find(n => n.is_town_hall && Math.abs(n.x-px) <= 1 && Math.abs(n.y-py) <= 1);
  if (nearHall) { openTownMenu(nearHall); return; }

  // NPC shop?
  const nearShop = state.npc_shops.find(s => Math.abs(s.x - px) <= 1 && Math.abs(s.y - py) <= 1);
  if (nearShop) { openShopMenu(nearShop.key); return; }

  // Own pile or other's pile?
  const pilesHere = state.piles.filter(pl => pl.x === px && pl.y === py);
  if (pilesHere.length) { openPileMenu(); return; }

  // Player market nearby?
  const nearMarket = state.nodes.find(n => n.is_market && Math.abs(n.x-px)<=1 && Math.abs(n.y-py)<=1);
  if (nearMarket) {
    const action = prompt('At player market: type "sell" or "buy"');
    if (!action) return;
    const rtype  = prompt('Resource type:');
    if (!rtype) return;
    const amt    = parseFloat(prompt('Amount:') || '0');
    if (isNaN(amt) || amt <= 0) return;
    WS.send({ type: 'market_trade', action: action.trim(), resource_type: rtype.trim(), amount: amt });
  }
}

// ------------------------------------------------------------------- boot
window.addEventListener('load', () => {
  const loginScreen = document.getElementById('login-screen');
  const gameScreen  = document.getElementById('game-screen');
  const loginBtn    = document.getElementById('login-btn');
  const usernameIn  = document.getElementById('username-input');
  const passwordIn  = document.getElementById('password-input');
  const loginErr    = document.getElementById('login-error');

  async function startGame(username, password) {
    loginErr.textContent = '';
    loginBtn.disabled = true;

    const basePath = location.pathname.replace(/\/[^/]*$/, '');
    let token;
    try {
      const res  = await fetch(`${basePath}/api/login`, {
        method:  'POST',
        headers: { 'Content-Type': 'application/json' },
        body:    JSON.stringify({ username, password }),
      });
      const data = await res.json();
      if (!res.ok) { loginErr.textContent = data.detail || 'Login failed.'; loginBtn.disabled = false; return; }
      token = data.token;
    } catch {
      loginErr.textContent = 'Could not reach server.'; loginBtn.disabled = false; return;
    }

    loginScreen.style.display = 'none';
    gameScreen.style.display  = 'block';

    // HUD is hidden by default
    document.getElementById('hud').style.display    = 'none';
    document.getElementById('hud-wb').style.display = 'none';
    document.getElementById('hud-toggle').textContent = '[H] hud';

    const canvas = document.getElementById('game');
    Renderer.init(canvas, state);
    Input.init(msg => WS.send(msg), handleKey);

    WS.on('init', msg => {
      state.player        = msg.player;
      state.player.username = username;
      state.nodes         = msg.nodes;
      state.world_parcels = msg.parcels || [];
      state.piles         = msg.piles   || [];
      state.crops         = msg.crops   || [];
      state.towns         = msg.towns   || [];
      state.market        = msg.market;
      state.npc_shops     = msg.npc_shops || [];
      state.prices        = msg.prices;
      state.season        = msg.season;
      state.world         = msg.world || { w: 1000, h: 1000 };
      _checkTownCrossing();
    });

    WS.on('tick', msg => {
      const uname = state.player ? state.player.username : null;
      state.player  = msg.player;
      if (uname) state.player.username = uname;
      state.players = msg.players;
      state.nodes   = msg.nodes;
      state.piles   = msg.piles  || [];
      state.crops   = msg.crops  || [];
      state.prices  = msg.prices;
      state.season  = msg.season;
      const flatMult = state.player.flat_tire ? 3.0 : 1.0;
      Input.setSpeedMult(_loadSpeedMult(state.player) * flatMult);
      _checkTownCrossing();
      // Cancel parcel preview if player moved off that parcel
      if (state.parcelPreview !== null) {
        const pp = state.world_parcels.find(p => p.id === state.parcelPreview);
        if (pp) {
          const px = state.player.x, py = state.player.y;
          if (px < pp.x || px >= pp.x + pp.w || py < pp.y || py >= pp.y + pp.h) {
            state.parcelPreview = null;
          }
        }
      }
    });

    WS.on('sold', msg => {
      state.player.coins = msg.coins;
      if (msg.earned > 0) {
        state.player.bucket = {};
        showNotice(`Sold for ${msg.earned} coins!`);
      } else if (msg.msg) {
        showNotice(msg.msg);
      }
    });

    WS.on('parcel_bought', msg => {
      state.player.coins = msg.coins;
      state.parcelPreview = null;
      const idx = state.world_parcels.findIndex(p => p.id === msg.parcel.id);
      if (idx >= 0) state.world_parcels[idx] = msg.parcel;
      showNotice('Land purchased!');
    });

    WS.on('parcel_update', msg => {
      const idx = state.world_parcels.findIndex(p => p.id === msg.parcel.id);
      if (idx >= 0) state.world_parcels[idx] = msg.parcel;
    });

    WS.on('built', msg => {
      state.player.coins = msg.coins;
      state.nodes.push(msg.structure);
      showNotice(`Built ${msg.structure.type}!`);
    });

    WS.on('season_change', msg => {
      state.season = msg.season;
      showNotice(`Season changed: ${msg.season.name.toUpperCase()}!`);
    });

    WS.on('town_update', msg => {
      const idx = state.towns.findIndex(t => t.id === msg.town.id);
      if (idx >= 0) state.towns[idx] = msg.town;
      // Refresh town info display if player is in this town
      if (state.currentTownId === msg.town.id) {
        state.currentTownId = null;  // force re-check
        _checkTownCrossing();
      }
    });

    WS.on('notice', msg => showNotice(msg.msg));

    WS.connect(token);

    function loop(now) {
      Input.update(now);
      Renderer.draw();
      updateHud();
      if (!state.hudVisible && state.player) {
        document.getElementById('hud-toggle').textContent =
          `[H] hud  (${state.player.x}, ${state.player.y})`;
      }
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }

  function tryLogin() {
    const u  = usernameIn.value.trim();
    const pw = passwordIn.value;
    if (u && pw) startGame(u, pw);
    else loginErr.textContent = 'Enter username and password.';
  }

  loginBtn.addEventListener('click', tryLogin);
  passwordIn.addEventListener('keydown', e => { if (e.key === 'Enter') tryLogin(); });
  usernameIn.addEventListener('keydown', e => { if (e.key === 'Enter') passwordIn.focus(); });
});
