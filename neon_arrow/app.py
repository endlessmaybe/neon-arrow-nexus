from __future__ import annotations

from array import array
from copy import deepcopy
from dataclasses import dataclass
import json
import math
import os
from pathlib import Path
import random
import time
from typing import Any

import pygame

from .engine import (
    DIRECTIONS,
    GRID_COLS,
    GRID_ROWS,
    LEVEL_CONFIGS,
    TOTAL_LEVELS,
    create_basic_level,
    create_level,
    create_session_seed,
    safe_arrow_ids,
    session_code,
    solve_current_state,
    trace_arrow,
)


BASE_WINDOW_SIZE = (1280, 800)
WINDOW_SIZE = (1600, 1000)
MIN_WINDOW_SIZE = (1000, 660)
FPS = 60

BG_TOP = (5, 9, 18)
BG_MID = (8, 14, 27)
BG_BOTTOM = (8, 11, 22)
TEXT = (240, 248, 255)
MUTED = (144, 164, 193)
SUBTLE = (92, 112, 145)
CYAN = (60, 236, 255)
BLUE = (75, 142, 255)
MAGENTA = (255, 86, 210)
PURPLE = (142, 121, 255)
GREEN = (112, 246, 181)
GOLD = (255, 198, 92)
RED = (255, 101, 133)
PANEL = (10, 17, 31, 238)
PANEL_SOFT = (14, 23, 41, 210)
PANEL_INNER = (17, 27, 46, 186)
HAIRLINE = (145, 178, 220)

SAVE_DIR = Path(os.environ.get("LOCALAPPDATA", Path.home())) / "NeonArrowNexus"
SAVE_FILE = SAVE_DIR / "savegame.json"


@dataclass
class Particle:
    x: float
    y: float
    vx: float
    vy: float
    life: float
    max_life: float
    color: tuple[int, int, int]
    size: float


@dataclass
class ExitingArrow:
    arrow: dict[str, Any]
    elapsed: float = 0.0
    duration: float = 0.86


def _clamp(value: float, low: float, high: float) -> float:
    return max(low, min(high, value))


def _smoothstep(value: float) -> float:
    value = _clamp(value, 0.0, 1.0)
    return value * value * (3.0 - 2.0 * value)


def _exit_opacity(progress: float) -> int:
    """Let the ordered exit remain readable before a restrained final fade."""
    fade_progress = _clamp((progress - 0.55) / 0.45, 0.0, 1.0)
    return int(round(255 * (1.0 - _smoothstep(fade_progress))))


def _polyline_length(points: list[tuple[float, float]]) -> float:
    return sum(
        math.hypot(end[0] - start[0], end[1] - start[1])
        for start, end in zip(points, points[1:])
    )


def _point_on_polyline(points: list[tuple[float, float]], distance: float) -> tuple[float, float]:
    if not points:
        return (0.0, 0.0)
    if len(points) == 1:
        return points[0]
    total = _polyline_length(points)
    distance = _clamp(distance, 0.0, total)
    walked = 0.0
    for start, end in zip(points, points[1:]):
        segment = math.hypot(end[0] - start[0], end[1] - start[1])
        if segment <= 1e-9:
            continue
        if walked + segment >= distance:
            ratio = (distance - walked) / segment
            return (
                start[0] + (end[0] - start[0]) * ratio,
                start[1] + (end[1] - start[1]) * ratio,
            )
        walked += segment
    return points[-1]


def _slice_polyline(
    points: list[tuple[float, float]],
    start_distance: float,
    end_distance: float,
) -> list[tuple[float, float]]:
    """Return the visible interval of a polyline, preserving any bends inside it."""
    if not points:
        return []
    total = _polyline_length(points)
    start_distance = _clamp(start_distance, 0.0, total)
    end_distance = _clamp(end_distance, start_distance, total)
    result = [_point_on_polyline(points, start_distance)]
    walked = 0.0
    for start, end in zip(points, points[1:]):
        walked += math.hypot(end[0] - start[0], end[1] - start[1])
        if start_distance + 1e-6 < walked < end_distance - 1e-6:
            result.append(end)
    finish = _point_on_polyline(points, end_distance)
    if math.hypot(finish[0] - result[-1][0], finish[1] - result[-1][1]) > 1e-6:
        result.append(finish)
    return result


def _mix(a: tuple[int, int, int], b: tuple[int, int, int], amount: float) -> tuple[int, int, int]:
    amount = _clamp(amount, 0.0, 1.0)
    return tuple(int(x + (y - x) * amount) for x, y in zip(a, b))


def _point_segment_distance(
    point: tuple[float, float],
    start: tuple[float, float],
    end: tuple[float, float],
) -> float:
    dx = end[0] - start[0]
    dy = end[1] - start[1]
    length_sq = dx * dx + dy * dy
    if length_sq <= 1e-9:
        return math.hypot(point[0] - start[0], point[1] - start[1])
    ratio = ((point[0] - start[0]) * dx + (point[1] - start[1]) * dy) / length_sq
    ratio = _clamp(ratio, 0.0, 1.0)
    nearest = (start[0] + ratio * dx, start[1] + ratio * dy)
    return math.hypot(point[0] - nearest[0], point[1] - nearest[1])


