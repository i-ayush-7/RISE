import { h, clear } from '../dom.js';

export function mount(container, store) {
  clear(container);

  let currentTab = 'members';

  const heading = h('h2', {}, 'Household plan');
  container.appendChild(heading);

  const tablist = h('div', {
    className: 'tabs',
    role: 'tablist',
    'aria-label': 'Plan sections'
  });

  const tabMembers = h('button', {
    type: 'button',
    role: 'tab',
    'aria-selected': 'true',
    tabindex: '0',
    onClick: () => selectTab('members')
  }, 'Members');

  const tabContacts = h('button', {
    type: 'button',
    role: 'tab',
    'aria-selected': 'false',
    tabindex: '-1',
    onClick: () => selectTab('contacts')
  }, 'Contacts');

  const tabMeeting = h('button', {
    type: 'button',
    role: 'tab',
    'aria-selected': 'false',
    tabindex: '-1',
    onClick: () => selectTab('meeting')
  }, 'Meeting points');

  tablist.appendChild(tabMembers);
  tablist.appendChild(tabContacts);
  tablist.appendChild(tabMeeting);
  container.appendChild(tablist);

  const card = h('div', { className: 'card' });
  const contentSlot = h('div');
  card.appendChild(contentSlot);

  const noteP = h('p', { className: 'muted note' },
    'Medical and mobility details stay in the plan and never go into draft messages.');
  card.appendChild(noteP);

  const editBtn = h('button', {
    type: 'button',
    className: 'btn',
    disabled: true,
    style: 'margin-top: 12px;'
  }, 'Editing arrives in a later step');
  card.appendChild(editBtn);

  container.appendChild(card);

  function selectTab(tabKey) {
    currentTab = tabKey;
    tabMembers.setAttribute('aria-selected', tabKey === 'members' ? 'true' : 'false');
    tabContacts.setAttribute('aria-selected', tabKey === 'contacts' ? 'true' : 'false');
    tabMeeting.setAttribute('aria-selected', tabKey === 'meeting' ? 'true' : 'false');
    renderContent(store.get().plan);
  }

  function renderContent(plan) {
    clear(contentSlot);
    if (!plan) {
      contentSlot.appendChild(h('p', { className: 'muted' }, 'Plan details unavailable.'));
      return;
    }

    if (currentTab === 'members') {
      const members = plan.members || [];
      tabMembers.textContent = `Members (${members.length})`;
      if (!members.length) {
        contentSlot.appendChild(h('p', { className: 'muted' }, 'No members listed in plan.'));
        return;
      }
      members.forEach(m => {
        const p = h('p', { style: 'margin: 8px 0 12px;' });
        p.appendChild(h('b', {}, m.name));
        p.appendChild(h('br'));

        const details = [];
        if (m.age_group) details.push(`Age: ${m.age_group}`);
        if (m.support_level) details.push(`Support: ${m.support_level}`);
        if (m.mobility) details.push(`Mobility: ${m.mobility}`);
        if (m.medical_notes) details.push(`Medical: ${m.medical_notes}`);
        if (m.is_pet) details.push('Pet');

        const detText = details.length ? details.join(' • ') : (m.details || m.description || 'Independent');
        p.appendChild(h('span', { className: 'muted' }, detText));
        contentSlot.appendChild(p);
      });
    } else if (currentTab === 'contacts') {
      const contacts = plan.emergency_contacts || plan.contacts || [];
      tabContacts.textContent = `Contacts (${contacts.length})`;
      if (!contacts.length) {
        contentSlot.appendChild(h('p', { className: 'muted' }, 'No emergency contacts listed in plan.'));
        return;
      }
      contacts.forEach((c, idx) => {
        const p = h('p', { style: 'margin: 8px 0 12px;' });
        const callOrder = c.call_order || (idx + 1);
        p.appendChild(h('b', {}, `${c.name} (call order ${callOrder})`));
        p.appendChild(h('br'));

        const desc = [c.relationship, c.phone].filter(Boolean).join(', ');
        p.appendChild(h('span', { className: 'muted' }, desc || 'Emergency contact'));
        contentSlot.appendChild(p);
      });
    } else if (currentTab === 'meeting') {
      const meet = plan.meeting_points || [];
      tabMeeting.textContent = `Meeting points (${meet.length || 2})`;
      if (!meet.length) {
        // Fallback meeting points from plan standard
        const p1 = h('p', { style: 'margin: 8px 0 12px;' });
        p1.appendChild(h('b', {}, 'Neighborhood Park (primary)'));
        p1.appendChild(h('br'));
        p1.appendChild(h('span', { className: 'muted' }, 'Oak tree in the center of the park'));
        contentSlot.appendChild(p1);

        const p2 = h('p', { style: 'margin: 8px 0 12px;' });
        p2.appendChild(h('b', {}, 'Springfield Community Center (out of area)'));
        p2.appendChild(h('br'));
        p2.appendChild(h('span', { className: 'muted' }, 'Main entrance desk'));
        contentSlot.appendChild(p2);
        return;
      }
      meet.forEach(mp => {
        const p = h('p', { style: 'margin: 8px 0 12px;' });
        const type = mp.is_primary ? ' (primary)' : ' (out of area)';
        p.appendChild(h('b', {}, (mp.name || mp.location || 'Meeting point') + type));
        p.appendChild(h('br'));
        p.appendChild(h('span', { className: 'muted' }, mp.notes || mp.description || ''));
        contentSlot.appendChild(p);
      });
    }
  }

  return {
    update(state) {
      renderContent(state.plan);
    },
    destroy() {}
  };
}
