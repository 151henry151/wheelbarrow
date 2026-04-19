/* global Renderer, Terrain */
const Input = (() => {
  let sendFn      = null;
  let onKey       = null;
  let autopilotBlocked = false;
  /** Last sampled fwd (–1..1) for edge detect — snap facing when starting drive from rest. */
  let lastFwdSample = 0;
  /**
   * Last JSON.stringify({fwd, turn}) sent. Server integrates from stored _input_fwd/_input_turn
   * each tick, so ~30×/s redundant move frames flood the WebSocket and starve tick delivery.
   * Send when fwd/turn changes; optional face_angle on one packet does not affect this key.
   */
  let lastSentMoveSig = JSON.stringify({ fwd: 0, turn: 0 });
  let lastMoveSendTime = 0;
  /** While keys are held, re-send so a single dropped WebSocket message cannot zero input forever. */
  const MOVE_RESEND_MS = 33;
  /** Cap steady-state move sends (~20/s) so the server is not fed 60/s identical frames. */
  const MOVE_HOLD_MIN_MS = 50;

  const held = {};

  /** Physical WASD → keys used in `held` (works when layout/char key differs, e.g. AZERTY). */
  function _codeToWasd(code) {
    if (code === 'KeyW') return 'w';
    if (code === 'KeyA') return 'a';
    if (code === 'KeyS') return 's';
    if (code === 'KeyD') return 'd';
    return null;
  }

  /** Movement: arrows or WASD (by character or physical key code). */
  function _isMoveKey(key, code) {
    if (['ArrowUp', 'ArrowDown', 'ArrowLeft', 'ArrowRight'].includes(key)) return true;
    if (_codeToWasd(code)) return true;
    const k = key.length === 1 ? key.toLowerCase() : '';
    return k === 'w' || k === 'a' || k === 's' || k === 'd';
  }

  function init(fn, keyFn) {
    sendFn = fn;
    onKey  = keyFn;
    window.addEventListener('blur', () => {
      clearHeldKeys();
      if (sendFn) {
        const z = { type: 'move', fwd: 0, turn: 0 };
        sendFn(z);
        lastSentMoveSig = _moveSig(z);
      }
    });
    window.addEventListener('keydown', e => {
      if (e.ctrlKey || e.altKey || e.metaKey) return;
      if (_isMoveKey(e.key, e.code)) {
        e.preventDefault();
        if (e.key.startsWith('Arrow')) held[e.key] = true;
        else {
          const w = _codeToWasd(e.code);
          if (w) held[w] = true;
          else held[e.key.toLowerCase()] = true;
        }
        return;
      }
      e.preventDefault();
      onKey && onKey(e.key);
    });
    window.addEventListener('keyup', e => {
      if (_isMoveKey(e.key, e.code)) {
        if (e.key.startsWith('Arrow')) delete held[e.key];
        else {
          const w = _codeToWasd(e.code);
          if (w) delete held[w];
          else delete held[e.key.toLowerCase()];
        }
      } else delete held[e.key];
    });
  }

  /** Server integrates from last _input_fwd/_input_turn; compare only fwd+turn for dedupe. */
  function _moveSig(msg) {
    return JSON.stringify({ fwd: msg.fwd, turn: msg.turn });
  }

  /**
   * Up/Down = forward/back; Left/Right = turn. Starting fwd/back from rest (no turn) snaps facing
   * to the orbit camera via face_angle, then drives — so you can point the view and drive into it.
   */
  function update(now, player, world) {
    if (!sendFn || autopilotBlocked) return;

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
    const wasAtRest = lastFwdSample === 0;
    if (
      fwd !== 0
      && wasAtRest
      && turn === 0
      && typeof Renderer !== 'undefined'
      && typeof Renderer.getCameraFacingAngle === 'function'
    ) {
      const a = Renderer.getCameraFacingAngle();
      if (Number.isFinite(a)) msg.face_angle = a;
    }
    lastFwdSample = fwd;

    const t = (typeof now === 'number' && Number.isFinite(now)) ? now : performance.now();
    const sig = _moveSig(msg);
    const moving = fwd !== 0 || turn !== 0;
    const sigChanged = sig !== lastSentMoveSig;
    if (moving) {
      if (!sigChanged && t - lastMoveSendTime < MOVE_HOLD_MIN_MS) return;
    } else {
      const resendDue = t - lastMoveSendTime >= MOVE_RESEND_MS;
      if (sig === lastSentMoveSig && !resendDue) return;
    }
    lastSentMoveSig = sig;
    lastMoveSendTime = t;
    sendFn(msg);
    // Starting drive from rest: duplicate-send so a lone lost packet cannot leave _input_fwd at 0
    // while the optimistic client angle (game.js) still rotates the barrow.
    if (wasAtRest && fwd !== 0) {
      const dup = { ...msg };
      queueMicrotask(() => {
        if (sendFn) sendFn(dup);
      });
    }
  }

  function setAutopilotBlocked(v) {
    autopilotBlocked = !!v;
  }

  function clearHeldKeys() {
    for (const k of Object.keys(held)) delete held[k];
    lastFwdSample = 0;
    lastSentMoveSig = JSON.stringify({ fwd: 0, turn: 0 });
    lastMoveSendTime = 0;
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

  /** True while steering keys held — camera snaps to barrow heading instead of lerping (see renderer). */
  function isTurnKeyHeld() {
    return !!(
      held.ArrowLeft
      || held.ArrowRight
      || held.a
      || held.d
    );
  }

  return { init, update, setAutopilotBlocked, clearHeldKeys, isWheelbarrowControlActive, isTurnKeyHeld };
})();
