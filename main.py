from __future__ import annotations

import argparse
import json
import os
from pathlib import Path


def configure_windows_high_dpi() -> None:
    """Ask SDL to render at native Windows pixels instead of DPI-virtualized pixels."""
    if os.name != "nt":
        return
    os.environ.setdefault("SDL_WINDOWS_DPI_AWARENESS", "permonitorv2")
    # Keep window and drawable coordinates in native pixels. This avoids the
    # 125%/150% Windows compatibility upscaling that makes Pygame text blurry.
    os.environ.setdefault("SDL_WINDOWS_DPI_SCALING", "0")
    # Environment hints are not sufficient on every packaged SDL/Pygame build.
    # Declare process-level Per-Monitor V2 awareness before pygame creates the
    # first window so Windows never bitmap-scales the finished frame.
    try:
        import ctypes

        user32 = ctypes.windll.user32
        if not user32.SetProcessDpiAwarenessContext(ctypes.c_void_p(-4)):
            raise OSError("SetProcessDpiAwarenessContext returned false")
    except (AttributeError, OSError):
        try:
            ctypes.windll.shcore.SetProcessDpiAwareness(2)
        except (AttributeError, OSError):
            try:
                ctypes.windll.user32.SetProcessDPIAware()
            except (AttributeError, OSError):
                pass


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description="霓虹箭域 · Neon Arrow Nexus · Python Edition")
    parser.add_argument("--headless-check", action="store_true", help="使用虚拟显示运行一次真实 Pygame 冒烟测试")
    parser.add_argument("--screenshot", type=Path, help="渲染一张真实 Pygame 游戏截图")
    parser.add_argument(
        "--scene",
        choices=["setup", "basic", "ready", "level1", "playing", "level2", "level3", "difficulty", "complete"],
        default="ready",
        help="截图场景",
    )
    parser.add_argument("--width", type=int, default=1600)
    parser.add_argument("--height", type=int, default=1000)
    return parser.parse_args()


def main() -> int:
    args = parse_args()
    configure_windows_high_dpi()
    if args.headless_check or args.screenshot:
        os.environ.setdefault("SDL_VIDEODRIVER", "dummy")
        os.environ.setdefault("SDL_AUDIODRIVER", "dummy")

    from neon_arrow.app import NeonArrowApp, render_screenshot, smoke_check

    if args.headless_check:
        print(json.dumps(smoke_check(), ensure_ascii=False, indent=2))
        return 0

    if args.screenshot:
        args.screenshot.parent.mkdir(parents=True, exist_ok=True)
        render_screenshot(str(args.screenshot), args.scene, (args.width, args.height))
        print(args.screenshot)
        return 0

    app = NeonArrowApp((args.width, args.height))
    app.run()
    return 0


if __name__ == "__main__":
    raise SystemExit(main())
