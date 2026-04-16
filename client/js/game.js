const PARCEL_SIZE = 10;

// Mirrored from server constants for UI display
const STRUCTURE_DEFS = {
  stable:        { label: 'Horse Stable',   cost: '200c',                produces: 'manure'  },
  gravel_pit:    { label: 'Gravel Pit',     cost: '300c + 20 gravel',    produces: 'gravel'  },
  compost_heap:  { label: 'Compost Heap',   cost: '150c + 10 manure',    produces: 'compost' },
  topsoil_mound: { label: 'Topsoil Mound',  cost: '250c + 20 topsoil',   produces: 'topsoil' },
  market:        { label: 'Player Market',  cost: '2000c + 50 wood + 30 stone', produces: null },
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
  { key: 'flat',   label: 'Fix Flat Tire (40c flat)'    },
];
const UPGRADE_LABELS = {
  bucket: 'Barrow size',
  tire:   'Tire quality',
  handle: 'Handle quality',
  barrow: 'Barrow material',
};
const UPGRADE_COSTS = {
  bucket: {2:600,  3:1800,  4:5500,  5:16000, 6:45000},
  tire:   {2:400,  3:1200,  4:4000,  5:12000, 6:35000},
  handle: {2:500,  3:1500,  4:4500,  5:13000, 6:38000},
  barrow: {2:700,  3:2000,  4:6000,  5:18000, 6:50000},
};

const state = {
  player:    null,
  players:   [],
  nodes:     [],
  parcels:   [],
  piles:     [],
  crops:     [],
  market:    null,
  npc_shops: [],
  prices:    {},
  season:    null,
  world:     { w: 100, h: 100 },
  buildMenuOpen: false,
  shopMenuOpen:  false,
  shopType:      null,
  pileMenuOpen:  false,
};

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

// ---------------------------------------------------------------- HUD update
function updateHud() {
  if (!state.player) return;

  // Season
  if (state.season) {
    const mins = Math.ceil(state.season.remaining_s / 60);
    document.getElementById('hud-season').textContent =
      `Season: ${state.season.name}  (${mins}m left)`;
  }

  // Coins
  document.getElementById('hud-coins-val').textContent = state.player.coins;

  // Bucket
  const bucket = state.player.bucket || {};
  const total  = Object.values(bucket).reduce((a,b) => a+b, 0);
  const cap    = state.player.bucket_cap || 10;
  const lines  = Object.entries(bucket).filter(([,v]) => v > 0).map(([k,v]) => `${k}: ${v}`);
  document.getElementById('hud-bucket-contents').textContent = lines.length ? lines.join('\n') : 'empty';
  document.getElementById('hud-bucket-fill').style.width = `${Math.min(100, (total/cap)*100)}%`;

  // Pocket
  const pocket = state.player.pocket || {};
  const pLines = Object.entries(pocket).filter(([,v]) => v > 0).map(([k,v]) => `${k}: ${v}`);
  document.getElementById('hud-pocket').textContent = pLines.length ? 'pocket: ' + pLines.join('  ') : '';

  // Market prices
  document.getElementById('hud-prices').textContent =
    Object.entries(state.prices).map(([k,v]) => `${k[0].toUpperCase()}${k.slice(1)}: ${v}c`).join('  ');

  // WB condition
  _updateWbHud();

  // Context hint
  _updateHint();
}

function _updateWbHud() {
  const p = state.player;
  const comps = [
    { key: 'paint',  barId: 'wb-paint-bar',  valId: 'wb-paint-val'  },
    { key: 'tire',   barId: 'wb-tire-bar',   valId: 'wb-tire-val'   },
    { key: 'handle', barId: 'wb-handle-bar', valId: 'wb-handle-val' },
  ];
  for (const c of comps) {
    const v   = Math.round(p[`wb_${c.key}`] ?? 100);
    const bar = document.getElementById(c.barId);
    bar.style.width = `${v}%`;
    bar.className   = 'wb-bar' + (v < 25 ? ' low' : v < 50 ? ' med' : '');
    document.getElementById(c.valId).textContent = v;
  }
  const flatInd = document.getElementById('wb-flat-ind');
  flatInd.textContent = p.flat_tire ? ' FLAT' : '';

  // Upgrade levels
  document.getElementById('wb-upgrades').textContent =
    `Barrow L${p.wb_bucket_level}  Tire L${p.wb_tire_level}  Handle L${p.wb_handle_level}  Mat L${p.wb_barrow_level}`;
}

