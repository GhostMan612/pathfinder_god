// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================
// Browser face behavior. htmx owns navigation/dashboard refreshes; this file
// owns only the one thing htmx cannot do well natively: consuming a POST-like
// SSE turn stream without EventSource's automatic reconnect (which would run
// the same turn twice).

const form = document.getElementById('turn-form');
const actionInput = document.getElementById('action');
const submitButton = form ? form.querySelector('button[type="submit"]') : null;
const statusEl = document.getElementById('turn-status');
const logEl = document.getElementById('turn-log');
const sceneEl = document.getElementById('face-scene');
const sceneLabel = document.getElementById('scene-label');
const canvas = document.getElementById('face-map');

let running = false;
let narrationBlock = null;

function setStatus(text) {
  if (statusEl) statusEl.textContent = text;
}

function log(text, cls = '') {
  if (!logEl) return;
  const line = document.createElement('div');
  line.className = 'log-line ' + cls;
  line.textContent = text;
  logEl.appendChild(line);
  logEl.scrollTop = logEl.scrollHeight;
}

function startNarration() {
  if (!logEl) return;
  narrationBlock = document.createElement('div');
  narrationBlock.className = 'log-line log-narration';
  logEl.appendChild(narrationBlock);
}

function appendNarration(text) {
  if (!text) return;
  if (!narrationBlock) startNarration();
  narrationBlock.textContent += text;
  logEl.scrollTop = logEl.scrollHeight;
}

function parseSSEBlock(block) {
  let event = 'message';
  const data = [];
  for (const rawLine of block.split('\n')) {
    if (!rawLine || rawLine.startsWith(':')) continue;
    const colon = rawLine.indexOf(':');
    const field = colon === -1 ? rawLine : rawLine.slice(0, colon);
    let value = colon === -1 ? '' : rawLine.slice(colon + 1);
    if (value.startsWith(' ')) value = value.slice(1);
    if (field === 'event') event = value || 'message';
    else if (field === 'data') data.push(value);
  }
  return { event, data: data.join('\n') };
}

function handleEvent(eventName, payload) {
  let data;
  try {
    data = JSON.parse(payload);
  } catch (_) {
    return;
  }

  if (eventName === 'start') {
    setStatus(`Turn ${data.turn_num} — ${data.phase}`);
    log(`Turn ${data.turn_num} begins (${data.phase}, round ${data.round}).`, 'log-encounter');
    startNarration();
    return;
  }

  if (eventName === 'dice') {
    for (const roll of (data.dice_rolls || [])) {
      const notation = roll.notation || 'roll';
      const total = roll.total ?? roll.result ?? roll.value ?? '?';
      const dc = roll.dc != null ? ` vs DC ${roll.dc}` : '';
      const outcome = roll.success === true ? ' — success' : roll.success === false ? ' — failure' : '';
      log(`Dice ${notation}: ${total}${dc}${outcome}`, 'log-dice');
    }
    return;
  }

  if (eventName === 'hp') {
    for (const change of (data.hp_changes || [])) {
      const delta = change.healed ? `+${change.healed}` : change.damage ? `-${change.damage}` : '';
      log(`${change.name || 'Target'}: HP ${change.hp}${delta ? ` (${delta})` : ''}`, 'log-hp');
    }
    return;
  }

  if (eventName === 'encounter') {
    log(`Encounter ${data.kind || ''} ${data.status || ''}: ${data.summary || ''}`, 'log-encounter');
    return;
  }

  if (eventName === 'encounter_stage' && data.scene) {
    setScene(data.scene);
    log('Stage scene updated.', 'log-encounter');
    return;
  }

  if (eventName === 'narration') {
    appendNarration(data.text || '');
    return;
  }

  if (eventName === 'error') {
    log(data.message || 'Turn failed.', 'log-error');
    setStatus('Turn failed.');
    return;
  }

  if (eventName === 'end') {
    log('Turn complete.', 'log-encounter');
    setStatus('Turn complete.');
    return;
  }
}

