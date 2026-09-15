import {
  DIRECTIONS,
  GRID_COLS,
  GRID_ROWS,
  LEVEL_CONFIGS,
  createLevel,
  traceArrow,
} from "./engine.js";

const $ = (selector) => document.querySelector(selector);
const canvas = $("#gameCanvas");
const ctx = canvas.getContext("2d");
const boardCard = $("#boardCard");
const startOverlay = $("#startOverlay");
const resultOverlay = $("#resultOverlay");
const toast = $("#toast");

const ui = {
  level: $("#levelValue"), levelName: $("#levelName"), score: $("#scoreValue"), combo: $("#comboValue"),
  comboLabel: $("#comboLabel"), time: $("#timeValue"), lives: $("#livesValue"), status: $("#statusText"),
  chargeNumber: $("#chargeNumber"), chargeFill: $("#chargeFill"), overdrive: $("#overdriveButton"),
  overdriveState: $("#overdriveState"), sectorIndex: $("#sectorIndex"), levelNote: $("#levelNote"),
  remaining: $("#remainingValue"), cleared: $("#clearedValue"), bestCombo: $("#bestComboValue"),
  resultEyebrow: $("#resultEyebrow"), resultTitle: $("#resultTitle"), resultText: $("#resultText"),
  resultScore: $("#resultScore"), resultCombo: $("#resultCombo"), resultTime: $("#resultTime"),
  next: $("#nextButton"), sound: $("#soundButton"), hint: $("#hintButton"), restart: $("#restartButton"),
  start: $("#startButton"),
};

const state = {
  levelIndex: 0,
  level: null,
  active: new Map(),
  score: 0,
  levelStartScore: 0,
  combo: 0,
  bestCombo: 0,
  lives: 4,
  timeLeft: 0,
  charge: 0,
  overdrive: false,
  sound: true,
  status: "ready",
  cleared: 0,
  hoveredId: null,
  flashId: null,
  flashUntil: 0,
  hintId: null,
  hintUntil: 0,
  ghosts: [],
  particles: [],
  roundToken: 0,
  lastFrame: performance.now(),
};

const stars = Array.from({ length: 84 }, (_, index) => ({
  x: ((index * 73) % 997) / 997,
  y: ((index * 151 + 31) % 991) / 991,
  r: 0.35 + ((index * 17) % 13) / 14,
  a: 0.13 + ((index * 29) % 21) / 48,
}));

let metrics = { width: 0, height: 0, cell: 0, ox: 0, oy: 0, dpr: 1 };
let audioContext = null;
let toastTimer = 0;

function ensureAudio() {
  if (!state.sound) return null;
  if (!audioContext) audioContext = new (window.AudioContext || window.webkitAudioContext)();
  if (audioContext.state === "suspended") audioContext.resume();
  return audioContext;
}

function tone(frequency, duration = 0.08, type = "sine", volume = 0.035, delay = 0) {
  const audio = ensureAudio();
  if (!audio) return;
  const oscillator = audio.createOscillator();
  const gain = audio.createGain();
  const start = audio.currentTime + delay;
  oscillator.type = type;
  oscillator.frequency.setValueAtTime(frequency, start);
  gain.gain.setValueAtTime(0.0001, start);
  gain.gain.exponentialRampToValueAtTime(volume, start + 0.012);
  gain.gain.exponentialRampToValueAtTime(0.0001, start + duration);
  oscillator.connect(gain).connect(audio.destination);
  oscillator.start(start);
  oscillator.stop(start + duration + 0.02);
}

function soundSuccess(combo, prism = false) {
  tone(350 + Math.min(combo, 10) * 28, 0.09, "triangle", 0.035);
  tone(prism ? 880 : 620, 0.11, "sine", 0.022, 0.045);
}

function soundError() {
  tone(130, 0.11, "sawtooth", 0.025);
  tone(92, 0.15, "square", 0.012, 0.055);
}

function soundPower() {
  [260, 390, 540, 760].forEach((frequency, index) => tone(frequency, 0.18, "triangle", 0.028, index * 0.05));
}