class NeonArrowApp:
    def __init__(self, size: tuple[int, int] = WINDOW_SIZE, *, load_save: bool = True) -> None:
        pygame.mixer.pre_init(44100, -16, 1, 256)
        pygame.init()
        pygame.font.init()
        flags = pygame.RESIZABLE | pygame.DOUBLEBUF
        self.screen = pygame.display.set_mode(size, flags)
        pygame.display.set_caption("霓虹箭域 · Neon Arrow Nexus · Python Edition")
        self.clock = pygame.time.Clock()
        self.running = True
        self.fonts: dict[tuple[int, bool], pygame.font.Font] = {}
        self.rng = random.Random(20260915)
        self.stars = [
            (
                self.rng.random(),
                self.rng.random(),
                self.rng.uniform(0.7, 2.2),
                self.rng.uniform(0.4, 1.8),
            )
            for _ in range(42)
        ]
        self.particles: list[Particle] = []
        self.exiting_arrows: list[ExitingArrow] = []
        self.buttons: list[tuple[pygame.Rect, str]] = []
        self.hovered_arrow_id: str | None = None
        self.banner_text = ""
        self.banner_until = 0.0
        self.reduced_motion = False
        self.boot_started_at = time.perf_counter()
        self.boot_duration = 1.15
        self.boot_enabled = os.environ.get("SDL_VIDEODRIVER", "").lower() != "dummy"
        self.shake = 0.0
        self.history: list[dict[str, Any]] = []
        self.ai_queue: list[str] = []
        self.ai_next_at = 0.0
        self.persistence_enabled = load_save
        self.sound_enabled = True
        self.sounds = self.build_sounds()
        self.game_mode = "advanced"
        self.pending_mode: str | None = None
        self.pending_difficulty: int | None = None
        self.resume_available = False
        self.resume_state = "ready"
        self.resume_mode = "advanced"
        self.resume_level_index = 0
        self.training_mode = False
        self.undos_used = 0
        self.ai_used = False
        self.last_stars = 0
        self.best_stars = [0] * TOTAL_LEVELS
        self.session_seed = create_session_seed()
        self.level_index = 0
        self.level: dict[str, Any] = {}
        self.arrows: list[dict[str, Any]] = []
        self.score = 0
        self.combo = 0
        self.energy = 0
        self.lives = 0
        self.time_left = 0.0
        self.overdrive = False
        self.state = "ready"
        self.last_tick = time.perf_counter()
        self.load_level(0, keep_state=True)
        restored = False
        if load_save:
            restored = self.load_progress(silent=True)
        if restored:
            self.resume_available = True
            self.resume_state = self.state
            self.resume_mode = self.game_mode
            self.resume_level_index = self.level_index
        # Every real program launch starts from an explicit mode+difficulty
        # chooser.  A loaded save remains available, but it can only be resumed
        # after the player deliberately selects the matching mode/difficulty.
        self.state = "setup"

    def layout_scale(self) -> float:
        width, height = self.screen.get_size()
        base_width, base_height = BASE_WINDOW_SIZE
        # Scale the game board and major layout rails on larger native-DPI
        # windows without letting a maximized window become excessively loose.
        return _clamp(min(width / base_width, height / base_height), 0.90, 1.20)

    def px(self, value: float) -> int:
        return max(1, int(round(value * self.layout_scale())))

    def build_sounds(self) -> dict[str, pygame.mixer.Sound]:
        if not pygame.mixer.get_init():
            return {}

        def make_tone(frequency: float, milliseconds: int, volume: float) -> pygame.mixer.Sound:
            rate = 44100
            count = max(1, int(rate * milliseconds / 1000))
            samples = array("h")
            for index in range(count):
                fade = max(0.0, 1.0 - index / count)
                attack = min(1.0, index / max(1, int(count * 0.08)))
                value = int(32767 * volume * fade * attack * math.sin(math.tau * frequency * index / rate))
                samples.append(value)
            return pygame.mixer.Sound(buffer=samples.tobytes())

        try:
            return {
                "clear": make_tone(690, 105, 0.22),
                "error": make_tone(135, 150, 0.16),
                "power": make_tone(930, 190, 0.20),
                "undo": make_tone(360, 90, 0.14),
                "save": make_tone(820, 90, 0.15),
                "ai": make_tone(1040, 110, 0.14),
                "win": make_tone(1240, 260, 0.18),
            }
        except pygame.error:
            return {}

    def play_sound(self, name: str) -> None:
        if self.sound_enabled and name in self.sounds:
            self.sounds[name].play()

    def capture_move_state(self) -> dict[str, Any]:
        return {
            "arrows": deepcopy(self.arrows),
            "score": self.score,
            "combo": self.combo,
            "energy": self.energy,
            "lives": self.lives,
            "time_left": self.time_left,
            "overdrive": self.overdrive,
            "state": self.state,
            "training_mode": self.training_mode,
            "undos_used": self.undos_used,
            "ai_used": self.ai_used,
            "last_stars": self.last_stars,
            "best_stars": list(self.best_stars),
        }

    def restore_move_state(self, snapshot: dict[str, Any]) -> None:
        self.exiting_arrows.clear()
        self.arrows = deepcopy(snapshot["arrows"])
        self.score = int(snapshot["score"])
        self.combo = int(snapshot["combo"])
        self.energy = int(snapshot["energy"])
        self.lives = int(snapshot["lives"])
        self.time_left = float(snapshot["time_left"])
        self.overdrive = bool(snapshot["overdrive"])
        self.state = str(snapshot["state"])
        self.training_mode = bool(snapshot.get("training_mode", False))
        self.undos_used = int(snapshot.get("undos_used", 0))
        self.ai_used = bool(snapshot.get("ai_used", False))
        self.last_stars = int(snapshot.get("last_stars", 0))
        best_stars = snapshot.get("best_stars", self.best_stars)
        if isinstance(best_stars, list) and len(best_stars) == TOTAL_LEVELS:
            self.best_stars = [max(0, min(3, int(value))) for value in best_stars]

    def save_progress(self, *, manual: bool = False) -> None:
        if not self.persistence_enabled:
            return
        snapshot = self.capture_move_state()
        if self.state == "setup":
            # Persist setting changes made around the startup chooser without
            # replacing the resumable gameplay state by the transient chooser.
            snapshot["state"] = self.resume_state if self.resume_available else "ready"
        data = {
            "version": 2,
            "game_mode": self.game_mode,
            "session_seed": self.session_seed,
            "level_index": self.level_index,
            "settings": {
                "sound_enabled": self.sound_enabled,
                "reduced_motion": self.reduced_motion,
            },
            **snapshot,
        }
        try:
            SAVE_DIR.mkdir(parents=True, exist_ok=True)
            temporary = SAVE_FILE.with_suffix(".tmp")
            temporary.write_text(json.dumps(data, ensure_ascii=False, indent=2), encoding="utf-8")
            temporary.replace(SAVE_FILE)
            if manual:
                self.play_sound("save")
                self.flash_banner("进度已保存")
        except OSError:
            self.flash_banner("自动存档失败，但当前游戏可继续")

    def load_progress(self, silent: bool = False) -> bool:
        if not self.persistence_enabled:
            return False
        if not SAVE_FILE.exists():
            return False
        try:
            data = json.loads(SAVE_FILE.read_text(encoding="utf-8"))
            if data.get("version") not in {1, 2}:
                return False
            self.session_seed = int(data["session_seed"]) & 0xFFFFFFFF
            index = int(data["level_index"])
            if not 0 <= index < TOTAL_LEVELS:
                return False
            mode = str(data.get("game_mode", "advanced"))
            self.game_mode = mode if mode in {"basic", "advanced"} else "advanced"
            self.load_level(index, keep_state=True)
            self.restore_move_state(data)
            settings = data.get("settings", {})
            if isinstance(settings, dict):
                self.sound_enabled = bool(settings.get("sound_enabled", self.sound_enabled))
                self.reduced_motion = bool(settings.get("reduced_motion", self.reduced_motion))
            if self.state not in {"ready", "playing", "level_complete", "campaign_complete", "training_complete", "failed"}:
                self.state = "ready"
            if not silent:
                self.flash_banner("已恢复上次自动存档")
            return True
        except (OSError, ValueError, KeyError, TypeError, json.JSONDecodeError):
            return False

    def undo_last_move(self) -> None:
        if not self.history:
            self.flash_banner("当前没有可撤销的操作")
            return
        self.restore_move_state(self.history.pop())
        self.undos_used += 1
        self.ai_queue.clear()
        self.play_sound("undo")
        self.flash_banner("已撤销上一步")
        self.save_progress()

    def start_ai_solver(self) -> None:
        if self.state != "playing" or not self.arrows:
            return
        solution = solve_current_state(self.level, self.arrows)
        if not solution:
            self.flash_banner("自动求解器没有找到完整可行解序")
            return
        self.history.append(self.capture_move_state())
        self.history = self.history[-30:]
        self.ai_used = True
        self.score = max(0, self.score - 300)
        self.ai_queue = solution
        self.ai_next_at = time.perf_counter()
        self.play_sound("ai")
        self.flash_banner(f"AI 自动求解启动 · 已计算 {len(solution)} 步可行解序（-300）")
        self.save_progress()

    def select_level(self, index: int) -> None:
        if not 0 <= index < TOTAL_LEVELS:
            return
        self.session_seed = create_session_seed()
        self.training_mode = True
        self.score = 0
        self.energy = 0
        self.combo = 0
        self.load_level(index, keep_state=True)
        self.state = "ready"
        self.flash_banner(f"单关训练 · 第 {index + 1} 关已随机生成")
        self.save_progress()

    def select_setup_mode(self, mode: str) -> None:
        if mode not in {"basic", "advanced"}:
            return
        self.pending_mode = mode

    def select_setup_difficulty(self, index: int) -> None:
        if 0 <= index < TOTAL_LEVELS:
            self.pending_difficulty = index

    def start_selected_game(self) -> None:
        if self.pending_mode is None or self.pending_difficulty is None:
            self.flash_banner("请先选择玩法模式和难度")
            return
        self.game_mode = self.pending_mode
        self.session_seed = create_session_seed()
        self.training_mode = True
        self.score = 0
        self.energy = 0
        self.combo = 0
        self.overdrive = False
        self.load_level(self.pending_difficulty, keep_state=True)
        self.state = "playing"
        self.resume_available = False
        mode_name = "基础模式" if self.game_mode == "basic" else "进阶模式"
        self.flash_banner(f"{mode_name} · {self.level['config']['difficulty']}")
        self.save_progress()

    def resume_selected_game(self) -> None:
        if not self.resume_available:
            self.flash_banner("当前没有可继续的存档")
            return
        if self.pending_mode != self.resume_mode or self.pending_difficulty != self.resume_level_index:
            self.flash_banner("请先选择与存档一致的模式和难度")
            return
        self.state = self.resume_state
        self.flash_banner("已继续上次进度")

    def return_to_setup(self) -> None:
        self.pending_mode = None
        self.pending_difficulty = None
        self.state = "setup"

    def stars_earned(self) -> int:
        config = self.level.get("config", {})
        full_lives = max(1, int(config.get("lives", 1)))
        full_time = max(1.0, float(config.get("time", 1)))
        time_ratio = self.time_left / full_time
        if self.ai_used:
            return 1
        stars = 1
        if self.lives > 0:
            stars = 2
        if self.lives >= max(1, full_lives - 1) and time_ratio >= 0.35:
            stars = 3
        if self.undos_used > 0:
            stars = min(stars, 2)
        return stars

    def finish_current_level(self) -> None:
        self.last_stars = self.stars_earned()
        self.best_stars[self.level_index] = max(self.best_stars[self.level_index], self.last_stars)
        self.ai_queue.clear()
        self.play_sound("win")
        if self.training_mode:
            self.state = "training_complete"
        elif self.level_index == TOTAL_LEVELS - 1:
            self.state = "campaign_complete"
        else:
            self.state = "level_complete"
        self.save_progress()

    def font(self, size: int, bold: bool = False) -> pygame.font.Font:
        font_scale = min(1.10, self.layout_scale())
        rendered_size = max(8, int(round(size * font_scale)))
        key = (rendered_size, bold)
        if key not in self.fonts:
            names = ["Microsoft YaHei UI", "Microsoft YaHei", "Segoe UI", "Arial"]
            path = None
            for name in names:
                path = pygame.font.match_font(name, bold=bold)
                if path:
                    break
            self.fonts[key] = pygame.font.Font(path, rendered_size)
            self.fonts[key].set_bold(bold)
        return self.fonts[key]

    def new_run(self, auto_start: bool = False) -> None:
        self.session_seed = create_session_seed()
        self.training_mode = False
        self.level_index = 0
        self.score = 0
        self.combo = 0
        self.energy = 0
        self.overdrive = False
        self.load_level(0, keep_state=True)
        self.state = "playing" if auto_start else "ready"
        self.flash_banner(f"NEW RUN · {session_code(self.session_seed)}")
        self.save_progress()

    def load_level(self, level_index: int, keep_state: bool = False) -> None:
        self.level_index = level_index
        self.level = (
            create_basic_level(level_index, self.session_seed)
            if self.game_mode == "basic"
            else create_level(level_index, self.session_seed)
        )
        self.arrows = deepcopy(self.level["arrows"])
        self.exiting_arrows.clear()
        config = self.level["config"]
        self.lives = int(config["lives"])
        self.time_left = float(config["time"])
        self.combo = 0
        self.overdrive = False
        self.undos_used = 0
        self.ai_used = False
        self.last_stars = 0
        self.history.clear()
        self.ai_queue.clear()
        if not keep_state:
            self.state = "playing"

    def restart_level(self) -> None:
        self.load_level(self.level_index)
        self.flash_banner("本关已按同一 RUN 重置")
        self.save_progress()

    def start_game(self) -> None:
        self.state = "playing"
        self.flash_banner("箭域同步完成")
        self.save_progress()

    def next_level(self) -> None:
        if self.level_index >= TOTAL_LEVELS - 1:
            self.new_run(auto_start=True)
            return
        self.load_level(self.level_index + 1)
        self.flash_banner(f"进入第 {self.level_index + 1} 关 · {self.level['config']['difficulty']}")
        self.save_progress()

    def activate_overdrive(self) -> None:
        if self.state != "playing":
            return
        if self.energy < 100:
            self.flash_banner(f"量子能量不足 · {self.energy}%")
            return
        self.overdrive = True
        self.play_sound("power")
        self.flash_banner("量子超载已激活 · 下一次受阻箭可相位穿透")
        self.save_progress()

    def flash_banner(self, text: str, duration: float = 2.2) -> None:
        self.banner_text = text
        self.banner_until = time.perf_counter() + duration

    def toggle_reduced_motion(self) -> None:
        self.reduced_motion = not self.reduced_motion
        if self.reduced_motion:
            self.boot_enabled = False
        self.flash_banner("低动态模式已开启" if self.reduced_motion else "低动态模式已关闭")
        self.save_progress()

    def board_geometry(self) -> tuple[pygame.Rect, int, tuple[int, int]]:
        width, height = self.screen.get_size()
        sidebar_width = max(self.px(286), min(self.px(330), int(width * 0.25)))
        board_panel = pygame.Rect(
            sidebar_width + self.px(50),
            self.px(96),
            width - sidebar_width - self.px(82),
            height - self.px(126),
        )
        cell = max(
            self.px(30),
            min(
                (board_panel.width - self.px(80)) // GRID_COLS,
                (board_panel.height - self.px(70)) // GRID_ROWS,
                self.px(50),
            ),
        )
        grid_width = cell * GRID_COLS
        grid_height = cell * GRID_ROWS
        origin = (
            board_panel.centerx - grid_width // 2,
            board_panel.centery - grid_height // 2 + self.px(6),
        )
        return board_panel, cell, origin

    def cell_center(self, x: int, y: int) -> tuple[int, int]:
        _, cell, origin = self.board_geometry()
        return origin[0] + x * cell + cell // 2, origin[1] + y * cell + cell // 2

    def arrow_visual_points(self, arrow: dict[str, Any]) -> list[tuple[float, float]]:
        head = self.cell_center(arrow["head"]["x"], arrow["head"]["y"])
        _, cell, _ = self.board_geometry()
        visual_route = arrow.get("visual_route")
        if visual_route:
            return [
                (head[0] + float(point["dx"]) * cell, head[1] + float(point["dy"]) * cell)
                for point in visual_route
            ]

        cells = arrow.get("cells", [])
        if len(cells) <= 1:
            return [head]
        return [self.cell_center(cell_data["x"], cell_data["y"]) for cell_data in cells]

    def exiting_arrow_points(
        self,
        arrow: dict[str, Any],
        progress: float,
    ) -> list[tuple[float, float]]:
        """Move an arrow head-first so its body follows the route instead of translating rigidly."""
        points = self.arrow_visual_points(arrow)
        if len(points) < 2:
            return points
        body_length = _polyline_length(points)
        head = points[-1]
        direction = DIRECTIONS[arrow["dir"]]
        dx = float(direction["x"])
        dy = float(direction["y"])
        width, height = self.screen.get_size()
        margin = float(self.px(72))
        if dx > 0:
            edge_distance = width + margin - head[0]
        elif dx < 0:
            edge_distance = head[0] + margin
        elif dy > 0:
            edge_distance = height + margin - head[1]
        else:
            edge_distance = head[1] + margin

        extension = max(1.0, edge_distance + body_length)
        exit_end = (head[0] + dx * extension, head[1] + dy * extension)
        path = [*points, exit_end]
        # Give the body-following phase enough screen time to be readable.
        # If the complete off-screen distance drives one easing curve, a short
        # 2-4 cell L-shape straightens in only a handful of frames on a 1600px
        # window and still feels like a rigid sprite translation.  The first
        # phase therefore pulls the complete body through its own bend; only
        # after that does the straightened arrow continue toward the edge.
        follow_phase = 0.42
        if progress <= follow_phase:
            local = _clamp(progress / follow_phase, 0.0, 1.0)
            travel = body_length * _smoothstep(local)
        else:
            local = _clamp((progress - follow_phase) / (1.0 - follow_phase), 0.0, 1.0)
            travel = body_length + max(0.0, extension - body_length) * _smoothstep(local)
        return _slice_polyline(path, travel, travel + body_length)

    def arrow_at_point(self, pos: tuple[int, int]) -> dict[str, Any] | None:
        _, cell, origin = self.board_geometry()
        gx = int((pos[0] - origin[0]) // cell)
        gy = int((pos[1] - origin[1]) // cell)
        if not (0 <= gx < GRID_COLS and 0 <= gy < GRID_ROWS):
            return None
        for arrow in reversed(self.arrows):
            points = self.arrow_visual_points(arrow)
            if len(points) > 1:
                hit_radius = max(8.0, cell * 0.17)
                if any(
                    _point_segment_distance(pos, start, end) <= hit_radius
                    for start, end in zip(points, points[1:])
                ):
                    return arrow
            elif any(cell_data["x"] == gx and cell_data["y"] == gy for cell_data in arrow["cells"]):
                return arrow
        return None

    def handle_arrow_click(self, arrow: dict[str, Any], *, automated: bool = False) -> None:
        if self.state != "playing":
            return
        if not automated:
            self.ai_queue.clear()
            self.history.append(self.capture_move_state())
            self.history = self.history[-30:]
        config = self.level["config"]
        trace = trace_arrow(
            arrow,
            self.arrows,
            config["gates"],
            config["portals"],
            config.get("phase_locks", []),
        )
        clear = bool(trace["clear"])
        forced = self.overdrive and not clear

        if clear or forced:
            self.exiting_arrows.append(
                ExitingArrow(
                    arrow=deepcopy(arrow),
                    duration=0.60 if self.reduced_motion else 0.86,
                )
            )
            if self.hovered_arrow_id == arrow["id"]:
                self.hovered_arrow_id = None
            self.arrows = [item for item in self.arrows if item["id"] != arrow["id"]]
            self.combo += 1
            base = 0 if automated else 150 + min(12, self.combo) * 18
            if arrow.get("prism") and not automated:
                base += 180
            self.score += base
            if forced:
                self.energy = 0
                self.overdrive = False
                self.play_sound("power")
                self.flash_banner("相位穿透成功 · 稳定度未受损")
            else:
                self.energy = min(100, self.energy + (22 if arrow.get("prism") else 14))
                self.play_sound("clear")
                if not automated:
                    self.flash_banner(f"CLEAR +{base} · COMBO ×{self.combo}", 1.25)
            head_x, head_y = self.cell_center(arrow["head"]["x"], arrow["head"]["y"])
            self.spawn_burst(head_x, head_y, arrow["color"], 18 if arrow.get("prism") else 11)
            if not self.arrows:
                self.finish_current_level()
        else:
            self.lives -= 1
            self.combo = 0
            self.shake = 0.32
            self.play_sound("error")
            blocker = trace.get("blocker_label") or trace.get("blocker_id") or "路径回环"
            self.flash_banner(f"碰撞 · 被 {blocker} 阻挡 · 稳定度 -1")
            hx, hy = self.cell_center(arrow["head"]["x"], arrow["head"]["y"])
            self.spawn_burst(hx, hy, RED, 14)
            if self.lives <= 0:
                self.state = "failed"
        self.save_progress()

    def spawn_burst(self, x: float, y: float, color: tuple[int, int, int], count: int) -> None:
        if self.reduced_motion:
            count = min(count, 4)
        for _ in range(count):
            angle = self.rng.uniform(0, math.tau)
            speed = self.rng.uniform(25, 80) if self.reduced_motion else self.rng.uniform(55, 210)
            life = self.rng.uniform(0.35, 0.8)
            self.particles.append(
                Particle(
                    x=x,
                    y=y,
                    vx=math.cos(angle) * speed,
                    vy=math.sin(angle) * speed,
                    life=life,
                    max_life=life,
                    color=color,
                    size=self.rng.uniform(1.5, 4.2),
                )
            )

    def update(self, dt: float) -> None:
        if self.state == "playing":
            self.time_left -= dt
            if self.time_left <= 0:
                self.time_left = 0
                self.state = "failed"
                self.flash_banner("时间耗尽")
                self.save_progress()

        if self.state == "playing" and self.ai_queue and time.perf_counter() >= self.ai_next_at:
            arrow_id = self.ai_queue.pop(0)
            arrow = next((item for item in self.arrows if item["id"] == arrow_id), None)
            if arrow is not None:
                self.handle_arrow_click(arrow, automated=True)
            self.ai_next_at = time.perf_counter() + 0.14

        if self.shake > 0:
            self.shake = max(0.0, self.shake - dt)

        active_exits: list[ExitingArrow] = []
        for exiting in self.exiting_arrows:
            exiting.elapsed += dt
            if exiting.elapsed < exiting.duration:
                active_exits.append(exiting)
        self.exiting_arrows = active_exits

        updated: list[Particle] = []
        for particle in self.particles:
            particle.life -= dt
            if particle.life <= 0:
                continue
            particle.x += particle.vx * dt
            particle.y += particle.vy * dt
            particle.vx *= 0.985
            particle.vy *= 0.985
            updated.append(particle)
        self.particles = updated

    def handle_action(self, action: str) -> None:
        if action == "mode_basic":
            self.select_setup_mode("basic")
        elif action == "mode_advanced":
            self.select_setup_mode("advanced")
        elif action.startswith("difficulty_"):
            self.select_setup_difficulty(int(action.split("_", 1)[1]))
        elif action == "start_selected":
            self.start_selected_game()
        elif action == "resume_selected":
            self.resume_selected_game()
        elif action == "start":
            self.start_game()
        elif action == "overdrive":
            self.activate_overdrive()
        elif action == "restart":
            self.restart_level()
        elif action == "undo":
            self.undo_last_move()
        elif action == "ai_solve":
            self.start_ai_solver()
        elif action == "save":
            self.save_progress(manual=True)
        elif action == "toggle_sound":
            self.sound_enabled = not self.sound_enabled
            self.flash_banner("音效已开启" if self.sound_enabled else "音效已关闭")
            self.save_progress()
        elif action == "toggle_motion":
            self.toggle_reduced_motion()
        elif action == "next":
            self.next_level()
        elif action == "new_run":
            self.new_run(auto_start=True)
        elif action == "home":
            self.return_to_setup()
        elif action.startswith("select_"):
            self.select_level(int(action.split("_", 1)[1]))

    def process_event(self, event: pygame.event.Event) -> None:
        if event.type == pygame.QUIT:
            self.save_progress()
            self.running = False
        elif event.type == pygame.VIDEORESIZE:
            width = max(MIN_WINDOW_SIZE[0], event.w)
            height = max(MIN_WINDOW_SIZE[1], event.h)
            self.screen = pygame.display.set_mode((width, height), pygame.RESIZABLE | pygame.DOUBLEBUF)
        elif event.type == pygame.KEYDOWN:
            if event.key == pygame.K_ESCAPE:
                self.save_progress()
                self.running = False
            elif self.state == "setup" and event.key == pygame.K_b:
                self.select_setup_mode("basic")
            elif self.state == "setup" and event.key == pygame.K_n:
                self.select_setup_mode("advanced")
            elif self.state == "setup" and event.key in (pygame.K_1, pygame.K_2, pygame.K_3):
                self.select_setup_difficulty(event.key - pygame.K_1)
            elif self.state == "setup" and event.key in (pygame.K_RETURN, pygame.K_SPACE):
                self.start_selected_game()
            elif event.key in (pygame.K_RETURN, pygame.K_SPACE) and self.state == "ready":
                self.start_game()
            elif event.key == pygame.K_r:
                self.restart_level()
            elif event.key == pygame.K_o:
                self.activate_overdrive()
            elif event.key == pygame.K_u:
                self.undo_last_move()
            elif event.key == pygame.K_a:
                self.start_ai_solver()
            elif event.key == pygame.K_s:
                self.save_progress(manual=True)
            elif event.key == pygame.K_m:
                self.sound_enabled = not self.sound_enabled
                self.flash_banner("音效已开启" if self.sound_enabled else "音效已关闭")
                self.save_progress()
            elif event.key == pygame.K_v:
                self.toggle_reduced_motion()
            elif event.key in (pygame.K_1, pygame.K_2, pygame.K_3) and self.state == "ready":
                self.select_level(event.key - pygame.K_1)
        elif event.type == pygame.MOUSEMOTION:
            arrow = self.arrow_at_point(event.pos)
            self.hovered_arrow_id = arrow["id"] if arrow else None
        elif event.type == pygame.MOUSEBUTTONDOWN and event.button == 1:
            for rect, action in reversed(self.buttons):
                if rect.collidepoint(event.pos):
                    self.handle_action(action)
                    return
            arrow = self.arrow_at_point(event.pos)
            if arrow:
                self.handle_arrow_click(arrow)

    def draw_background(self, target: pygame.Surface, now: float) -> None:
        width, height = target.get_size()
        for y in range(0, height, 2):
            ratio = y / max(1, height - 1)
            color = _mix(BG_TOP, BG_BOTTOM, ratio)
            pygame.draw.rect(target, color, (0, y, width, 2))

        haze = pygame.Surface((width, height), pygame.SRCALPHA)
        glows = [
            ((int(width * 0.80), int(height * 0.16)), CYAN, int(min(width, height) * 0.34), 15),
            ((int(width * 0.42), int(height * 0.90)), PURPLE, int(min(width, height) * 0.42), 12),
        ]
        for center, color, radius, strength in glows:
            for scale, alpha in ((1.0, strength // 3), (0.58, strength)):
                pygame.draw.circle(haze, (*color, alpha), center, max(1, int(radius * scale)))
        target.blit(haze, (0, 0))

        for sx, sy, radius, speed in self.stars:
            x = int(sx * width)
            y = int((sy * height + (0 if self.reduced_motion else now * speed * 2.5)) % height)
            shade = 118 + int(radius * 22)
            pygame.draw.circle(target, (shade, min(255, shade + 7), 255), (x, y), 1)

    def draw_panel(self, target: pygame.Surface, rect: pygame.Rect, border: tuple[int, int, int] = PURPLE) -> None:
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        local = layer.get_rect()
        pygame.draw.rect(layer, PANEL, local, border_radius=18)
        pygame.draw.rect(layer, (*HAIRLINE, 42), local, width=1, border_radius=18)
        pygame.draw.line(layer, (*border, 96), (22, 1), (max(22, rect.width - 22), 1), width=1)
        target.blit(layer, rect.topleft)

    def draw_glow(self, target: pygame.Surface, center: tuple[int, int], radius: int, color: tuple[int, int, int], alpha: int = 32) -> None:
        if radius <= 0 or alpha <= 0:
            return
        size = radius * 2 + 8
        layer = pygame.Surface((size, size), pygame.SRCALPHA)
        c = (size // 2, size // 2)
        for scale, weight in ((1.0, 0.18), (0.72, 0.30), (0.48, 0.52), (0.26, 1.0)):
            pygame.draw.circle(layer, (*color, max(1, int(alpha * weight))), c, max(1, int(radius * scale)))
        target.blit(layer, (center[0] - c[0], center[1] - c[1]))

    def draw_chip(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        value: str,
        color: tuple[int, int, int],
    ) -> None:
        layer = pygame.Surface(rect.size, pygame.SRCALPHA)
        pygame.draw.rect(layer, PANEL_INNER, layer.get_rect(), border_radius=13)
        pygame.draw.rect(layer, (*HAIRLINE, 34), layer.get_rect(), width=1, border_radius=13)
        target.blit(layer, rect.topleft)
        self.draw_text(target, label, (rect.left + 13, rect.top + 9), 10, MUTED, True)
        self.draw_text(target, value, (rect.left + 13, rect.bottom - 10), 16, color, True, "bottomleft")

    def draw_text(
        self,
        target: pygame.Surface,
        text: str,
        pos: tuple[int, int],
        size: int,
        color: tuple[int, int, int] = TEXT,
        bold: bool = False,
        anchor: str = "topleft",
    ) -> pygame.Rect:
        surface = self.font(size, bold).render(text, True, color)
        rect = surface.get_rect()
        setattr(rect, anchor, pos)
        target.blit(surface, rect)
        return rect

    def draw_wrapped_text(
        self,
        target: pygame.Surface,
        text: str,
        rect: pygame.Rect,
        size: int,
        color: tuple[int, int, int] = MUTED,
        line_gap: int = 5,
    ) -> int:
        font = self.font(size)
        lines: list[str] = []
        current = ""
        for char in text:
            if char == "\n":
                lines.append(current)
                current = ""
                continue
            test = current + char
            if font.size(test)[0] > rect.width and current:
                lines.append(current)
                current = char
            else:
                current = test
        if current:
            lines.append(current)

        y = rect.top
        for line in lines:
            target.blit(font.render(line, True, color), (rect.left, y))
            y += font.get_linesize() + line_gap
            if y > rect.bottom:
                break
        return y

    def draw_header(self, target: pygame.Surface) -> None:
        width, _ = target.get_size()
        icon = (43, 42)
        pygame.draw.circle(target, (12, 28, 51), icon, 20)
        pygame.draw.circle(target, (*CYAN,), icon, 20, width=1)
        pygame.draw.line(target, TEXT, (35, 47), (50, 34), width=2)
        pygame.draw.polygon(target, TEXT, [(50, 34), (45, 35), (49, 40)])

        self.draw_text(target, "霓虹箭域", (76, 17), 24, TEXT, True)
        subtitle = (
            "基础 / 进阶双模式 · 启动时选择难度"
            if self.state == "setup"
            else "基础模式 · 单格直线判阻"
            if self.game_mode == "basic"
            else "进阶模式 · 随机长箭与机关"
        )
        self.draw_text(target, subtitle, (77, 49), 11, MUTED, False)

        run = session_code(self.session_seed)
        badge = pygame.Rect(width - 184, 25, 150, 36)
        pygame.draw.rect(target, (10, 20, 36), badge, border_radius=11)
        pygame.draw.rect(target, (*HAIRLINE, 48), badge, width=1, border_radius=11)
        self.draw_text(target, "RUN", (badge.left + 12, badge.centery), 9, MUTED, True, "midleft")
        self.draw_text(target, run, (badge.right - 12, badge.centery), 13, CYAN, True, "midright")

    def draw_sidebar(self, target: pygame.Surface) -> None:
        width, height = target.get_size()
        sidebar_width = max(self.px(286), min(self.px(330), int(width * 0.25)))
        rect = pygame.Rect(self.px(28), self.px(96), sidebar_width - self.px(12), height - self.px(126))
        self.draw_panel(target, rect, CYAN)
        config = self.level["config"]
        x = rect.left + 22
        content_width = rect.width - 44
        y = rect.top + 20
        mode_name = "基础模式" if self.game_mode == "basic" else "进阶模式"
        self.draw_text(target, f"{mode_name} · 难度 {self.level_index + 1} / 3", (x, y), 10, CYAN, True)
        y += 21
        self.draw_text(target, config["name"], (x, y), 21, TEXT, True)
        y += 30
        diff_color = GREEN if self.level_index == 0 else GOLD if self.level_index == 1 else RED
        diff_badge = pygame.Rect(x, y, 86, 24)
        pygame.draw.rect(target, _mix((12, 24, 46), diff_color, 0.16), diff_badge, border_radius=8)
        pygame.draw.rect(target, (*diff_color, 90), diff_badge, width=1, border_radius=8)
        self.draw_text(target, config["difficulty"], diff_badge.center, 11, diff_color, True, "center")
        best = self.best_stars[self.level_index] if self.best_stars else 0
        self.draw_text(target, "★" * best + "☆" * (3 - best), (rect.right - 20, y + 3), 12, GOLD if best else SUBTLE, True, "topright")
        y += 37

        gap = 8
        chip_w = (content_width - gap) // 2
        chip_h = 49
        time_color = GOLD if self.time_left > 20 else RED
        self.draw_chip(target, pygame.Rect(x, y, chip_w, chip_h), "剩余箭路", f"{len(self.arrows):02d}", CYAN)
        self.draw_chip(target, pygame.Rect(x + chip_w + gap, y, chip_w, chip_h), "倒计时", f"{max(0, math.ceil(self.time_left)):03d}s", time_color)
        y += chip_h + 8
        self.draw_chip(target, pygame.Rect(x, y, chip_w, chip_h), "积分", f"{self.score:,}", TEXT)
        self.draw_chip(target, pygame.Rect(x + chip_w + gap, y, chip_w, chip_h), "连击", f"×{self.combo}", MAGENTA if self.combo else MUTED)
        y += chip_h + 10

        status = pygame.Rect(x, y, content_width, 34)
        pygame.draw.rect(target, (12, 25, 49), status, border_radius=11)
        status_color = GREEN if self.lives > 1 else RED
        pygame.draw.rect(target, (*status_color, 58), status, width=1, border_radius=11)
        self.draw_text(target, "稳定度", (status.left + 12, status.centery), 10, MUTED, True, "midleft")
        pip_x = status.right - 16
        for index in range(int(config["lives"]) - 1, -1, -1):
            active = index < self.lives
            color = GREEN if active and self.lives > 1 else RED if active else (58, 72, 96)
            pygame.draw.circle(target, color, (pip_x, status.centery), 5 if active else 4)
            if active:
                pygame.draw.circle(target, TEXT, (pip_x, status.centery), 2)
            pip_x -= 18
        y += 46

        self.draw_text(target, "QUANTUM ENERGY", (x, y), 10, MUTED, True)
        self.draw_text(target, "OVERDRIVE READY" if self.energy >= 100 else "CHARGING", (rect.right - 22, y), 9, CYAN if self.energy >= 100 else SUBTLE, True, "topright")
        y += 18
        bar = pygame.Rect(x, y, content_width, 10)
        pygame.draw.rect(target, (24, 38, 63), bar, border_radius=5)
        fill = bar.copy()
        fill.width = int(bar.width * self.energy / 100)
        if fill.width:
            fill_color = CYAN if self.energy >= 100 else _mix(MAGENTA, CYAN, self.energy / 100)
            self.draw_glow(target, (fill.right, fill.centery), 15, fill_color, 18)
            pygame.draw.rect(target, fill_color, fill, border_radius=5)
        pygame.draw.rect(target, (*CYAN, 82), bar, width=1, border_radius=5)
        self.draw_text(target, f"{self.energy}%", (bar.right, y + 15), 10, CYAN if self.energy == 100 else MUTED, True, "topright")
        y += 35

        self.draw_text(target, "本关提示", (x, y), 9, SUBTLE, True)
        note_rect = pygame.Rect(x, y + 18, content_width, 48)
        self.draw_wrapped_text(target, config["note"], note_rect, 10, MUTED, 2)
        y += 67

        if config["gates"]:
            mechanisms = []
            if any(gate["turn"] in ("cw", "ccw") for gate in config["gates"]):
                mechanisms.append("90° 折光")
            if any(gate["turn"] == "flip" for gate in config["gates"]):
                mechanisms.append("180° 反相")
            if config["portals"]:
                mechanisms.append("双跃迁" if len(config["portals"]) > 1 else "跃迁环")
            if config.get("phase_locks"):
                mechanisms.append("相位封锁")
            if config.get("unique_solution"):
                mechanisms.append("唯一解序")
            self.draw_text(target, "机制  " + " · ".join(mechanisms), (x, y), 9, PURPLE, False)

        button_width = rect.width - 44
        half_width = (button_width - 8) // 2
        self.draw_button(
            target,
            pygame.Rect(x, rect.bottom - 152, button_width, 32),
            "激活量子超载   O" if self.energy >= 100 else f"量子超载 · {self.energy}%",
            "overdrive",
            CYAN if self.energy >= 100 else (72, 88, 113),
            enabled=self.energy >= 100,
        )
        self.draw_button(
            target,
            pygame.Rect(x, rect.bottom - 114, half_width, 32),
            "撤销   U",
            "undo",
            MAGENTA,
            enabled=bool(self.history),
        )
        self.draw_button(
            target,
            pygame.Rect(x + half_width + 8, rect.bottom - 114, half_width, 32),
            "保存   S",
            "save",
            CYAN,
            enabled=self.persistence_enabled,
        )
        self.draw_button(
            target,
            pygame.Rect(x, rect.bottom - 76, button_width, 32),
            "AI 自动求解   A" if not self.ai_queue else "AI 求解进行中…",
            "ai_solve",
            GREEN,
            enabled=self.state == "playing" and bool(self.arrows) and not self.ai_queue,
        )
        third_width = (button_width - 16) // 3
        self.draw_button(target, pygame.Rect(x, rect.bottom - 38, third_width, 28), "重开 R", "restart", (73, 89, 118))
        self.draw_button(
            target,
            pygame.Rect(x + third_width + 8, rect.bottom - 38, third_width, 28),
            "低动态 V",
            "toggle_motion",
            CYAN if self.reduced_motion else (73, 89, 118),
        )
        self.draw_button(
            target,
            pygame.Rect(x + (third_width + 8) * 2, rect.bottom - 38, third_width, 28),
            "音效 M",
            "toggle_sound",
            GOLD if self.sound_enabled else (73, 89, 118),
        )

    def draw_button(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        action: str,
        color: tuple[int, int, int],
        enabled: bool = True,
        large: bool = False,
    ) -> None:
        mouse = pygame.mouse.get_pos()
        hovered = rect.collidepoint(mouse) and enabled
        pressed = hovered and bool(pygame.mouse.get_pressed(num_buttons=3)[0])
        border = color if enabled else (73, 89, 118)

        visual = rect.copy()
        if pressed:
            visual = visual.move(0, 1).inflate(-2, -2)
        fill = _mix((11, 20, 35), color, 0.10 if not hovered else 0.18)
        pygame.draw.rect(target, fill, visual, border_radius=10)
        pygame.draw.rect(target, (*border, 112 if hovered else 58), visual, width=1, border_radius=10)

        label_color = TEXT if enabled else (102, 116, 142)
        text_pos = visual.center
        self.draw_text(target, label, text_pos, 15 if large else 11, label_color, True, "center")
        if enabled:
            self.buttons.append((rect.copy(), action))

    def draw_board(self, target: pygame.Surface, now: float) -> None:
        board_panel, cell, origin = self.board_geometry()
        self.draw_panel(target, board_panel, PURPLE)
        title_y = board_panel.top + 15
        self.draw_text(target, "箭路棋盘", (board_panel.left + 22, title_y), 10, TEXT, True)

        live_color = GREEN if self.state == "playing" else CYAN
        self.draw_text(target, f"剩余 {len(self.arrows):02d}", (board_panel.right - 22, title_y), 10, live_color, True, "topright")

        grid_rect = pygame.Rect(origin[0], origin[1], cell * GRID_COLS, cell * GRID_ROWS)
        grid_layer = pygame.Surface(grid_rect.size, pygame.SRCALPHA)
        pygame.draw.rect(grid_layer, (5, 12, 24, 228), grid_layer.get_rect(), border_radius=16)
        for gy in range(GRID_ROWS):
            for gx in range(GRID_COLS):
                if (gx + gy) % 2:
                    pygame.draw.rect(
                        grid_layer,
                        (42, 64, 92, 10),
                        pygame.Rect(gx * cell + 1, gy * cell + 1, max(1, cell - 2), max(1, cell - 2)),
                    )
        for x in range(GRID_COLS + 1):
            px = min(grid_rect.width - 1, x * cell)
            pygame.draw.line(grid_layer, (112, 145, 177, 18), (px, 0), (px, grid_rect.height))
        for y in range(GRID_ROWS + 1):
            py = min(grid_rect.height - 1, y * cell)
            pygame.draw.line(grid_layer, (112, 145, 177, 18), (0, py), (grid_rect.width, py))
        pygame.draw.rect(grid_layer, (*HAIRLINE, 42), grid_layer.get_rect(), width=1, border_radius=16)
        target.blit(grid_layer, grid_rect.topleft)

        self.draw_special_cells(target, now)

        glow = pygame.Surface(target.get_size(), pygame.SRCALPHA)
        for arrow in self.arrows:
            self.draw_arrow(glow, arrow, now)
        width, height = target.get_size()
        for exiting in self.exiting_arrows:
            progress = _clamp(exiting.elapsed / max(0.001, exiting.duration), 0.0, 1.0)
            points = self.exiting_arrow_points(exiting.arrow, progress)
            if not points:
                continue
            exit_layer = pygame.Surface(target.get_size(), pygame.SRCALPHA)
            self.draw_arrow(
                exit_layer,
                exiting.arrow,
                now,
                force_highlight=False,
                points_override=points,
                head_override=points[-1],
            )
            exit_layer.set_alpha(_exit_opacity(progress))
            glow.blit(exit_layer, (0, 0))
        if self.shake > 0:
            offset = (
                int(math.sin(now * 80) * 5 * (self.shake / 0.32)),
                int(math.cos(now * 67) * 3 * (self.shake / 0.32)),
            )
        else:
            offset = (0, 0)
        target.blit(glow, offset)

    def draw_special_cells(self, target: pygame.Surface, now: float) -> None:
        config = self.level["config"]
        _, cell, _ = self.board_geometry()
        radius = max(8, int(cell * 0.28))
        fx = pygame.Surface(target.get_size(), pygame.SRCALPHA)
        for gate in config["gates"]:
            center = self.cell_center(gate["x"], gate["y"])
            color = GOLD if gate["turn"] == "flip" else PURPLE
            pulse = 0.75 + 0.25 * math.sin(now * 3.2 + gate["x"])
            pygame.draw.circle(fx, (*color, 78), center, radius + 3, width=2)
            angle = now * (1.4 if gate["turn"] != "ccw" else -1.4)
            points = []
            sides = 4 if gate["turn"] == "flip" else 3
            for index in range(sides):
                a = angle + index * math.tau / sides
                points.append((center[0] + math.cos(a) * radius * pulse, center[1] + math.sin(a) * radius * pulse))
            pygame.draw.polygon(fx, (*color, 225), points, width=2)
            label = "180" if gate["turn"] == "flip" else "90"
            self.draw_text(fx, label, center, 9, color, True, "center")

        for portal in config["portals"]:
            centers = [self.cell_center(portal[key]["x"], portal[key]["y"]) for key in ("a", "b")]
            for center in centers:
                pulse = radius + int(3 * math.sin(now * 4.0))
                pygame.draw.circle(fx, (*MAGENTA, 120), center, pulse + 3, width=2)
                pygame.draw.circle(fx, (*CYAN, 220), center, max(4, pulse - 5), width=2)
                self.draw_text(fx, portal["id"], center, 10, TEXT, True, "center")

        for phase_lock in config.get("phase_locks", []):
            center = self.cell_center(phase_lock["x"], phase_lock["y"])
            unlock_remaining = int(phase_lock["unlock_remaining"])
            active = len(self.arrows) > unlock_remaining
            color = RED if active else GREEN
            pulse = 0.72 + 0.28 * math.sin(now * 4.6 + phase_lock["x"] * 0.7)
            outer = radius + 10 + int(3 * pulse)
            pygame.draw.circle(fx, (*color, 190 if active else 120), center, outer, width=2)
            arm = max(5, int(radius * 0.72))
            if active:
                pygame.draw.line(fx, (*color, 235), (center[0] - arm, center[1]), (center[0] + arm, center[1]), 2)
                pygame.draw.line(fx, (*color, 235), (center[0], center[1] - arm), (center[0], center[1] + arm), 2)
            else:
                pygame.draw.circle(fx, (*GREEN, 220), center, max(3, radius // 3), width=2)
            self.draw_text(fx, phase_lock["id"], (center[0], center[1] - radius - 7), 8, color, True, "midbottom")
            self.draw_text(
                fx,
                f"≤{unlock_remaining}",
                (center[0], center[1] + radius + 8),
                7,
                color if active else MUTED,
                True,
                "midtop",
            )
        target.blit(fx, (0, 0))

    def draw_arrow(
        self,
        layer: pygame.Surface,
        arrow: dict[str, Any],
        now: float,
        *,
        offset: tuple[float, float] = (0.0, 0.0),
        force_highlight: bool | None = None,
        points_override: list[tuple[float, float]] | None = None,
        head_override: tuple[float, float] | None = None,
    ) -> None:
        base_head = self.cell_center(arrow["head"]["x"], arrow["head"]["y"])
        head = head_override or (base_head[0] + offset[0], base_head[1] + offset[1])
        _, cell, _ = self.board_geometry()
        angle = float(DIRECTIONS[arrow["dir"]]["angle"])
        if points_override is None:
            points = [
                (point[0] + offset[0], point[1] + offset[1])
                for point in self.arrow_visual_points(arrow)
            ]
        else:
            points = list(points_override)
        if not points:
            return
        color = tuple(arrow["color"])
        highlighted = (
            arrow["id"] == self.hovered_arrow_id
            if force_highlight is None
            else force_highlight
        )
        pulse = 0.5 + 0.5 * math.sin(now * 7.0 + int(arrow["id"][1:]))
        glow_alpha = 82 if highlighted else 34
        if len(points) > 1:
            # Keep the strong, instantly readable silhouette used by tap-away
            # arrow games: one dark outline, one saturated body and a narrow
            # highlight.  The neon layer remains an accent rather than turning
            # every bend into a fuzzy knot.
            outer_width = max(7, min(11, int(round(cell * (0.24 if highlighted else 0.20)))))
            separator_width = max(5, min(8, int(round(cell * 0.16))))
            color_width = max(4, min(6, int(round(cell * 0.12))))
            core_width = max(1, min(2, int(round(cell * 0.045))))
            pygame.draw.lines(layer, (*color, glow_alpha), False, points, outer_width)
            pygame.draw.lines(layer, (2, 8, 18, 245), False, points, separator_width)
            pygame.draw.lines(layer, (*color, 255), False, points, color_width)
            pygame.draw.lines(layer, (240, 253, 255, 225), False, points, core_width)
            pygame.draw.aalines(layer, (*color, 255), False, points)

            # Rounded caps make short and long routes read as one continuous
            # arrow rather than separate line segments.  They also mirror the
            # clean, thick-line silhouette common in current tap-away puzzles.
            cap_radius = max(2, color_width // 2)
            for point in points[:-1]:
                pygame.draw.circle(layer, (2, 8, 18, 245), point, max(cap_radius + 1, separator_width // 2))
                pygame.draw.circle(layer, (*color, 255), point, cap_radius)
                pygame.draw.circle(layer, (240, 253, 255, 210), point, max(1, core_width // 2))
        else:
            center = points[0]
            pygame.draw.circle(layer, (*color, glow_alpha), center, 12 if highlighted else 9)

        # Keep the arrowhead inside its own grid cell as well.  Fixed 16/12 px
        # geometry used to overlap adjacent arrows at the minimum window size.
        tip_length = max(8.0, min(14.0, cell * 0.30))
        wing_length = max(6.0, min(11.0, cell * 0.23))
        halo_push = max(2.0, min(4.0, cell * 0.08))
        tip = (head[0] + math.cos(angle) * tip_length, head[1] + math.sin(angle) * tip_length)
        left = (head[0] + math.cos(angle + 2.45) * wing_length, head[1] + math.sin(angle + 2.45) * wing_length)
        right = (head[0] + math.cos(angle - 2.45) * wing_length, head[1] + math.sin(angle - 2.45) * wing_length)
        pygame.draw.polygon(layer, (*color, 70 if not highlighted else 120), [
            (tip[0] + math.cos(angle) * halo_push, tip[1] + math.sin(angle) * halo_push),
            (left[0] - 2, left[1] - 2),
            (right[0] + 2, right[1] + 2),
        ])
        pygame.draw.polygon(layer, (*color, 255), [tip, left, right])
        pygame.draw.aalines(layer, (248, 255, 255, 250), True, [tip, left, right])
        inner_wing = max(4.0, wing_length * 0.52)
        inner_tip = max(6.0, tip_length * 0.68)
        inner_left = (head[0] + math.cos(angle + 2.55) * inner_wing, head[1] + math.sin(angle + 2.55) * inner_wing)
        inner_right = (head[0] + math.cos(angle - 2.55) * inner_wing, head[1] + math.sin(angle - 2.55) * inner_wing)
        pygame.draw.polygon(layer, (245, 255, 255, 235), [
            (head[0] + math.cos(angle) * inner_tip, head[1] + math.sin(angle) * inner_tip),
            inner_left,
            inner_right,
        ])

        if arrow.get("prism"):
            marker = points[0]
            prism_color = _mix(color, (255, 255, 255), 0.35 + 0.3 * pulse)
            pygame.draw.circle(layer, (*prism_color, 75), marker, 11)
            pygame.draw.circle(layer, (*prism_color, 240), marker, 5, width=2)

        if self.overdrive:
            pygame.draw.circle(layer, (*CYAN, 28), head, 18 + int(pulse * 5), width=2)

    def draw_particles(self, target: pygame.Surface) -> None:
        fx = pygame.Surface(target.get_size(), pygame.SRCALPHA)
        for particle in self.particles:
            ratio = particle.life / particle.max_life
            alpha = int(255 * ratio)
            radius = max(1, int(particle.size * (0.5 + ratio)))
            pygame.draw.circle(fx, (*particle.color, alpha // 3), (int(particle.x), int(particle.y)), radius * 3)
            pygame.draw.circle(fx, (*particle.color, alpha), (int(particle.x), int(particle.y)), radius)
        target.blit(fx, (0, 0))

    def draw_progress(self, target: pygame.Surface) -> None:
        board_panel, _, _ = self.board_geometry()
        y = board_panel.bottom - 28
        gap = 18
        total_width = 3 * 94 + 2 * gap
        x = board_panel.centerx - total_width // 2
        for index in range(3):
            rect = pygame.Rect(x + index * (94 + gap), y, 94, 6)
            if index < self.level_index:
                color = GREEN
            elif index == self.level_index:
                color = CYAN
            else:
                color = (53, 63, 91)
            pygame.draw.rect(target, color, rect, border_radius=3)
            node = (rect.centerx, rect.centery)
            pygame.draw.circle(target, (10, 20, 40), node, 8)
            pygame.draw.circle(target, color, node, 6, width=2)
            if index <= self.level_index:
                pygame.draw.circle(target, color, node, 2)
            self.draw_text(target, f"0{index + 1}", (rect.centerx, rect.top - 7), 8, color, True, "midbottom")

    def draw_banner(self, target: pygame.Surface, now: float) -> None:
        if now > self.banner_until or not self.banner_text:
            return
        width, _ = target.get_size()
        text_surface = self.font(13, True).render(self.banner_text, True, TEXT)
        rect = text_surface.get_rect(center=(width // 2, 82))
        panel = rect.inflate(46, 18)
        self.draw_glow(target, panel.center, min(86, panel.width // 3), CYAN, 20)
        pygame.draw.rect(target, (8, 21, 43), panel, border_radius=14)
        pygame.draw.rect(target, (*CYAN, 118), panel, width=1, border_radius=14)
        pygame.draw.circle(target, CYAN, (panel.left + 14, panel.centery), 3)
        target.blit(text_surface, rect)

    def draw_result_metric(
        self,
        target: pygame.Surface,
        rect: pygame.Rect,
        label: str,
        value: str,
        color: tuple[int, int, int],
    ) -> None:
        pygame.draw.rect(target, (12, 24, 48), rect, border_radius=14)
        pygame.draw.rect(target, (*color, 54), rect, width=1, border_radius=14)
        self.draw_text(target, label, (rect.centerx, rect.top + 12), 9, MUTED, True, "midtop")
        self.draw_text(target, value, (rect.centerx, rect.bottom - 13), 18, color, True, "midbottom")

    def draw_overlay(self, target: pygame.Surface) -> None:
        if self.state == "playing" or self.exiting_arrows:
            return
        width, height = target.get_size()
        dim = pygame.Surface((width, height), pygame.SRCALPHA)
        dim.fill((1, 4, 13, 176))
        target.blit(dim, (0, 0))

        is_ready = self.state == "ready"
        is_setup = self.state == "setup"
        panel_width = min(800 if is_setup else 760 if is_ready else 650, width - 90)
        panel_height = min(570 if is_setup else 500, height - 70)
        panel = pygame.Rect(0, 0, panel_width, panel_height)
        panel.center = (width // 2, height // 2 + 8)
        accent = RED if self.state == "failed" else GREEN if self.state in {"level_complete", "campaign_complete", "training_complete"} else CYAN
        self.draw_glow(target, panel.center, min(panel.width // 3, 210), accent, 20)
        self.draw_panel(target, panel, accent)

        config = self.level["config"]
        cx = panel.centerx
        if self.state == "setup":
            self.draw_text(target, "NEON ARROW NEXUS", (cx, panel.top + 38), 10, CYAN, True, "midtop")
            self.draw_text(target, "选择玩法与难度", (cx, panel.top + 68), 30, TEXT, True, "midtop")
            self.draw_text(target, "每次启动都先明确选择；基础规则与进阶机制互不混用。", (cx, panel.top + 112), 10, MUTED, False, "midtop")

            self.draw_text(target, "01  玩法模式", (cx, panel.top + 154), 9, SUBTLE, True, "midtop")
            basic_selected = self.pending_mode == "basic"
            advanced_selected = self.pending_mode == "advanced"
            self.draw_button(
                target,
                pygame.Rect(cx - 262, panel.top + 180, 250, 48),
                ("✓  " if basic_selected else "") + "基础模式 · 单格箭头",
                "mode_basic",
                GREEN if basic_selected else CYAN,
                large=True,
            )
            self.draw_button(
                target,
                pygame.Rect(cx + 12, panel.top + 180, 250, 48),
                ("✓  " if advanced_selected else "") + "进阶模式 · 长箭机关",
                "mode_advanced",
                GREEN if advanced_selected else PURPLE,
                large=True,
            )
            mode_note = (
                "作业原始规则：每支箭只占一个逻辑格，沿上/下/左/右直线判断能否离场。"
                if self.pending_mode == "basic"
                else "扩展玩法：2–4 格随机长箭，并加入折光、反相、跃迁与阶段相位锁。"
                if self.pending_mode == "advanced"
                else "先选择基础模式或进阶模式。"
            )
            self.draw_text(target, mode_note, (cx, panel.top + 240), 9, MUTED, False, "midtop")

            self.draw_text(target, "02  难度", (cx, panel.top + 278), 9, SUBTLE, True, "midtop")
            diff_names = ("简单", "中等", "终极困难")
            diff_colors = (CYAN, GOLD, RED)
            button_w = 150
            gap = 14
            total = button_w * 3 + gap * 2
            start_x = cx - total // 2
            for index, (name, color) in enumerate(zip(diff_names, diff_colors)):
                selected = self.pending_difficulty == index
                self.draw_button(
                    target,
                    pygame.Rect(start_x + index * (button_w + gap), panel.top + 304, button_w, 42),
                    ("✓ " if selected else "") + name,
                    f"difficulty_{index}",
                    GREEN if selected else color,
                )

            ready_to_start = self.pending_mode is not None and self.pending_difficulty is not None
            summary = "请选择模式和难度后开始新一局。"
            if ready_to_start:
                mode_name = "基础模式" if self.pending_mode == "basic" else "进阶模式"
                summary = f"已选择：{mode_name} · {diff_names[self.pending_difficulty]}"
            self.draw_text(target, summary, (cx, panel.top + 363), 10, TEXT if ready_to_start else MUTED, True, "midtop")

            can_resume = (
                self.resume_available
                and self.pending_mode == self.resume_mode
                and self.pending_difficulty == self.resume_level_index
            )
            if can_resume:
                self.draw_button(target, pygame.Rect(cx - 214, panel.bottom - 128, 196, 44), "继续上次进度", "resume_selected", PURPLE)
                self.draw_button(target, pygame.Rect(cx + 18, panel.bottom - 128, 196, 44), "新开此难度", "start_selected", CYAN)
            else:
                self.draw_button(target, pygame.Rect(cx - 142, panel.bottom - 118, 284, 48), "开始游戏", "start_selected", CYAN if ready_to_start else SUBTLE, large=True)
            self.draw_text(target, "快捷键：B 基础 · N 进阶 · 1/2/3 难度 · Enter 开始", (cx, panel.bottom - 49), 8, SUBTLE, False, "midtop")

        elif self.state == "ready":
            mode_text = "单关训练" if self.training_mode else "三关挑战"
            logo = (cx, panel.top + 72)
            pygame.draw.circle(target, (9, 22, 43), logo, 26)
            pygame.draw.circle(target, CYAN, logo, 25, width=1)
            pygame.draw.line(target, TEXT, (logo[0] - 10, logo[1] + 9), (logo[0] + 13, logo[1] - 12), 3)
            pygame.draw.polygon(target, TEXT, [(logo[0] + 13, logo[1] - 12), (logo[0] + 7, logo[1] - 10), (logo[0] + 12, logo[1] - 5)])

            self.draw_text(target, "霓虹箭域", (cx, panel.top + 111), 32, TEXT, True, "midtop")
            self.draw_text(target, "观察方向，判断路径，依次清空三关", (cx, panel.top + 154), 11, MUTED, False, "midtop")
            self.draw_text(
                target,
                f"RUN {session_code(self.session_seed)}  ·  {mode_text}  ·  第 {self.level_index + 1} 关 / {config['target']} 条箭",
                (cx, panel.top + 188),
                10,
                PURPLE,
                True,
                "midtop",
            )
            self.draw_text(target, "选择关卡", (cx, panel.top + 222), 10, MUTED, True, "midtop")
            level_y = panel.top + 246
            level_w = 142
            level_gap = 10
            level_total = level_w * 3 + level_gap * 2
            level_x = cx - level_total // 2
            for index, level_config in enumerate(LEVEL_CONFIGS):
                color = CYAN if index == 0 else GOLD if index == 1 else RED
                button_rect = pygame.Rect(level_x + index * (level_w + level_gap), level_y, level_w, 38)
                self.draw_button(target, button_rect, f"0{index + 1}  {level_config['difficulty']}", f"select_{index}", color)

            self.draw_text(target, "U 撤销  ·  A 自动求解  ·  V 低动态  ·  M 音效", (cx, panel.top + 302), 9, SUBTLE, False, "midtop")
            self.draw_button(target, pygame.Rect(cx - 142, panel.bottom - 68, 284, 46), "进入箭域", "start", CYAN, large=True)

        elif self.state == "level_complete":
            self.draw_text(target, "SECTOR STABILIZED", (cx, panel.top + 46), 11, GREEN, True, "midtop")
            self.draw_text(target, f"第 {self.level_index + 1} 关完成", (cx, panel.top + 80), 31, TEXT, True, "midtop")
            self.draw_text(target, f"{config['name']} · {config['difficulty']}", (cx, panel.top + 126), 13, CYAN, True, "midtop")
            stars = self.stars_earned()
            self.draw_text(target, "★" * stars + "☆" * (3 - stars), (cx, panel.top + 166), 30, GOLD, True, "midtop")
            metric_y = panel.top + 224
            metric_w = 145
            gap = 12
            total = metric_w * 3 + gap * 2
            mx = cx - total // 2
            self.draw_result_metric(target, pygame.Rect(mx, metric_y, metric_w, 70), "SCORE", f"{self.score:,}", CYAN)
            self.draw_result_metric(target, pygame.Rect(mx + metric_w + gap, metric_y, metric_w, 70), "ENERGY", f"{self.energy}%", MAGENTA)
            self.draw_result_metric(target, pygame.Rect(mx + (metric_w + gap) * 2, metric_y, metric_w, 70), "STABILITY", str(self.lives), GREEN)
            self.draw_text(target, "下一层箭域将叠加新的射线路径机制。", (cx, panel.top + 319), 11, MUTED, False, "midtop")
            self.draw_button(target, pygame.Rect(cx - 142, panel.bottom - 74, 284, 48), f"进入第 {self.level_index + 2} 关", "next", CYAN, large=True)

        elif self.state == "campaign_complete":
            self.draw_text(target, "CAMPAIGN COMPLETE", (cx, panel.top + 42), 11, GREEN, True, "midtop")
            self.draw_text(target, "三关全部完成", (cx, panel.top + 78), 34, TEXT, True, "midtop")
            self.draw_text(target, "THREE SECTORS · ZERO FOURTH LEVEL", (cx, panel.top + 126), 10, GOLD, True, "midtop")
            stars = self.stars_earned()
            self.draw_text(target, "★" * stars + "☆" * (3 - stars), (cx, panel.top + 164), 32, GOLD, True, "midtop")
            metric_y = panel.top + 224
            metric_w = 180
            gap = 16
            self.draw_result_metric(target, pygame.Rect(cx - metric_w - gap // 2, metric_y, metric_w, 76), "FINAL SCORE", f"{self.score:,}", CYAN)
            self.draw_result_metric(target, pygame.Rect(cx + gap // 2, metric_y, metric_w, 76), "RUN CODE", session_code(self.session_seed), PURPLE)
            self.draw_text(target, "完整三关流程已结束，可以立即生成一组全新的随机挑战。", (cx, panel.top + 330), 11, MUTED, False, "midtop")
            self.draw_button(target, pygame.Rect(cx - 152, panel.bottom - 76, 304, 48), "返回模式与难度选择", "home", MAGENTA, large=True)

        elif self.state == "training_complete":
            self.draw_text(target, "TRAINING COMPLETE", (cx, panel.top + 44), 11, GREEN, True, "midtop")
            self.draw_text(target, f"第 {self.level_index + 1} 关训练完成", (cx, panel.top + 82), 30, TEXT, True, "midtop")
            self.draw_text(target, f"{config['name']} · {config['difficulty']}", (cx, panel.top + 128), 13, CYAN, True, "midtop")
            stars = self.last_stars or self.stars_earned()
            self.draw_text(target, "★" * stars + "☆" * (3 - stars), (cx, panel.top + 170), 30, GOLD, True, "midtop")
            self.draw_text(target, "训练模式只练当前关，不会把跳关误算成完整三关通关。", (cx, panel.top + 228), 11, MUTED, False, "midtop")
            self.draw_button(target, pygame.Rect(cx - 214, panel.bottom - 78, 196, 48), "再练一次", "restart", PURPLE, large=True)
            self.draw_button(target, pygame.Rect(cx + 18, panel.bottom - 78, 196, 48), "返回模式选择", "home", CYAN, large=True)

        elif self.state == "failed":
            warning = (cx, panel.top + 92)
            self.draw_glow(target, warning, 48, RED, 28)
            pygame.draw.circle(target, (43, 15, 29), warning, 28)
            pygame.draw.circle(target, RED, warning, 27, width=2)
            self.draw_text(target, "!", warning, 25, RED, True, "center")
            self.draw_text(target, "SIGNAL LOST", (cx, panel.top + 138), 11, RED, True, "midtop")
            self.draw_text(target, "本关挑战失败", (cx, panel.top + 171), 30, TEXT, True, "midtop")
            reason = "稳定度耗尽" if self.lives <= 0 else "倒计时归零"
            self.draw_text(target, reason, (cx, panel.top + 219), 13, RED, True, "midtop")
            self.draw_text(target, "重开会保留同一个 RUN 和同一张地图，便于重新判断路径。", (cx, panel.top + 260), 11, MUTED, False, "midtop")
            self.draw_button(target, pygame.Rect(cx - 142, panel.bottom - 78, 284, 48), "重开本关", "restart", RED, large=True)

    def draw_boot_sequence(self, target: pygame.Surface, now: float) -> None:
        if not self.boot_enabled or self.reduced_motion:
            return
        elapsed = now - self.boot_started_at
        if elapsed >= self.boot_duration:
            self.boot_enabled = False
            return

        width, height = target.get_size()
        progress = _clamp(elapsed / self.boot_duration, 0.0, 1.0)
        reveal = 1.0 - (1.0 - min(1.0, progress / 0.72)) ** 3
        fade = 1.0 if progress < 0.78 else _clamp((1.0 - progress) / 0.22, 0.0, 1.0)
        alpha_scale = fade

        layer = pygame.Surface((width, height), pygame.SRCALPHA)
        layer.fill((2, 6, 17, int(244 * alpha_scale)))
        center = (width // 2, height // 2 - 34)

        # Sparse orbital geometry: one hero mark, not a wall of effects.
        for index, radius in enumerate((52, 72, 100)):
            rect = pygame.Rect(center[0] - radius, center[1] - radius, radius * 2, radius * 2)
            start = -math.pi / 2 + index * 0.7
            sweep = math.tau * (0.18 + reveal * (0.48 - index * 0.05))
            color = CYAN if index == 0 else PURPLE if index == 1 else MAGENTA
            pygame.draw.arc(layer, (*color, int((215 - index * 45) * alpha_scale)), rect, start, start + sweep, 2)

        pulse_radius = int(32 + 5 * math.sin(now * 4.2))
        pygame.draw.circle(layer, (8, 22, 43, int(245 * alpha_scale)), center, pulse_radius)
        pygame.draw.circle(layer, (*CYAN, int(210 * alpha_scale)), center, pulse_radius, width=1)
        pygame.draw.circle(layer, (*PURPLE, int(130 * alpha_scale)), center, max(12, pulse_radius - 10), width=1)

        line_reveal = max(0.0, min(1.0, (progress - 0.08) / 0.35))
        dx = int(16 * line_reveal)
        dy = int(15 * line_reveal)
        pygame.draw.line(layer, (*TEXT, int(245 * alpha_scale)), (center[0] - dx, center[1] + dy), (center[0] + dx, center[1] - dy), 3)
        if line_reveal > 0.72:
            pygame.draw.polygon(
                layer,
                (*TEXT, int(245 * alpha_scale)),
                [
                    (center[0] + dx, center[1] - dy),
                    (center[0] + dx - 9, center[1] - dy + 2),
                    (center[0] + dx - 2, center[1] - dy + 9),
                ],
            )

        title_alpha = int(255 * _clamp((progress - 0.24) / 0.28, 0.0, 1.0) * alpha_scale)
        if title_alpha > 0:
            title = self.font(28, True).render("NEON ARROW NEXUS", True, TEXT)
            title.set_alpha(title_alpha)
            title_rect = title.get_rect(midtop=(center[0], center[1] + 126))
            layer.blit(title, title_rect)

            subtitle = self.font(10, True).render("PRISMATIC ROUTE CONTROL  //  SYSTEM SYNC", True, CYAN)
            subtitle.set_alpha(int(title_alpha * 0.78))
            layer.blit(subtitle, subtitle.get_rect(midtop=(center[0], center[1] + 166)))

        bar_width = min(420, int(width * 0.34))
        bar = pygame.Rect(center[0] - bar_width // 2, center[1] + 205, bar_width, 4)
        pygame.draw.rect(layer, (42, 58, 82, int(180 * alpha_scale)), bar, border_radius=2)
        fill = bar.copy()
        fill.width = max(1, int(bar.width * reveal))
        pygame.draw.rect(layer, (*CYAN, int(235 * alpha_scale)), fill, border_radius=2)
        scan_x = int(width * progress)
        pygame.draw.line(layer, (*CYAN, int(34 * alpha_scale)), (scan_x, 0), (scan_x, height), 1)

        status_text = "CALIBRATING VECTOR MATRIX" if progress < 0.64 else "ROUTE CORE ONLINE"
        status = self.font(9, True).render(status_text, True, MUTED if progress < 0.64 else GREEN)
        status.set_alpha(int(220 * alpha_scale))
        layer.blit(status, status.get_rect(midtop=(center[0], center[1] + 222)))
        target.blit(layer, (0, 0))

    def render(self) -> None:
        now = time.perf_counter()
        visual_now = 0.0 if self.reduced_motion else now
        self.buttons.clear()
        self.draw_background(self.screen, visual_now)
        self.draw_header(self.screen)
        self.draw_sidebar(self.screen)
        self.draw_board(self.screen, visual_now)
        self.draw_progress(self.screen)
        self.draw_particles(self.screen)
        self.draw_banner(self.screen, now)
        self.draw_overlay(self.screen)
        self.draw_boot_sequence(self.screen, now)

    def set_demo_scene(self, scene: str) -> None:
        self.boot_enabled = False
        if scene == "setup":
            self.pending_mode = "basic"
            self.pending_difficulty = 1
            self.state = "setup"
        elif scene == "basic":
            self.game_mode = "basic"
            self.session_seed = 20260917
            self.load_level(1)
            self.energy = 36
            self.combo = 3
            self.score = 960
        elif scene == "ready":
            self.load_level(0, keep_state=True)
            self.state = "ready"
        elif scene in {"level1", "playing"}:
            self.load_level(0)
            self.energy = 42
            self.combo = 4
            self.score = 1280
        elif scene == "level2":
            self.load_level(1)
            self.energy = 100
            self.combo = 6
            self.score = 4280
        elif scene == "level3":
            self.load_level(2)
            self.energy = 78
            self.combo = 9
            self.score = 9780
        elif scene == "complete":
            self.load_level(2)
            self.arrows = []
            self.score = 16840
            self.energy = 100
            self.combo = 17
            self.state = "campaign_complete"
        else:
            raise ValueError(f"Unknown demo scene: {scene}")

    def run(self) -> None:
        while self.running:
            dt = self.clock.tick(FPS) / 1000.0
            for event in pygame.event.get():
                self.process_event(event)
            self.update(dt)
            self.render()
            pygame.display.flip()
        self.save_progress()
        pygame.quit()


def render_screenshot(path: str, scene: str = "ready", size: tuple[int, int] = WINDOW_SIZE) -> None:
    app = NeonArrowApp(size, load_save=False)
    app.set_demo_scene(scene)
    app.render()
    pygame.display.flip()
    pygame.image.save(app.screen, path)
    pygame.quit()


def smoke_check() -> dict[str, Any]:
    app = NeonArrowApp((1100, 700), load_save=False)
    app.state = "playing"
    app.render()
    before = len(app.arrows)
    safe = safe_arrow_ids(app.level, app.arrows)
    if not safe:
        pygame.quit()
        raise RuntimeError("首关未找到可消除箭路")
    arrow = next(item for item in app.arrows if item["id"] == safe[0])
    app.handle_arrow_click(arrow)
    after = len(app.arrows)
    result = {
        "run": session_code(app.session_seed),
        "level": app.level_index + 1,
        "before": before,
        "after": after,
        "score": app.score,
        "state": app.state,
    }
    pygame.quit()
    if after != before - 1:
        raise RuntimeError("Pygame 冒烟测试未能真实消除箭路")
    return result
