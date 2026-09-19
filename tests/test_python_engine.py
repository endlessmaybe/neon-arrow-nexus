from __future__ import annotations

from copy import deepcopy

import pytest

from neon_arrow.engine import (
    DIRECTIONS,
    LEVEL_CONFIGS,
    TOTAL_LEVELS,
    count_initially_blocked,
    create_level,
    has_unique_solution,
    is_solution_valid,
    safe_arrow_ids,
    session_code,
    solve_current_state,
    trace_ray,
)


def level_signature(level: dict) -> tuple:
    return tuple(
        (
            arrow["dir"],
            tuple((cell["x"], cell["y"]) for cell in arrow["cells"]),
        )
        for arrow in level["arrows"]
    )


def test_game_has_exactly_three_difficulty_levels() -> None:
    assert TOTAL_LEVELS == 3
    assert len(LEVEL_CONFIGS) == TOTAL_LEVELS
    assert [item["difficulty"] for item in LEVEL_CONFIGS] == ["简单", "中等", "终极困难"]
    with pytest.raises(IndexError):
        create_level(TOTAL_LEVELS, 123)


@pytest.mark.parametrize("seed", [1, 42, 20260915, 0xDEADBEEF])
def test_all_levels_are_randomized_but_solvable(seed: int) -> None:
    for index, config in enumerate(LEVEL_CONFIGS):
        level = create_level(index, seed)
        low, high = config["target_range"]
        assert low <= len(level["arrows"]) <= high
        time_low, time_high = config["time_range"]
        assert time_low <= level["config"]["time"] <= time_high
        assert is_solution_valid(level)
        assert safe_arrow_ids(level)
        assert count_initially_blocked(level) > 0


def _assert_physical_long_arrow(arrow: dict) -> None:
    cells = arrow["cells"]
    assert 2 <= len(cells) <= 4
    assert cells[-1] == arrow["head"]
    assert "visual_route" not in arrow
    assert "visual_length_class" not in arrow

    for previous, current in zip(cells, cells[1:]):
        dx = current["x"] - previous["x"]
        dy = current["y"] - previous["y"]
        assert abs(dx) + abs(dy) == 1

    previous = cells[-2]
    head = cells[-1]
    final = (head["x"] - previous["x"], head["y"] - previous["y"])
    direction = DIRECTIONS[arrow["dir"]]
    assert final == (direction["x"], direction["y"])


@pytest.mark.parametrize("seed", [1, 42, 20260915])
def test_all_levels_use_real_random_long_arrow_bodies(seed: int) -> None:
    for level_index in range(TOTAL_LEVELS):
        level = create_level(level_index, seed)
        lengths = set()
        occupied: set[tuple[int, int]] = set()
        reserved = {(gate["x"], gate["y"]) for gate in level["config"]["gates"]}
        for portal in level["config"]["portals"]:
            reserved.add((portal["a"]["x"], portal["a"]["y"]))
            reserved.add((portal["b"]["x"], portal["b"]["y"]))
        for phase_lock in level["config"].get("phase_locks", []):
            reserved.add((phase_lock["x"], phase_lock["y"]))

        for arrow in level["arrows"]:
            _assert_physical_long_arrow(arrow)
            lengths.add(len(arrow["cells"]))
            for cell in arrow["cells"]:
                key = (cell["x"], cell["y"])
                assert key not in occupied
                assert key not in reserved
                occupied.add(key)
        assert lengths == {2, 3, 4}


def test_same_run_is_reproducible_and_new_run_changes_layout() -> None:
    first = create_level(2, 123456789)
    same = create_level(2, 123456789)
    different = create_level(2, 987654321)
    assert level_signature(first) == level_signature(same)
    assert level_signature(first) != level_signature(different)


def test_terminal_level_fresh_runs_have_distinct_layouts() -> None:
    signatures = {level_signature(create_level(2, seed)) for seed in range(100, 108)}
    assert len(signatures) == 8


def test_dense_level_generation_retries_deterministically() -> None:
    first = create_level(2, 23)
    second = create_level(2, 23)
    assert len(first["arrows"]) == first["config"]["target"]
    assert 38 <= len(first["arrows"]) <= 42
    assert level_signature(first) == level_signature(second)
    assert is_solution_valid(first)


def test_terminal_level_is_not_forced_into_a_unique_solution_chain() -> None:
    level = create_level(2, 20260915)
    assert "unique_solution" not in level["config"]
    assert len(safe_arrow_ids(level)) > 1
    assert not has_unique_solution(level)