function showToast(message, toneName = "normal") {
  window.clearTimeout(toastTimer);
  toast.textContent = message;
  toast.className = `toast show${toneName === "danger" ? " danger" : toneName === "gold" ? " gold" : ""}`;
  toastTimer = window.setTimeout(() => { toast.className = "toast"; }, 1350);
}

function resizeCanvas() {
  const rect = canvas.getBoundingClientRect();
  const dpr = Math.min(window.devicePixelRatio || 1, 2);
  const pixelWidth = Math.max(1, Math.round(rect.width * dpr));
  const pixelHeight = Math.max(1, Math.round(rect.height * dpr));
  if (canvas.width !== pixelWidth || canvas.height !== pixelHeight) {
    canvas.width = pixelWidth;
    canvas.height = pixelHeight;
  }
  const cell = Math.min((rect.width - 90) / (GRID_COLS - 1), (rect.height - 86) / (GRID_ROWS - 1));
  metrics = {
    width: rect.width,
    height: rect.height,
    cell,
    ox: (rect.width - cell * (GRID_COLS - 1)) / 2,
    oy: (rect.height - cell * (GRID_ROWS - 1)) / 2,
    dpr,
  };
}

function point(cell) {
  return { x: metrics.ox + cell.x * metrics.cell, y: metrics.oy + cell.y * metrics.cell };
}

function withCanvasScale(callback) {
  ctx.save();
  ctx.setTransform(metrics.dpr, 0, 0, metrics.dpr, 0, 0);
  callback();
  ctx.restore();
}

function drawBackdrop(now) {
  ctx.clearRect(0, 0, metrics.width, metrics.height);
  const glow = ctx.createRadialGradient(metrics.width * 0.52, metrics.height * 0.47, 8, metrics.width * 0.52, metrics.height * 0.47, metrics.width * 0.58);
  glow.addColorStop(0, "rgba(72, 89, 190, 0.09)");
  glow.addColorStop(0.55, "rgba(35, 242, 255, 0.018)");
  glow.addColorStop(1, "rgba(2, 4, 14, 0)");
  ctx.fillStyle = glow;
  ctx.fillRect(0, 0, metrics.width, metrics.height);

  for (const star of stars) {
    const pulse = 0.65 + Math.sin(now * 0.0012 + star.x * 18) * 0.35;
    ctx.globalAlpha = star.a * pulse;
    ctx.fillStyle = "#b9c6ff";
    ctx.beginPath();
    ctx.arc(star.x * metrics.width, star.y * metrics.height, star.r, 0, Math.PI * 2);
    ctx.fill();
  }
  ctx.globalAlpha = 1;

  ctx.strokeStyle = "rgba(113, 137, 219, 0.055)";
  ctx.lineWidth = 1;
  for (let x = 0; x < GRID_COLS; x += 1) {
    const px = metrics.ox + x * metrics.cell;
    ctx.beginPath(); ctx.moveTo(px, metrics.oy); ctx.lineTo(px, metrics.oy + metrics.cell * (GRID_ROWS - 1)); ctx.stroke();
  }
  for (let y = 0; y < GRID_ROWS; y += 1) {
    const py = metrics.oy + y * metrics.cell;
    ctx.beginPath(); ctx.moveTo(metrics.ox, py); ctx.lineTo(metrics.ox + metrics.cell * (GRID_COLS - 1), py); ctx.stroke();
  }
  for (let y = 0; y < GRID_ROWS; y += 1) {
    for (let x = 0; x < GRID_COLS; x += 1) {
      const p = point({ x, y });
      ctx.fillStyle = "rgba(137, 163, 255, 0.2)";
      ctx.beginPath(); ctx.arc(p.x, p.y, Math.max(1.15, metrics.cell * 0.025), 0, Math.PI * 2); ctx.fill();
    }
  }
}

function drawGate(gate, now) {
  const p = point(gate);
  const size = metrics.cell * 0.58;
  const rotation = now * 0.0007 * (gate.turn === "cw" ? 1 : -1);
  ctx.save();
  ctx.translate(p.x, p.y);
  ctx.rotate(rotation);
  ctx.shadowColor = "#8b7cff";
  ctx.shadowBlur = 14;
  ctx.strokeStyle = "rgba(139, 124, 255, 0.86)";
  ctx.lineWidth = Math.max(1.5, metrics.cell * 0.035);
  ctx.setLineDash([size * 0.18, size * 0.12]);
  ctx.strokeRect(-size / 2, -size / 2, size, size);
  ctx.rotate(Math.PI / 4);
  ctx.strokeStyle = "rgba(53, 242, 255, 0.44)";
  ctx.strokeRect(-size * 0.31, -size * 0.31, size * 0.62, size * 0.62);
  ctx.restore();
  ctx.setLineDash([]);
}

