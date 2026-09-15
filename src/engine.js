export const GRID_COLS = 9;
export const GRID_ROWS = 12;

export const DIRECTIONS = {
  up: { x: 0, y: -1, angle: -Math.PI / 2 },
  right: { x: 1, y: 0, angle: 0 },
  down: { x: 0, y: 1, angle: Math.PI / 2 },
  left: { x: -1, y: 0, angle: Math.PI },
};

export const LEVEL_CONFIGS = [
  {
    name: "星潮启航",
    seed: 0x51a7c0de,
    target: 20,
    time: 82,
    lives: 4,
    gates: [],
    note: "熟悉箭路、连击与量子超载。",
  },
  {
    name: "折光回廊",
    seed: 0x7f42b19d,
    target: 26,
    time: 88,
    lives: 4,
    gates: [
      { x: 4, y: 3, turn: "cw" },
      { x: 4, y: 8, turn: "ccw" },
    ],
    note: "光门会把飞行方向旋转 90°。",
  },
  {
    name: "极光奇点",
    seed: 0xc0ffee42,
    target: 32,
    time: 96,
    lives: 4,
    gates: [
      { x: 2, y: 4, turn: "cw" },
      { x: 6, y: 4, turn: "ccw" },
      { x: 4, y: 8, turn: "cw" },
    ],
    note: "高密度箭阵与三重折光门的最终挑战。",
  },
];

const COLORS = ["#35f2ff", "#ff4fd8", "#8b7cff", "#79ffb7", "#ffc857", "#ff6b8b"];
const DIR_NAMES = Object.keys(DIRECTIONS);
const keyOf = (x, y) => `${x},${y}`;

function inBounds(x, y) {
  return x >= 0 && x < GRID_COLS && y >= 0 && y < GRID_ROWS;
}

function mulberry32(seed) {
  let value = seed >>> 0;
  return () => {
    value += 0x6d2b79f5;
    let t = value;
    t = Math.imul(t ^ (t >>> 15), t | 1);
    t ^= t + Math.imul(t ^ (t >>> 7), t | 61);
    return ((t ^ (t >>> 14)) >>> 0) / 4294967296;
  };
}

function turnDirection(dirName, turn) {
  const order = ["up", "right", "down", "left"];
  const index = order.indexOf(dirName);
  const delta = turn === "cw" ? 1 : -1;
  return order[(index + delta + order.length) % order.length];
}

function gateMap(gates) {
  return new Map(gates.map((gate) => [keyOf(gate.x, gate.y), gate]));
}

export function traceRay({ head, dir, occupied = new Map(), gates = [] }) {
  const gatesByCell = gateMap(gates);
  const path = [];
  const seen = new Set();
  let direction = dir;
  let x = head.x;
  let y = head.y;

  for (let step = 0; step < GRID_COLS * GRID_ROWS * 2; step += 1) {
    const vector = DIRECTIONS[direction];
    x += vector.x;
    y += vector.y;

    if (!inBounds(x, y)) {
      return { clear: true, path, exit: { x, y }, dir: direction };
    }

    const loopKey = `${x},${y},${direction}`;
    if (seen.has(loopKey)) {
      return { clear: false, path, loop: true, blockerId: null };
    }
    seen.add(loopKey);

    const cellKey = keyOf(x, y);
    const blockerId = occupied.get(cellKey);
    path.push({ x, y, dir: direction });
    if (blockerId) {
      return { clear: false, path, blockerId, loop: false };
    }

    const gate = gatesByCell.get(cellKey);
    if (gate) {
      direction = turnDirection(direction, gate.turn);
      path[path.length - 1].gate = gate.turn;
      path[path.length - 1].dirAfter = direction;
    }
  }

  return { clear: false, path, loop: true, blockerId: null };
}

export function buildOccupied(arrows, excludeId = null) {
  const occupied = new Map();
  for (const arrow of arrows) {
    if (arrow.id === excludeId) continue;
    for (const cell of arrow.cells) occupied.set(keyOf(cell.x, cell.y), arrow.id);
  }
  return occupied;
}

export function traceArrow(arrow, arrows, gates = []) {
  return traceRay({
    head: arrow.head,
    dir: arrow.dir,
    occupied: buildOccupied(arrows, arrow.id),
    gates,
  });
}

