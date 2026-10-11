import { h, clear } from '../dom.js';
import { setScenario, reset, tool, getStatus } from '../api.js';

export function mount(container, store) {
  clear(container);

  const layout = h('div', { className: 'two' });

  // Left card: Scenario controls, Reset, Large text
  const leftCard = h('div', { className: 'card' });
  leftCard.appendChild(h('h2', {}, 'Scenario controls'));

  const scenarioChips = h('div', { className: 'chips' });

  const scenarios = [
    { key: 'flood', label: 'Flood drill' },
    { key: 'heat', label: 'Heatwave drill' },
    { key: 'rec', label: 'Recorded real alert' },
    { key: 'none', label: 'No alerts' },
    { key: 'live', label: 'Live alerts', note: 'needs internet' }
  ];

  const scenarioButtons = {};
  scenarios.forEach(sc => {
    const btnText = sc.note ? `${sc.label} (${sc.note})` : sc.label;
    const btn = h('button', {
      type: 'button',
      className: 'btn',
      'aria-pressed': 'false',
      onClick: () => handleSelectScenario(sc.key)
    }, btnText);
    scenarioButtons[sc.key] = btn;
    scenarioChips.appendChild(btn);
  });
  leftCard.appendChild(scenarioChips);

  const spinnerSlot = h('div', { style: 'margin: 8px 0; min-height: 24px;' });
  leftCard.appendChild(spinnerSlot);

  const actionChips = h('div', { className: 'chips' });

  const resetBtn = h('button', {
    type: 'button',
    className: 'btn',
    onClick: () => resetDialog.showModal()
  }, 'Reset demo');
  actionChips.appendChild(resetBtn);

  const largeTextBtn = h('button', {
    type: 'button',
    className: 'btn',
    'aria-pressed': String(store.get().prefs.largeText),
    onClick: () => {
      const current = store.get().prefs.largeText;
      const next = !current;
      document.body.classList.toggle('big', next);
      store.set({ prefs: { ...store.get().prefs, largeText: next } });
      largeTextBtn.setAttribute('aria-pressed', String(next));
    }
  }, 'Large text');
  actionChips.appendChild(largeTextBtn);

  leftCard.appendChild(actionChips);
  layout.appendChild(leftCard);

  // Right card: About text
  const aboutCard = h('div', { className: 'card' });
  aboutCard.appendChild(h('h2', {}, 'About R.I.S.E.'));
  aboutCard.appendChild(h('p', {},
    'Rapid Incident Safety and Escalation: a simulated household emergency copilot. This page imitates an assistant front end and is not affiliated with any assistant brand.'));
  aboutCard.appendChild(h('p', { className: 'muted' },
    'R.I.S.E. never contacts anyone. It records who you confirm is safe, shows who to contact next, and drafts a message you can copy. Advice is general preparedness guidance. Follow local authorities and call your local emergency number if anyone is in danger.'));
  layout.appendChild(aboutCard);

  container.appendChild(layout);

  // Reset confirmation dialog
  const resetDialog = h('dialog');
  resetDialog.appendChild(h('h2', {}, 'Reset demo?'));
  resetDialog.appendChild(h('p', { className: 'muted' },
    'This will restart the MCP server with the initial flood scenario, clear check-in status, and reset activity logs.'));
  const dialogActions = h('div', { className: 'chips', style: 'justify-content: flex-end; margin-top: 18px;' });
  const cancelResetBtn = h('button', {
    type: 'button',
    className: 'btn',
    onClick: () => resetDialog.close()
  }, 'Cancel');
  const confirmResetBtn = h('button', {
    type: 'button',
    className: 'btn pri',
    onClick: async () => {
      resetDialog.close();
      await handleReset();
    }
  }, 'Reset');
  dialogActions.appendChild(cancelResetBtn);
  dialogActions.appendChild(confirmResetBtn);
  resetDialog.appendChild(dialogActions);
  container.appendChild(resetDialog);

  async function handleSelectScenario(key) {
    clear(spinnerSlot);
    const sp = h('span', { className: 'spinner' });
    spinnerSlot.appendChild(sp);
    spinnerSlot.appendChild(document.createTextNode(' Switching scenario...'));

    for (const b of Object.values(scenarioButtons)) b.disabled = true;
    resetBtn.disabled = true;

    await setScenario(key);
    await refreshAll();

    for (const b of Object.values(scenarioButtons)) b.disabled = false;
    resetBtn.disabled = false;
    clear(spinnerSlot);
  }

  async function handleReset() {
    clear(spinnerSlot);
    const sp = h('span', { className: 'spinner' });
    spinnerSlot.appendChild(sp);
    spinnerSlot.appendChild(document.createTextNode(' Resetting demo...'));

    for (const b of Object.values(scenarioButtons)) b.disabled = true;
    resetBtn.disabled = true;

    await reset();
    await refreshAll();

    for (const b of Object.values(scenarioButtons)) b.disabled = false;
    resetBtn.disabled = false;
    clear(spinnerSlot);

    store.set({ view: 'home' });
  }

  async function refreshAll() {
    const stat = await getStatus();
    const [p, a, ad, c] = await Promise.all([
      tool('get_household_plan', {}),
      tool('get_active_alerts', {}),
      tool('get_safety_advice', {}),
      tool('get_checkin_status', {})
    ]);

    store.set({
      scenario: stat.scenario || store.get().scenario,
      status: { ...store.get().status, ...stat },
      plan: p.ok ? p.result : store.get().plan,
      alerts: a.ok ? a.result : { ok: false, error: a.error, alerts: [] },
      advice: ad.ok ? ad.result : { ok: false, error: ad.error },
      checkin: c.ok && typeof c.result === 'object' ? { ...c.result, active: true } : { active: false }
    });
  }

  return {
    update(state) {
      const currentSc = state.scenario || 'flood';
      for (const [key, btn] of Object.entries(scenarioButtons)) {
        const isSelected = (key === currentSc);
        btn.setAttribute('aria-pressed', String(isSelected));
        if (isSelected) {
          btn.style.borderColor = 'var(--c)';
        } else {
          btn.style.borderColor = '';
        }
      }
      largeTextBtn.setAttribute('aria-pressed', String(state.prefs.largeText));
    },
    destroy() {
      if (resetDialog.open) resetDialog.close();
    }
  };
}
