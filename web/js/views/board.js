import { h, clear, icon } from '../dom.js';
import { tool, skipTime, getStatus } from '../api.js';

function initials(name) {
  if (!name) return '';
  return name.split(/\s+/).map(p => p[0]).join('').slice(0, 2).toUpperCase();
}

function statusWord(status) {
  switch (status) {
    case 'safe': return 'Safe';
    case 'needs_help': return 'Needs help';
    case 'not_responding': return 'Not responding';
    default: return 'Pending';
  }
}

export function mount(container, store) {
  clear(container);

  const wrapper = h('div');

  // Empty state container
  const emptyCard = h('div', { className: 'card' });
  emptyCard.appendChild(h('h2', {}, 'Family check-in'));
  emptyCard.appendChild(h('p', { className: 'muted' }, 'No check-in is active. Start one to track who is safe.'));
  const startBtn = h('button', {
    type: 'button',
    className: 'btn pri',
    onClick: async () => {
      const res = await tool('start_checkin', { reason: 'Web board start' });
      if (res.ok) {
        const st = await tool('get_checkin_status', {});
        if (st.ok && typeof st.result === 'object') {
          store.set({ checkin: { ...st.result, active: true } });
        }
      } else {
        alert(res.error || 'Failed to start check-in');
      }
    }
  }, 'Start check-in');
  emptyCard.appendChild(startBtn);
  wrapper.appendChild(emptyCard);

  // Active state container
  const activeLayout = h('div', { className: 'two' });

  // Left card: details, member controls
  const leftCard = h('div', { className: 'card' });
  leftCard.appendChild(h('h2', {}, 'Family check-in'));

  const speakableP = h('p');
  const speakableB = h('b');
  speakableP.appendChild(speakableB);
  leftCard.appendChild(speakableP);

  const metaP = h('p', { className: 'muted note' });
  leftCard.appendChild(metaP);

  const meterDiv = h('div', { className: 'meter', 'aria-hidden': 'true' });
  const meterBars = [h('i'), h('i'), h('i')];
  meterBars.forEach(b => meterDiv.appendChild(b));
  leftCard.appendChild(meterDiv);

  const skipBtn = h('button', {
    type: 'button',
    className: 'btn',
    onClick: async () => {
      skipBtn.disabled = true;
      await skipTime(5);
      const st = await tool('get_checkin_status', {});
      const stat = await getStatus();
      skipBtn.disabled = false;
      if (st.ok && typeof st.result === 'object') {
        store.set({
          checkin: { ...st.result, active: true },
          status: { ...store.get().status, ...stat }
        });
      }
    }
  }, 'Skip time +5 min');
  leftCard.appendChild(skipBtn);

  const noteLabelP = h('p', { style: 'margin: 12px 0 4px' });
  const noteLabel = h('label', { className: 'muted note', for: 'note-input' }, 'Note for Needs help (optional)');
  noteLabelP.appendChild(noteLabel);
  leftCard.appendChild(noteLabelP);

  const noteRow = h('div', { className: 'row', style: 'margin-bottom: 12px' });
  const noteInput = h('input', {
    id: 'note-input',
    type: 'text',
    maxlength: '300',
    placeholder: 'For example: fell and cannot stand'
  });
  noteRow.appendChild(noteInput);
  leftCard.appendChild(noteRow);

  const membersDiv = h('div', { className: 'members' });
  leftCard.appendChild(membersDiv);
  activeLayout.appendChild(leftCard);

  // Right stack: Next steps, Draft message, Timeline
  const rightStack = h('div', { className: 'stack' });

  // Next steps card
  const stepsCard = h('div', { className: 'card' });
  stepsCard.appendChild(h('h2', {}, 'Next steps'));
  const stepsList = h('ol', { className: 'steps' });
  stepsCard.appendChild(stepsList);
  rightStack.appendChild(stepsCard);

  // Draft message card
  const draftCard = h('div', { className: 'card' });
  draftCard.appendChild(h('h2', {}, 'Draft message'));
  const draftPre = h('pre', { className: 'draft' });
  draftCard.appendChild(draftPre);

  const draftActions = h('div', { className: 'chips' });
  const copyBtn = h('button', {
    type: 'button',
    className: 'btn',
    onClick: () => {
      const text = draftPre.textContent || '';
      if (navigator.clipboard && navigator.clipboard.writeText) {
        navigator.clipboard.writeText(text).then(() => {
          copyBtn.textContent = 'Copied!';
          setTimeout(() => { copyBtn.textContent = 'Copy message'; }, 2000);
        }).catch(() => {
          copyBtn.textContent = 'Select and copy the text above';
        });
      } else {
        copyBtn.textContent = 'Select and copy the text above';
      }
    }
  }, 'Copy message');
  draftActions.appendChild(copyBtn);

  const closeBtn = h('button', {
    type: 'button',
    className: 'btn pri',
    onClick: () => {
      confirmDialog.showModal();
    }
  }, 'Close check-in');
  draftActions.appendChild(closeBtn);
  draftCard.appendChild(draftActions);

  draftCard.appendChild(h('p', { className: 'muted note' },
    'R.I.S.E. does not contact anyone. Use your phone to call or message.'));
  rightStack.appendChild(draftCard);

  // Recent activity card
  const tlCard = h('div', { className: 'card' });
  tlCard.appendChild(h('h2', {}, 'Recent activity'));
  const tlList = h('ul', { className: 'tl' });
  tlCard.appendChild(tlList);
  rightStack.appendChild(tlCard);

  activeLayout.appendChild(rightStack);
  wrapper.appendChild(activeLayout);

  // Dialog for Close check-in confirmation
  const confirmDialog = h('dialog');
  confirmDialog.appendChild(h('h2', {}, 'Close check-in?'));
  confirmDialog.appendChild(h('p', { className: 'muted' },
    'This marks the current check-in complete and stops escalation tracking.'));
  const dialogActions = h('div', { className: 'chips', style: 'justify-content: flex-end; margin-top: 18px;' });
  const cancelCloseBtn = h('button', {
    type: 'button',
    className: 'btn',
    onClick: () => confirmDialog.close()
  }, 'Cancel');
  const confirmCloseBtn = h('button', {
    type: 'button',
    className: 'btn pri',
    onClick: async () => {
      confirmDialog.close();
      const res = await tool('close_checkin', {});
      if (res.ok) {
        const st = await tool('get_checkin_status', {});
        store.set({
          checkin: { ...(st.result || {}), active: false }
        });
      }
    }
  }, 'Close check-in');
  dialogActions.appendChild(cancelCloseBtn);
  dialogActions.appendChild(confirmCloseBtn);
  confirmDialog.appendChild(dialogActions);
  wrapper.appendChild(confirmDialog);

  container.appendChild(wrapper);

  async function handleRecord(memberName, status) {
    const noteVal = (status === 'needs_help') ? noteInput.value.trim() : '';
    const args = { member_name: memberName, status };
    if (noteVal) args.note = noteVal;

    const res = await tool('record_checkin', args);
    const st = await tool('get_checkin_status', {});
    if (st.ok && typeof st.result === 'object') {
      store.set({ checkin: { ...st.result, active: true } });
    }
    if (!res.ok) {
      alert(res.error || 'Failed to record status');
    }
  }

  function renderMembers(state) {
    clear(membersDiv);
    const { plan, checkin } = state;
    const members = (plan && plan.members) || [];
    const checkinMembers = (checkin && checkin.members) || [];
    const memberMap = {};
    for (const cm of checkinMembers) {
      const nameKey = (cm.member_name || cm.name || '').toLowerCase();
      memberMap[nameKey] = cm;
    }

    members.forEach(m => {
      const cm = memberMap[(m.name || '').toLowerCase()] || {};
      const st = cm.status || 'pending';
      const memCard = h('div', { className: 'mem' });

      const av = h('div', { className: 'av ' + st, 'aria-hidden': 'true' }, initials(m.name));
      memCard.appendChild(av);

      const mb = h('div', { className: 'mb' });
      mb.appendChild(h('b', {}, m.name));

      const statusSpan = h('span', { className: 'st ' + st }, statusWord(st));
      mb.appendChild(statusSpan);

      if (cm.note) {
        mb.appendChild(h('div', { className: 'muted note' }, 'Note: ' + cm.note));
      }

      const acts = h('div', { className: 'acts' });
      const safeBtn = h('button', {
        type: 'button',
        className: 'btn ok',
        onClick: () => handleRecord(m.name, 'safe')
      }, 'Safe');
      const needsBtn = h('button', {
        type: 'button',
        className: 'btn warn',
        onClick: () => handleRecord(m.name, 'needs_help')
      }, 'Needs help');
      const norespBtn = h('button', {
        type: 'button',
        className: 'btn',
        onClick: () => handleRecord(m.name, 'not_responding')
      }, 'Not responding');

      acts.appendChild(safeBtn);
      acts.appendChild(needsBtn);
      acts.appendChild(norespBtn);
      mb.appendChild(acts);

      memCard.appendChild(mb);
      membersDiv.appendChild(memCard);
    });
  }

  function renderSteps(steps) {
    clear(stepsList);
    const list = Array.isArray(steps) ? steps : [];
    if (!list.length) {
      stepsList.appendChild(h('li', { className: 'muted' }, 'No next steps.'));
      return;
    }
    list.forEach(item => {
      const isUrgent = item.priority === 0 || item.p === 0;
      const li = h('li', { className: isUrgent ? 'p0' : '' });
      li.appendChild(document.createTextNode(item.action || item.a || ''));
      const reason = item.reason || item.r || '';
      if (reason) {
        li.appendChild(h('br'));
        li.appendChild(h('span', { className: 'muted' }, reason));
      }
      stepsList.appendChild(li);
    });
  }

  function renderTimeline(activity) {
    clear(tlList);
    const checkinActivity = (activity || [])
      .filter(item => {
        const name = (item.tool || item.name || '').toLowerCase();
        return name.includes('checkin') || name.includes('check_in');
      })
      .slice(0, 6);

    if (!checkinActivity.length) {
      tlList.appendChild(h('li', { className: 'muted' }, 'Nothing yet.'));
      return;
    }

    checkinActivity.forEach(item => {
      const li = h('li');
      const timeStr = item.time ? new Date(item.time).toLocaleTimeString([], { hour: '2-digit', minute: '2-digit', second: '2-digit' }) : '';
      li.appendChild(h('span', { className: 'tt' }, timeStr));

      let desc = item.tool || item.name || '';
      if (desc === 'start_checkin') desc = 'Check-in started';
      else if (desc === 'close_checkin') desc = 'Check-in closed';
      else if (desc === 'record_checkin') {
        let args = item.arguments || item.args || {};
        if (typeof args === 'string') {
          try { args = JSON.parse(args); } catch (e) {}
        }
        const mName = args.member_name || args.member || '';
        const stWord = statusWord(args.status || '');
        desc = `${mName} marked as ${stWord.toLowerCase()}`;
      }
      li.appendChild(document.createTextNode(desc));
      tlList.appendChild(li);
    });
  }

  return {
    update(state) {
      const { checkin, status, activity } = state;
      const active = Boolean(checkin && checkin.active);

      if (!active) {
        emptyCard.classList.remove('hidden');
        activeLayout.classList.add('hidden');
        return;
      }

      emptyCard.classList.add('hidden');
      activeLayout.classList.remove('hidden');

      speakableB.textContent = checkin.speakable || 'Check-in is active.';

      const elapsed = checkin.elapsed_minutes || 0;
      const lvl = checkin.level || 0;
      const offset = (status && status.clock_offset_minutes) || 0;
      const offsetText = offset ? ` Demo clock: +${offset} min (simulated).` : '';
      metaP.textContent = `Elapsed ${elapsed} min. Escalation level ${lvl} of 3 (demo thresholds: 5, 10 and 20 minutes).${offsetText}`;

      meterBars.forEach((bar, idx) => {
        if (lvl > idx) bar.classList.add('on');
        else bar.classList.remove('on');
      });

      renderMembers(state);
      renderSteps(checkin.next_steps);
      draftPre.textContent = checkin.draft_message || '';
      renderTimeline(activity);
    },
    destroy() {
      if (confirmDialog.open) confirmDialog.close();
    }
  };
}