function _updateHint() {
  const hint = document.getElementById('hud-hint');
  if (state.buildMenuOpen || state.shopMenuOpen || state.pileMenuOpen) {
    hint.textContent = '';
    return;
  }
  const p   = state.player;
  const px  = p.x, py = p.y;

  const atMarket = state.market && px === state.market.x && py === state.market.y;
  const total    = Object.values(p.bucket || {}).reduce((a,b) => a+b, 0);

  const hints = [];
  if (atMarket && total > 0) hints.push('[Space] sell all at NPC market');

  // NPC shops
  const nearShop = state.npc_shops.find(s => Math.abs(s.x - px) <= 1 && Math.abs(s.y - py) <= 1);
  if (nearShop) hints.push(`[E] open ${nearShop.label}`);

  // Parcel
  const parcelKey = `${Math.floor(px/PARCEL_SIZE)},${Math.floor(py/PARCEL_SIZE)}`;
  const myParcel  = state.parcels.find(p2 => `${p2.px},${p2.py}` === parcelKey && p2.owner_id === p.id);
  const anyParcel = state.parcels.find(p2 => `${p2.px},${p2.py}` === parcelKey);
  if (myParcel) {
    if (total > 0) hints.push('[U] unload to pile');
    hints.push('[P] build menu');
    hints.push('[F] farm (plant/fertilize/harvest)');
  } else if (!anyParcel) {
    hints.push('[B] buy parcel (500c)');
  } else {
    hints.push(`land: ${anyParcel.owner_name}`);
  }

  // Player piles at current tile
  const pilesHere = state.piles.filter(p2 => p2.x === px && p2.y === py);
  if (pilesHere.length) {
    const ownPiles   = pilesHere.filter(p2 => p2.owner_id === p.id);
    const otherPiles = pilesHere.filter(p2 => p2.owner_id !== p.id && p2.sell_price != null);
    if (ownPiles.length)   hints.push('[E] manage pile prices');
    if (otherPiles.length) hints.push('[E] buy from pile');
  }

  // Resource collecting
  const near = state.nodes.find(n => !n.is_structure && Math.abs(n.x-px)<=1 && Math.abs(n.y-py)<=1 && n.amount > 0);
  if (near) hints.push(`Collecting ${near.type}...`);

  // Crop
  const crop = state.crops.find(c => c.x === px && c.y === py);
  if (crop) hints.push(crop.ready ? '[F] harvest crop' : '[F] fertilize or check crop');

  // Player market nearby
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
      const levelKey = `wb_${comp}_level`;
      const cur      = p[levelKey] || 1;
      const next     = cur + 1;
      if (costs[next] !== undefined) {
        entries.push({ comp, level: next, cost: costs[next] });
      }
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
        div.innerHTML = `<span class="key">[${i+1}]</span> ${UPGRADE_LABELS[e.comp]} → L${e.level} — ${e.cost}c`;
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

function closeAllMenus() {
  state.buildMenuOpen = false;
  state.shopMenuOpen  = false;
  state.shopType      = null;
  state.pileMenuOpen  = false;
  document.getElementById('build-menu').style.display = 'none';
  document.getElementById('shop-menu').style.display  = 'none';
  document.getElementById('pile-menu').style.display  = 'none';
}

// --------------------------------------------------------------- key handler
function handleKey(key) {
  // ---- Build menu ----
  if (state.buildMenuOpen) {
    if (key === 'Escape') { closeAllMenus(); return; }
    const idx = parseInt(key) - 1;
    if (idx >= 0 && idx < STRUCT_KEYS.length) {
      WS.send({ type: 'build', structure_type: STRUCT_KEYS[idx] });
      closeAllMenus();
    }
    return;
  }

  // ---- Shop menu ----
  if (state.shopMenuOpen) {
    if (key === 'Escape') { closeAllMenus(); return; }
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
        if (costs[cur + 1] !== undefined) entries.push({ comp, level: cur + 1 });
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
    if (key === 'Escape') { closeAllMenus(); return; }
    const idx = parseInt(key) - 1;
    const p   = state.player;
    const pilesHere = state.piles.filter(pl => pl.x === p.x && pl.y === p.y);
    if (idx < 0 || idx >= pilesHere.length) return;
    const pile = pilesHere[idx];
    if (pile.owner_id === p.id) {
      // Set price
      const priceStr = prompt(`Set sell price per unit for ${pile.resource_type} (leave blank to mark not for sale):`);
      if (priceStr === null) { closeAllMenus(); return; }
      const price = priceStr.trim() === '' ? null : parseFloat(priceStr);
      if (priceStr.trim() !== '' && isNaN(price)) { closeAllMenus(); return; }
      WS.send({ type: 'set_pile_price', resource_type: pile.resource_type, price });
    } else if (pile.sell_price != null) {
      const maxAfford = Math.floor(p.coins / pile.sell_price);
      const space     = (p.bucket_cap || 10) - Object.values(p.bucket || {}).reduce((a,b)=>a+b,0);
      const maxBuy    = Math.min(pile.amount, space, maxAfford);
      if (maxBuy <= 0) {
        showNotice('Cannot afford or no bucket space.');
        closeAllMenus();
        return;
      }
      WS.send({ type: 'buy_pile', resource_type: pile.resource_type, amount: maxBuy });
    }
    closeAllMenus();
    return;
  }

  // ---- Normal keys ----
  const lk = key.toLowerCase();
  if (key === ' ')  { WS.send({ type: 'sell' }); }
  if (lk === 'b')   { WS.send({ type: 'buy_parcel' }); }
  if (lk === 'p')   { openBuildMenu(); }
  if (lk === 'u')   { WS.send({ type: 'unload' }); }
  if (lk === 'f')   { WS.send({ type: 'farm' }); }
  if (lk === 'e')   { _contextInteract(); }
}

function _contextInteract() {
  const p       = state.player;
  const px      = p.x, py = p.y;

  // NPC shop?
  const nearShop = state.npc_shops.find(s => Math.abs(s.x - px) <= 1 && Math.abs(s.y - py) <= 1);
  if (nearShop) { openShopMenu(nearShop.key); return; }

  // Own pile or other's pile?
  const pilesHere = state.piles.filter(pl => pl.x === px && pl.y === py);
  if (pilesHere.length) { openPileMenu(); return; }

  // Player market nearby?
  const nearMarket = state.nodes.find(n => n.is_market && Math.abs(n.x-px)<=1 && Math.abs(n.y-py)<=1);
  if (nearMarket) {
    // Simple: prompt for sell or buy
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

    const canvas = document.getElementById('game');
    Renderer.init(canvas, state);
    Input.init(msg => WS.send(msg), handleKey);

    WS.on('init', msg => {
      state.player    = msg.player;
      state.nodes     = msg.nodes;
      state.parcels   = msg.parcels;
      state.piles     = msg.piles  || [];
      state.crops     = msg.crops  || [];
      state.market    = msg.market;
      state.npc_shops = msg.npc_shops || [];
      state.prices    = msg.prices;
      state.season    = msg.season;
      state.world     = msg.world;
    });

    WS.on('tick', msg => {
      state.player  = msg.player;
      state.players = msg.players;
      state.nodes   = msg.nodes;
      state.parcels = msg.parcels;
      state.piles   = msg.piles  || [];
      state.crops   = msg.crops  || [];
      state.prices  = msg.prices;
      state.season  = msg.season;
      // Update input with flat-tire multiplier
      const flatMult = state.player.flat_tire ? 3.0 : 1.0;
      Input.setSpeedMult(flatMult);
    });

    WS.on('sold', msg => {
      state.player.coins  = msg.coins;
      if (msg.earned > 0) {
        state.player.bucket = {};
        showNotice(`Sold for ${msg.earned} coins!`);
      } else if (msg.msg) {
        showNotice(msg.msg);
      }
    });

    WS.on('parcel_bought', msg => {
      state.player.coins = msg.coins;
      state.parcels.push(msg.parcel);
      showNotice('Land purchased!');
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

    WS.on('notice', msg => showNotice(msg.msg));

    WS.connect(token);

    function loop(now) {
      Input.update(now);
      Renderer.draw();
      updateHud();
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }

  function tryLogin() {
    const u = usernameIn.value.trim();
    const pw = passwordIn.value;
    if (u && pw) startGame(u, pw);
    else loginErr.textContent = 'Enter username and password.';
  }

  loginBtn.addEventListener('click', tryLogin);
  passwordIn.addEventListener('keydown', e => { if (e.key === 'Enter') tryLogin(); });
  usernameIn.addEventListener('keydown', e => { if (e.key === 'Enter') passwordIn.focus(); });
});