function arrowPolyline(arrow) {
  if (arrow.cells.length > 1) return arrow.cells.map(point);
  const head = point(arrow.head);
  const vector = DIRECTIONS[arrow.dir];
  return [
    { x: head.x - vector.x * metrics.cell * 0.48, y: head.y - vector.y * metrics.cell * 0.48 },
    head,
  ];
}

function drawArrow(arrow, now, alpha = 1) {
  const points = arrowPolyline(arrow);
  const isHover = state.hoveredId === arrow.id;
  const isFlash = state.flashId === arrow.id && now < state.flashUntil;
  const isHint = state.hintId === arrow.id && now < state.hintUntil;
  const color = isFlash ? "#ff5f7f" : isHint ? "#ffc857" : arrow.color;
  const pulse = isHint ? 1 + Math.sin(now * 0.012) * 0.16 : 1;
  ctx.save();
  ctx.globalAlpha = alpha;
  ctx.lineCap = "round";
  ctx.lineJoin = "round";
  ctx.shadowColor = color;
  ctx.shadowBlur = (isHover || isHint ? 19 : 10) * pulse;
  ctx.strokeStyle = color;
  ctx.lineWidth = metrics.cell * (isHover ? 0.2 : 0.16) * pulse;
  ctx.beginPath();
  points.forEach((p, index) => index ? ctx.lineTo(p.x, p.y) : ctx.moveTo(p.x, p.y));
  ctx.stroke();

  const head = point(arrow.head);
  const direction = DIRECTIONS[arrow.dir];
  const tip = metrics.cell * 0.34 * pulse;
  ctx.translate(head.x, head.y);
  ctx.rotate(direction.angle);
  ctx.fillStyle = color;
  ctx.beginPath();
  ctx.moveTo(tip, 0);
  ctx.lineTo(-tip * 0.58, tip * 0.68);
  ctx.lineTo(-tip * 0.58, -tip * 0.68);
  ctx.closePath();
  ctx.fill();
  if (arrow.prism) {
    ctx.strokeStyle = "#fff0a6";
    ctx.lineWidth = Math.max(1, metrics.cell * 0.026);
    ctx.shadowColor = "#ffc857";
    ctx.shadowBlur = 12;
    ctx.rotate(Math.PI / 4);
    const diamond = metrics.cell * 0.2;
    ctx.strokeRect(-diamond / 2, -diamond / 2, diamond, diamond);
  }
  ctx.restore();
}

function drawGhosts(now) {
  state.ghosts = state.ghosts.filter((ghost) => now - ghost.start < 500);
  for (const ghost of state.ghosts) {
    const age = (now - ghost.start) / 500;
    ctx.save();
    ctx.globalAlpha = (1 - age) * 0.7;
    ctx.strokeStyle = ghost.arrow.color;
    ctx.shadowColor = ghost.arrow.color;
    ctx.shadowBlur = 18;
    ctx.lineWidth = Math.max(2, metrics.cell * 0.09 * (1 - age * 0.5));
    ctx.lineCap = "round";
    ctx.beginPath();
    const start = point(ghost.arrow.head);
    ctx.moveTo(start.x, start.y);
    const visible = Math.max(1, Math.ceil(ghost.trace.path.length * Math.min(1, age * 1.8)));
    ghost.trace.path.slice(0, visible).forEach((cell) => {
      const p = point(cell); ctx.lineTo(p.x, p.y);
    });
    const exit = point(ghost.trace.exit);
    if (age > 0.7) ctx.lineTo(exit.x, exit.y);
    ctx.stroke();
    ctx.restore();
  }
}

