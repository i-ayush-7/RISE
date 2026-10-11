import { h, clear } from '../dom.js';

export function mount(container, store) {
  clear(container);

  const card = h('div', { className: 'card' });
  card.appendChild(h('h2', {}, 'MCP activity log'));

  const protoLine = h('p', { className: 'muted note', style: 'margin-top: 0;' });
  card.appendChild(protoLine);

  const list = h('ul', { className: 'log', style: 'max-height: none;' });
  card.appendChild(list);

  container.appendChild(card);

  function render(state) {
    const proto = (state.status && state.status.protocol_version) || 'unknown';
    protoLine.textContent = `Connected to MCP server (protocol version: ${proto}). Full log, newest first.`;

    clear(list);
    const entries = state.activity || [];
    if (!entries.length) {
      list.appendChild(h('li', { className: 'muted' }, 'No log entries recorded yet.'));
      return;
    }

    entries.forEach(entry => {
      const isOk = Boolean(entry.ok);
      const li = h('li', { className: isOk ? '' : 'err' });

      const lh = h('div', { className: 'lh' });
      const timeStr = entry.time ? new Date(entry.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
      lh.appendChild(h('span', { className: 'tt' }, timeStr));
      lh.appendChild(h('b', {}, entry.tool || entry.name || 'tool'));
      lh.appendChild(h('span', { className: 'muted note' }, `${entry.ms || 0} ms`));
      lh.appendChild(h('span', { className: 'okb' + (isOk ? '' : ' bad') }, isOk ? 'Success' : 'Error'));
      li.appendChild(lh);

      const argsStr = typeof entry.arguments === 'string'
        ? entry.arguments
        : JSON.stringify(entry.arguments || entry.args || {}, null, 2);
      const code = h('code', {}, argsStr);
      li.appendChild(code);

      if (entry.result !== undefined || entry.response !== undefined) {
        const details = h('details', { style: 'margin-top: 6px;' });
        details.appendChild(h('summary', { className: 'muted note', style: 'cursor: pointer;' }, 'Result payload'));
        const resVal = entry.result !== undefined ? entry.result : entry.response;
        const resStr = typeof resVal === 'string' ? resVal : JSON.stringify(resVal, null, 2);
        const pre = h('pre', { className: 'draft', style: 'margin-top: 6px; font-size: 0.8rem;' });
        pre.textContent = resStr;
        details.appendChild(pre);
        li.appendChild(details);
      }

      list.appendChild(li);
    });
  }

  return {
    update(state) {
      render(state);
    },
    destroy() {}
  };
}
