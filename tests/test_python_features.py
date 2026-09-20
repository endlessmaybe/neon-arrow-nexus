from __future__ import annotations

import os
from pathlib import Path
import tempfile

os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

import pygame

import neon_arrow.app as app_module
from neon_arrow.app import CONTROL_HELP, NeonArrowApp, _exit_opacity
from neon_arrow.engine import TOTAL_LEVELS, is_solution_valid, safe_arrow_ids


def _use_temp_save() -> Path:
    root = Path(tempfile.gettempdir()) / "neon-arrow-nexus-tests"
    root.mkdir(parents=True, exist_ok=True)
    app_module.SAVE_DIR = root
    app_module.SAVE_FILE = root / "savegame.json"
    app_module.SAVE_FILE.unlink(missing_ok=True)
    return app_module.SAVE_FILE


def test_undo_restores_a_real_move() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=True)
    app.state = "playing"
    arrow_id = app.level["solution_order"][0]
    arrow = next(item for item in app.arrows if item["id"] == arrow_id)
    before = len(app.arrows)
    app.handle_arrow_click(arrow)
    assert len(app.arrows) == before - 1
    app.undo_last_move()
    assert len(app.arrows) == before
    pygame.quit()


def test_auto_save_and_restore_progress() -> None:
    save_file = _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=True)
    app.state = "playing"
    app.score = 1234
    app.energy = 56
    app.save_progress()
    assert save_file.exists()

    restored = NeonArrowApp((1100, 700), load_save=True)
    assert restored.score == 1234
    assert restored.energy == 56
    assert restored.level_index == app.level_index
    pygame.quit()


def test_saved_progress_still_reopens_on_setup_and_requires_matching_choice() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=True)
    app.select_setup_mode("basic")
    app.select_setup_difficulty(2)
    app.start_selected_game()
    app.score = 2468
    app.save_progress()

    restored = NeonArrowApp((1100, 700), load_save=True)
    assert restored.state == "setup"
    assert restored.pending_mode is None
    assert restored.pending_difficulty is None
    assert restored.resume_available is True
    assert restored.resume_mode == "basic"
    assert restored.resume_level_index == 2
    assert restored.score == 2468

    restored.start_selected_game()
    assert restored.state == "setup"
    restored.select_setup_mode("basic")
    restored.select_setup_difficulty(2)
    restored.resume_selected_game()
    assert restored.state == "playing"
    assert restored.score == 2468
    pygame.quit()


def test_accessibility_settings_persist() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=True)
    app.reduced_motion = True
    app.sound_enabled = False
    app.save_progress()

    restored = NeonArrowApp((1100, 700), load_save=True)
    assert restored.reduced_motion is True
    assert restored.sound_enabled is False
    pygame.quit()


def test_every_launch_requires_mode_and_difficulty_selection() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    assert app.state == "setup"
    assert app.pending_mode is None
    assert app.pending_difficulty is None
    app.start_selected_game()
    assert app.state == "setup"
    app.select_setup_mode("basic")
    app.start_selected_game()
    assert app.state == "setup"
    pygame.quit()


def test_basic_mode_is_real_single_cell_assignment_rule() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.select_setup_mode("basic")
    app.select_setup_difficulty(1)
    app.start_selected_game()

    assert app.state == "playing"
    assert app.game_mode == "basic"
    assert app.level_index == 1
    assert app.training_mode is False
    assert all(len(arrow["cells"]) == 1 for arrow in app.arrows)
    assert app.level["config"]["gates"] == []
    assert app.level["config"]["portals"] == []
    assert app.level["config"]["phase_locks"] == []
    assert is_solution_valid(app.level)
    pygame.quit()


def test_advanced_mode_still_uses_long_arrow_mechanics() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.select_setup_mode("advanced")
    app.select_setup_difficulty(2)
    app.start_selected_game()

    assert app.game_mode == "advanced"
    assert app.level_index == 2
    assert app.training_mode is False
    assert any(len(arrow["cells"]) > 1 for arrow in app.arrows)
    assert app.level["config"]["portals"]
    assert app.level["config"]["phase_locks"]
    pygame.quit()


def test_mid_game_difficulty_switch_keeps_mode_and_starts_fresh_level() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.select_setup_mode("basic")
    app.select_setup_difficulty(0)
    app.start_selected_game()
    original_seed = app.session_seed

    app.score = 999
    app.energy = 88
    app.combo = 7
    app.open_difficulty_menu()
    assert app.difficulty_menu_open is True
    app.switch_difficulty(2)

    assert app.difficulty_menu_open is False
    assert app.state == "playing"
    assert app.game_mode == "basic"
    assert app.level_index == 2
    assert app.training_mode is True
    assert app.session_seed != original_seed
    assert app.score == 0
    assert app.energy == 0
    assert app.combo == 0
    assert all(len(arrow["cells"]) == 1 for arrow in app.arrows)
    assert app.level["config"]["difficulty"] == "终极困难"
    pygame.quit()


def test_d_key_opens_difficulty_menu_and_number_key_switches() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.select_setup_mode("advanced")
    app.select_setup_difficulty(0)
    app.start_selected_game()

    app.process_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_d))
    assert app.difficulty_menu_open is True
    app.process_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_2))

    assert app.difficulty_menu_open is False
    assert app.level_index == 1
    assert app.game_mode == "advanced"
    assert app.state == "playing"
    pygame.quit()


def test_difficulty_menu_pauses_timer_and_exposes_sidebar_button() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.select_setup_mode("advanced")
    app.select_setup_difficulty(1)
    app.start_selected_game()
    before = app.time_left

    app.open_difficulty_menu()
    app.update(5.0)
    assert app.time_left == before

    app.close_difficulty_menu()
    app.render()
    assert "open_difficulty" in {action for _rect, action in app.buttons}
    pygame.quit()


