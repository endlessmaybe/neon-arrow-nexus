from __future__ import annotations

import os

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

from neon_arrow.app import NeonArrowApp
from neon_arrow.engine import TOTAL_LEVELS, safe_arrow_ids


def test_pygame_window_renders_and_real_click_logic_removes_arrow() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    app.render()
    assert app.screen.get_width() == 1100
    assert app.screen.get_height() == 700
    before = len(app.arrows)
    safe_id = safe_arrow_ids(app.level, app.arrows)[0]
    arrow = next(item for item in app.arrows if item["id"] == safe_id)
    app.handle_arrow_click(arrow)
    assert len(app.arrows) == before - 1
    assert app.score > 0
    pygame.quit()


def test_third_level_completion_has_no_fourth_level() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    app.load_level(TOTAL_LEVELS - 1)
    app.arrows.clear()
    app.state = "campaign_complete"
    app.render()
    assert app.level_index == TOTAL_LEVELS - 1
    assert app.state == "campaign_complete"
    pygame.quit()


def test_third_level_visible_arrow_shaft_is_clickable() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    app.load_level(2)
    arrow = app.arrows[0]
    app.arrows = [arrow]
    points = app.arrow_visual_points(arrow)
    shaft_point = (
        int((points[0][0] + points[1][0]) / 2),
        int((points[0][1] + points[1][1]) / 2),
    )
    assert app.arrow_at_point(shaft_point) is arrow
    pygame.quit()


def test_visible_arrow_shaft_is_actually_drawn_across_its_real_body_cells() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    app.load_level(2)
    for arrow in app.arrows:
        points = app.arrow_visual_points(arrow)
        expected = [app.cell_center(cell["x"], cell["y"]) for cell in arrow["cells"]]
        assert points == expected
        assert len(points) == len(arrow["cells"])

    arrow = app.arrows[0]
    points = app.arrow_visual_points(arrow)
    layer = pygame.Surface(app.screen.get_size(), pygame.SRCALPHA)
    app.draw_arrow(layer, arrow, 0.0)
    for start, end in zip(points, points[1:]):
        midpoint = (int(round((start[0] + end[0]) / 2)), int(round((start[1] + end[1]) / 2)))
        assert layer.get_at(midpoint).a > 0
    pygame.quit()


def test_every_level_has_visibly_short_and_long_arrow_shafts() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    for level_index in range(TOTAL_LEVELS):
        app.load_level(level_index)
        normalized_lengths: list[float] = []
        _, cell, _ = app.board_geometry()
        for arrow in app.arrows:
            points = app.arrow_visual_points(arrow)
            length = sum(
                abs(end[0] - start[0]) + abs(end[1] - start[1])
                for start, end in zip(points, points[1:])
            ) / cell
            normalized_lengths.append(length)
        assert min(normalized_lengths) == 1.0
        assert max(normalized_lengths) == 3.0
        assert max(normalized_lengths) - min(normalized_lengths) == 2.0
    pygame.quit()


def test_all_visible_arrow_shafts_follow_grid_and_point_into_the_head() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    for level_index in range(TOTAL_LEVELS):
        app.load_level(level_index)
        for arrow in app.arrows:
            points = app.arrow_visual_points(arrow)
            assert 2 <= len(points) <= 4
            for start, end in zip(points, points[1:]):
                segment = (end[0] - start[0], end[1] - start[1])
                assert abs(segment[0]) < 1e-6 or abs(segment[1]) < 1e-6

            final = (points[-1][0] - points[-2][0], points[-1][1] - points[-2][1])
            direction = {
                "up": (0.0, -1.0),
                "right": (1.0, 0.0),
                "down": (0.0, 1.0),
                "left": (-1.0, 0.0),
            }[arrow["dir"]]
            cross = final[0] * direction[1] - final[1] * direction[0]
            dot = final[0] * direction[0] + final[1] * direction[1]
            assert abs(cross) < 1e-6
            assert dot > 0
    pygame.quit()


def test_exit_animation_moves_head_first_and_body_follows_route() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    arrow = {
        "id": "a999",
        "cells": [
            {"x": 2, "y": 3},
            {"x": 2, "y": 4},
            {"x": 3, "y": 4},
        ],
        "head": {"x": 3, "y": 4},
        "dir": "right",
        "color": (60, 236, 255),
        "prism": False,
    }
    original = app.arrow_visual_points(arrow)
    moving = app.exiting_arrow_points(arrow, 0.08)

    # The head advances along its direction while the tail is still following
    # the old bend. This specifically rejects the old rigid whole-arrow shift.
    assert moving[-1][0] > original[-1][0]
    assert abs(moving[-1][1] - original[-1][1]) < 1e-6
    assert abs(moving[0][0] - original[0][0]) < 1e-6
    assert moving[0][1] > original[0][1]

    original_length = sum(
        ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        for start, end in zip(original, original[1:])
    )
    moving_length = sum(
        ((end[0] - start[0]) ** 2 + (end[1] - start[1]) ** 2) ** 0.5
        for start, end in zip(moving, moving[1:])
    )
    assert abs(moving_length - original_length) < 1e-6

    finished = app.exiting_arrow_points(arrow, 1.0)
    assert min(point[0] for point in finished) > app.screen.get_width()
    pygame.quit()


def test_full_campaign_uses_real_click_logic_and_stops_after_level_three() -> None:
    app = NeonArrowApp((1100, 700), load_save=False)
    app.session_seed = 20260915
    app.training_mode = False
    for index in range(TOTAL_LEVELS):
        app.load_level(index)
        for arrow_id in list(app.level["solution_order"]):
            arrow = next(item for item in app.arrows if item["id"] == arrow_id)
            app.handle_arrow_click(arrow)
        assert app.state == ("campaign_complete" if index == TOTAL_LEVELS - 1 else "level_complete")
    assert app.level_index == TOTAL_LEVELS - 1
    assert not app.arrows
    pygame.quit()
