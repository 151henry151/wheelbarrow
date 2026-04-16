const Input = (() => {
  const MOVE_INTERVAL_MS = 150;
  const dirKeys = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' };
  const held = {};
  let lastMove = 0;
  let sendFn = null;
  let onKey = null;   // callback for non-movement keys

  function init(fn, keyFn) {
    sendFn = fn;
    onKey  = keyFn;
    window.addEventListener('keydown', e => {
      if (dirKeys[e.key]) { e.preventDefault(); held[e.key] = true; return; }
      e.preventDefault();
      onKey && onKey(e.key);
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
