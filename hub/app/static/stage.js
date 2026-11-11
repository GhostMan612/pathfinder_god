// ============================================================
// As Above, So Below. As Within, So Without.
// The Future Dictates the Past and the Past is Always Present.
// ============================================================
// Minimal encounter-stage island. Three.js is pinned at 0.170.0 (jsDelivr).
import * as THREE from 'https://cdn.jsdelivr.net/npm/three@0.170.0/build/three.module.js';

const THREE_VERSION = '0.170.0';
const mount = document.getElementById('three-mount');
const canvas2d = document.getElementById('grid2d');
const statusEl = document.getElementById('status');
const logEl = document.getElementById('log');
let sceneData = null;
let ws = null;
let renderer = null;
let threeScene = null;
let camera = null;

function campaignId() {
  const n = Number(document.getElementById('campaign-id').value || 1);
  return Number.isFinite(n) && n > 0 ? Math.floor(n) : 1;
}

function apiKey() {
  return (document.getElementById('api-key').value || '').trim();
}

function setStatus(text) { statusEl.textContent = text; }
function log(text) {
  logEl.textContent = text + (logEl.textContent ? '\n' + logEl.textContent : '');
}

function tokenColor(token) {
  if (token.color) return token.color;
  if (token.kind === 'hero') return '#4fc3f7';
  if (token.kind === 'monster') return '#ef5350';
  if (token.kind === 'npc') return '#81c784';
  if (token.kind === 'loot') return '#ffd54f';
  return '#b0bec5';
}

// ── 2D grid ──────────────────────────────────────────────────────────
function draw2d(scene) {
  const ctx = canvas2d.getContext('2d');
  ctx.clearRect(0, 0, canvas2d.width, canvas2d.height);
  if (!scene || !scene.grid) return;
  const gw = Math.max(1, scene.grid.w | 0);
  const gh = Math.max(1, scene.grid.h | 0);
  const pad = 12;
  const cell = Math.max(4, Math.min(
    (canvas2d.width - pad * 2) / gw,
    (canvas2d.height - pad * 2) / gh
  ));
  const ox = (canvas2d.width - cell * gw) / 2;
  const oy = (canvas2d.height - cell * gh) / 2;

  ctx.fillStyle = '#080a0f';
  ctx.fillRect(0, 0, canvas2d.width, canvas2d.height);

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
    ctx.arc(cx, cy, Math.max(3, cell * 0.32), 0, Math.PI * 2);
    ctx.fill();
    ctx.fillStyle = '#0b0d12';
    ctx.font = `${Math.max(7, Math.floor(cell * 0.34))}px ui-sans-serif`;
    ctx.textAlign = 'center';
    ctx.textBaseline = 'middle';
    ctx.fillText((token.name || '?').slice(0, 2).toUpperCase(), cx, cy);
  }

  ctx.strokeStyle = '#2a3142';
  ctx.lineWidth = 1;
  ctx.strokeRect(ox, oy, cell * gw, cell * gh);
}

// ── 3D view ──────────────────────────────────────────────────────────
function initThree() {
  if (renderer) return;
  renderer = new THREE.WebGLRenderer({ antialias: true });
  renderer.setPixelRatio(Math.min(window.devicePixelRatio || 1, 2));
  renderer.setSize(mount.clientWidth || 640, mount.clientHeight || 420, false);
  mount.appendChild(renderer.domElement);

  threeScene = new THREE.Scene();
  threeScene.background = new THREE.Color(0x05070b);
  camera = new THREE.PerspectiveCamera(
    65,
    (mount.clientWidth || 640) / (mount.clientHeight || 420),
    0.05,
    60
  );
  threeScene.add(new THREE.AmbientLight(0xbfc7d8, 0.55));
  const lamp = new THREE.PointLight(0xffd27a, 1.15, 18, 2);
  lamp.position.set(1.5, 3.0, 1.5);
  threeScene.add(lamp);
  window.addEventListener('resize', onResize);
}

function onResize() {
  if (!renderer || !camera) return;
  const w = mount.clientWidth || 640;
  const h = mount.clientHeight || 420;
  renderer.setSize(w, h, false);
  camera.aspect = w / h;
  camera.updateProjectionMatrix();
}

function clearGroup(group) {
  for (const child of [...group.children]) {
    group.remove(child);
    if (child.geometry) child.geometry.dispose();
    if (child.material) child.material.dispose();
  }
}

