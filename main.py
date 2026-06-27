"""Entry point for LabMidnight."""

from __future__ import annotations

import os


def prefer_discrete_gpu() -> None:
    os.environ.setdefault("SDL_RENDER_DRIVER", "direct3d11")
    os.environ.setdefault("SDL_HINT_RENDER_SCALE_QUALITY", "nearest")
    os.environ.setdefault("__NV_PRIME_RENDER_OFFLOAD", "1")
    os.environ.setdefault("__GLX_VENDOR_LIBRARY_NAME", "nvidia")
    os.environ.setdefault("DRI_PRIME", "1")


prefer_discrete_gpu()

from src.core.game import Game


def main() -> None:
    Game().run()


if __name__ == "__main__":
    main()
    
