#!/usr/bin/env python3
"""Install the bundled Agent Skills for a supported local client or build a portable bundle."""

from __future__ import annotations

import argparse
from pathlib import Path
import shutil
import zipfile


PLATFORM_PATHS = {
    "codex": Path("~/.agents/skills"),
    "claude-code": Path("~/.claude/skills"),
    "qwen-code": Path("~/.qwen/skills"),
    "workbuddy": Path("~/.workbuddy/skills"),
}


def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("platform", choices=(*PLATFORM_PATHS, "qwenwork", "portable"))
    parser.add_argument("--target", help="Override the installation directory or bundle path")
    parser.add_argument("--force", action="store_true", help="Replace an existing skill after explicit review")
    return parser.parse_args()


def skill_dirs(root: Path) -> list[Path]:
    return sorted(path for path in (root / "skills").iterdir() if (path / "SKILL.md").exists())


def build_bundle(root: Path, skills: list[Path], target: Path) -> None:
    target.parent.mkdir(parents=True, exist_ok=True)
    if target.exists():
        raise ValueError(f"Refusing to overwrite bundle: {target}")
    with zipfile.ZipFile(target, "w", zipfile.ZIP_DEFLATED) as archive:
        for skill in skills:
            for path in sorted(skill.rglob("*")):
                if path.is_file() and "__pycache__" not in path.parts:
                    archive.write(path, Path("skills") / path.relative_to(root / "skills"))
        for name in ("qwen-extension.json",):
            path = root / name
            if path.exists():
                archive.write(path, name)
    print(f"Created portable skill bundle: {target}")


def main() -> int:
    args = parse_args()
    root = Path(__file__).resolve().parent.parent
    skills = skill_dirs(root)
    if args.platform in {"qwenwork", "portable"}:
        default = root / "dist" / ("qwenwork-skill-bundle.zip" if args.platform == "qwenwork" else "agent-skills-bundle.zip")
        target = Path(args.target).expanduser().resolve() if args.target else default
        build_bundle(root, skills, target)
        return 0

    target_root = Path(args.target).expanduser().resolve() if args.target else PLATFORM_PATHS[args.platform].expanduser()
    target_root.mkdir(parents=True, exist_ok=True)
    conflicts = [target_root / skill.name for skill in skills if (target_root / skill.name).exists()]
    if conflicts and not args.force:
        joined = "\n".join(str(path) for path in conflicts)
        raise ValueError(f"Refusing to overwrite existing skills:\n{joined}\nReview them, then rerun with --force if replacement is intentional.")
    for skill in skills:
        target = target_root / skill.name
        if target.exists():
            shutil.rmtree(target)
        shutil.copytree(skill, target, ignore=shutil.ignore_patterns("__pycache__", "*.pyc"))
        print(f"Installed {skill.name} -> {target}")
    print(f"Installed {len(skills)} skills for {args.platform}. Start a new session if they are not visible.")
    return 0


if __name__ == "__main__":
    try:
        raise SystemExit(main())
    except (ValueError, OSError) as error:
        raise SystemExit(f"ERROR: {error}") from None