function emitParticles(arrow, amount = 12) {
  const origin = point(arrow.head);
  for (let index = 0; index < amount; index += 1) {
    const angle = (Math.PI * 2 * index) / amount + Math.random() * 0.35;
    const speed = 18 + Math.random() * 46;
    state.particles.push({
      x: origin.x, y: origin.y,
      vx: Math.cos(angle) * speed, vy: Math.sin(angle) * speed,
      life: 0.55 + Math.random() * 0.4, age: 0, color: arrow.prism ? "#ffc857" : arrow.color,
    });
  }
}

function drawParticles(dt) {
  state.particles = state.particles.filter((particle) => particle.age < particle.life);
  for (const particle of state.particles) {
    particle.age += dt;
    particle.x += particle.vx * dt;
    particle.y += particle.vy * dt;
    particle.vx *= 0.985;
    particle.vy *= 0.985;
    const alpha = Math.max(0, 1 - particle.age / particle.life);
    ctx.globalAlpha = alpha;
    ctx.fillStyle = particle.color;
    ctx.shadowColor = particle.color;
    ctx.shadowBlur = 8;
    ctx.beginPath(); ctx.arc(particle.x, particle.y, 1.2 + alpha * 1.5, 0, Math.PI * 2); ctx.fill();
  }
  ctx.globalAlpha = 1;
  ctx.shadowBlur = 0;
}

function formatScore(value) {
  return Math.max(0, Math.round(value)).toString().padStart(6, "0");
}

function updateHud() {
  const config = state.level?.config ?? LEVEL_CONFIGS[state.levelIndex];
  const total = state.level?.arrows.length ?? config.target;
  ui.level.textContent = `${String(state.levelIndex + 1).padStart(2, "0")} / ${String(LEVEL_CONFIGS.length).padStart(2, "0")}`;
  ui.levelName.textContent = config.name;
  ui.score.textContent = formatScore(state.score);
  ui.combo.textContent = `×${state.combo}`;
  ui.comboLabel.textContent = state.combo >= 8 ? "超导连击" : state.combo >= 4 ? "节奏升温" : "保持节奏";
  ui.time.textContent = Math.max(0, state.timeLeft).toFixed(1);
  ui.time.style.color = state.timeLeft <= 15 && state.status === "playing" ? "#ff6b8b" : "";
  ui.lives.textContent = `${"◆ ".repeat(Math.max(0, state.lives)).trim()}${state.lives < config.lives ? `  ${"◇ ".repeat(config.lives - state.lives).trim()}` : ""}`;
  ui.lives.setAttribute("aria-label", `剩余 ${state.lives} 点稳定度`);
  ui.chargeNumber.textContent = `${Math.round(state.charge)}%`;
  ui.chargeFill.style.width = `${Math.min(100, state.charge)}%`;
  ui.sectorIndex.textContent = String(state.levelIndex + 1).padStart(2, "0");
  ui.levelNote.textContent = config.note;
  ui.remaining.textContent = String(state.active.size);
  ui.cleared.textContent = String(state.cleared);
  ui.bestCombo.textContent = `×${state.bestCombo}`;

  if (state.overdrive) {
    ui.overdrive.disabled = false;
    ui.overdrive.classList.add("active");
    ui.overdrive.classList.remove("ready");
    ui.overdriveState.textContent = "已激活 · 点击受阻箭路";
  } else if (state.charge >= 100 && state.status === "playing") {
    ui.overdrive.disabled = false;
    ui.overdrive.classList.add("ready");
    ui.overdrive.classList.remove("active");
    ui.overdriveState.textContent = "能量充满 · 可以启动";
  } else {
    ui.overdrive.disabled = true;
    ui.overdrive.classList.remove("ready", "active");
    ui.overdriveState.textContent = "能量未充满";
  }

  ui.hint.disabled = state.status !== "playing" || state.active.size === 0;
}

function setStatus(text) {
  ui.status.textContent = text;
}