async function runTurn(campaignId, action) {
  if (running) return;
  running = true;
  if (submitButton) submitButton.disabled = true;
  setStatus('Resolving…');
  if (logEl) logEl.textContent = '';
  narrationBlock = null;
  log('> ' + action, 'log-narration');
  startNarration();

  const url = `/play/turn/stream?campaign_id=${encodeURIComponent(campaignId)}`
    + `&action=${encodeURIComponent(action)}&actor=player`;

  try {
    const response = await fetch(url, {
      method: 'GET',
      headers: { 'Accept': 'text/event-stream' },
      credentials: 'same-origin',
      cache: 'no-store'
    });
    if (!response.ok) {
      let message = `HTTP ${response.status}`;
      try {
        const body = await response.json();
        message = body.detail || message;
      } catch (_) {}
      throw new Error(message);
    }
    if (!response.body) throw new Error('Streaming is not supported by this browser.');

    const reader = response.body.getReader();
    const decoder = new TextDecoder();
    let buffer = '';
    while (true) {
      const { value, done } = await reader.read();
      if (done) break;
      buffer += decoder.decode(value, { stream: true }).replace(/\r\n/g, '\n');
      let split;
      while ((split = buffer.indexOf('\n\n')) !== -1) {
        const block = buffer.slice(0, split);
        buffer = buffer.slice(split + 2);
        if (!block.trim()) continue;
        const parsed = parseSSEBlock(block);
        handleEvent(parsed.event, parsed.data);
      }
    }
    if (buffer.trim()) {
      const parsed = parseSSEBlock(buffer);
      handleEvent(parsed.event, parsed.data);
    }
    setStatus('Turn complete. Dashboard refreshed.');
    document.body.dispatchEvent(new CustomEvent('pfg-turn-complete', { bubbles: true }));
  } catch (error) {
    log(`Turn failed: ${error.message}`, 'log-error');
    setStatus('Turn failed.');
  } finally {
    running = false;
    if (submitButton) submitButton.disabled = false;
  }
}

function tokenColor(token) {
  if (token.color) return token.color;
  if (token.kind === 'hero') return '#67c7f2';
  if (token.kind === 'monster') return '#ef6b6b';
  if (token.kind === 'npc') return '#7bd88f';
  if (token.kind === 'loot') return '#ffd54f';
  if (token.kind === 'door') return '#ffb74d';
  if (token.kind === 'trap') return '#ff8a65';
  return '#b0bec5';
}

function drawScene(scene) {
  if (!canvas) return;
  const ctx = canvas.getContext('2d');
  ctx.clearRect(0, 0, canvas.width, canvas.height);
  ctx.fillStyle = '#05070b';
  ctx.fillRect(0, 0, canvas.width, canvas.height);

  if (!scene || !scene.grid) {
    ctx.fillStyle = '#8f9bb1';
    ctx.font = '14px Segoe UI, sans-serif';
    ctx.textAlign = 'center';
    ctx.fillText('No active scene yet.', canvas.width / 2, canvas.height / 2);
    if (sceneLabel) sceneLabel.textContent = 'No active scene';
    return;
  }

  const gw = Math.max(1, scene.grid.w | 0);
  const gh = Math.max(1, scene.grid.h | 0);
  const pad = 14;
  const cell = Math.max(4, Math.min(
    (canvas.width - pad * 2) / gw,
    (canvas.height - pad * 2) / gh
  ));
  const ox = (canvas.width - cell * gw) / 2;
  const oy = (canvas.height - cell * gh) / 2;
  const walkable = Array.isArray(scene.walkable) ? scene.walkable : [];

  for (let y = 0; y < gh; y++) {
    for (let x = 0; x < gw; x++) {
      const row = walkable[y] || [];
      const open = row.length ? !!row[x] : true;
      ctx.fillStyle = open ? '#1b2434' : '#0a0d13';
      ctx.fillRect(ox + x * cell, oy + y * cell, cell - 1, cell - 1);
    }
  }

  for (const door of (scene.doors || [])) {
    ctx.fillStyle = '#ffb74d';
    ctx.fillRect(
      ox + door.x * cell + 2,
      oy + door.y * cell + 2,
      Math.max(2, cell - 4),
      Math.max(2, cell - 4)
    );
  }

  for (const token of (scene.tokens || [])) {
    const cx = ox + token.x * cell + cell / 2;
    const cy = oy + token.y * cell + cell / 2;
    ctx.beginPath();
    ctx.fillStyle = tokenColor(token);
    ctx.arc(cx, cy, Math.max(3, cell * 0.3), 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#080b11';
    ctx.font = `${Math.max(7, Math.floor(cell * 0.33))}px Segoe UI, sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText((token.name || '?').slice(0, 2).toUpperCase(), cx, cy);
  }

  ctx.strokeStyle = '#263249';
  ctx.strokeRect(ox, oy, cell * gw, cell * gh);
  if (sceneLabel) {
    sceneLabel.textContent = `${gw} × ${gh} grid · ${(scene.tokens || []).length} tokens`;
  }
}

function setScene(scene) {
  if (!sceneEl) return;
  sceneEl.dataset.scene = JSON.stringify(scene);
  drawScene(scene);
}

function initialScene() {
  if (!sceneEl) return null;
  const raw = sceneEl.dataset.scene || '';
  if (!raw) return null;
  try {
    return JSON.parse(raw);
  } catch (_) {
    return null;
  }
}

if (form) {
  form.addEventListener('submit', (event) => {
    event.preventDefault();
    const action = (actionInput.value || '').trim();
    if (!action) {
      actionInput.focus();
      return;
    }
    runTurn(form.dataset.campaignId, action);
  });
}

for (const chip of document.querySelectorAll('.chip[data-action]')) {
  chip.addEventListener('click', () => {
    if (!actionInput) return;
    actionInput.value = chip.dataset.action || '';
    actionInput.focus();
  });
}

drawScene(initialScene());
