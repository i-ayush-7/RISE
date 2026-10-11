import { h, clear, icon } from '../dom.js';
import { buildScene, updatePinPositions } from '../scene.js';
import { chat, tool } from '../api.js';

function initials(name) {
  if (!name) return '';
  return name.split(/\s+/).map(p => p[0]).join('').slice(0, 2).toUpperCase();
}

function firstName(name) {
  if (!name) return '';
  return name.split(/\s+/)[0];
}

export function mount(container, store) {
  clear(container);

  const homeRoot = h('div', { className: 'home' });
  const colLeft = h('div', { className: 'col' });
  const colRight = h('div', { className: 'col' });

  // Left Column
  const sceneSlot = h('div');
  colLeft.appendChild(sceneSlot);

  const chatCard = h('div', { className: 'card chatc' });
  const msgsBox = h('div', {
    className: 'msgs',
    id: 'msgs',
    role: 'log',
    'aria-live': 'polite',
    'aria-label': 'Conversation'
  });
  chatCard.appendChild(msgsBox);

  const chipsBox = h('div', { className: 'chips' });
  const defaultChips = [
    'What should we do?',
    'Any alerts?',
    'Start a check-in',
    'Who needs help?',
    'How is everyone?'
  ];
  for (const text of defaultChips) {
    const chipBtn = h('button', {
      type: 'button',
      className: 'chip',
      onClick: () => handleSend(text)
    }, text);
    chipsBox.appendChild(chipBtn);
  }
  chatCard.appendChild(chipsBox);

  const form = h('form', { className: 'row', id: 'form', onSubmit: (e) => {
    e.preventDefault();
    handleSend(inputEl.value);
  }});

  const field = h('div', { className: 'field' });
  field.appendChild(icon('spark'));

  const inputEl = h('input', {
    id: 'q',
    type: 'text',
    autocomplete: 'off',
    maxlength: '200',
    'aria-label': 'Ask R.I.S.E.',
    placeholder: 'Ask R.I.S.E. anything'
  });
  field.appendChild(inputEl);

  const micBtn = h('button', {
    type: 'button',
    className: 'mic',
    disabled: true,
    title: 'Voice is off in this prototype',
    'aria-label': 'Voice is off in this prototype'
  }, icon('mic'));
  field.appendChild(micBtn);

  form.appendChild(field);

  const sendBtn = h('button', {
    type: 'submit',
    className: 'btn pri'
  }, icon('send'), 'Send');
  form.appendChild(sendBtn);

  chatCard.appendChild(form);
  colLeft.appendChild(chatCard);

  // Right Column
  // 1. Current Situation Card
  const situationCard = h('div', { className: 'card' });
  const sitHd = h('div', { className: 'hd', style: 'margin-bottom: 12px' });
  sitHd.appendChild(h('h2', {}, 'Current situation'));
  const viewAlertsBtn = h('button', {
    type: 'button',
    className: 'chip',
    onClick: () => store.set({ view: 'alerts' })
  }, 'View details', icon('arr'));
  sitHd.appendChild(viewAlertsBtn);
  situationCard.appendChild(sitHd);

  const sitBody = h('div');
  situationCard.appendChild(sitBody);
  colRight.appendChild(situationCard);

  // 2. Family Check-in Card
  const checkinCard = h('div', { className: 'card' });
  const chkHd = h('div', { className: 'hd', style: 'margin-bottom: 10px' });
  chkHd.appendChild(h('h2', {}, 'Family check-in'));
  chkHd.appendChild(icon('ppl'));
  checkinCard.appendChild(chkHd);

  const chkBody = h('div');
  checkinCard.appendChild(chkBody);
  colRight.appendChild(checkinCard);

  // 3. MCP Activity Log Card
  const logCard = h('div', { className: 'card grow' });
  const logHd = h('div', { className: 'hd', style: 'margin-bottom: 12px' });
  logHd.appendChild(h('h2', {}, 'MCP activity log'));
  const viewLogBtn = h('button', {
    type: 'button',
    className: 'chip',
    onClick: () => store.set({ view: 'log' })
  }, 'View all', icon('arr'));
  logHd.appendChild(viewLogBtn);
  logCard.appendChild(logHd);

  const logList = h('ul', { className: 'log s' });
  logCard.appendChild(logList);
  colRight.appendChild(logCard);

  homeRoot.appendChild(colLeft);
  homeRoot.appendChild(colRight);
  container.appendChild(homeRoot);

  let renderedMsgCount = 0;

  async function handleSend(text) {
    const clean = (text || '').trim();
    if (!clean) return;
    inputEl.value = '';

    const currentMsgs = [...store.get().messages, { role: 'user', text: clean }];
    store.set({ messages: currentMsgs, busy: { ...store.get().busy, chat: true } });

    const res = await chat(clean);
    const replyText = (res && res.reply) || (res && res.error) || 'Something went wrong.';

    store.set({
      messages: [...store.get().messages, { role: 'assistant', text: replyText }],
      busy: { ...store.get().busy, chat: false }
    });

    if (res && res.refresh && res.refresh.includes('checkin')) {
      const st = await tool('get_checkin_status', {});
      if (st.ok && typeof st.result === 'object') {
        store.set({ checkin: { ...store.get().checkin, active: true, ...st.result } });
      }
    }
  }

  function renderMessages(messages) {
    if (messages.length === renderedMsgCount) return;
    clear(msgsBox);
    for (const m of messages) {
      if (m.role === 'user') {
        msgsBox.appendChild(h('div', { className: 'msg me' }, m.text));
      } else {
        const botBubble = h('div', { className: 'msg bot' });
        const bav = h('div', { className: 'bav' }, icon('home2'));
        botBubble.appendChild(bav);

        const content = h('div');
        content.appendChild(h('span', { className: 'muted note' }, 'R.I.S.E. (simulated)'));
        content.appendChild(h('br'));
        content.appendChild(document.createTextNode(m.text));
        botBubble.appendChild(content);

        msgsBox.appendChild(botBubble);
      }
    }
    renderedMsgCount = messages.length;
    msgsBox.scrollTop = msgsBox.scrollHeight;
  }

  function renderSituation(state) {
    clear(sitBody);
    const { alerts, advice } = state;
    const topAlert = (alerts && alerts.alerts && alerts.alerts[0]) || null;

    if (alerts && alerts.ok === false && alerts.error) {
      const alertDiv = h('div', { className: 'alert fail' });
      alertDiv.appendChild(h('div', { className: 'ai' }, icon('warn')));
      const txt = h('div');
      txt.appendChild(h('h3', {}, 'Alert service unavailable'));
      txt.appendChild(h('p', { className: 'muted note' }, 'Do not assume there are no active alerts. Follow local authorities.'));
      alertDiv.appendChild(txt);
      sitBody.appendChild(alertDiv);
      return;
    }

    if (!topAlert) {
      const alertDiv = h('div', { className: 'alert ok' });
      alertDiv.appendChild(h('div', { className: 'ai' }, icon('okk')));
      const txt = h('div');
      txt.appendChild(h('h3', {}, 'No active alerts'));
      txt.appendChild(h('p', { className: 'muted note' }, (advice && advice.headline) || 'No severe weather alerts in effect.'));
      alertDiv.appendChild(txt);
      sitBody.appendChild(alertDiv);
      return;
    }

    const isHigh = topAlert.severity && topAlert.severity.toLowerCase() === 'warning';
    const alertDiv = h('div', { className: 'alert' + (isHigh ? ' high' : '') });
    alertDiv.appendChild(h('div', { className: 'ai' }, icon(topAlert.hazard === 'Heat' ? 'sun' : 'warn')));

    const txt = h('div');
    const kk = h('div', { className: 'kk' });
    kk.appendChild(h('b', {}, (topAlert.severity || 'Alert').toUpperCase()));
    const modeBadge = (alerts && alerts.data_mode ? alerts.data_mode.toUpperCase() : 'UNKNOWN');
    kk.appendChild(h('span', { className: 'tag' }, modeBadge));
    txt.appendChild(kk);

    txt.appendChild(h('h3', {}, topAlert.headline || 'Active Emergency Alert'));
    if (topAlert.instructions) {
      txt.appendChild(h('p', { className: 'quote note muted' }, topAlert.instructions));
    }
    alertDiv.appendChild(txt);
    sitBody.appendChild(alertDiv);
  }

  function renderCheckin(state) {
    clear(chkBody);
    const { checkin, plan } = state;
    const active = Boolean(checkin && checkin.active);

    if (!active) {
      chkBody.appendChild(h('p', { className: 'muted', style: 'margin: 0 0 12px' }, 'No check-in is active.'));
      const startBtn = h('button', {
        type: 'button',
        className: 'btn pri wide',
        onClick: async () => {
          const res = await tool('start_checkin', { reason: 'Web start' });
          if (res.ok) {
            const st = await tool('get_checkin_status', {});
            store.set({ checkin: { ...st.result, active: true }, view: 'board' });
          }
        }
      }, icon('play'), 'Start check-in');
      chkBody.appendChild(startBtn);
      return;
    }

    const members = (plan && plan.members) || [];
    const checkinMembers = (checkin && checkin.members) || [];
    const memberStatuses = {};
    for (const cm of checkinMembers) {
      const nameKey = (cm.member_name || cm.name || '').toLowerCase();
      memberStatuses[nameKey] = cm.status || 'pending';
    }

    const safeCount = checkinMembers.filter(m => m.status === 'safe').length;
    const totalCount = members.length || checkinMembers.length;

    chkBody.appendChild(h('p', { className: 'muted note', style: 'margin: 0' },
      `${safeCount} of ${totalCount} people confirmed safe`));

    const avs = h('div', { className: 'avs' });
    members.forEach(m => {
      const st = memberStatuses[(m.name || '').toLowerCase()] || 'pending';
      const avw = h('div', { className: 'avw' });
      avw.appendChild(h('div', { className: 'av ' + st, 'aria-hidden': 'true' }, initials(m.name)));
      avw.appendChild(h('span', { className: 'note' }, firstName(m.name)));
      avw.appendChild(h('span', { className: 'st ' + st }, st.replace('_', ' ')));
      avs.appendChild(avw);
    });
    chkBody.appendChild(avs);

    const contBtn = h('button', {
      type: 'button',
      className: 'btn pri wide',
      onClick: () => store.set({ view: 'board' })
    }, 'Continue check-in', icon('arr'));
    chkBody.appendChild(contBtn);
  }

  function renderActivity(activity) {
    clear(logList);
    const recent = (activity || []).slice(0, 5);
    if (!recent.length) {
      logList.appendChild(h('li', { className: 'muted' }, 'No activity yet.'));
      return;
    }

    for (const item of recent) {
      const li = h('li', { className: item.ok ? '' : 'err' });
      const lh = h('div', { className: 'lh' });
      const timeStr = item.time ? new Date(item.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
      lh.appendChild(h('span', { className: 'tt' }, timeStr));
      lh.appendChild(h('b', {}, item.tool || item.name || 'tool'));
      lh.appendChild(h('span', { className: 'okb' + (item.ok ? '' : ' bad') }, item.ok ? 'OK' : 'FAIL'));
      li.appendChild(lh);
      logList.appendChild(li);
    }
  }

  const onResize = () => updatePinPositions(sceneSlot);
  window.addEventListener('resize', onResize);

  return {
    update(state) {
      clear(sceneSlot);
      sceneSlot.appendChild(buildScene(state));
      updatePinPositions(sceneSlot);

      renderMessages(state.messages || []);
      renderSituation(state);
      renderCheckin(state);
      renderActivity(state.activity || []);
    },
    destroy() {
      window.removeEventListener('resize', onResize);
    }
  };
}