function prepareLevel(index, { autoStart = false, resetCampaign = false } = {}) {
  state.roundToken += 1;
  if (resetCampaign) state.score = 0;
  state.levelIndex = index;
  state.level = createLevel(index);
  state.active = new Map(state.level.arrows.map((arrow) => [arrow.id, arrow]));
  state.levelStartScore = state.score;
  state.combo = 0;
  state.bestCombo = 0;
  state.lives = state.level.config.lives;
  state.timeLeft = state.level.config.time;
  state.charge = 0;
  state.overdrive = false;
  state.cleared = 0;
  state.hoveredId = null;
  state.flashId = null;
  state.hintId = null;
  state.ghosts = [];
  state.particles = [];
  state.status = autoStart ? "playing" : "ready";
  resultOverlay.classList.remove("show");
  if (autoStart) startOverlay.classList.remove("show");
  setStatus(autoStart ? "箭域同步中" : "等待同步");
  updateHud();
}

function startGame() {
  if (state.status === "playing") return;
  ensureAudio();
  if (state.status !== "ready") prepareLevel(state.levelIndex, { autoStart: false });
  state.status = "playing";
  state.lastFrame = performance.now();
  startOverlay.classList.remove("show");
  resultOverlay.classList.remove("show");
  setStatus("箭域同步中");
  tone(320, 0.12, "triangle", 0.025);
  tone(560, 0.15, "sine", 0.02, 0.06);
  updateHud();
  canvas.focus({ preventScroll: true });
}

function restartLevel() {
  const wasReady = state.status === "ready";
  state.score = state.levelStartScore;
  prepareLevel(state.levelIndex, { autoStart: !wasReady });
  if (wasReady) startOverlay.classList.add("show");
  showToast("当前扇区已重新校准");
}

function finishLevel() {
  if (state.status === "result") return;
  state.status = "result";
  const timeBonus = Math.max(0, Math.round(state.timeLeft * 28));
  state.score += timeBonus;
  const levelScore = state.score - state.levelStartScore;
  ui.resultEyebrow.textContent = state.levelIndex === LEVEL_CONFIGS.length - 1 ? "NEXUS STABILIZED" : "SECTOR CLEARED";
  ui.resultTitle.textContent = state.levelIndex === LEVEL_CONFIGS.length - 1 ? "奇点完全稳定" : "箭域已清空";
  ui.resultText.textContent = state.levelIndex === LEVEL_CONFIGS.length - 1
    ? "三座扇区全部完成，折光网络已经恢复稳定。"
    : `${state.level.config.name} 已完成，下一扇区将引入更复杂的箭路。`;
  ui.resultScore.textContent = `+${levelScore}`;
  ui.resultCombo.textContent = `×${state.bestCombo}`;
  ui.resultTime.textContent = `+${timeBonus}`;
  ui.next.textContent = state.levelIndex === LEVEL_CONFIGS.length - 1 ? "重新挑战全程" : "进入下一扇区";
  ui.next.dataset.action = state.levelIndex === LEVEL_CONFIGS.length - 1 ? "campaign" : "next";
  setStatus("扇区已清空");
  soundPower();
  updateHud();
  window.setTimeout(() => resultOverlay.classList.add("show"), 260);
}

function failLevel(reason) {
  if (!["playing", "clearing"].includes(state.status)) return;
  state.status = "failed";
  state.combo = 0;
  ui.resultEyebrow.textContent = "SYNC INTERRUPTED";
  ui.resultTitle.textContent = "箭域同步失败";
  ui.resultText.textContent = reason;
  ui.resultScore.textContent = `+${Math.max(0, state.score - state.levelStartScore)}`;
  ui.resultCombo.textContent = `×${state.bestCombo}`;
  ui.resultTime.textContent = "+0";
  ui.next.textContent = "重新挑战本关";
  ui.next.dataset.action = "retry";
  setStatus("同步中断");
  soundError();
  updateHud();
  resultOverlay.classList.add("show");
}

