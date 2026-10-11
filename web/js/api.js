async function request(url, options = {}) {
  const controller = new AbortController();
  const timer = setTimeout(() => controller.abort(), 15000);
  try {
    const res = await fetch(url, {
      ...options,
      signal: controller.signal
    });
    clearTimeout(timer);
    const data = await res.json().catch(() => null);
    if (!res.ok) {
      return {
        ok: false,
        status: res.status,
        error: (data && (data.error || data.message)) || `HTTP ${res.status}`,
        ...(data || {})
      };
    }
    return data || { ok: true };
  } catch (err) {
    clearTimeout(timer);
    return { ok: false, error: 'connection', network: true };
  }
}

export async function getStatus() {
  return request('/api/status');
}

export async function tool(name, args = {}) {
  const res = await request('/api/tool', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ name, arguments: args })
  });
  if (!res.ok) {
    return {
      ok: false,
      error: res.error || 'tool error',
      ms: res.ms || 0,
      network: Boolean(res.network)
    };
  }
  return {
    ok: true,
    result: res.result,
    ms: res.ms || 0
  };
}

export async function chat(text) {
  return request('/api/chat', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ text })
  });
}

export async function getActivity(afterId = 0) {
  return request(`/api/activity?after=${encodeURIComponent(afterId)}`);
}

export async function setScenario(key) {
  return request('/api/scenario', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ scenario: key })
  });
}

export async function reset() {
  return request('/api/reset', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({})
  });
}

export async function skipTime(minutes = 5) {
  return request('/api/demo/skip-time', {
    method: 'POST',
    headers: { 'Content-Type': 'application/json' },
    body: JSON.stringify({ minutes: Number(minutes) })
  });
}
