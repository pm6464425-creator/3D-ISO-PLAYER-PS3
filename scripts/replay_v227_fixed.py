#!/usr/bin/env python3
from pathlib import Path
import os
import subprocess
import sys

ROOT = Path(__file__).resolve().parents[1]
WORKFLOW = ROOT / ".github/workflows/build-v227-fixed.yml"


def extract_run_blocks(text: str):
    lines = text.splitlines()
    blocks = []
    i = 0
    while i < len(lines):
        line = lines[i]
        if line.strip() == "run: |":
            base = len(line) - len(line.lstrip())
            i += 1
            out = []
            while i < len(lines):
                raw = lines[i]
                if raw.strip() == "":
                    out.append("")
                    i += 1
                    continue
                indent = len(raw) - len(raw.lstrip())
                if indent <= base:
                    break
                cut = min(len(raw), base + 2)
                out.append(raw[cut:])
                i += 1
            blocks.append("\n".join(out).rstrip() + "\n")
            continue
        i += 1
    return blocks


def sync_runner_files(env, env_pos, path_pos):
    env_file = Path(env.get("GITHUB_ENV", "")) if env.get("GITHUB_ENV") else None
    path_file = Path(env.get("GITHUB_PATH", "")) if env.get("GITHUB_PATH") else None

    if env_file and env_file.exists():
        lines = env_file.read_text(errors="replace").splitlines()
        for line in lines[env_pos:]:
            if not line or line.startswith("#") or "=" not in line:
                continue
            key, value = line.split("=", 1)
            env[key] = value
        env_pos = len(lines)

    if path_file and path_file.exists():
        lines = path_file.read_text(errors="replace").splitlines()
        new_paths = [x for x in lines[path_pos:] if x]
        if new_paths:
            env["PATH"] = os.pathsep.join(new_paths + [env.get("PATH", "")])
        path_pos = len(lines)

    return env_pos, path_pos


def main():
    if not WORKFLOW.exists():
        raise SystemExit(f"Missing workflow: {WORKFLOW}")

    blocks = extract_run_blocks(WORKFLOW.read_text())
    if not blocks:
        raise SystemExit("No run blocks found in V2.27 fixed workflow")

    old_clone = "git clone --depth 1 --branch v1.0.0 https://github.com/Cruslan/PS3-Movian-Next.git /tmp/movian-next"
    new_clone = "git clone --recurse-submodules --shallow-submodules --depth 1 --branch v1.0.0 https://github.com/Cruslan/PS3-Movian-Next.git /tmp/movian-next"

    env = os.environ.copy()
    env_pos = 0
    path_pos = 0

    for n, block in enumerate(blocks, 1):
        if old_clone in block:
            block = block.replace(old_clone, new_clone)
            block = block.replace(
                "cd /tmp/movian-next\nmake prepare",
                "cd /tmp/movian-next\n"
                "test -f ext/gumbo-parser/src/attribute.c\n"
                "echo 'Movian submodules ready: gumbo-parser present'\n"
                "make prepare",
                1,
            )

        first = next((x.strip() for x in block.splitlines() if x.strip()), "<empty>")
        print(f"\n=== V2.27 replay block {n}/{len(blocks)}: {first[:120]} ===", flush=True)
        p = subprocess.run(
            ["bash", "-euo", "pipefail", "-c", block],
            cwd=str(ROOT),
            env=env,
        )
        if p.returncode != 0:
            raise SystemExit(p.returncode)

        env_pos, path_pos = sync_runner_files(env, env_pos, path_pos)

    required = [
        ROOT / "FLOW_MOVIE_V2_27_INTERNAL_SELF_LOG.pkg",
        ROOT / "FLOW_MOVIE_V2_27_INTERNAL_SELF_LOG_GNPDRM.pkg",
        ROOT / "pkgfiles/USRDIR/flow_player.self",
        ROOT / "generated_main_v227.cpp",
        ROOT / "generated_rsxutil_v227.cpp",
    ]
    for p in required:
        if not p.exists() or p.stat().st_size == 0:
            raise SystemExit(f"Missing final artifact: {p}")

    print("\nV2.27 fixed replay completed successfully.")


if __name__ == "__main__":
    main()
