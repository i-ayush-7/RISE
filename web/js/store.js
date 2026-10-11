let savedLargeText = false;
try {
  savedLargeText = localStorage.getItem('rise_large_text') === 'true';
} catch (e) {
  savedLargeText = false;
}

const state = {
  view: 'home',
  scenario: 'flood',
  status: {
    server: 'down',
    protocol_version: null,
    clock_offset_minutes: 0
  },
  plan: null,
  alerts: {
    ok: false,
    data_mode: 'simulated',
    source: '',
    retrieved_at: '',
    alerts: [],
    error: null
  },
  advice: {
    ok: false,
    urgency: 'none',
    headline: '',
    actions: [],
    official_instructions: '',
    disclaimer: '',
    data_mode: '',
    error: null
  },
  checkin: {
    active: false,
    ok: false,
    counts: {},
    all_accounted_for: false,
    elapsed_minutes: 0,
    level: 0,
    speakable: '',
    next_steps: [],
    draft_message: '',
    members: [],
    error: null
  },
  messages: [
    {
      role: 'assistant',
      text: "I'm R.I.S.E., a simulated household emergency assistant. Ask what to do, or start a check-in. I never contact anyone."
    }
  ],
  activity: [],
  busy: {
    chat: false,
    action: false,
    scenario: false
  },
  prefs: {
    largeText: savedLargeText
  }
};

const subscribers = new Set();

export const store = {
  get() {
    return state;
  },
  set(patch) {
    if (!patch || typeof patch !== 'object') return;
    Object.assign(state, patch);
    if (patch.prefs && patch.prefs.largeText !== undefined) {
      try {
        localStorage.setItem('rise_large_text', String(patch.prefs.largeText));
      } catch (e) {}
    }
    for (const fn of subscribers) {
      try {
        fn(state, patch);
      } catch (err) {
        console.error('Store subscriber error', err);
      }
    }
  },
  subscribe(fn) {
    subscribers.add(fn);
    return () => subscribers.delete(fn);
  }
};