function renderStage3d(scene) {
  initThree();
  if (!scene || !scene.grid) return;
  let root = threeScene.getObjectByName('stage-root');
  if (!root) {
    root = new THREE.Group();
    root.name = 'stage-root';
    threeScene.add(root);
  }
  clearGroup(root);

  const tile = Number(scene.grid.tile_m || 1.5);
  const spawn = scene.spawn || {};
  const hero = (scene.tokens || []).find(t => t.kind === 'hero') || {};
  const cx = Number(hero.x ?? spawn.x ?? 1) + 0.5;
  const cy = Number(hero.y ?? spawn.y ?? 1) + 0.5;

  // The viewer stands in the character's current 5-ft square.
  camera.position.set(cx * tile, 1.65, cy * tile);
  const exit = scene.exit || spawn;
  camera.lookAt(
    (Number(exit.x ?? cx) + 0.5) * tile,
    1.1,
    (Number(exit.y ?? cy) + 0.5) * tile
  );

  // Local floor: only the patch visible from this square.
  const floorGeo = new THREE.PlaneGeometry(tile * 9, tile * 9, 9, 9);
  const floorMat = new THREE.MeshStandardMaterial({
    color: 0x1a2333,
    roughness: 0.95,
    metalness: 0.02,
    side: THREE.DoubleSide
  });
  const floor = new THREE.Mesh(floorGeo, floorMat);
  floor.rotation.x = -Math.PI / 2;
  floor.position.set(cx * tile, 0, cy * tile);
  root.add(floor);

  const grid = new THREE.GridHelper(tile * 9, 9, 0x33415a, 0x1f2a3d);
  grid.position.set(cx * tile, 0.01, cy * tile);
  root.add(grid);

  // Blocked cells near the viewer are wireframe only.
  const walkable = Array.isArray(scene.walkable) ? scene.walkable : [];
  for (let dy = -4; dy <= 4; dy++) {
    for (let dx = -4; dx <= 4; dx++) {
      const gx = Math.floor(cx) + dx;
      const gy = Math.floor(cy) + dy;
      const row = walkable[gy] || [];
      if (!row.length || row[gx]) continue;
      const box = new THREE.Mesh(
        new THREE.BoxGeometry(tile, 1.8, tile),
        new THREE.MeshBasicMaterial({ color: 0x3a4761, wireframe: true })
      );
      box.position.set((gx + 0.5) * tile, 0.9, (gy + 0.5) * tile);
      root.add(box);
    }
  }

  for (const token of (scene.tokens || [])) {
    const dx = Number(token.x) - cx;
    const dy = Number(token.y) - cy;
    if (Math.abs(dx) > 4 || Math.abs(dy) > 4) continue;
    const mat = new THREE.MeshStandardMaterial({
      color: tokenColor(token),
      roughness: 0.6
    });
    const body = new THREE.Mesh(
      new THREE.CylinderGeometry(tile * 0.22, tile * 0.3, tile * 0.9, 10),
      mat
    );
    body.position.set(
      (Number(token.x) + 0.5) * tile,
      tile * 0.45,
      (Number(token.y) + 0.5) * tile
    );
    root.add(body);
  }

  // Breadcrumb trail: wireframe only. The rest of the world is not built.
  const spawnPoint = scene.spawn || { x: cx - 0.5, y: cy - 0.5 };
  const exitPoint = scene.exit || spawnPoint;
  const points = [
    new THREE.Vector3(
      (Number(spawnPoint.x) + 0.5) * tile,
      0.05,
      (Number(spawnPoint.y) + 0.5) * tile
    ),
    new THREE.Vector3(
      (Number(exitPoint.x) + 0.5) * tile,
      0.05,
      (Number(exitPoint.y) + 0.5) * tile
    )
  ];
  const trail = new THREE.Line(
    new THREE.BufferGeometry().setFromPoints(points),
    new THREE.LineDashedMaterial({
      color: 0xd4af37,
      dashSize: 0.25,
      gapSize: 0.18
    })
  );
  trail.computeLineDistances();
  root.add(trail);

  renderer.render(threeScene, camera);
}

function setScene(scene) {
  sceneData = scene;
  draw2d(scene);
  renderStage3d(scene);
  setStatus(
    `Scene: ${scene?.grid?.w || '?'} × ${scene?.grid?.h || '?'} grid, ` +
    `${(scene?.tokens || []).length} tokens.`
  );
}

// ── transport ────────────────────────────────────────────────────────
function connectStage() {
  const cid = campaignId();
  if (ws) { try { ws.close(); } catch (_) {} }
  const scheme = location.protocol === 'https:' ? 'wss' : 'ws';
  const key = apiKey();
  const url = `${scheme}://${location.host}/stream` +
    (key ? '?api_key=' + encodeURIComponent(key) : '');
  ws = new WebSocket(url);
  ws.onopen = () => {
    setStatus('Connected. Asking the GM for a turn…');
    ws.send(JSON.stringify({
      type: 'turn',
      campaign_id: cid,
      action: 'look around the current encounter',
      actor: 'player'
    }));
  };
  ws.onmessage = (event) => {
    let data;
    try { data = JSON.parse(event.data); } catch (_) { return; }
    if (data.type === 'encounter_stage' && data.scene) {
      setScene(data.scene);
    } else if (data.type === 'chunk' && data.text) {
      log(data.text);
    } else if (data.type === 'error') {
      setStatus('Hub error: ' + (data.message || 'unknown'));
    } else if (data.type === 'end') {
      setStatus('Turn complete.');
    }
  };
  ws.onerror = () => setStatus('WebSocket error.');
  ws.onclose = () => {
    if (ws) setStatus('Disconnected.');
    ws = null;
  };
}

async function fetchScene() {
  const cid = campaignId();
  const headers = { 'Content-Type': 'application/json' };
  const key = apiKey();
  if (key) headers['X-API-Key'] = key;
  setStatus('Fetching the current location scene…');
  try {
    const resp = await fetch('/map/generate', {
      method: 'POST',
      headers,
      body: JSON.stringify({
        prompt: 'current location encounter stage',
        grid_enabled: true,
        campaign_id: cid
      })
    });
    const body = await resp.json();
    if (!resp.ok) throw new Error(body.detail || ('HTTP ' + resp.status));
    if (body.scene) setScene(body.scene);
    else setStatus('No scene returned.');
  } catch (err) {
    setStatus('Fetch failed: ' + err.message);
  }
}

document.getElementById('connect').addEventListener('click', connectStage);
document.getElementById('fetch-scene').addEventListener('click', fetchScene);
draw2d(null);
initThree();
renderer.render(threeScene, camera);
