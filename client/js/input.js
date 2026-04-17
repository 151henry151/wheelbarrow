/* global Renderer, Terrain */
const Input = (() => {
  const BASE_INTERVAL_MS = 150;
  const dirKeys = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' };
  const held = {};
  let lastMove    = 0;
  let speedMult   = 1.0;   // increased when flat tyre
  let sendFn      = null;
  let onKey       = null;
  let autopilotBlocked = false;

  function init(fn, keyFn) {
    sendFn = fn;
    onKey  = keyFn;
    window.addEventListener('keydown', e => {
      // Never intercept browser shortcuts (Ctrl/Alt/Meta combos like Ctrl+R, Ctrl+Shift+R)
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (dirKeys[e.key]) { e.preventDefault(); held[e.key] = true; return; }
      e.preventDefault();
      onKey && onKey(e.key);
    });
    window.addEventListener('keyup', e => { delete held[e.key]; });
  }

  function setSpeedMult(mult) {
    speedMult = mult;
  }

  function update(now, player, world) {
    if (!sendFn || autopilotBlocked) return;

    let dir = null;
    let terrainM = 1;

    if (typeof Renderer !== 'undefined' && typeof Renderer.getCameraMoveBasis === 'function') {
      const { fx, fz } = Renderer.getCameraMoveBasis();
      let vx = 0;
      let vz = 0;
      if (held.ArrowUp) { vx += fx; vz += fz; }
      if (held.ArrowDown) { vx -= fx; vz -= fz; }
      if (held.ArrowLeft) { vx += fz; vz -= fx; }
      if (held.ArrowRight) { vx -= fz; vz += fx; }
      const len = Math.hypot(vx, vz);
      if (len < 1e-8) return;
      const nx = vx / len;
      const nz = vz / len;
      let best = 'up';
      let bestDot = -Infinity;
      const cardinals = [
        ['up', -nz],
        ['down', nz],
        ['left', -nx],
        ['right', nx],
      ];
      for (const [name, d] of cardinals) {
        if (d > bestDot) {
          bestDot = d;
          best = name;
        }
      }
      dir = best;
      if (player && typeof Terrain !== 'undefined') {
        terrainM = Terrain.moveIntervalMult(
          player.x,
          player.y,
          dir,
          world && world.w,
          world && world.h,
        );
      }
    } else {
      for (const [key, d] of Object.entries(dirKeys)) {
        if (held[key]) {
          dir = d;
          if (player && typeof Terrain !== 'undefined') {
            terrainM = Terrain.moveIntervalMult(
              player.x,
              player.y,
              dir,
              world && world.w,
              world && world.h,
            );
          }
          break;
        }
      }
      if (!dir) return;
    }

    const interval = BASE_INTERVAL_MS * speedMult * terrainM;
    if (now - lastMove < interval) return;
    sendFn({ type: 'move', dir });
    lastMove = now;
  }

  function setAutopilotBlocked(v) {
    autopilotBlocked = !!v;
  }

  function clearHeldKeys() {
    for (const k of Object.keys(held)) delete held[k];
  }

  return { init, update, setSpeedMult, setAutopilotBlocked, clearHeldKeys };
})();
