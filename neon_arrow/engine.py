from __future__ import annotations

from copy import deepcopy
import random
import secrets
from typing import Any

GRID_COLS = 13
GRID_ROWS = 16

DIRECTIONS: dict[str, dict[str, int | float]] = {
    "up": {"x": 0, "y": -1, "angle": -1.5707963267948966},
    "right": {"x": 1, "y": 0, "angle": 0.0},
    "down": {"x": 0, "y": 1, "angle": 1.5707963267948966},
    "left": {"x": -1, "y": 0, "angle": 3.141592653589793},
}

LEVEL_CONFIGS: list[dict[str, Any]] = [
    {
        "name": "星潮启航",
        "difficulty": "简单",
        "difficulty_key": "easy",
        "seed_salt": 0x51A7C0DE,
        "target_range": (18, 22),
        "time_range": (98, 110),
        "lives": 5,
        "gates": [],
        "portals": [],
        "phase_locks": [],
        "note": "先熟悉箭路判断、连击和棱镜充能。",
    },
    {
        "name": "折光回廊",
        "difficulty": "中等",
        "difficulty_key": "medium",
        "seed_salt": 0x7F42B19D,
        "target_range": (27, 32),
        "time_range": (106, 120),
        "lives": 4,
        "gates": [
            {"x": 3, "y": 3, "turn": "cw"},
            {"x": 8, "y": 9, "turn": "ccw"},
        ],
        "portals": [],
        "phase_locks": [],
        "note": "折光门会把射线旋转 90°，不能只看箭头附近。",
    },
    {
        "name": "终焉奇点",
        "difficulty": "终极困难",
        "difficulty_key": "hard",
        "seed_salt": 0xC0FFEE42,
        "target_range": (38, 42),
        "time_range": (120, 136),
        "lives": 2,
        "gates": [
            {"x": 2, "y": 4, "turn": "cw"},
            {"x": 9, "y": 3, "turn": "ccw"},
            {"x": 5, "y": 7, "turn": "flip"},
            {"x": 9, "y": 11, "turn": "cw"},
            {"x": 6, "y": 12, "turn": "flip"},
        ],
        "portals": [
            {"id": "A", "a": {"x": 1, "y": 1}, "b": {"x": 10, "y": 13}},
            {"id": "B", "a": {"x": 10, "y": 5}, "b": {"x": 1, "y": 12}},
        ],
        "phase_locks": [
            {"id": "P1", "x": 4, "y": 2, "unlock_remaining": 30},
            {"id": "P2", "x": 7, "y": 9, "unlock_remaining": 20},
            {"id": "P3", "x": 3, "y": 13, "unlock_remaining": 11},
        ],
        "min_boundary_steps": 1,
        "min_phase_affected": 1,
        "note": "双跃迁、折光/反相与三道相位锁叠加；相位锁会随剩余箭数分阶段解除。",
    },
]

# 作业题目的原始规则单独保留为“基础模式”。基础模式中的每支箭只占
# 一个逻辑格，碰撞只看箭头朝向到棋盘边界之间是否存在其它箭；多格
# 箭身、折光/反相、跃迁和相位锁只属于进阶模式，不能拿来替代基础规则。
BASIC_LEVEL_CONFIGS: list[dict[str, Any]] = [
    {
        "name": "基础航线",
        "difficulty": "简单",
        "difficulty_key": "easy",
        "seed_salt": 0x13572468,
        "target_range": (18, 22),
        "time_range": (95, 110),
        "lives": 3,
        "note": "单格四方向箭头，只判断同一行或同一列到边界的直线路径。",
    },
    {
        "name": "密集航线",
        "difficulty": "中等",
        "difficulty_key": "medium",
        "seed_salt": 0x24681357,
        "target_range": (28, 34),
        "time_range": (105, 122),
        "lives": 3,
        "note": "仍是作业原始单格规则，但箭头更密集、可选路径更容易互相遮挡。",
    },
    {
        "name": "极限航线",
        "difficulty": "终极困难",
        "difficulty_key": "hard",
        "seed_salt": 0x10293847,
        "target_range": (40, 48),
        "time_range": (118, 136),
        "lives": 3,
        "note": "高密度单格箭阵；规则不加机关，难度完全来自方向判断与消除顺序。",
    },
]