function clearArrow(arrow, trace, { phased = false } = {}) {
  if (!state.active.has(arrow.id)) return;
  state.active.delete(arrow.id);
  state.ghosts.push({ arrow, trace, start: performance.now() });
  state.combo += 1;
  state.bestCombo = Math.max(state.bestCombo, state.combo);
  state.cleared += 1;

  const comboBonus = Math.min(260, state.combo * 22);
  const prismBonus = arrow.prism ? 160 : 0;
  const phaseBonus = phased ? 220 : 0;
  state.score += 100 + comboBonus + prismBonus + phaseBonus;
  if (!phased) {
    state.charge = Math.min(100, state.charge + 12 + Math.min(state.combo * 1.7, 12) + (arrow.prism ? 18 : 0));
  }

  emitParticles(arrow, arrow.prism ? 22 : 13);
  soundSuccess(state.combo, arrow.prism);
  if (arrow.prism) showToast("棱镜共振 · 量子能量增幅", "gold");
  else if (state.combo === 5) showToast("5 连击 · 能量流升温");
  else if (state.combo === 10) showToast("10 连击 · 超导节奏", "gold");

  if (state.active.size === 0) {
    state.status = "clearing";
    const token = state.roundToken;
    window.setTimeout(() => { if (token === state.roundToken) finishLevel(); }, 480);
  }
  updateHud();
}

function chooseArrow(id) {
  if (state.status !== "playing") return false;
  const arrow = state.active.get(id);
  if (!arrow) return false;
  const activeArrows = [...state.active.values()];
  const trace = traceArrow(arrow, activeArrows, state.level.config.gates);

  if (trace.clear) {
    clearArrow(arrow, trace);
    return true;
  }

  if (state.overdrive) {
    const phaseTrace = {
      ...trace,
      clear: true,
      exit: trace.path.length ? trace.path[trace.path.length - 1] : arrow.head,
    };
    state.overdrive = false;
    state.charge = 0;
    clearArrow(arrow, phaseTrace, { phased: true });
    showToast("相位穿透 · 阻挡已无效", "gold");
    soundPower();
    return true;
  }

  state.lives -= 1;
  state.combo = 0;
  state.flashId = arrow.id;
  state.flashUntil = performance.now() + 520;
  boardCard.classList.remove("shake");
  void boardCard.offsetWidth;
  boardCard.classList.add("shake");
  showToast(trace.loop ? "折光回路锁死 · 换一条箭路" : "路径受阻 · 稳定度 -1", "danger");
  soundError();
  updateHud();
  if (state.lives <= 0) failLevel("连续碰撞耗尽了稳定度。重新观察箭头前方的完整飞行路径。 ");
  return false;
}

function useOverdrive() {
  if (state.status !== "playing" || state.charge < 100 || state.overdrive) return;
  state.overdrive = true;
  showToast("量子超载已就绪 · 可穿透一条受阻箭路", "gold");
  soundPower();
  updateHud();
}

function useHint() {
  if (state.status !== "playing") return;
  const activeArrows = [...state.active.values()];
  const id = state.level.solutionOrder.find((candidateId) => {
    const arrow = state.active.get(candidateId);
    return arrow && traceArrow(arrow, activeArrows, state.level.config.gates).clear;
  });
  if (!id) {
    showToast("当前没有可直接离场的箭路", "danger");
    return;
  }
  state.score = Math.max(0, state.score - 120);
  state.hintId = id;
  state.hintUntil = performance.now() + 2200;
  showToast("安全箭路已标记 · 积分 -120");
  tone(720, 0.11, "sine", 0.025);
  updateHud();
}

function distanceToSegment(px, py, ax, ay, bx, by) {
  const abx = bx - ax;
  const aby = by - ay;
  const lengthSq = abx * abx + aby * aby;
  if (!lengthSq) return Math.hypot(px - ax, py - ay);
  const t = Math.max(0, Math.min(1, ((px - ax) * abx + (py - ay) * aby) / lengthSq));
  return Math.hypot(px - (ax + t * abx), py - (ay + t * aby));
}

function hitTest(clientX, clientY) {
  const rect = canvas.getBoundingClientRect();
  const x = clientX - rect.left;
  const y = clientY - rect.top;
  const arrows = [...state.active.values()].reverse();
  let nearest = null;
  let nearestDistance = Infinity;
  for (const arrow of arrows) {
    const points = arrowPolyline(arrow);
    for (let index = 0; index < points.length - 1; index += 1) {
      const distance = distanceToSegment(x, y, points[index].x, points[index].y, points[index + 1].x, points[index + 1].y);
      if (distance < metrics.cell * 0.34 && distance < nearestDistance) {
        nearest = arrow.id;
        nearestDistance = distance;
      }
    }
    const head = point(arrow.head);
    const headDistance = Math.hypot(x - head.x, y - head.y);
    if (headDistance < metrics.cell * 0.42 && headDistance < nearestDistance) {
      nearest = arrow.id;
      nearestDistance = headDistance;
    }
  }
  return nearest;
}

