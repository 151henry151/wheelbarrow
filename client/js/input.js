/* global Renderer, Terrain */
const Input = (() => {
  /** Input sample rate (matches server game tick order of magnitude). */
  const INPUT_INTERVAL_MS = 50;
  let lastSend = 0;
  let sendFn      = null;
  let onKey       = null;
  let autopilotBlocked = false;

  const held = {};

  function init(fn, keyFn) {
    sendFn = fn;
    onKey  = keyFn;
    window.addEventListener('keydown', e => {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(e.key)) {
        e.preventDefault();
        held[e.key] = true;
        return;
      }
      e.preventDefault();
      onKey && onKey(e.key);
    });
    window.addEventListener('keyup', e => { delete held[e.key]; });
  }

  /**
   * Tank-style: Up/Down = forward/back along wheelbarrow facing; Left/Right = rotate.
   * Server integrates continuously (any angle).
   */
  function update(now, player, world) {
    if (!sendFn || autopilotBlocked) return;
    if (now - lastSend < INPUT_INTERVAL_MS) return;

    let fwd = 0;
    let turn = 0;
    if (held.ArrowUp) fwd += 1;
    if (held.ArrowDown) fwd -= 1;
    if (held.ArrowLeft) turn += 1;
    if (held.ArrowRight) turn -= 1;
    fwd = Math.max(-1, Math.min(1, fwd));
    turn = Math.max(-1, Math.min(1, turn));

    lastSend = now;
    sendFn({ type: 'move', fwd, turn });
  }

  function setAutopilotBlocked(v) {
    autopilotBlocked = !!v;
  }

  function clearHeldKeys() {
    for (const k of Object.keys(held)) delete held[k];
  }

  /**
   * True while any movement/turn arrow is held — camera locks behind the wheelbarrow.
   * When all released, the player can orbit yaw with the mouse until they drive again.
   */
  function isWheelbarrowControlActive() {
    return !!(
      held.ArrowUp
      || held.ArrowDown
      || held.ArrowLeft
      || held.ArrowRight
    );
  }

  return { init, update, setAutopilotBlocked, clearHeldKeys, isWheelbarrowControlActive };
})();