TOTAL_LEVELS = len(LEVEL_CONFIGS)
MAX_GENERATION_ATTEMPTS = 48_000
MAX_GENERATION_RESTARTS = 24

COLORS = [
    (53, 242, 255),
    (255, 79, 216),
    (139, 124, 255),
    (121, 255, 183),
    (255, 200, 87),
    (255, 107, 139),
]
DIR_NAMES = tuple(DIRECTIONS)


def _key(x: int, y: int) -> tuple[int, int]:
    return x, y


def in_bounds(x: int, y: int) -> bool:
    return 0 <= x < GRID_COLS and 0 <= y < GRID_ROWS


def _mix_seed(session_seed: int, salt: int) -> int:
    value = (int(session_seed) ^ int(salt) ^ 0x9E3779B9) & 0xFFFFFFFF
    value = ((value ^ (value >> 16)) * 0x21F0AAAD) & 0xFFFFFFFF
    value = ((value ^ (value >> 15)) * 0x735A2D97) & 0xFFFFFFFF
    return (value ^ (value >> 15)) & 0xFFFFFFFF


def create_session_seed() -> int:
    return secrets.randbits(32)


def _basic_visual_route(direction: str) -> list[dict[str, float]]:
    """Return a short in-cell shaft for a logically single-cell arrow."""
    vector = DIRECTIONS[direction]
    # The logical arrow occupies only the head cell.  This tiny route is purely
    # visual so the direction remains easy to read without turning it into a
    # multi-cell body.
    return [
        {"dx": -float(vector["x"]) * 0.28, "dy": -float(vector["y"]) * 0.28},
        {"dx": 0.0, "dy": 0.0},
    ]


def session_code(session_seed: int) -> str:
    """Return a compact human-readable RUN id."""
    alphabet = "0123456789ABCDEFGHIJKLMNOPQRSTUVWXYZ"
    value = int(session_seed) & 0xFFFFFFFF
    if value == 0:
        return "0000000"
    chars: list[str] = []
    while value:
        value, rem = divmod(value, 36)
        chars.append(alphabet[rem])
    return "".join(reversed(chars)).rjust(7, "0")[-7:]


def _turn_direction(direction: str, turn: str) -> str:
    order = ("up", "right", "down", "left")
    index = order.index(direction)
    delta = 2 if turn == "flip" else 1 if turn == "cw" else -1
    return order[(index + delta) % len(order)]


