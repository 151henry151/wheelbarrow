const WS = (() => {
  let socket = null;
  const handlers = {};
  let onDisconnect = null;

  function connect(token, onOpen, onDisconnect_) {
    const proto = location.protocol === 'https:' ? 'wss' : 'ws';
    const base  = location.pathname.replace(/\/[^/]*$/, '');
    socket = new WebSocket(`${proto}://${location.host}${base}/ws?token=${token}`);
    onDisconnect = typeof onDisconnect_ === 'function' ? onDisconnect_ : null;

    socket.addEventListener('open', () => onOpen && onOpen());
    socket.addEventListener('message', e => {
      // Process synchronously so we drain frames promptly; deferring with queueMicrotask
      // backlog microtasks and delayed processing, which made server tick sends time out.
      let msg;
      try {
        msg = JSON.parse(e.data);
      } catch (err) {
        console.warn('Wheelbarrow: invalid WS JSON', err);
        return;
      }
      const fn = handlers[msg.type];
      if (!fn) return;
      try {
        fn(msg);
      } catch (err2) {
        console.error('Wheelbarrow: WS handler error', msg.type, err2);
      }
    });
    socket.addEventListener('close', () => {
      console.warn('WS disconnected');
      if (onDisconnect) {
        try {
          onDisconnect();
        } catch (e) {
          console.warn('onDisconnect failed', e);
        }
        onDisconnect = null;
      }
      const bar = document.getElementById('notice-bar');
      if (bar) {
        bar.textContent = 'Disconnected from server — refresh the page to reconnect.';
        bar.style.display = 'block';
        bar.style.opacity = '1';
      }
    });
  }

  function on(type, fn) { handlers[type] = fn; }

  function send(obj) {
    if (!socket) return;
    if (socket.readyState !== WebSocket.OPEN) {
      console.warn('Wheelbarrow: WS.send skipped (readyState=', socket.readyState, ')');
      return;
    }
    socket.send(JSON.stringify(obj));
  }

  return { connect, on, send };
})();
