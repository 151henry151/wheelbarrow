const Input = (() => {
  const MOVE_INTERVAL_MS = 150; // ms between moves while key held
  const held = {};
  const dirKeys = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' };
  let lastMove = 0;
  let sendFn = null;

  function init(fn) {
    sendFn = fn;
    window.addEventListener('keydown', e => {
      if (dirKeys[e.key]) { e.preventDefault(); held[e.key] = true; }
      if (e.key === ' ') { e.preventDefault(); sendFn && sendFn({ type: 'sell' }); }
    });
    window.addEventListener('keyup', e => { delete held[e.key]; });
  }

  function update(now) {
    if (!sendFn) return;
    if (now - lastMove < MOVE_INTERVAL_MS) return;
    for (const [key, dir] of Object.entries(dirKeys)) {
      if (held[key]) {
        sendFn({ type: 'move', dir });
        lastMove = now;
        break;
      }
    }
  }

  return { init, update };
})();