def _gate_map(gates: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    return {_key(gate["x"], gate["y"]): gate for gate in gates}


def _portal_map(portals: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    result: dict[tuple[int, int], dict[str, Any]] = {}
    for portal in portals:
        a = portal["a"]
        b = portal["b"]
        result[_key(a["x"], a["y"])] = {"id": portal["id"], "exit": dict(b)}
        result[_key(b["x"], b["y"])] = {"id": portal["id"], "exit": dict(a)}
    return result


def _phase_lock_map(phase_locks: list[dict[str, Any]]) -> dict[tuple[int, int], dict[str, Any]]:
    return {_key(lock["x"], lock["y"]): lock for lock in phase_locks}


def trace_ray(
    head: dict[str, int],
    direction: str,
    occupied: dict[tuple[int, int], str] | None = None,
    gates: list[dict[str, Any]] | None = None,
    portals: list[dict[str, Any]] | None = None,
    phase_locks: list[dict[str, Any]] | None = None,
    remaining_count: int | None = None,
) -> dict[str, Any]:
    occupied = occupied or {}
    gates = gates or []
    portals = portals or []
    phase_locks = phase_locks or []
    gates_by_cell = _gate_map(gates)
    portals_by_cell = _portal_map(portals)
    phase_locks_by_cell = _phase_lock_map(phase_locks)
    path: list[dict[str, Any]] = []
    seen: set[tuple[int, int, str]] = set()
    x = head["x"]
    y = head["y"]
    current_direction = direction

    # A ray state is fully described by (x, y, direction).  `seen` catches a
    # true cycle, while this upper bound prevents malformed custom maps from
    # running forever without prematurely rejecting a long but valid route.
    max_ray_states = GRID_COLS * GRID_ROWS * len(DIRECTIONS)
    for _ in range(max_ray_states + 1):
        vector = DIRECTIONS[current_direction]
        x += int(vector["x"])
        y += int(vector["y"])

        if not in_bounds(x, y):
            return {
                "clear": True,
                "path": path,
                "exit": {"x": x, "y": y},
                "dir": current_direction,
            }

        loop_key = (x, y, current_direction)
        if loop_key in seen:
            return {"clear": False, "path": path, "loop": True, "blocker_id": None}
        seen.add(loop_key)

        cell_key = _key(x, y)
        phase_lock = phase_locks_by_cell.get(cell_key)
        if phase_lock:
            unlock_remaining = int(phase_lock["unlock_remaining"])
            active = remaining_count is None or remaining_count > unlock_remaining
            step: dict[str, Any] = {"x": x, "y": y, "dir": current_direction}
            step["phase_lock"] = phase_lock["id"]
            step["phase_lock_active"] = active
            path.append(step)
            if active:
                return {
                    "clear": False,
                    "path": path,
                    "blocker_id": f"phase:{phase_lock['id']}",
                    "blocker_kind": "phase_lock",
                    "blocker_label": f"相位锁 {phase_lock['id']}",
                    "loop": False,
                }

        blocker_id = occupied.get(cell_key)
        if not phase_lock:
            step = {"x": x, "y": y, "dir": current_direction}
            path.append(step)
        if blocker_id is not None:
            return {
                "clear": False,
                "path": path,
                "blocker_id": blocker_id,
                "loop": False,
            }

        gate = gates_by_cell.get(cell_key)
        if gate:
            current_direction = _turn_direction(current_direction, gate["turn"])
            step["gate"] = gate["turn"]
            step["dir_after"] = current_direction

        portal = portals_by_cell.get(cell_key)
        if portal:
            step["portal"] = portal["id"]
            step["portal_exit"] = dict(portal["exit"])
            x = portal["exit"]["x"]
            y = portal["exit"]["y"]

    return {"clear": False, "path": path, "loop": True, "blocker_id": None}


def build_occupied(arrows: list[dict[str, Any]], exclude_id: str | None = None) -> dict[tuple[int, int], str]:
    occupied: dict[tuple[int, int], str] = {}
    for arrow in arrows:
        if arrow["id"] == exclude_id:
            continue
        for cell in arrow["cells"]:
            occupied[_key(cell["x"], cell["y"])] = arrow["id"]
    return occupied


def trace_arrow(
    arrow: dict[str, Any],
    arrows: list[dict[str, Any]],
    gates: list[dict[str, Any]] | None = None,
    portals: list[dict[str, Any]] | None = None,
    phase_locks: list[dict[str, Any]] | None = None,
) -> dict[str, Any]:
    return trace_ray(
        arrow["head"],
        arrow["dir"],
        build_occupied(arrows, arrow["id"]),
        gates,
        portals,
        phase_locks,
        len(arrows),
    )


def _choose_body_cells(
    head: dict[str, int],
    direction: str,
    requested_length: int,
    occupied: dict[tuple[int, int], str],
    reserved: set[tuple[int, int]],
    rng: random.Random,
) -> list[dict[str, int]]:
    """Build a real multi-cell arrow body from tail to head.

    The cell immediately behind the head is always aligned with the arrow's
    direction, so the final visible segment points cleanly into the arrowhead.
    Earlier body segments may continue straight or turn 90 degrees, producing
    the older long, irregular tap-away silhouette without letting bodies overlap
    other arrows or mechanism cells.
    """
    forward = DIRECTIONS[direction]
    travel = (-int(forward["x"]), -int(forward["y"]))
    cells_from_head = [dict(head)]
    used = {_key(head["x"], head["y"])}
    previous = dict(head)

    for index in range(1, requested_length):
        left = (-travel[1], travel[0])
        right = (travel[1], -travel[0])

        # Keep the segment touching the head perfectly aligned.  Farther back,
        # favor continuing straight while still allowing random 90-degree bends.
        options = [travel] if index == 1 else [travel, travel, travel, left, right]
        rng.shuffle(options)
        placed = False
        for step_x, step_y in options:
            candidate = {"x": previous["x"] + step_x, "y": previous["y"] + step_y}
            candidate_key = _key(candidate["x"], candidate["y"])
            if not in_bounds(candidate["x"], candidate["y"]):
                continue
            if candidate_key in occupied or candidate_key in reserved or candidate_key in used:
                continue
            cells_from_head.append(candidate)
            used.add(candidate_key)
            previous = candidate
            travel = (step_x, step_y)
            placed = True
            break
        if not placed:
            break

    return list(reversed(cells_from_head))


def _generate_candidate(
    arrow_number: int,
    occupied: dict[tuple[int, int], str],
    reserved: set[tuple[int, int]],
    gates: list[dict[str, Any]],
    portals: list[dict[str, Any]],
    rng: random.Random,
    min_boundary_steps: int = 0,
) -> dict[str, Any] | None:
    head = {"x": rng.randrange(GRID_COLS), "y": rng.randrange(GRID_ROWS)}
    head_key = _key(head["x"], head["y"])
    if head_key in occupied or head_key in reserved:
        return None

    direction_options = list(DIR_NAMES)
    if min_boundary_steps > 0:
        boundary_steps = {
            "up": head["y"],
            "right": GRID_COLS - 1 - head["x"],
            "down": GRID_ROWS - 1 - head["y"],
            "left": head["x"],
        }
        filtered = [name for name in direction_options if boundary_steps[name] >= min_boundary_steps]
        if filtered:
            direction_options = filtered
    direction = rng.choice(direction_options)
    ray = trace_ray(head, direction, occupied, gates, portals)
    if not ray["clear"]:
        return None

    # Restore the original physical long-arrow layout: arrows occupy and render
    # 2-4 actual grid cells instead of being compressed into a tiny decorative
    # route inside a single anchor cell.
    requested_length = rng.randint(2, 4)
    cells = _choose_body_cells(head, direction, requested_length, occupied, reserved, rng)
    if len(cells) < 2:
        return None

    return {
        "id": f"a{arrow_number}",
        "cells": cells,
        "head": dict(head),
        "dir": direction,
        "color": COLORS[arrow_number % len(COLORS)],
        "prism": arrow_number % 7 == 0,
    }


def _safe_ids_for_state(level: dict[str, Any], arrows: list[dict[str, Any]]) -> list[str]:
    config = level["config"]
    return [
        arrow["id"]
        for arrow in arrows
        if trace_arrow(
            arrow,
            arrows,
            config["gates"],
            config["portals"],
            config.get("phase_locks", []),
        )["clear"]
    ]


def _derive_solution_order(level: dict[str, Any]) -> list[str] | None:
    """Derive one complete solution while respecting dynamic phase locks."""
    remaining = deepcopy(level["arrows"])
    construction_rank = {arrow["id"]: index for index, arrow in enumerate(level["arrows"])}
    solved: list[str] = []
    while remaining:
        safe = _safe_ids_for_state(level, remaining)
        if not safe:
            return None
        # Prefer arrows that were placed later during reverse construction.
        # This keeps the generated path stable while still allowing multiple
        # valid choices on the terminal level.
        arrow_id = max(safe, key=lambda item: construction_rank[item])
        solved.append(arrow_id)
        remaining = [arrow for arrow in remaining if arrow["id"] != arrow_id]
    return solved


def create_level(level_index: int = 0, session_seed: int | None = None) -> dict[str, Any]:
    if not isinstance(level_index, int) or not 0 <= level_index < TOTAL_LEVELS:
        raise IndexError(f"关卡索引 {level_index} 越界；整局只有 {TOTAL_LEVELS} 关。")

    if session_seed is None:
        session_seed = create_session_seed()
    session_seed &= 0xFFFFFFFF
    template = deepcopy(LEVEL_CONFIGS[level_index])
    generation_seed = _mix_seed(session_seed, template["seed_salt"])
    rng = random.Random(generation_seed)
    template["target"] = rng.randint(*template["target_range"])
    template["time"] = rng.randint(*template["time_range"])
    template["session_seed"] = session_seed
    template["generation_seed"] = generation_seed

    reserved = {_key(gate["x"], gate["y"]) for gate in template["gates"]}
    for portal in template["portals"]:
        reserved.add(_key(portal["a"]["x"], portal["a"]["y"]))
        reserved.add(_key(portal["b"]["x"], portal["b"]["y"]))
    for phase_lock in template.get("phase_locks", []):
        reserved.add(_key(phase_lock["x"], phase_lock["y"]))

    construction_order: list[dict[str, Any]] = []
    attempts = 0
    restart_used = 0
    solution_order: list[str] | None = None

    # Every level uses the same physical long-arrow generator.  Deterministic
    # restarts preserve RUN reproducibility if a dense construction saturates.
    for restart in range(MAX_GENERATION_RESTARTS):
        restart_used = restart
        if restart > 0:
            retry_salt = 0xA5A5_0000 ^ restart
            rng = random.Random(_mix_seed(generation_seed, retry_salt))

        occupied: dict[tuple[int, int], str] = {}
        construction_order = []
        attempts = 0

        while len(construction_order) < template["target"] and attempts < MAX_GENERATION_ATTEMPTS:
            attempts += 1
            arrow_number = len(construction_order) + 1
            candidate = _generate_candidate(
                arrow_number,
                occupied,
                reserved,
                template["gates"],
                template["portals"],
                rng,
                int(template.get("min_boundary_steps", 0)),
            )
            if candidate is None:
                continue
            for cell in candidate["cells"]:
                occupied[_key(cell["x"], cell["y"])] = candidate["id"]
            construction_order.append(candidate)

        if len(construction_order) == template["target"]:
            provisional = {
                "index": level_index,
                "config": template,
                "arrows": deepcopy(construction_order),
                "solution_order": [],
            }
            candidate_solution = _derive_solution_order(provisional)
            if candidate_solution is None:
                continue
            min_phase_affected = int(template.get("min_phase_affected", 0))
            if min_phase_affected:
                phase_affected = sum(
                    1
                    for arrow in provisional["arrows"]
                    if trace_arrow(
                        arrow,
                        provisional["arrows"],
                        template["gates"],
                        template["portals"],
                        template.get("phase_locks", []),
                    ).get("blocker_kind")
                    == "phase_lock"
                )
                if phase_affected < min_phase_affected:
                    continue
            initial_safe = len(_safe_ids_for_state(provisional, provisional["arrows"]))
            safe_range = template.get("initial_safe_range")
            if safe_range and not int(safe_range[0]) <= initial_safe <= int(safe_range[1]):
                continue
            solution_order = candidate_solution
            break

    if len(construction_order) < template["target"] or solution_order is None:
        raise RuntimeError(
            f"第 {level_index + 1} 关生成失败：目标 {template['target']}，实际 {len(construction_order)}，"
            f"已执行 {restart_used + 1} 轮确定性构造重试。"
        )

    arrows = deepcopy(construction_order)
    return {
        "index": level_index,
        "config": template,
        "arrows": arrows,
        "solution_order": solution_order,
    }


def create_basic_level(level_index: int = 0, session_seed: int | None = None) -> dict[str, Any]:
    """Generate a solvable level using only single-cell arrows."""
    if not isinstance(level_index, int) or not 0 <= level_index < TOTAL_LEVELS:
        raise IndexError(f"基础模式关卡索引 {level_index} 越界。")
    if session_seed is None:
        session_seed = create_session_seed()
    session_seed &= 0xFFFFFFFF
    template = deepcopy(BASIC_LEVEL_CONFIGS[level_index])
    generation_seed = _mix_seed(session_seed, int(template["seed_salt"]))
    rng = random.Random(generation_seed)
    template["target"] = rng.randint(*template["target_range"])
    template["time"] = rng.randint(*template["time_range"])
    template["session_seed"] = session_seed
    template["generation_seed"] = generation_seed
    template["gates"] = []
    template["portals"] = []
    template["phase_locks"] = []
    template["mode"] = "basic"

    for restart in range(16):
        attempt_rng = random.Random(_mix_seed(generation_seed, restart + 1))
        occupied: dict[tuple[int, int], str] = {}
        arrows: list[dict[str, Any]] = []
        attempts = 0
        while len(arrows) < int(template["target"]) and attempts < 30000:
            attempts += 1
            x = attempt_rng.randrange(GRID_COLS)
            y = attempt_rng.randrange(GRID_ROWS)
            if _key(x, y) in occupied:
                continue
            directions = list(DIR_NAMES)
            attempt_rng.shuffle(directions)
            direction = next((name for name in directions if trace_ray({"x": x, "y": y}, name, occupied)["clear"]), None)
            if direction is None:
                continue
            arrow_id = f"b{len(arrows) + 1}"
            head = {"x": x, "y": y}
            arrows.append({
                "id": arrow_id,
                "cells": [dict(head)],
                "head": dict(head),
                "dir": direction,
                "color": COLORS[len(arrows) % len(COLORS)],
                "prism": False,
                "visual_route": _basic_visual_route(direction),
            })
            occupied[_key(x, y)] = arrow_id
        if len(arrows) == int(template["target"]):
            return {
                "index": level_index,
                "config": template,
                "arrows": deepcopy(arrows),
                "solution_order": [arrow["id"] for arrow in reversed(arrows)],
            }
    raise RuntimeError(f"基础模式第 {level_index + 1} 个难度生成失败。")


def unique_solution_order(
    level: dict[str, Any],
    arrows: list[dict[str, Any]] | None = None,
) -> list[str] | None:
    """Return the only legal clear-arrow sequence, or ``None`` if it is not unique."""
    remaining = deepcopy(arrows if arrows is not None else level["arrows"])
    order: list[str] = []
    while remaining:
        safe = safe_arrow_ids(level, remaining)
        if len(safe) != 1:
            return None
        arrow_id = safe[0]
        order.append(arrow_id)
        remaining = [arrow for arrow in remaining if arrow["id"] != arrow_id]
    return order


def has_unique_solution(level: dict[str, Any], arrows: list[dict[str, Any]] | None = None) -> bool:
    return unique_solution_order(level, arrows) is not None


def is_solution_valid(level: dict[str, Any]) -> bool:
    remaining = deepcopy(level["arrows"])
    config = level["config"]
    for arrow_id in level["solution_order"]:
        arrow = next((item for item in remaining if item["id"] == arrow_id), None)
        if arrow is None:
            return False
        if not trace_arrow(
            arrow,
            remaining,
            config["gates"],
            config["portals"],
            config.get("phase_locks", []),
        )["clear"]:
            return False
        remaining = [item for item in remaining if item["id"] != arrow_id]
    return not remaining


def count_initially_blocked(level: dict[str, Any]) -> int:
    config = level["config"]
    return sum(
        1
        for arrow in level["arrows"]
        if not trace_arrow(
            arrow,
            level["arrows"],
            config["gates"],
            config["portals"],
            config.get("phase_locks", []),
        )["clear"]
    )


def safe_arrow_ids(level: dict[str, Any], arrows: list[dict[str, Any]] | None = None) -> list[str]:
    current = arrows if arrows is not None else level["arrows"]
    return _safe_ids_for_state(level, current)


def solve_current_state(
    level: dict[str, Any],
    arrows: list[dict[str, Any]] | None = None,
) -> list[str] | None:
    """Solve the *current* board by repeatedly recomputing safe arrows.

    The solver does not blindly replay the generation-time answer.  This matters
    after the player has already removed arrows (including a quantum-overdrive
    removal): every step is checked again against the board that actually
    remains.  Removing an arrow can only remove blockers, so a generated level
    that was solvable remains solvable after any successful removal.
    """
    remaining = deepcopy(arrows if arrows is not None else level["arrows"])
    solution_rank = {arrow_id: index for index, arrow_id in enumerate(level["solution_order"])}
    solved: list[str] = []

    while remaining:
        safe = safe_arrow_ids(level, remaining)
        if not safe:
            return None
        arrow_id = min(safe, key=lambda item: solution_rank.get(item, len(solution_rank)))
        solved.append(arrow_id)
        remaining = [arrow for arrow in remaining if arrow["id"] != arrow_id]

    return solved
