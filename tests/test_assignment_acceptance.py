from __future__ import annotations

from copy import deepcopy
import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from neon_arrow.app import NeonArrowApp
from neon_arrow.engine import safe_arrow_ids, trace_ray


def _app() -> NeonArrowApp:
    app = NeonArrowApp((1000, 700), load_save=False)
    app.save_progress = lambda: None  # type: ignore[method-assign]
    app.game_mode = "basic"
    app.session_seed = 20260919
    app.load_level(0)
    app.state = "playing"
    return app


def _manual_arrow(
    arrow_id: str,
    x: int,
    y: int,
    direction: str,
) -> dict[str, object]:
    return {
        "id": arrow_id,
        "cells": [{"x": x, "y": y}],
        "head": {"x": x, "y": y},
        "dir": direction,
        "color": (53, 242, 255),
        "prism": False,
    }


def test_t01_unblocked_arrow_leaves_board_and_is_removed() -> None:
    app = _app()
    before = len(app.arrows)
    safe_id = safe_arrow_ids(app.level, app.arrows)[0]
    arrow = next(item for item in app.arrows if item["id"] == safe_id)

    app.handle_arrow_click(arrow)

    assert len(app.arrows) == before - 1
    assert all(item["id"] != safe_id for item in app.arrows)
    assert app.exiting_arrows
    pygame.quit()


def test_t02_blocked_arrow_stays_and_costs_one_life() -> None:
    app = _app()
    blocked = _manual_arrow("blocked", 2, 4, "right")
    blocker = _manual_arrow("blocker", 4, 4, "up")
    app.arrows = [blocked, blocker]  # type: ignore[list-item]
    app.lives = 3

    app.handle_arrow_click(blocked)  # type: ignore[arg-type]

    assert [item["id"] for item in app.arrows] == ["blocked", "blocker"]
    assert app.lives == 2
    assert app.state == "playing"
    pygame.quit()


def test_t03_outward_edge_arrows_exit_without_out_of_bounds_error() -> None:
    cases = [
        ({"x": 0, "y": 5}, "left"),
        ({"x": 12, "y": 5}, "right"),
        ({"x": 5, "y": 0}, "up"),
        ({"x": 5, "y": 15}, "down"),
    ]

    for head, direction in cases:
        result = trace_ray(head, direction)
        assert result["clear"] is True
        assert result["path"] == []


def test_t04_clearing_last_arrow_enters_result_then_next_level() -> None:
    app = _app()
    last_arrow = _manual_arrow("last", 12, 5, "right")
    app.arrows = [last_arrow]  # type: ignore[list-item]
    app.level_index = 0
    app.training_mode = False

    app.handle_arrow_click(last_arrow)  # type: ignore[arg-type]

    assert app.arrows == []
    assert app.state == "level_complete"

    app.next_level()
    assert app.level_index == 1
    assert app.state == "playing"
    assert app.arrows
    pygame.quit()


def test_t05_last_remaining_life_enters_failed_state() -> None:
    app = _app()
    blocked = _manual_arrow("blocked", 2, 4, "right")
    blocker = _manual_arrow("blocker", 4, 4, "up")
    app.arrows = [blocked, blocker]  # type: ignore[list-item]
    app.lives = 1

    app.handle_arrow_click(blocked)  # type: ignore[arg-type]

    assert app.lives == 0
    assert app.state == "failed"
    assert len(app.arrows) == 2
    pygame.quit()


def test_t06_restart_restores_same_run_layout_and_initial_state() -> None:
    app = _app()
    initial_arrows = deepcopy(app.arrows)
    initial_lives = int(app.level["config"]["lives"])
    initial_time = float(app.level["config"]["time"])
    safe_id = safe_arrow_ids(app.level, app.arrows)[0]
    arrow = next(item for item in app.arrows if item["id"] == safe_id)

    app.handle_arrow_click(arrow)
    app.lives = max(0, app.lives - 1)
    app.time_left = max(0.0, app.time_left - 10.0)
    app.restart_level()

    assert app.arrows == initial_arrows
    assert app.lives == initial_lives
    assert app.time_left == initial_time
    assert app.combo == 0
    assert app.state == "playing"
    pygame.quit()
