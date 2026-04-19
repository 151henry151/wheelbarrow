const GAME_VERSION = 'v0.12.63';

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
  fertilizer: 0.65,
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
  stable:        { label: 'Horse Stable',    cost: '200c start + foundation + building', produces: 'manure'  },
  gravel_pit:    { label: 'Gravel Pit',      cost: '300c start + foundation + building', produces: 'gravel'  },
  compost_heap:  { label: 'Compost Heap',    cost: '150c start + foundation + building', produces: 'compost' },
  topsoil_mound: { label: 'Topsoil Mound',   cost: '250c start + foundation + building', produces: 'topsoil' },
  market:        { label: 'Player Market',   cost: '2000c start + foundation + building', produces: null     },
  town_hall:     { label: 'Town Hall',       cost: '5000c start + foundation + building', produces: null },
  silo:          { label: 'Grain Silo',      cost: '500c start + 60 stone + 80 wood',      produces: null },
};
const STRUCT_KEYS = Object.keys(STRUCTURE_DEFS);

const SEED_SHOP = {
  wheat_seed: { label: 'Wheat Seeds ×10', cost: 25 },
  fertilizer: { label: 'Fertilizer ×5',  cost: 50 },
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
const WB_BUCKET_CAPS = {1:10, 2:16, 3:26, 4:40, 5:60, 6:85};

// Mirrored from server/game/constants.py (bridge costs)
const BRIDGE_COIN_COST = 30;
const BRIDGE_WOOD_REQUIRED = 10;

// Fallback if init sends no npc_markets (mirrors server MARKET_TILE)
const NPC_MARKET_FALLBACK = { x: 500, y: 560 };

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
  roads:        [],
  soil_tiles:   [],
  water_tiles:  [],
  bridge_tiles: [],
  poor_soil_tiles: [],
  crops:        [],
  npc_markets:  [],
  npc_shops:    [],
  prices:       {},
  season:       null,
  world:        { w: 1000, h: 1000 },

  // Wheelbarrow sprite facing (screen/world: up = −y, down = +y)
  facing:         'down',
  _otherFacing:   {},   // player id -> 'up'|'down'|'left'|'right'
  _prevOtherPos:  {},
  _prevSelfPos:   null,

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

  sellAutopilotActive: false,
  sellAutopilotPile:   null,   // { x, y, resource_type } while running
  /** Set each frame: orbit yaw locked behind barrow while any move/turn key or autopilot */
  cameraFollowDriving: false,
  _tickWaiters:        [],
  _soldWaiter:         null,
};

// ---------------------------------------------------------------- helpers

function _facingFromDelta(dx, dy) {
  if (dx === 0 && dy === 0) return null;
  if (Math.abs(dx) > Math.abs(dy)) return dx > 0 ? 'right' : 'left';
  return dy > 0 ? 'down' : 'up';
}

/** Server angle (radians): east=0, south=π/2 — map to cardinal for [L]/[J] hints. */
function _facingFromAngle(a) {
  if (a == null || !Number.isFinite(a)) return 'down';
  const x = Math.cos(a);
  const y = Math.sin(a);
  if (Math.abs(x) >= Math.abs(y)) return x >= 0 ? 'right' : 'left';
  return y >= 0 ? 'down' : 'up';
}

function _parcelAt(x, y) {
  for (const p of state.world_parcels) {
    if (x >= p.x && x < p.x + p.w && y >= p.y && y < p.y + p.h) return p;
  }
  return null;
}

