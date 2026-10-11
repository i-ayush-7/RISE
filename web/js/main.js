import { h, clear, icon } from './dom.js';
import { store } from './store.js';
import { getStatus, tool, getActivity } from './api.js';

import * as homeView from './views/home.js';
import * as boardView from './views/board.js';
import * as alertsView from './views/alerts.js';
import * as planView from './views/plan.js';
import * as logView from './views/log.js';
import * as moreView from './views/more.js';

const VIEWS = {
  home: homeView,
  board: boardView,
  alerts: alertsView,
  plan: planView,
  log: logView,
  more: moreView
};

const NAV_ITEMS = [
  { key: 'home', label: 'Chat', icon: 'home' },
  { key: 'board', label: 'Board', icon: 'board' },
  { key: 'alerts', label: 'Alerts', icon: 'alerts' },
  { key: 'plan', label: 'Plan', icon: 'plan' },
  { key: 'log', label: 'Log', icon: 'log' },
  { key: 'more', label: 'More', icon: 'more' }
];

function init() {
  const appRoot = document.getElementById('app');
  if (!appRoot) return;
  clear(appRoot);

  if (store.get().prefs.largeText) {
    document.body.classList.add('big');
  }

  // Skip link
  const skipLink = h('a', {
    href: '#main',
    className: 'skip-link'
  }, 'Skip to main content');
  appRoot.appendChild(skipLink);

  // Shell Layout
  const appLayout = h('div', { className: 'app' });

  // Nav
  const nav = h('nav', { 'aria-label': 'Main navigation' });
  const colBtn = h('button', {
    type: 'button',
    id: 'col',
    className: 'cb',
    'aria-label': 'Collapse or expand menu',
    onClick: () => appLayout.classList.toggle('mini')
  }, icon('arr'));
  nav.appendChild(colBtn);

  const navButtons = {};
  NAV_ITEMS.forEach(item => {
    const btn = h('button', {
      type: 'button',
      onClick: () => store.set({ view: item.key })
    }, icon(item.icon), h('span', {}, item.label));
    navButtons[item.key] = btn;
    nav.appendChild(btn);
  });
  appLayout.appendChild(nav);

  // Content Column (Header + Main)
  const contentCol = h('div', { style: 'display: flex; flex-direction: column; min-height: 0; height: 100%;' });

  // Header
  const header = h('header', { className: 'top' });
  const logo = h('div', { className: 'logo' });
  logo.appendChild(icon('home2'));
  logo.appendChild(h('span', {}, 'R.I.S.E.'));
  header.appendChild(logo);

  const simBadge = h('span', { className: 'badge' },
    'SIMULATED Alexa+ experience, not affiliated with Amazon');
  header.appendChild(simBadge);

  const modeBadge = h('span', { className: 'badge sim', id: 'mode-badge' }, 'SIMULATED');
  header.appendChild(modeBadge);

  header.appendChild(h('div', { className: 'sp' }));

  const connStatus = h('div', { style: 'display: flex; align-items: center;' });
  const connDot = h('span', { className: 'dot' });
  const connText = h('span', { className: 'note muted' }, 'Connected');
  connStatus.appendChild(connDot);
  connStatus.appendChild(connText);
  header.appendChild(connStatus);

  contentCol.appendChild(header);

  // Main area
  const main = h('main', {
    id: 'main',
    tabindex: '-1',
    className: 'stage'
  });
  contentCol.appendChild(main);

  appLayout.appendChild(contentCol);
  appRoot.appendChild(appLayout);

  // Live announcer for accessibility
  const liveAnnouncer = h('div', {
    className: 'visually-hidden',
    'aria-live': 'polite',
    'aria-atomic': 'true'
  });
  appRoot.appendChild(liveAnnouncer);

  // Offline / Connection Error overlay
  const errorScreen = h('div', {
    className: 'card hidden',
    style: 'margin: 40px auto; max-width: 520px; text-align: center;'
  });
  errorScreen.appendChild(h('h2', {}, 'Connection lost'));
  errorScreen.appendChild(h('p', { className: 'muted' },
    'Could not reach the R.I.S.E. backend service. Make sure the server is running:'));
  errorScreen.appendChild(h('code', { style: 'display: inline-block; padding: 10px 16px; margin: 12px 0;' },
    'python -m bff'));
  errorScreen.appendChild(h('br'));
  const retryBtn = h('button', {
    type: 'button',
    className: 'btn pri',
    style: 'margin-top: 14px;',
    onClick: () => initialFetch()
  }, 'Retry connection');
  errorScreen.appendChild(retryBtn);
  contentCol.appendChild(errorScreen);

  let currentViewName = null;
  let activeViewInstance = null;
  let lastAnnouncedMsg = '';

  function renderApp(state) {
    // Update Header badges and connection
    const mode = (state.alerts && state.alerts.data_mode ? state.alerts.data_mode.toUpperCase() : 'SIMULATED');
    modeBadge.textContent = mode;

    const isUp = state.status && state.status.server === 'up';
    if (isUp) {
      connDot.classList.remove('down');
      connText.textContent = 'Connected';
      errorScreen.classList.add('hidden');
      main.classList.remove('hidden');
    } else {
      connDot.classList.add('down');
      connText.textContent = 'Offline';
    }

    // Update Nav active states
    for (const [key, btn] of Object.entries(navButtons)) {
      if (key === state.view) {
        btn.setAttribute('aria-current', 'page');
      } else {
        btn.removeAttribute('aria-current');
      }
    }

    // Announce newest assistant message
    const msgs = state.messages || [];
    if (msgs.length) {
      const last = msgs[msgs.length - 1];
      if (last.role === 'assistant' && last.text !== lastAnnouncedMsg) {
        lastAnnouncedMsg = last.text;
        liveAnnouncer.textContent = 'Assistant: ' + last.text;
      }
    }

    // Switch view if needed
    if (currentViewName !== state.view) {
      if (activeViewInstance && typeof activeViewInstance.destroy === 'function') {
        activeViewInstance.destroy();
      }
      currentViewName = state.view;
      const viewModule = VIEWS[currentViewName] || VIEWS.home;
      activeViewInstance = viewModule.mount(main, store);
      activeViewInstance.update(state);

      const hHeading = main.querySelector('h1, h2');
      if (hHeading) {
        hHeading.setAttribute('tabindex', '-1');
        hHeading.focus();
      } else {
        main.focus();
      }
    } else if (activeViewInstance) {
      activeViewInstance.update(state);
    }
  }

  store.subscribe((state) => renderApp(state));

  async function initialFetch() {
    const stat = await getStatus();
    if (!stat.ok) {
      store.set({ status: { server: 'down' } });
      errorScreen.classList.remove('hidden');
      main.classList.add('hidden');
      return;
    }

    errorScreen.classList.add('hidden');
    main.classList.remove('hidden');

    const [p, a, ad, c, act] = await Promise.all([
      tool('get_household_plan', {}),
      tool('get_active_alerts', {}),
      tool('get_safety_advice', {}),
      tool('get_checkin_status', {}),
      getActivity(0)
    ]);

    store.set({
      scenario: stat.scenario || 'flood',
      status: { ...stat, server: 'up' },
      plan: p.ok ? p.result : null,
      alerts: a.ok ? a.result : { ok: false, error: a.error, alerts: [] },
      advice: ad.ok ? ad.result : { ok: false, error: ad.error },
      checkin: c.ok && typeof c.result === 'object' ? { ...c.result, active: true } : { active: false },
      activity: act.ok && Array.isArray(act.entries) ? act.entries : []
    });
  }

  initialFetch();

  // Polling loops
  let isPolling = true;

  async function pollActivity() {
    if (!isPolling || document.hidden) return;
    try {
      const act = await getActivity(0);
      if (act.ok && Array.isArray(act.entries)) {
        store.set({ activity: act.entries });
      }
    } catch (e) {}
    if (isPolling) setTimeout(pollActivity, 2000);
  }

  async function pollStatus() {
    if (!isPolling || document.hidden) return;
    try {
      const stat = await getStatus();
      if (stat.ok) {
        store.set({
          scenario: stat.scenario || store.get().scenario,
          status: { ...store.get().status, ...stat, server: 'up' }
        });
      } else {
        store.set({ status: { ...store.get().status, server: 'down' } });
      }
    } catch (e) {
      store.set({ status: { ...store.get().status, server: 'down' } });
    }
    if (isPolling) setTimeout(pollStatus, 10000);
  }

  async function pollCheckin() {
    if (!isPolling || document.hidden) return;
    const s = store.get();
    if (s.checkin.active || s.view === 'board') {
      try {
        const c = await tool('get_checkin_status', {});
        if (c.ok && typeof c.result === 'object') {
          store.set({ checkin: { ...c.result, active: true } });
        } else if (c.error && c.error.includes('No check-in is active')) {
          store.set({ checkin: { active: false } });
        }
      } catch (e) {}
    }
    if (isPolling) setTimeout(pollCheckin, 5000);
  }

  setTimeout(pollActivity, 2000);
  setTimeout(pollStatus, 10000);
  setTimeout(pollCheckin, 5000);

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      initialFetch();
      setTimeout(pollActivity, 1000);
      setTimeout(pollStatus, 2000);
      setTimeout(pollCheckin, 1000);
    }
  });

  window.addEventListener('focus', () => {
    initialFetch();
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
