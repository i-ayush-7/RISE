import { h, svg, clear, icon } from './dom.js';

const IP = [
  [975, 380],
  [1350, 490],
  [930, 640],
  [1235, 590],
  [985, 770]
];

const P = [
  [60, 22],
  [88, 36],
  [66, 58],
  [86, 68],
  [72, 84]
];

function initials(name) {
  if (!name) return '';
  return name.split(/\s+/).map(p => p[0]).join('').slice(0, 2).toUpperCase();
}

function firstName(name) {
  if (!name) return '';
  return name.split(/\s+/)[0];
}

function statusInfo(statusKey) {
  switch (statusKey) {
    case 'safe':
      return { label: 'Safe', iconName: 'okk', className: 'safe' };
    case 'needs_help':
      return { label: 'Needs help', iconName: 'bad', className: 'needs' };
    case 'not_responding':
      return { label: 'Not responding', iconName: 'warn', className: 'noresp' };
    default:
      return { label: 'Pending', iconName: 'more', className: 'pending' };
  }
}

export function buildScene(state) {
  const { plan, alerts, advice, checkin } = state;
  const topAlert = (alerts && alerts.alerts && alerts.alerts[0]) || null;
  const hazard = (topAlert && topAlert.hazard) || '';
  const isFlood = hazard.toLowerCase() === 'flood';
  const isHeat = hazard.toLowerCase() === 'heat';
  const photo = isFlood;

  let h1Text = '';
  let h1Accent = '';
  let h2Text = '';

  const active = Boolean(checkin && checkin.active);

  if (active) {
    const sp = (checkin && checkin.speakable) || '';
    if (checkin.all_accounted_for) {
      h1Text = sp || 'Everyone is confirmed safe.';
      h2Text = '';
    } else {
      const match = sp.match(/^(.*?)([\.\!\?])\s+(.*)$/);
      if (match) {
        h1Text = match[1] + match[2];
        h2Text = match[3];
      } else {
        h1Text = sp || 'Check-in active.';
        h2Text = '';
      }
    }
  } else {
    if (alerts && alerts.ok === false && alerts.error) {
      h1Text = 'Alerts could not be checked.';
      h2Text = 'Do not assume there are none.';
    } else if (alerts && alerts.ok && (!alerts.alerts || alerts.alerts.length === 0)) {
      h1Text = 'No active alerts.';
      h2Text = (advice && advice.headline) || 'All quiet in your area.';
    } else {
      h1Text = 'No check-in ';
      h1Accent = 'running.';
      h2Text = (advice && advice.headline) || (topAlert && topAlert.headline) || '';
    }
  }

  const container = h('div', { className: 'scene' + (photo ? ' ph' : '') });

  if (photo) {
    const img = h('img', {
      className: 'sc',
      src: '/assets/house-rain.jpg',
      alt: ''
    });
    container.appendChild(img);
  } else {
    const skyColors = isHeat ? ['#2b1a33', '#8a4630'] : (isFlood ? ['#0a1430', '#1c3359'] : ['#0b1630', '#18305a']);
    const svgEl = svg('svg', {
      className: 'sc',
      viewBox: '0 0 640 280',
      preserveAspectRatio: 'xMaxYMid slice',
      'aria-hidden': 'true'
    });

    const defs = svg('defs');
    const grad = svg('linearGradient', { id: 'sk', x1: '0', y1: '0', x2: '0', y2: '1' },
      svg('stop', { offset: '0', 'stop-color': skyColors[0] }),
      svg('stop', { offset: '1', 'stop-color': skyColors[1] })
    );
    defs.appendChild(grad);

    const radGrad = (id, color, opacity) => svg('radialGradient', { id },
      svg('stop', { offset: '0', 'stop-color': color, 'stop-opacity': String(opacity) }),
      svg('stop', { offset: '1', 'stop-color': color, 'stop-opacity': '0' })
    );

    defs.appendChild(radGrad('sun', '#ffb066', 0.7));
    defs.appendChild(radGrad('moon', '#bcd4ff', 0.45));
    defs.appendChild(radGrad('warm', '#ffc766', 0.35));
    svgEl.appendChild(defs);

    svgEl.appendChild(svg('rect', { width: '640', height: '280', fill: 'url(#sk)' }));

    if (isHeat) {
      svgEl.appendChild(svg('circle', { cx: '540', cy: '64', r: '90', fill: 'url(#sun)' }));
      svgEl.appendChild(svg('circle', { cx: '540', cy: '64', r: '20', fill: '#ffd9a0' }));
    } else {
      svgEl.appendChild(svg('circle', { cx: '560', cy: '52', r: '46', fill: 'url(#moon)' }));
      svgEl.appendChild(svg('circle', { cx: '560', cy: '52', r: '16', fill: '#dce8ff' }));
    }

    svgEl.appendChild(svg('path', { d: 'M0 236q320-22 640 4v40H0z', fill: '#09101f' }));
    svgEl.appendChild(svg('circle', { cx: '380', cy: '214', r: '34', fill: '#0d2233' }));
    svgEl.appendChild(svg('circle', { cx: '620', cy: '208', r: '28', fill: '#0d2233' }));
    svgEl.appendChild(svg('ellipse', { cx: '495', cy: '205', rx: '130', ry: '60', fill: 'url(#warm)' }));
    svgEl.appendChild(svg('rect', { x: '410', y: '150', width: '170', height: '90', fill: '#15203a' }));
    svgEl.appendChild(svg('rect', { x: '440', y: '108', width: '110', height: '46', fill: '#1a2744' }));
    svgEl.appendChild(svg('polygon', { points: '398,152 495,106 592,152', fill: '#0d1730' }));
    svgEl.appendChild(svg('polygon', { points: '430,110 495,80 560,110', fill: '#0d1730' }));

    const winGroup = svg('g', { fill: '#ffd27a' },
      svg('rect', { x: '424', y: '172', width: '26', height: '30' }),
      svg('rect', { x: '462', y: '172', width: '26', height: '30' }),
      svg('rect', { x: '500', y: '172', width: '26', height: '30' }),
      svg('rect', { x: '466', y: '122', width: '22', height: '22' }),
      svg('rect', { x: '502', y: '122', width: '22', height: '22' })
    );
    svgEl.appendChild(winGroup);
    svgEl.appendChild(svg('rect', { x: '540', y: '196', width: '26', height: '44', fill: '#0a1124' }));

    if (isFlood) {
      svgEl.appendChild(svg('path', { d: 'M0 250q80-9 160 0t160 0 160 0 160 0v30H0z', fill: '#2f6bb5', 'fill-opacity': '.5' }));
      for (let i = 0; i < 46; i++) {
        const rx = (i * 47) % 660;
        const ry = (i * 61) % 230;
        svgEl.appendChild(svg('line', {
          x1: String(rx),
          y1: String(ry),
          x2: String(rx - 9),
          y2: String(ry + 24),
          stroke: '#a9c8ff',
          'stroke-opacity': '.35',
          'stroke-width': '1.3'
        }));
      }
    }
    container.appendChild(svgEl);
  }

  const scrim = h('div', { className: 'scrim' });
  container.appendChild(scrim);

  const sct = h('div', { className: 'sct' });
  const planTitle = (plan && plan.name) || 'The Rivera Family';
  sct.appendChild(h('p', { className: 'kick' }, planTitle + ' (fictional)'));

  const h1 = h('h1');
  if (h1Accent) {
    h1.appendChild(document.createTextNode(h1Text));
    h1.appendChild(h('span', { className: 'ac' }, h1Accent));
  } else {
    h1.appendChild(document.createTextNode(h1Text));
  }
  sct.appendChild(h1);

  if (h2Text) {
    sct.appendChild(h('p', {}, h2Text));
  }
  container.appendChild(sct);

  const members = (plan && plan.members) || [];
  const memberStatuses = {};
  if (active && checkin && Array.isArray(checkin.members)) {
    for (const cm of checkin.members) {
      const nameKey = (cm.member_name || cm.name || '').toLowerCase();
      memberStatuses[nameKey] = cm.status || 'pending';
    }
  }

  members.forEach((m, idx) => {
    const mName = m.name || '';
    const stKey = active ? (memberStatuses[mName.toLowerCase()] || 'pending') : '';
    const stObj = statusInfo(stKey);

    const pin = h('div', { className: 'pin' });
    if (photo) {
      if (idx < IP.length) {
        pin.dataset.ix = String(IP[idx][0]);
        pin.dataset.iy = String(IP[idx][1]);
      } else {
        const extraIdx = idx - IP.length;
        const gx = 750 + (extraIdx % 4) * 160;
        const gy = 800 + Math.floor(extraIdx / 4) * 60;
        pin.dataset.ix = String(gx);
        pin.dataset.iy = String(gy);
      }
    } else {
      if (idx < P.length) {
        pin.style.left = P[idx][0] + '%';
        pin.style.top = P[idx][1] + '%';
      } else {
        const extraIdx = idx - P.length;
        pin.style.left = (20 + (extraIdx % 4) * 20) + '%';
        pin.style.top = (82 + Math.floor(extraIdx / 4) * 8) + '%';
      }
    }

    const paClass = 'pa' + (active && stKey ? ' ' + stObj.className : '');
    const pa = h('span', { className: paClass }, initials(mName));
    pin.appendChild(pa);

    const label = h('span');
    label.appendChild(document.createTextNode(firstName(mName)));
    if (active && stKey) {
      label.appendChild(document.createTextNode(' '));
      const stSpan = h('span', { className: 'st ' + stObj.className }, stObj.label);
      label.appendChild(stSpan);
    }
    pin.appendChild(label);
    container.appendChild(pin);
  });

  return container;
}

export function updatePinPositions(root) {
  const sc = (root || document).querySelector('.scene.ph');
  if (!sc) return;
  const W = sc.clientWidth;
  const H = sc.clientHeight;
  if (!W || !H) return;
  const k = Math.max(W / 1672, H / 896);
  const ox = (W - 1672 * k) * 0.7;
  const oy = (H - 896 * k) * 0.45;
  const pins = sc.querySelectorAll('.pin[data-ix]');
  for (const p of pins) {
    const ix = Number(p.dataset.ix);
    const iy = Number(p.dataset.iy);
    p.style.left = (ox + ix * k) + 'px';
    p.style.top = (oy + iy * k) + 'px';
  }
}
