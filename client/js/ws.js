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
      const msg = JSON.parse(e.data);
      const fn = handlers[msg.type];
      if (fn) fn(msg);
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
    if (socket && socket.readyState === WebSocket.OPEN)
      socket.send(JSON.stringify(obj));
  }

  return { connect, on, send };
})();
