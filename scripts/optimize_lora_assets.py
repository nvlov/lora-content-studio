"""Оптимизация исходных PNG Лоры из Figma (4096×4096 RGBA, ~10МБ)
в JPG 1024×1024 (~150КБ) для использования в Claude Vision и gpt-image-2 /edits.

Запуск: venv\\Scripts\\python.exe scripts\\optimize_lora_assets.py

Идемпотентно: пропускает файлы, у которых оптимизированная копия новее исходника.
Оригиналы НЕ удаляются — нужны для ручной загрузки в Kling Subject Library.
"""
import sys
from pathlib import Path

# Подключаем корень проекта к sys.path чтобы импортировать config.
ROOT = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(ROOT))

from PIL import Image

import config

SRC_DIR = config.LORA_ASSETS_DIR
DST_DIR = config.LORA_OPTIMIZED_DIR

TARGET_SIZE = 1024
JPG_QUALITY = 90


def optimize_one(src: Path, dst: Path) -> bool:
    """Конвертирует один PNG в JPG 1024px. Возвращает True если сделана работа."""
    if dst.exists() and dst.stat().st_mtime >= src.stat().st_mtime:
        return False
    with Image.open(src) as im:
        if im.mode in ("RGBA", "LA", "P"):
            bg = Image.new("RGB", im.size, (255, 255, 255))
            bg.paste(im, mask=im.split()[-1] if im.mode == "RGBA" else None)
            im = bg
        elif im.mode != "RGB":
            im = im.convert("RGB")
        im.thumbnail((TARGET_SIZE, TARGET_SIZE), Image.Resampling.LANCZOS)
        dst.parent.mkdir(parents=True, exist_ok=True)
        im.save(dst, "JPEG", quality=JPG_QUALITY, optimize=True)
    return True


def slugify(name: str) -> str:
    """Lora_2_Greetings_v1.png -> lora_greetings_v1.jpg"""
    stem = Path(name).stem.lower()
    stem = stem.replace(" ", "_").replace("__", "_")
    if stem.startswith("lora_2_"):
        stem = "lora_" + stem[len("lora_2_"):]
    elif stem.startswith("lora_21_"):
        stem = "lora_var21_" + stem[len("lora_21_"):]
    return stem + ".jpg"


def main() -> int:
    if not SRC_DIR.exists():
        print(f"Нет папки {SRC_DIR}", file=sys.stderr)
        return 1
    sources = sorted(p for p in SRC_DIR.glob("*.png") if p.is_file())
    if not sources:
        print(f"Нет PNG в {SRC_DIR}", file=sys.stderr)
        return 1

    print(f"Оптимизирую {len(sources)} файлов из {SRC_DIR.relative_to(ROOT)}")
    print(f"Цель: {DST_DIR.relative_to(ROOT)}  размер: {TARGET_SIZE}px JPG q{JPG_QUALITY}\n")

    done = skipped = 0
    for src in sources:
        dst = DST_DIR / slugify(src.name)
        if optimize_one(src, dst):
            dst_size_kb = dst.stat().st_size / 1024
            print(f"  + {src.name:40s} -> {dst.name:30s} ({dst_size_kb:.0f} КБ)")
            done += 1
        else:
            print(f"  = {dst.name} актуально, пропуск")
            skipped += 1

    print(f"\nГотово: оптимизировано {done}, пропущено {skipped}")
    return 0


if __name__ == "__main__":
    sys.exit(main())