def test_sidebar_control_icons_have_complete_purpose_help() -> None:
    expected = {
        "open_difficulty",
        "overdrive",
        "undo",
        "save",
        "ai_solve",
        "restart",
        "toggle_motion",
        "toggle_sound",
    }
    assert set(CONTROL_HELP) == expected
    for title, shortcut, description in CONTROL_HELP.values():
        assert title
        assert shortcut
        assert len(description) >= 12


def test_hovering_sidebar_control_exposes_contextual_help(monkeypatch) -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    app.render()
    rect = next(rect for rect, action in app.buttons if action == "restart")
    monkeypatch.setattr(pygame.mouse, "get_pos", lambda: rect.center)
    app.render()
    assert app.hovered_action == "restart"
    pygame.quit()


def test_static_render_assets_are_reused_between_frames() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    app.render()
    background = app._background_cache
    grid_layers = tuple(app._grid_cache.values())
    arrow_layer = app._effect_layers["arrow_glow"]

    app.render()
    assert app._background_cache is background
    assert tuple(app._grid_cache.values()) == grid_layers
    assert app._effect_layers["arrow_glow"] is arrow_layer
    pygame.quit()


def test_hover_does_not_reveal_route_safety(monkeypatch) -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    app.hovered_arrow_id = app.arrows[0]["id"]

    def forbidden_hover_trace(*_args: object, **_kwargs: object) -> dict[str, object]:
        raise AssertionError("悬停不应调用安全路径判定")

    monkeypatch.setattr(app_module, "trace_arrow", forbidden_hover_trace)
    app.render()
    pygame.quit()


def test_manual_safe_route_hint_control_is_removed() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    app.score = 500
    app.render()

    assert "hint" not in {action for _rect, action in app.buttons}
    assert not hasattr(app, "hint_arrow_id")
    app.process_event(pygame.event.Event(pygame.KEYDOWN, key=pygame.K_h))
    assert app.score == 500
    assert not hasattr(app, "hint_arrow_id")
    pygame.quit()


def test_cleared_arrow_animates_out_before_disappearing() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    safe_id = safe_arrow_ids(app.level, app.arrows)[0]
    arrow = next(item for item in app.arrows if item["id"] == safe_id)

    app.handle_arrow_click(arrow)
    assert safe_id not in {item["id"] for item in app.arrows}
    assert len(app.exiting_arrows) == 1
    assert app.exiting_arrows[0].arrow["id"] == safe_id

    assert app.exiting_arrows[0].duration >= 0.80
    app.update(0.40)
    assert len(app.exiting_arrows) == 1
    app.render()

    app.update(0.47)
    assert not app.exiting_arrows
    pygame.quit()


def test_exit_fade_is_visibly_progressive() -> None:
    assert _exit_opacity(0.10) == 255
    assert _exit_opacity(0.55) == 255
    mid_alpha = _exit_opacity(0.78)
    late_alpha = _exit_opacity(0.90)
    assert 120 <= mid_alpha <= 170
    assert 25 <= late_alpha <= 65
    assert mid_alpha > late_alpha > 0


def test_exit_geometry_flows_head_first_instead_of_rigid_translation(monkeypatch) -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    synthetic_points = [(120.0, 360.0), (120.0, 240.0), (240.0, 240.0)]
    synthetic_arrow = {"id": "a999", "dir": "right"}
    monkeypatch.setattr(app, "arrow_visual_points", lambda _arrow: synthetic_points)

    early = app.exiting_arrow_points(synthetic_arrow, 0.16)
    head_dx = early[-1][0] - synthetic_points[-1][0]
    head_dy = early[-1][1] - synthetic_points[-1][1]
    tail_dx = early[0][0] - synthetic_points[0][0]
    tail_dy = early[0][1] - synthetic_points[0][1]

    # The head has already moved along the final rightward heading while the
    # tail is still travelling through the original vertical leg.  A rigid
    # translation would give both endpoints exactly the same displacement.
    assert head_dx > 0
    assert abs(head_dy) < 1e-6
    assert abs(tail_dx) < 1e-6
    assert tail_dy < 0
    assert (round(head_dx, 3), round(head_dy, 3)) != (round(tail_dx, 3), round(tail_dy, 3))

    # By the end of the dedicated follow phase the whole body has been pulled
    # through the bend and is aligned with the arrow's exit direction.
    straightened = app.exiting_arrow_points(synthetic_arrow, 0.42)
    assert all(abs(point[1] - straightened[0][1]) < 1e-6 for point in straightened)
    pygame.quit()


def test_ai_solver_completes_current_level() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    app.start_ai_solver()
    guard = 0
    while app.state == "playing" and guard < 100:
        app.ai_next_at = 0
        app.update(0)
        guard += 1
    assert app.state == "level_complete"
    assert not app.arrows
    assert guard < 100
    pygame.quit()


def test_level_selection_keeps_campaign_at_three_levels() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.select_level(TOTAL_LEVELS - 1)
    assert app.level_index == TOTAL_LEVELS - 1
    assert app.state == "ready"
    assert len(app.level["solution_order"]) == len(app.arrows)
    pygame.quit()


def test_selected_third_level_is_training_not_fake_campaign_clear() -> None:
    _use_temp_save()
    app = NeonArrowApp((1100, 700), load_save=False)
    app.select_level(TOTAL_LEVELS - 1)
    app.start_game()
    for arrow_id in list(app.level["solution_order"]):
        arrow = next(item for item in app.arrows if item["id"] == arrow_id)
        app.handle_arrow_click(arrow)
    assert app.training_mode is True
    assert app.state == "training_complete"
    pygame.quit()
