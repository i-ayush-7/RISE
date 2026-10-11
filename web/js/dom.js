import { ICONS } from './icons.js';

export const SVG_NS = "http://www.w3.org/2000/svg";

export function h(tag, attrs, ...children) {
  const el = document.createElement(tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'className' || k === 'class') {
        el.className = v;
      } else if (k === 'dataset' && typeof v === 'object' && v !== null) {
        Object.assign(el.dataset, v);
      } else if (k.startsWith('on') && typeof v === 'function') {
        const ev = k.slice(2).toLowerCase();
        el.addEventListener(ev, v);
      } else if (k === 'disabled') {
        el.disabled = Boolean(v);
      } else if (k === 'checked') {
        el.checked = Boolean(v);
      } else if (k === 'value') {
        el.value = v;
      } else if (v !== null && v !== undefined && v !== false) {
        el.setAttribute(k, String(v));
      }
    }
  }

  const flatChildren = children.flat(Infinity);
  for (const c of flatChildren) {
    if (c === null || c === undefined || c === false) continue;
    if (typeof c === 'string' || typeof c === 'number') {
      el.appendChild(document.createTextNode(String(c)));
    } else if (c instanceof Node) {
      el.appendChild(c);
    }
  }
  return el;
}

export function svg(tag, attrs, ...children) {
  const el = document.createElementNS(SVG_NS, tag);
  if (attrs) {
    for (const [k, v] of Object.entries(attrs)) {
      if (k === 'className' || k === 'class') {
        el.setAttribute('class', v);
      } else if (k.startsWith('on') && typeof v === 'function') {
        const ev = k.slice(2).toLowerCase();
        el.addEventListener(ev, v);
      } else if (v !== null && v !== undefined && v !== false) {
        el.setAttribute(k, String(v));
      }
    }
  }
  const flatChildren = children.flat(Infinity);
  for (const c of flatChildren) {
    if (c === null || c === undefined || c === false) continue;
    if (typeof c === 'string' || typeof c === 'number') {
      el.appendChild(document.createTextNode(String(c)));
    } else if (c instanceof Node) {
      el.appendChild(c);
    }
  }
  return el;
}

export function clear(el) {
  while (el.firstChild) {
    el.removeChild(el.firstChild);
  }
}

export function icon(name, extraClass = '') {
  const container = svg('svg', {
    class: ('ic ' + extraClass).trim(),
    viewBox: '0 0 24 24',
    fill: 'none',
    stroke: 'currentColor',
    'stroke-width': '1.8',
    'stroke-linecap': 'round',
    'stroke-linejoin': 'round',
    'aria-hidden': 'true'
  });
  const parts = ICONS[name] || [];
  for (const [childTag, childAttrs] of parts) {
    const child = svg(childTag, childAttrs);
    container.appendChild(child);
  }
  return container;
}