/** Matches server free pile pickup (priced → owner only; on owner's land → owner only; else public). */
function _canFreePickPile(pile, player) {
  if (pile.sell_price != null) return pile.owner_id === player.id;
  const par = _parcelAt(pile.x, pile.y);
  if (par && par.owner_id === pile.owner_id) return player.id === pile.owner_id;
  return true;
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

/** 0 = untilled / needs till, 1 = tilled ready for seeds (from server soil_tiles). */
function _soilTilledAt(x, y) {
  const e = state.soil_tiles.find(t => t.x === x && t.y === y);
  return e ? e.tilled : 0;
}

function _poorSoilAt(x, y) {
  return (state.poor_soil_tiles || []).some(t => t.x === x && t.y === y);
}

function _adjFromFacing(px, py, facing) {
  const m = { up: [0, -1], down: [0, 1], left: [-1, 0], right: [1, 0] };
  const d = m[facing] || [0, 1];
  return { x: px + d[0], y: py + d[1] };
}

function _nearNpcMarket(px, py) {
  const mks = state.npc_markets || [];
  return mks.some(m => Math.abs(m.x - px) <= 1 && Math.abs(m.y - py) <= 1);
}

function _onNpcMarketTile(px, py) {
  const mks = state.npc_markets || [];
  return mks.some(m => m.x === px && m.y === py);
}

/** Matches server effective_bucket_cap (half while handle is snapped). */
function effectiveBucketCap(p) {
  if (!p) return 10;
  return p.bucket_cap_effective != null ? p.bucket_cap_effective : (p.bucket_cap || 10);
}

function _bucketTotalPlayer(p) {
  return Object.values(p.bucket || {}).reduce((a, b) => a + b, 0);
}

function _npcMarketTarget() {
  const markets = state.npc_markets && state.npc_markets.length
    ? state.npc_markets
    : [NPC_MARKET_FALLBACK];
  const ref = state.sellAutopilotPile || state.player;
  const hx = ref.x != null ? ref.x : state.player.x;
  const hy = ref.y != null ? ref.y : state.player.y;
  let best = markets[0];
  let bestD = Infinity;
  for (const m of markets) {
    if (m.x === undefined || m.y === undefined) continue;
    const d = Math.abs(m.x - hx) + Math.abs(m.y - hy);
    if (d < bestD) {
      bestD = d;
      best = m;
    }
  }
  return { x: best.x, y: best.y };
}

function _findPileAt(hx, hy, rtype) {
  return state.piles.find(pl => pl.x === hx && pl.y === hy && pl.resource_type === rtype);
}

function waitNextTick() {
  return new Promise(resolve => {
    state._tickWaiters.push(resolve);
  });
}

function _angleWrap(d) {
  let a = d;
  while (a > Math.PI) a -= 2 * Math.PI;
  while (a < -Math.PI) a += 2 * Math.PI;
  return a;
}

async function _autopilotMoveToTile(tx, ty) {
  const ARRIVE = 0.45;
  let guard = 0;
  while (
    state.sellAutopilotActive &&
    guard++ < 8000
  ) {
    const px = state.player.x;
    const py = state.player.y;
    const dx = tx + 0.5 - px;
    const dy = ty + 0.5 - py;
    if (Math.hypot(dx, dy) < ARRIVE) break;
    const desired = Math.atan2(dy, dx);
    const cur = state.player.angle != null ? state.player.angle : Math.PI / 2;
    const diff = _angleWrap(desired - cur);
    const turn = Math.max(-1, Math.min(1, diff * 2.2));
    let fwd = Math.abs(diff) < 0.35 ? 1.0 : 0.35;
    state.facing = _facingFromAngle(cur);
    WS.send({ type: 'move', fwd, turn });
    await waitNextTick();
  }
  const px = state.player.x;
  const py = state.player.y;
  return Math.hypot(tx + 0.5 - px, ty + 0.5 - py) < ARRIVE * 1.5;
}

/**
 * Wait on pile tile until we should go sell (full barrow or pile empty with cargo left),
 * or done (pile and bucket empty).
 */
async function _waitLoadPhase(rtype, hx, hy) {
  while (state.sellAutopilotActive) {
    if (Math.floor(state.player.x) !== hx || Math.floor(state.player.y) !== hy) {
      await _autopilotMoveToTile(hx, hy);
      continue;
    }
    const pile = _findPileAt(hx, hy, rtype);
    const pa = pile ? pile.amount : 0;
    const ld = _bucketTotalPlayer(state.player);
    const cap = effectiveBucketCap(state.player);
    if (pa <= 0 && ld <= 0) return 'done';
    if (ld >= cap - 0.06) return 'sell';
    if (pa <= 0 && ld > 0) return 'sell';
    await waitNextTick();
  }
  return 'abort';
}

function waitForSoldMessage() {
  return new Promise(resolve => {
    state._soldWaiter = resolve;
  });
}

function stopSellAutopilot(reason) {
  if (!state.sellAutopilotActive) return;
  state.sellAutopilotActive = false;
  state.sellAutopilotPile = null;
  if (typeof Input !== 'undefined') {
    Input.setAutopilotBlocked(false);
    Input.clearHeldKeys();
  }
  if (typeof WS !== 'undefined' && WS.send) WS.send({ type: 'move', fwd: 0, turn: 0 });
  const banner = document.getElementById('autopilot-banner');
  if (banner) banner.style.display = 'none';
  if (state._soldWaiter) {
    const w = state._soldWaiter;
    state._soldWaiter = null;
    w();
  }
  const tw = state._tickWaiters.splice(0);
  tw.forEach(fn => fn());
  if (reason === 'user') showNotice('Autopilot stopped.');
  else if (reason === 'complete') showNotice('Autopilot finished — stood by empty pile.');
  // 'disconnect': silent — connection lost
}

async function runSellAutopilotLoop(rtype, hx, hy) {
  const market = _npcMarketTarget();
  while (state.sellAutopilotActive) {
    await _autopilotMoveToTile(hx, hy);
    if (!state.sellAutopilotActive) return;

    const phase = await _waitLoadPhase(rtype, hx, hy);
    if (!state.sellAutopilotActive || phase === 'abort') return;
    if (phase === 'done') {
      await _autopilotMoveToTile(hx, hy);
      return;
    }

    await _autopilotMoveToTile(market.x, market.y);
    if (!state.sellAutopilotActive) return;

    const bt = _bucketTotalPlayer(state.player);
    if (bt <= 0) continue;

    const soldPromise = waitForSoldMessage();
    WS.send({ type: 'sell' });
    await soldPromise;
    if (!state.sellAutopilotActive) return;
  }
}

function startSellAutopilotFromPile(pile) {
  if (state.sellAutopilotActive || !pile || pile.owner_id !== state.player.id) return;
  if (!pile.amount || pile.amount <= 0) return;

  state.sellAutopilotActive = true;
  state.sellAutopilotPile = { x: pile.x, y: pile.y, resource_type: pile.resource_type };
  Input.setAutopilotBlocked(true);
  Input.clearHeldKeys();
  const banner = document.getElementById('autopilot-banner');
  if (banner) banner.style.display = 'block';
  showNotice('Autopilot — load, NPC market, repeat. Press any key except H to stop.');

  runSellAutopilotLoop(pile.resource_type, pile.x, pile.y)
    .then(() => {
      if (state.sellAutopilotActive) stopSellAutopilot('complete');
    })
    .catch(() => stopSellAutopilot('user'));
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
  const cap    = effectiveBucketCap(player);
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

  document.getElementById('hud-version').textContent = GAME_VERSION;

  if (state.season) {
    const mins = Math.ceil(state.season.remaining_s / 60);
    document.getElementById('hud-season').textContent =
      `Season: ${state.season.name}  (${mins}m left)`;
  }

  document.getElementById('hud-coins-val').textContent = state.player.coins;

  const bucket = state.player.bucket || {};
  const total  = Object.values(bucket).reduce((a,b) => a+b, 0);
  const cap    = effectiveBucketCap(state.player);
  const lines  = Object.entries(bucket).filter(([,v]) => v > 0).map(([k,v]) => `${k}: ${v}`);
  document.getElementById('hud-bucket-contents').textContent = lines.length ? lines.join('\n') : 'empty';
  document.getElementById('hud-bucket-fill').style.width = `${Math.min(100, (total/cap)*100)}%`;

  const pocket = state.player.pocket || {};
  const pLines = Object.entries(pocket).filter(([,v]) => v > 0).map(([k,v]) => `${k}: ${v}`);
  document.getElementById('hud-pocket').textContent = pLines.length ? 'pocket: ' + pLines.join('  ') : '';

  // Prices only visible when standing at/near a market
  const px = state.player.x, py = state.player.y;
  const nearNpcMarket = _nearNpcMarket(px, py);
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
  const bucketCap  = WB_BUCKET_CAPS[p.wb_bucket_level] || 10;
  document.getElementById('wb-upgrades').textContent =
    `barrow: ${barrowName}  tire: ${tireName}  handle: ${handleName}  cap: ${bucketCap}`;
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

  if (state.sellAutopilotActive) {
    hints.push('Autopilot — any key except H stops');
  }

  if ((p.wb_handle ?? 100) <= 0) {
    hints.push('Snapped handle — half barrow capacity until you repair at Repair Shop');
  }

  const atMarket = _onNpcMarketTile(px, py);
  const total    = Object.values(p.bucket || {}).reduce((a,b) => a+b, 0);
  if (atMarket && total > 0) hints.push('[Space] sell all at NPC market');
  if (total > 0) {
    hints.push('[U] unload (pile at your feet; wheat → silo if standing on one)');
    const siloHere = state.nodes.find(
      n => n.is_silo && n.x === px && n.y === py && n.owner_id === p.id,
    );
    if (siloHere && (siloHere.silo_wheat || 0) > 0) {
      hints.push('[O] withdraw wheat from silo to barrow');
    }
  }

  const siteHere = state.nodes.find(
    n => n.construction_active && n.x === px && n.y === py && n.owner_id === p.id,
  );
  if (siteHere) {
    if (total > 0) hints.push('[G] deliver barrow materials to this construction site');
    else hints.push('[G] deliver materials when your barrow has stone, wood, etc.');
    const c = siteHere.construction;
    if (c) {
      const parts = [];
      for (const [k, v] of Object.entries(c.foundation_remaining || {})) {
        if (v > 0) parts.push(`${k} ${(+v).toFixed(1)}`);
      }
      for (const [k, v] of Object.entries(c.building_remaining || {})) {
        if (v > 0) parts.push(`${k} ${(+v).toFixed(1)}`);
      }
      if (parts.length) hints.push(`Construction still needs: ${parts.join(', ')}`);
    }
    hints.push('[X] cancel construction (refund deposited materials, not the start coins)');
  }

  const nearShop = state.npc_shops.find(s => Math.abs(s.x - px) <= 1 && Math.abs(s.y - py) <= 1);
  if (nearShop) hints.push(`[E] open ${nearShop.label}`);

  const nearHall = state.nodes.find(n => n.is_town_hall && Math.abs(n.x-px) <= 1 && Math.abs(n.y-py) <= 1);
  if (nearHall) hints.push('[E] town hall');

  if (state.season && state.season.name === 'fall') {
    hints.push('Winter kills crops in the ground; uncovered wheat piles rot — use a silo or sell.');
  }

  const parcel = _parcelAt(px, py);
  if (parcel) {
    if (parcel.owner_id === p.id) {
      hints.push('[P] build menu');
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
    const pick = pilesHere.find(pl => _canFreePickPile(pl, p) && pl.amount > 0);
    if (pick) {
      const cap  = effectiveBucketCap(p);
      const load = Object.values(p.bucket || {}).reduce((a, b) => a + b, 0);
      if (load < cap) hints.push(`Loading ${pick.resource_type} from pile…`);
    }
  }

  const near = state.nodes.find(n => !n.is_structure && Math.abs(n.x-px)<=1 && Math.abs(n.y-py)<=1 && n.amount > 0);
  if (near) hints.push(`Collecting ${near.type}...`);

  const isWinter = state.season && state.season.name === 'winter';
  const crop = state.crops.find(c => c.x === px && c.y === py);
  if (crop) {
    if (crop.winter_dead) {
      if (pilesHere.length) {
        hints.push('Clear pile on this tile before [F] till');
      }
      hints.push(isWinter
        ? 'Frozen soil — wait for spring to [F] till frosted crop'
        : '[F] till — clear frosted crop');
    } else {
      hints.push(crop.ready ? '[F] harvest crop'
        : '[F] fertilize (fertilizer, compost, or manure in barrow) / check crop');
    }
  } else if (parcel && parcel.owner_id === p.id) {
    if (pilesHere.length) {
      hints.push('Clear resource pile(s) on this tile before [F] till or plant');
    } else if (_poorSoilAt(px, py)) {
      if ((p.bucket || {}).dirt >= 1) {
        hints.push('[I] spread 1 dirt to improve poor soil (required before tilling)');
      } else {
        hints.push('Poor soil — load dirt, then [I] here before you can till or plant');
      }
    } else if (_soilTilledAt(px, py) === 1) {
      if (state.season && state.season.name === 'spring') {
        hints.push('[F] plant wheat (tilled soil)');
      } else if (isWinter) {
        hints.push('Tilled — frozen ground; plant wheat in spring');
      } else {
        hints.push('Tilled — planting wheat is only allowed in spring');
      }
    } else {
      hints.push(isWinter
        ? 'Frozen ground — wait for spring to [F] till and plant'
        : '[F] till soil before planting');
    }
  }

  const myStructHere = state.nodes.find(
    n => n.is_structure && !n.construction_active && n.x === px && n.y === py && n.owner_id === p.id,
  );
  if (myStructHere && !myStructHere.is_town_hall) {
    hints.push('[K] tear down building (partial material refund to piles)');
  }

  const adj = _adjFromFacing(px, py, state.facing);
  const waterFacing = (state.water_tiles || []).some(t => t.x === adj.x && t.y === adj.y);
  const parAdj = _parcelAt(adj.x, adj.y);
  if (waterFacing) {
    hints.push(`[J] bridge: pay ${BRIDGE_COIN_COST}c once per tile, then ${BRIDGE_WOOD_REQUIRED} wood total (facing water)`);
    if ((p.bucket || {}).dirt >= 1 && parAdj && parAdj.owner_id === p.id) {
      hints.push('[L] fill adjacent water with 1 dirt (your land only)');
    }
  }

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
    const wrap = document.createElement('div');
    wrap.className = 'pile-menu-entry';
    const div = document.createElement('div');
    div.className = 'build-option affordable';
    const isOwn  = pile.owner_id === p.id;
    const priceStr = pile.sell_price != null ? `${pile.sell_price}c/unit` : 'not for sale';
    if (isOwn) {
      div.innerHTML = `<span class="key">[${i+1}]</span> ${pile.resource_type}: ${pile.amount} — ${priceStr} (set price)`;
    } else {
      div.innerHTML = `<span class="key">[${i+1}]</span> Buy ${pile.resource_type}: ${pile.amount} @ ${priceStr}`;
    }
    wrap.appendChild(div);
    if (isOwn && pile.amount > 0) {
      const btn = document.createElement('button');
      btn.type = 'button';
      btn.className = 'pile-sell-all-btn';
      btn.textContent = 'Sell all at NPC market…';
      btn.addEventListener('click', (ev) => {
        ev.stopPropagation();
        if (state.sellAutopilotActive) {
          showNotice('Autopilot already running.');
          return;
        }
        if (!confirm(
          'Sell all at NPC market?\n\n'
          + 'Your wheelbarrow will autopilot: stand on this pile until your barrow loads, '
          + 'roll to the main NPC market tile and sell, return here, and repeat until this pile is empty. '
          + 'Then you stop on this tile.\n\n'
          + 'Press any key except H (HUD toggle) to cancel autopilot.',
        )) return;
        closeAllMenus();
        startSellAutopilotFromPile(pile);
      });
      wrap.appendChild(btn);
    }
    items.appendChild(wrap);
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
  if (state.sellAutopilotActive && key.toLowerCase() === 'h') {
    toggleHud();
    return;
  }

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
      const space     = effectiveBucketCap(p) - Object.values(p.bucket || {}).reduce((a,b)=>a+b,0);
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
  if (lk === 'g')  { WS.send({ type: 'deposit_build' }); return; }
  if (lk === 'x')  { WS.send({ type: 'cancel_construction' }); return; }
  if (lk === 'k')  { WS.send({ type: 'demolish_structure' }); return; }
  if (lk === 'i')  { WS.send({ type: 'improve_soil' }); return; }
  if (lk === 'l')  { WS.send({ type: 'fill_water', dir: state.facing }); return; }
  if (lk === 'j')  { WS.send({ type: 'bridge_deposit', dir: state.facing }); return; }
  if (lk === 'o')  { WS.send({ type: 'silo_withdraw' }); return; }
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

    // Focus: hidden login inputs can keep focus so window never receives WASD (Firefox especially).
    const canvas = document.getElementById('game');
    if (document.activeElement && typeof document.activeElement.blur === 'function') {
      document.activeElement.blur();
    }
    canvas.setAttribute('tabindex', '0');
    canvas.focus({ preventScroll: true });

    // HUD is hidden by default
    document.getElementById('hud').style.display    = 'none';
    document.getElementById('hud-wb').style.display = 'none';
    document.getElementById('hud-toggle').textContent = '[H] hud';

    Renderer.init(canvas, state);
    Input.init(msg => {
      if (msg.type === 'move' && msg.face_angle != null && state.player) {
        let a = Number(msg.face_angle);
        if (Number.isFinite(a)) {
          while (a > Math.PI) a -= 2 * Math.PI;
          while (a < -Math.PI) a += 2 * Math.PI;
          state.player.angle = a;
        }
      }
      WS.send(msg);
    }, handleKey);

    window.addEventListener('keydown', (e) => {
      if (!state.sellAutopilotActive) return;
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (e.key === 'h' || e.key === 'H') return;
      stopSellAutopilot('user');
      e.preventDefault();
      e.stopPropagation();
    }, true);

    WS.on('init', msg => {
      state.player        = msg.player;
      state.player.username = username;
      state.facing        = 'down';
      state._otherFacing  = {};
      state._prevOtherPos = {};
      state._prevSelfPos  = { x: msg.player.x, y: msg.player.y };
      state.players       = msg.players || [];
      state.nodes         = msg.nodes;
      state.world_parcels = msg.parcels || [];
      state.piles         = msg.piles   || [];
      state.roads         = msg.roads   || [];
      state.soil_tiles    = msg.soil_tiles || [];
      state.water_tiles   = msg.water_tiles || [];
      state.bridge_tiles  = msg.bridge_tiles || [];
      state.poor_soil_tiles = msg.poor_soil_tiles || [];
      state.crops         = msg.crops   || [];
      state.towns         = msg.towns   || [];
      state.npc_markets   = msg.npc_markets || (msg.market ? [msg.market] : []);
      state.npc_shops     = msg.npc_shops || [];
      state.prices        = msg.prices;
      state.season        = msg.season;
      state.world         = msg.world || { w: 1000, h: 1000 };
      _checkTownCrossing();
    });

    WS.on('tick', msg => {
      const uname = state.player ? state.player.username : null;
      const prevSelf = state._prevSelfPos;
      state.player  = msg.player;
      if (uname) state.player.username = uname;
      if (state.player.angle != null && Number.isFinite(state.player.angle)) {
        state.facing = _facingFromAngle(state.player.angle);
      } else if (prevSelf) {
        const f = _facingFromDelta(state.player.x - prevSelf.x, state.player.y - prevSelf.y);
        if (f) state.facing = f;
      }
      state._prevSelfPos = { x: state.player.x, y: state.player.y };

      for (const pl of msg.players) {
        if (state.player && pl.id === state.player.id) continue;
        if (pl.angle != null && Number.isFinite(pl.angle)) {
          state._otherFacing[pl.id] = _facingFromAngle(pl.angle);
        } else {
          const pr = state._prevOtherPos[pl.id];
          if (pr) {
            const f = _facingFromDelta(pl.x - pr.x, pl.y - pr.y);
            if (f) state._otherFacing[pl.id] = f;
          }
        }
        state._prevOtherPos[pl.id] = { x: pl.x, y: pl.y };
      }

      state.players = msg.players;
      state.nodes   = msg.nodes;
      state.piles   = msg.piles  || [];
      state.roads   = msg.roads  || [];
      state.soil_tiles = msg.soil_tiles || [];
      state.water_tiles = msg.water_tiles || [];
      state.bridge_tiles = msg.bridge_tiles || [];
      state.poor_soil_tiles = msg.poor_soil_tiles || [];
      state.crops   = msg.crops  || [];
      state.prices  = msg.prices;
      state.season  = msg.season;
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

      if (state._tickWaiters.length) {
        const fn = state._tickWaiters.shift();
        if (fn) fn();
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
      if (state._soldWaiter) {
        const w = state._soldWaiter;
        state._soldWaiter = null;
        w();
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
      const idx = state.nodes.findIndex(n => n.id === msg.structure.id);
      if (idx >= 0) state.nodes[idx] = msg.structure;
      else state.nodes.push(msg.structure);
      showNotice(msg.msg || `Built ${msg.structure.type}!`);
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

    WS.on('notice', msg => {
      if (msg.structure) {
        const idx = state.nodes.findIndex(n => n.id === msg.structure.id);
        if (idx >= 0) state.nodes[idx] = msg.structure;
        else state.nodes.push(msg.structure);
      }
      showNotice(msg.msg);
    });

    WS.connect(token, null, () => {
      stopSellAutopilot('disconnect');
      state.players = [];
      state._otherFacing = {};
      state._prevOtherPos = {};
    });

    function loop(now) {
      Input.update(now, state.player, state.world);
      state.cameraFollowDriving = !!(
        state.player
        && (
          state.sellAutopilotActive
          || (
            typeof Input.isWheelbarrowControlActive === 'function'
            && Input.isWheelbarrowControlActive()
          )
        )
      );
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
