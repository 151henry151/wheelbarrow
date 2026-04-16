const PARCEL_SIZE = 10;

const STRUCTURE_DEFS = {
  stable:        { label: 'Horse Stable',  cost: '200c',           produces: 'manure'  },
  gravel_pit:    { label: 'Gravel Pit',    cost: '300c + 20 grvl', produces: 'gravel'  },
  compost_heap:  { label: 'Compost Heap',  cost: '150c + 10 mnr',  produces: 'compost' },
  topsoil_mound: { label: 'Topsoil Mound', cost: '250c + 20 top',  produces: 'topsoil' },
};
const STRUCT_KEYS = Object.keys(STRUCTURE_DEFS);

const state = {
  player:  null,
  players: [],
  nodes:   [],
  parcels: [],
  market:  null,
  prices:  {},
  world:   { w: 100, h: 100 },
  buildMenuOpen: false,
};

// ---------------------------------------------------------------- notice bar
let noticeTimer = null;
function showNotice(msg) {
  const bar = document.getElementById('notice-bar');
  bar.textContent = msg;
  bar.style.display = 'block';
  bar.style.opacity = '1';
  if (noticeTimer) clearTimeout(noticeTimer);
  noticeTimer = setTimeout(() => { bar.style.opacity = '0'; setTimeout(() => bar.style.display = 'none', 400); }, 3000);
}

// ---------------------------------------------------------------- HUD
function updateHud() {
  if (!state.player) return;

  document.getElementById('hud-coins-val').textContent = state.player.coins;

  const bucket  = state.player.bucket || {};
  const total   = Object.values(bucket).reduce((a, b) => a + b, 0);
  const cap     = state.player.bucket_cap || 10;
  const lines   = Object.entries(bucket).filter(([,v]) => v > 0).map(([k,v]) => `${k}: ${v}`);
  document.getElementById('hud-bucket-contents').textContent = lines.length ? lines.join('\n') : 'empty';
  document.getElementById('hud-bucket-fill').style.width = `${Math.min(100, (total / cap) * 100)}%`;

  document.getElementById('hud-prices').textContent =
    Object.entries(state.prices).map(([k, v]) => `${k[0].toUpperCase()}${k.slice(1)}: ${v}c`).join('  ');

  const hint = document.getElementById('hud-hint');
  const px = state.player.x, py = state.player.y;
  const atMarket = state.market && px === state.market.x && py === state.market.y;

  if (state.buildMenuOpen) {
    hint.textContent = '';
    return;
  }
  if (atMarket && total > 0) {
    hint.textContent = '[Space] sell all';
    return;
  }
  const parcelKey = `${Math.floor(px / PARCEL_SIZE)},${Math.floor(py / PARCEL_SIZE)}`;
  const myParcel  = state.parcels.find(p => `${p.px},${p.py}` === parcelKey && p.owner_id === state.player.id);
  const anyParcel = state.parcels.find(p => `${p.px},${p.py}` === parcelKey);

  if (myParcel) {
    hint.textContent = '[P] build menu';
  } else if (!anyParcel) {
    hint.textContent = `[B] buy parcel (500c)`;
  } else {
    hint.textContent = `owned by ${anyParcel.owner_name}`;
  }

  const near = state.nodes.find(n => Math.abs(n.x - px) <= 1 && Math.abs(n.y - py) <= 1);
  if (near && !atMarket && !myParcel) {
    hint.textContent = `Collecting ${near.type}...`;
  }
}

// ------------------------------------------------------------ build menu
function openBuildMenu() {
  state.buildMenuOpen = true;
  const menu  = document.getElementById('build-menu');
  const items = document.getElementById('build-menu-items');
  items.innerHTML = '';
  STRUCT_KEYS.forEach((type, i) => {
    const def = STRUCTURE_DEFS[type];
    const div = document.createElement('div');
    div.className = 'build-option affordable';
    div.innerHTML = `<span class="key">[${i + 1}]</span> ${def.label} — ${def.cost} → ${def.produces}`;
    items.appendChild(div);
  });
  menu.style.display = 'block';
}

function closeBuildMenu() {
  state.buildMenuOpen = false;
  document.getElementById('build-menu').style.display = 'none';
}

// --------------------------------------------------------------- key handler
function handleKey(key) {
  if (state.buildMenuOpen) {
    if (key === 'Escape') { closeBuildMenu(); return; }
    const idx = parseInt(key) - 1;
    if (idx >= 0 && idx < STRUCT_KEYS.length) {
      WS.send({ type: 'build', structure_type: STRUCT_KEYS[idx] });
      closeBuildMenu();
    }
    return;
  }
  if (key === ' ')   WS.send({ type: 'sell' });
  if (key === 'b' || key === 'B') WS.send({ type: 'buy_parcel' });
  if (key === 'p' || key === 'P') openBuildMenu();
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
      const res = await fetch(`${basePath}/api/login`, {
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
      state.player  = msg.player;
      state.nodes   = msg.nodes;
      state.parcels = msg.parcels;
      state.market  = msg.market;
      state.prices  = msg.prices;
      state.world   = msg.world;
    });

    WS.on('tick', msg => {
      state.player  = msg.player;
      state.players = msg.players;
      state.nodes   = msg.nodes;
      state.parcels = msg.parcels;
      state.prices  = msg.prices;
    });

    WS.on('sold', msg => {
      state.player.coins  = msg.coins;
      state.player.bucket = {};
      showNotice(`Sold for ${msg.earned} coins!`);
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
    const p = passwordIn.value;
    if (u && p) startGame(u, p);
    else loginErr.textContent = 'Enter username and password.';
  }

  loginBtn.addEventListener('click', tryLogin);
  passwordIn.addEventListener('keydown', e => { if (e.key === 'Enter') tryLogin(); });
  usernameIn.addEventListener('keydown', e => { if (e.key === 'Enter') passwordIn.focus(); });
});