function chooseBodyCells(head, dirName, length, occupied, reserved, random) {
  const forward = DIRECTIONS[dirName];
  const initial = { x: -forward.x, y: -forward.y };
  const cellsFromHead = [{ ...head }];
  let previous = { ...head };
  let travel = initial;

  for (let index = 1; index < length; index += 1) {
    const left = { x: -travel.y, y: travel.x };
    const right = { x: travel.y, y: -travel.x };
    const options = index === 1
      ? [travel, travel, left, right]
      : [travel, travel, travel, left, right];
    let placed = false;

    for (let tryIndex = 0; tryIndex < options.length + 3; tryIndex += 1) {
      const option = options[Math.floor(random() * options.length)];
      const candidate = { x: previous.x + option.x, y: previous.y + option.y };
      const candidateKey = keyOf(candidate.x, candidate.y);
      if (!inBounds(candidate.x, candidate.y)) continue;
      if (occupied.has(candidateKey) || reserved.has(candidateKey)) continue;
      if (cellsFromHead.some((cell) => cell.x === candidate.x && cell.y === candidate.y)) continue;
      cellsFromHead.push(candidate);
      previous = candidate;
      travel = option;
      placed = true;
      break;
    }

    if (!placed) break;
  }

  return cellsFromHead.reverse();
}

function generateCandidate({ id, occupied, reserved, gates, random }) {
  const head = {
    x: Math.floor(random() * GRID_COLS),
    y: Math.floor(random() * GRID_ROWS),
  };
  const headKey = keyOf(head.x, head.y);
  if (occupied.has(headKey) || reserved.has(headKey)) return null;

  const dir = DIR_NAMES[Math.floor(random() * DIR_NAMES.length)];
  const ray = traceRay({ head, dir, occupied, gates });
  if (!ray.clear) return null;

  const requestedLength = 1 + Math.floor(random() * 4);
  const cells = chooseBodyCells(head, dir, requestedLength, occupied, reserved, random);
  if (!cells.length) return null;

  return {
    id: `a${id}`,
    cells,
    head: { ...head },
    dir,
    color: COLORS[id % COLORS.length],
    prism: id % 7 === 0,
  };
}

export function createLevel(levelIndex = 0) {
  const config = LEVEL_CONFIGS[levelIndex] ?? LEVEL_CONFIGS[0];
  const random = mulberry32(config.seed);
  const reserved = new Set(config.gates.map((gate) => keyOf(gate.x, gate.y)));
  const occupied = new Map();
  const constructionOrder = [];
  let attempts = 0;

  while (constructionOrder.length < config.target && attempts < 18000) {
    attempts += 1;
    const candidate = generateCandidate({
      id: constructionOrder.length + 1,
      occupied,
      reserved,
      gates: config.gates,
      random,
    });
    if (!candidate) continue;

    for (const cell of candidate.cells) occupied.set(keyOf(cell.x, cell.y), candidate.id);
    constructionOrder.push(candidate);
  }

  if (constructionOrder.length < Math.floor(config.target * 0.75)) {
    throw new Error(`Level ${levelIndex + 1} generation failed: only ${constructionOrder.length} arrows.`);
  }

  const arrows = constructionOrder.map((arrow) => ({
    ...arrow,
    cells: arrow.cells.map((cell) => ({ ...cell })),
  }));
  const solutionOrder = [...constructionOrder].reverse().map((arrow) => arrow.id);
  return {
    index: levelIndex,
    config: { ...config, gates: config.gates.map((gate) => ({ ...gate })) },
    arrows,
    solutionOrder,
  };
}

export function isSolutionValid(level) {
  const remaining = level.arrows.map((arrow) => ({
    ...arrow,
    cells: arrow.cells.map((cell) => ({ ...cell })),
  }));

  for (const id of level.solutionOrder) {
    const arrow = remaining.find((item) => item.id === id);
    if (!arrow) return false;
    const trace = traceArrow(arrow, remaining, level.config.gates);
    if (!trace.clear) return false;
    const index = remaining.findIndex((item) => item.id === id);
    remaining.splice(index, 1);
  }
  return remaining.length === 0;
}

export function countInitiallyBlocked(level) {
  return level.arrows.filter((arrow) => !traceArrow(arrow, level.arrows, level.config.gates).clear).length;
}
