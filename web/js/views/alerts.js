import { h, clear, icon } from '../dom.js';

export function mount(container, store) {
  clear(container);

  let currentTab = 'alerts';

  const heading = h('h2', {}, 'Alerts and advice');
  container.appendChild(heading);

  const tablist = h('div', {
    className: 'tabs',
    role: 'tablist',
    'aria-label': 'Alert sections'
  });

  const tabAlerts = h('button', {
    type: 'button',
    id: 'tab-alerts',
    role: 'tab',
    'aria-selected': 'true',
    'aria-controls': 'panel-alerts',
    tabindex: '0',
    onClick: () => selectTab('alerts')
  }, 'Active alerts');

  const tabAdvice = h('button', {
    type: 'button',
    id: 'tab-advice',
    role: 'tab',
    'aria-selected': 'false',
    'aria-controls': 'panel-advice',
    tabindex: '-1',
    onClick: () => selectTab('advice')
  }, 'Safety advice');

  tablist.appendChild(tabAlerts);
  tablist.appendChild(tabAdvice);
  container.appendChild(tablist);

  tablist.addEventListener('keydown', (e) => {
    if (e.key === 'ArrowRight' || e.key === 'ArrowLeft') {
      e.preventDefault();
      if (currentTab === 'alerts') {
        selectTab('advice');
        tabAdvice.focus();
      } else {
        selectTab('alerts');
        tabAlerts.focus();
      }
    }
  });

  const panelAlerts = h('div', {
    id: 'panel-alerts',
    role: 'tabpanel',
    'aria-labelledby': 'tab-alerts'
  });

  const panelAdvice = h('div', {
    id: 'panel-advice',
    role: 'tabpanel',
    'aria-labelledby': 'tab-advice',
    className: 'hidden'
  });

  container.appendChild(panelAlerts);
  container.appendChild(panelAdvice);

  function selectTab(tabKey) {
    currentTab = tabKey;
    if (tabKey === 'alerts') {
      tabAlerts.setAttribute('aria-selected', 'true');
      tabAlerts.setAttribute('tabindex', '0');
      tabAdvice.setAttribute('aria-selected', 'false');
      tabAdvice.setAttribute('tabindex', '-1');
      panelAlerts.classList.remove('hidden');
      panelAdvice.classList.add('hidden');
    } else {
      tabAdvice.setAttribute('aria-selected', 'true');
      tabAdvice.setAttribute('tabindex', '0');
      tabAlerts.setAttribute('aria-selected', 'false');
      tabAlerts.setAttribute('tabindex', '-1');
      panelAdvice.classList.remove('hidden');
      panelAlerts.classList.add('hidden');
    }
  }

  function renderAlerts(alertsState) {
    clear(panelAlerts);
    const card = h('div', { className: 'card' });

    if (alertsState && alertsState.ok === false && alertsState.error) {
      card.appendChild(h('h3', {}, 'Alert service unavailable'));
      card.appendChild(h('p', { className: 'muted' }, alertsState.error));
      panelAlerts.appendChild(card);
      return;
    }

    const alertsList = (alertsState && alertsState.alerts) || [];
    const mode = (alertsState && alertsState.data_mode ? alertsState.data_mode.toUpperCase() : 'UNKNOWN');
    const modeNote = mode === 'RECORDED' ? ' (a replay of a real past alert, not a live warning)' : '';
    const retrievedTime = alertsState && alertsState.retrieved_at ? ` Retrieved at ${alertsState.retrieved_at}.` : '';

    if (!alertsList.length) {
      card.appendChild(h('p', { className: 'muted' }, 'No active emergency alerts in your area.'));
      card.appendChild(h('p', { className: 'muted note' }, `Data mode: ${mode}${modeNote}.${retrievedTime}`));
      panelAlerts.appendChild(card);
      return;
    }

    alertsList.forEach(a => {
      const isHigh = a.severity && a.severity.toLowerCase() === 'warning';
      const aCard = h('div', { className: 'alert' + (isHigh ? ' high' : ''), style: 'margin-bottom: 12px' });
      aCard.appendChild(h('div', { className: 'ai' }, icon(a.hazard === 'Heat' ? 'sun' : 'warn')));

      const content = h('div');
      const kk = h('div', { className: 'kk' });
      kk.appendChild(h('b', {}, (a.severity || 'Alert').toUpperCase()));
      kk.appendChild(h('span', { className: 'tag' }, a.hazard || 'Emergency'));
      kk.appendChild(h('span', { className: 'tag' }, mode));
      content.appendChild(kk);

      content.appendChild(h('h3', {}, a.headline || 'Emergency Alert'));

      if (a.area) {
        content.appendChild(h('p', { className: 'note' }, `Area: ${a.area}`));
      }

      const times = [];
      if (a.issued) times.push(`Issued: ${a.issued}`);
      if (a.expires) times.push(`Expires: ${a.expires}`);
      if (times.length) {
        content.appendChild(h('p', { className: 'muted note' }, times.join(' • ')));
      }

      if (a.source) {
        content.appendChild(h('p', { className: 'muted note' }, `Source: ${a.source}`));
      }

      if (a.instructions) {
        content.appendChild(h('p', { className: 'quote note muted' }, a.instructions));
      }

      aCard.appendChild(content);
      card.appendChild(aCard);
    });

    card.appendChild(h('p', { className: 'muted note' }, `Data mode: ${mode}${modeNote}.${retrievedTime}`));
    panelAlerts.appendChild(card);
  }

  function renderAdvice(adviceState) {
    clear(panelAdvice);
    const layout = h('div', { className: 'two' });

    // Actions card
    const actCard = h('div', { className: 'card' });
    actCard.appendChild(h('h2', {}, 'Priority actions'));

    const headlineText = adviceState && adviceState.headline ? adviceState.headline : '';
    if (headlineText) {
      actCard.appendChild(h('p', { style: 'font-weight: 600; margin-bottom: 12px' }, headlineText));
    }

    const ol = h('ol', { className: 'steps' });
    const actions = (adviceState && adviceState.actions) || [];
    if (!actions.length) {
      ol.appendChild(h('li', { className: 'muted' }, 'No actions needed right now.'));
    } else {
      actions.forEach((act, idx) => {
        const li = h('li');
        li.appendChild(h('b', {}, `${idx + 1}. ${act.action || act.title || ''}`));
        if (act.reason) {
          li.appendChild(h('br'));
          li.appendChild(h('span', { className: 'muted' }, act.reason));
        }
        ol.appendChild(li);
      });
    }
    actCard.appendChild(ol);
    layout.appendChild(actCard);

    // Official instructions and disclaimer card
    const instCard = h('div', { className: 'card' });
    instCard.appendChild(h('h2', {}, 'From the alert'));

    const official = (adviceState && adviceState.official_instructions) || 'No official instructions.';
    instCard.appendChild(h('p', {}, official));

    const disclaimer = (adviceState && adviceState.disclaimer) ||
      'Shown exactly as the alert gives it. This is general preparedness guidance from your saved household plan. Follow instructions from local authorities.';
    instCard.appendChild(h('p', { className: 'muted note' }, disclaimer));

    layout.appendChild(instCard);
    panelAdvice.appendChild(layout);
  }

  return {
    update(state) {
      renderAlerts(state.alerts);
      renderAdvice(state.advice);
    },
    destroy() {}
  };
}
