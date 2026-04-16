const Input = (() => {
  const BASE_INTERVAL_MS = 150;
  const dirKeys = { ArrowUp:'up', ArrowDown:'down', ArrowLeft:'left', ArrowRight:'right' };
  const held = {};
  let lastMove    = 0;
  let speedMult   = 1.0;   // increased when flat tyre
  let sendFn      = null;
  let onKey       = null;

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

  function update(now) {
    if (!sendFn) return;
    const interval = BASE_INTERVAL_MS * speedMult;
    if (now - lastMove < interval) return;
    for (const [key, dir] of Object.entries(dirKeys)) {
      if (held[key]) {
        sendFn({ type: 'move', dir });
        lastMove = now;
        break;
      }
    }
  }

  return { init, update, setSpeedMult };
})();
