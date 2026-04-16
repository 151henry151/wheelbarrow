const state = {
  player:  null,
  players: [],
  nodes:   [],
  market:  null,
  prices:  {},
  world:   { w: 100, h: 100 },
};

// --- HUD helpers ---
function updateHud() {
  if (!state.player) return;
  document.getElementById('hud-coins-val').textContent = state.player.coins;

  const bucket = state.player.bucket || {};
  const total  = Object.values(bucket).reduce((a, b) => a + b, 0);
  const cap    = state.player.bucket_cap || 10;

  const contents = Object.entries(bucket)
    .filter(([, v]) => v > 0)
    .map(([k, v]) => `${k}: ${v}`)
    .join('  ');
  document.getElementById('hud-bucket-contents').textContent = contents || 'empty';
  document.getElementById('hud-bucket-fill').style.width = `${Math.min(100, (total / cap) * 100)}%`;

  // Hint
  const hint = document.getElementById('hud-hint');
  const atMarket = state.market &&
    state.player.x === state.market.x &&
    state.player.y === state.market.y;
  if (atMarket && total > 0) {
    hint.textContent = 'SPACE to sell';
  } else {
    // Check proximity to nodes
    const near = state.nodes.find(n =>
      Math.abs(n.x - state.player.x) <= 1 &&
      Math.abs(n.y - state.player.y) <= 1
    );
    hint.textContent = near ? `Collecting ${near.type}...` : '';
  }
}

// --- Boot ---
window.addEventListener('load', () => {
  const loginScreen = document.getElementById('login-screen');
  const gameScreen  = document.getElementById('game-screen');
  const loginBtn    = document.getElementById('login-btn');
  const usernameIn  = document.getElementById('username-input');
  const loginErr    = document.getElementById('login-error');

  async function startGame(username) {
    loginErr.textContent = '';
    const res = await fetch('/api/login', {
      method: 'POST',
      headers: { 'Content-Type': 'application/json' },
      body: JSON.stringify({ username }),
    });
    if (!res.ok) { loginErr.textContent = 'Could not log in.'; return; }
    const { token } = await res.json();

    loginScreen.style.display = 'none';
    gameScreen.style.display  = 'block';

    const canvas = document.getElementById('game');
    Renderer.init(canvas, state);
    Input.init(msg => WS.send(msg));

    WS.on('init', msg => {
      state.player  = msg.player;
      state.nodes   = msg.nodes;
      state.market  = msg.market;
      state.prices  = msg.prices;
      state.world   = msg.world;
    });

    WS.on('tick', msg => {
      state.player  = msg.player;
      state.players = msg.players;
      state.nodes   = msg.nodes;
    });

    WS.on('sold', msg => {
      state.player.coins  = msg.coins;
      state.player.bucket = {};
    });

    WS.connect(token);

    function loop(now) {
      Input.update(now);
      Renderer.draw();
      updateHud();
      requestAnimationFrame(loop);
    }
    requestAnimationFrame(loop);
  }

  loginBtn.addEventListener('click', () => {
    const u = usernameIn.value.trim();
    if (u) startGame(u);
  });
  usernameIn.addEventListener('keydown', e => {
    if (e.key === 'Enter') { const u = usernameIn.value.trim(); if (u) startGame(u); }
  });
});