function render(now, dt) {
  resizeCanvas();
  withCanvasScale(() => {
    drawBackdrop(now);
    state.level?.config.gates.forEach((gate) => drawGate(gate, now));
    for (const arrow of state.active.values()) drawArrow(arrow, now);
    drawGhosts(now);
    drawParticles(dt);
  });
}

function frame(now) {
  const dt = Math.min(0.05, Math.max(0, (now - state.lastFrame) / 1000));
  state.lastFrame = now;
  if (state.status === "playing") {
    state.timeLeft -= dt;
    if (state.timeLeft <= 0) {
      state.timeLeft = 0;
      failLevel("倒计时归零。优先寻找靠近边界且飞行射线没有阻挡的箭路。");
    }
    updateHud();
  }
  if (state.hintId && now >= state.hintUntil) state.hintId = null;
  if (state.flashId && now >= state.flashUntil) state.flashId = null;
  render(now, dt);
  requestAnimationFrame(frame);
}

canvas.addEventListener("pointermove", (event) => {
  state.hoveredId = state.status === "playing" ? hitTest(event.clientX, event.clientY) : null;
});
canvas.addEventListener("pointerleave", () => { state.hoveredId = null; });
canvas.addEventListener("pointerdown", (event) => {
  if (state.status !== "playing") return;
  event.preventDefault();
  const id = hitTest(event.clientX, event.clientY);
  if (id) chooseArrow(id);
});

ui.start.addEventListener("click", startGame);
ui.restart.addEventListener("click", restartLevel);
ui.hint.addEventListener("click", useHint);
ui.overdrive.addEventListener("click", useOverdrive);
ui.sound.addEventListener("click", () => {
  state.sound = !state.sound;
  ui.sound.classList.toggle("muted", !state.sound);
  ui.sound.setAttribute("aria-pressed", String(state.sound));
  if (state.sound) tone(420, 0.08, "sine", 0.025);
});
ui.next.addEventListener("click", () => {
  const action = ui.next.dataset.action;
  if (action === "retry") {
    state.score = state.levelStartScore;
    prepareLevel(state.levelIndex, { autoStart: true });
  } else if (action === "campaign") {
    prepareLevel(0, { autoStart: false, resetCampaign: true });
    startOverlay.classList.add("show");
  } else {
    prepareLevel(state.levelIndex + 1, { autoStart: true });
  }
  ensureAudio();
});

window.addEventListener("keydown", (event) => {
  if (event.repeat) return;
  const key = event.key.toLowerCase();
  if (event.key === "Enter" && state.status === "ready") startGame();
  else if (key === "r") restartLevel();
  else if (key === "h") useHint();
  else if (key === "o") useOverdrive();
});

window.addEventListener("resize", resizeCanvas);

window.__NEON_ARROW_GAME__ = {
  getState: () => ({
    levelIndex: state.levelIndex,
    status: state.status,
    score: state.score,
    combo: state.combo,
    lives: state.lives,
    timeLeft: state.timeLeft,
    charge: state.charge,
    remaining: state.active.size,
  }),
  start: startGame,
  restart: restartLevel,
  clickArrow: chooseArrow,
  getSolution: () => state.level.solutionOrder.filter((id) => state.active.has(id)),
  solveCurrentLevel: () => {
    if (state.status === "ready") startGame();
    const ids = state.level.solutionOrder.filter((id) => state.active.has(id));
    for (const id of ids) {
      if (state.status !== "playing") break;
      chooseArrow(id);
    }
    return state.active.size;
  },
  hitBlockedArrow: () => {
    if (state.status === "ready") startGame();
    const activeArrows = [...state.active.values()];
    const arrow = activeArrows.find((candidate) => !traceArrow(candidate, activeArrows, state.level.config.gates).clear);
    if (!arrow) return false;
    chooseArrow(arrow.id);
    return true;
  },
};

prepareLevel(0, { autoStart: false, resetCampaign: true });
resizeCanvas();
requestAnimationFrame(frame);
