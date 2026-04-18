/* global Renderer, Terrain */
const Input = (() => {
  /** Input sample rate (matches server game tick order of magnitude). */
  const INPUT_INTERVAL_MS = 33;
  let lastSend = 0;
  let sendFn      = null;
  let onKey       = null;
  let autopilotBlocked = false;
  /** Last sampled fwd (–1..1) for edge detect — snap facing when starting drive from rest. */
  let lastFwdSample = 0;

  const held = {};

  /** Movement: arrows or WASD (lowercase keys in `held`). */
  function _isMoveKey(key) {
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) return true;
    const k = key.length === 1 ? key.toLowerCase() : '';
    return k === 'w' || k === 'a' || k === 's' || k === 'd';
  }

  function init(fn, keyFn) {
    sendFn = fn;
    onKey  = keyFn;
    window.addEventListener('keydown', e => {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (_isMoveKey(e.key)) {
        e.preventDefault();
        if (e.key.startsWith('Arrow')) held[e.key] = true;
        else held[e.key.toLowerCase()] = true;
        return;
      }
      e.preventDefault();
      onKey && onKey(e.key);
    });
    window.addEventListener('keyup', e => {
      if (_isMoveKey(e.key)) {
        if (e.key.startsWith('Arrow')) delete held[e.key];
        else delete held[e.key.toLowerCase()];
      } else delete held[e.key];
    });
  }

  /**
   * Up/Down = forward/back; Left/Right = turn. Starting fwd/back from rest (no turn) snaps facing
   * to the orbit camera via face_angle, then drives — so you can point the view and drive into it.
   */
  function update(now, player, world) {
    if (!sendFn || autopilotBlocked) return;
    if (now - lastSend < INPUT_INTERVAL_MS) return;

    let fwd = 0;
    let turn = 0;
    if (held.ArrowUp || held.w) fwd += 1;
    if (held.ArrowDown || held.s) fwd -= 1;
    // Positive server turn increases angle (clockwise in x-right, y-down space); screen “left” is CCW.
    if (held.ArrowLeft || held.a) turn -= 1;
    if (held.ArrowRight || held.d) turn += 1;
    fwd = Math.max(-1, Math.min(1, fwd));
    turn = Math.max(-1, Math.min(1, turn));

    const msg = { type: 'move', fwd, turn };
    // From a full stop, align barrow to orbit camera before driving (not tank-facing).
    if (
      fwd !== 0
      && lastFwdSample === 0
      && turn === 0
      && typeof Renderer !== 'undefined'
      && typeof Renderer.getCameraFacingAngle === 'function'
    ) {
      const a = Renderer.getCameraFacingAngle();
      if (Number.isFinite(a)) msg.face_angle = a;
    }
    lastFwdSample = fwd;

    lastSend = now;
    sendFn(msg);
  }

  function setAutopilotBlocked(v) {
    autopilotBlocked = !!v;
  }

  function clearHeldKeys() {
    for (const k of Object.keys(held)) delete held[k];
    lastFwdSample = 0;
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
      || held.w
      || held.s
      || held.a
      || held.d
    );
  }

  return { init, update, setAutopilotBlocked, clearHeldKeys, isWheelbarrowControlActive };
})();
