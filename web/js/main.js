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

  const connStatus = h('div', { className: 'conn-status' });
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
  const errorTitle = h('h2', {}, 'Connection lost');
  errorScreen.appendChild(errorTitle);
  const errorMsg = h('p', { className: 'muted' },
    'Could not reach the R.I.S.E. backend service. Make sure the server is running:');
  errorScreen.appendChild(errorMsg);
  const errorCode = h('code', { style: 'display: inline-block; padding: 10px 16px; margin: 12px 0;' },
    'python -m bff');
  errorScreen.appendChild(errorCode);
  errorScreen.appendChild(h('br'));
  const retryBtn = h('button', {
    type: 'button',
    className: 'btn pri',
    style: 'margin-top: 14px;',
    onClick: () => initialFetch()
  }, 'Retry connection');
  errorScreen.appendChild(retryBtn);
  contentCol.appendChild(errorScreen);

  function showConnectionLost() {
    store.set({ status: { ...(store.get().status || {}), server: 'down' } });
    errorTitle.textContent = 'Connection lost';
    errorMsg.textContent = 'Could not reach the R.I.S.E. backend service. Make sure the server is running:';
    errorCode.textContent = 'python -m bff';
    errorCode.style.display = 'inline-block';
    retryBtn.textContent = 'Retry connection';
    errorScreen.classList.remove('hidden');
    main.classList.add('hidden');
  }

  function showServerDown() {
    store.set({ status: { ...(store.get().status || {}), server: 'down' } });
    errorTitle.textContent = 'MCP server unavailable';
    errorMsg.textContent = 'The BFF is running but its MCP server is not answering.';
    errorCode.textContent = 'python -m bff';
    errorCode.style.display = 'none';
    retryBtn.textContent = 'Retry connection';
    errorScreen.classList.remove('hidden');
    main.classList.add('hidden');
  }

  function clearError() {
    errorScreen.classList.add('hidden');
    main.classList.remove('hidden');
  }

  let currentViewName = null;
  let activeViewInstance = null;
  let lastAnnouncedMsg = '';

  function renderApp(state) {
    // Update Header badges and connection
    const mode = (state.alerts && state.alerts.data_mode ? state.alerts.data_mode.toUpperCase() : 'SIMULATED');
    modeBadge.textContent = mode;

    const isUp = Boolean(state.status && state.status.server === 'up');
    if (isUp) {
      connDot.classList.remove('down');
      connText.textContent = 'Connected';
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

  // Polling timers: one chain per poll type
  let activityTimer = null;
  let statusTimer = null;
  let checkinTimer = null;

  function cancelTimers() {
    if (activityTimer) { clearTimeout(activityTimer); activityTimer = null; }
    if (statusTimer) { clearTimeout(statusTimer); statusTimer = null; }
    if (checkinTimer) { clearTimeout(checkinTimer); checkinTimer = null; }
  }

  function scheduleActivity(ms = 2000) {
    if (activityTimer) clearTimeout(activityTimer);
    activityTimer = setTimeout(pollActivity, ms);
  }

  function scheduleStatus(ms = 10000) {
    if (statusTimer) clearTimeout(statusTimer);
    statusTimer = setTimeout(pollStatus, ms);
  }

  function scheduleCheckin(ms = 5000) {
    if (checkinTimer) clearTimeout(checkinTimer);
    checkinTimer = setTimeout(pollCheckin, ms);
  }

  async function initialFetch() {
    cancelTimers();
    const stat = await getStatus();
    const isReachable = Boolean(stat && !stat.network && stat.server);
    if (!isReachable) {
      showConnectionLost();
      return;
    }
    if (stat.server === 'down') {
      showServerDown();
      return;
    }

    clearError();

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
      plan: p.ok ? p.result : { ok: false, error: p.error || 'Failed to load household plan.' },
      alerts: a.ok ? a.result : { ok: false, error: a.error || 'Failed to load active alerts.', alerts: [] },
      advice: ad.ok ? ad.result : { ok: false, error: ad.error || 'Failed to load safety advice.' },
      checkin: c.ok && typeof c.result === 'object' ? { ...c.result, active: true } : { active: false, error: c.error && !c.error.includes('No check-in is active') ? c.error : undefined },
      activity: act.ok && Array.isArray(act.entries) ? act.entries : []
    });

    scheduleActivity(2000);
    scheduleStatus(10000);
    scheduleCheckin(5000);
  }

  async function pollActivity() {
    if (document.hidden) return;
    try {
      const act = await getActivity(0);
      if (act && act.ok && Array.isArray(act.entries)) {
        store.set({ activity: act.entries });
      }
    } catch (e) {}
    scheduleActivity(2000);
  }

  async function pollStatus() {
    if (document.hidden) return;
    try {
      const stat = await getStatus();
      if (stat && !stat.network && stat.server === 'up') {
        store.set({
          scenario: stat.scenario || store.get().scenario,
          status: { ...store.get().status, ...stat, server: 'up' }
        });
      } else if (stat && !stat.network && stat.server === 'down') {
        store.set({ status: { ...store.get().status, server: 'down' } });
      } else {
        store.set({ status: { ...store.get().status, server: 'down' } });
      }
    } catch (e) {
      store.set({ status: { ...store.get().status, server: 'down' } });
    }
    scheduleStatus(10000);
  }

  async function pollCheckin() {
    if (document.hidden) return;
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
    scheduleCheckin(5000);
  }

  initialFetch();

  document.addEventListener('visibilitychange', () => {
    if (!document.hidden) {
      initialFetch();
    }
  });

  window.addEventListener('focus', () => {
    if (!store.get().status || store.get().status.server !== 'up') {
      initialFetch();
    }
  });
}

if (document.readyState === 'loading') {
  document.addEventListener('DOMContentLoaded', init);
} else {
  init();
}