def test_terminal_level_has_real_progressive_phase_locks_and_double_portals() -> None:
    level = create_level(2, 20260915)
    config = level["config"]
    assert len(config["portals"]) == 2
    assert len(config["phase_locks"]) == 3
    assert [lock["unlock_remaining"] for lock in config["phase_locks"]] == [30, 20, 11]

    phase_blocked = [
        arrow["id"]
        for arrow in level["arrows"]
        if trace_ray(
            arrow["head"],
            arrow["dir"],
            occupied={
                (cell["x"], cell["y"]): other["id"]
                for other in level["arrows"]
                if other["id"] != arrow["id"]
                for cell in other["cells"]
            },
            gates=config["gates"],
            portals=config["portals"],
            phase_locks=config["phase_locks"],
            remaining_count=len(level["arrows"]),
        ).get("blocker_kind")
        == "phase_lock"
    ]
    assert phase_blocked


def test_phase_lock_changes_ray_state_when_threshold_is_reached() -> None:
    locks = [{"id": "PX", "x": 4, "y": 3, "unlock_remaining": 5}]
    locked = trace_ray(
        {"x": 4, "y": 4},
        "up",
        phase_locks=locks,
        remaining_count=8,
    )
    assert locked["clear"] is False
    assert locked["blocker_kind"] == "phase_lock"
    assert locked["blocker_label"] == "相位锁 PX"

    unlocked = trace_ray(
        {"x": 4, "y": 4},
        "up",
        phase_locks=locks,
        remaining_count=5,
    )
    assert unlocked["clear"] is True
    assert any(step.get("phase_lock") == "PX" and step.get("phase_lock_active") is False for step in unlocked["path"])


@pytest.mark.parametrize("seed", [1, 23, 42, 20260915])
def test_terminal_level_is_scattered_with_mixed_physical_lengths(seed: int) -> None:
    level = create_level(2, seed)
    arrows = level["arrows"]
    assert {arrow["dir"] for arrow in arrows} == {"up", "right", "down", "left"}
    lengths = set()
    for arrow in arrows:
        _assert_physical_long_arrow(arrow)
        lengths.add(len(arrow["cells"]))

    assert lengths == {2, 3, 4}
    assert len({arrow["head"]["x"] for arrow in arrows}) >= 7
    assert len({arrow["head"]["y"] for arrow in arrows}) >= 8
    assert len({(arrow["head"]["x"], arrow["head"]["y"]) for arrow in arrows}) == len(arrows)


def test_generation_stress_sample_is_stable_and_solvable() -> None:
    for seed in range(64):
        for index in range(TOTAL_LEVELS):
            level = create_level(index, seed)
            assert len(level["arrows"]) == level["config"]["target"]
            assert is_solution_valid(level)
            assert all(2 <= len(arrow["cells"]) <= 4 for arrow in level["arrows"])


def test_terminal_generation_handles_known_dense_retry_seeds() -> None:
    for seed in (268185663, 2111439849):
        level = create_level(2, seed)
        assert len(level["arrows"]) == level["config"]["target"]
        assert is_solution_valid(level)


def test_refraction_flip_and_portal_change_real_ray_path() -> None:
    refracted = trace_ray(
        {"x": 3, "y": 4},
        "up",
        gates=[{"x": 3, "y": 3, "turn": "cw"}],
    )
    assert refracted["clear"] is True
    assert any(step.get("gate") == "cw" and step.get("dir_after") == "right" for step in refracted["path"])

    flipped = trace_ray(
        {"x": 4, "y": 7},
        "up",
        gates=[{"x": 4, "y": 6, "turn": "flip"}],
    )
    assert flipped["clear"] is True
    assert any(step.get("gate") == "flip" and step.get("dir_after") == "down" for step in flipped["path"])

    portaled = trace_ray(
        {"x": 0, "y": 1},
        "right",
        portals=[{"id": "A", "a": {"x": 1, "y": 1}, "b": {"x": 8, "y": 11}}],
    )
    assert portaled["clear"] is True
    assert any(step.get("portal") == "A" and step["portal_exit"] == {"x": 8, "y": 11} for step in portaled["path"])


def test_solver_recomputes_complete_solution_from_current_board() -> None:
    level = create_level(2, 20260915)
    current = deepcopy(level["arrows"])
    first_safe = safe_arrow_ids(level, current)[0]
    current = [arrow for arrow in current if arrow["id"] != first_safe]
    solution = solve_current_state(level, current)
    assert solution is not None
    assert len(solution) == len(current)
    remaining = current
    for arrow_id in solution:
        assert arrow_id in safe_arrow_ids(level, remaining)
        remaining = [arrow for arrow in remaining if arrow["id"] != arrow_id]
    assert not remaining


def test_run_code_is_short_and_stable() -> None:
    assert session_code(0) == "0000000"
    assert session_code(123456789) == session_code(123456789)
    assert len(session_code(0xFFFFFFFF)) == 7
