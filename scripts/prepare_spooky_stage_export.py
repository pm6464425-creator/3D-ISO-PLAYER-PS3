#!/usr/bin/env python3
from pathlib import Path
from PIL import Image
import sys

if len(sys.argv) != 4:
    raise SystemExit('usage: prepare_spooky_stage_export.py <spookyflow> <stage_raw> <case_raw>')

repo = Path(sys.argv[1])
stage = Path(sys.argv[2])
cases = Path(sys.argv[3])
stage.mkdir(parents=True, exist_ok=True)
cases.mkdir(parents=True, exist_ok=True)


def raw_gray(src: Path, dst: Path, alpha=False):
    im = Image.open(src).convert('RGBA' if alpha else 'L')
    if alpha:
        im = im.getchannel('A')
    w, h = im.size
    dst.write_bytes(f'{w} {h}\n'.encode() + im.tobytes())


def raw_rgba(src: Path, dst: Path):
    im = Image.open(src).convert('RGBA')
    w, h = im.size
    dst.write_bytes(f'{w} {h}\n'.encode() + im.tobytes())

# Exact Stage assets from SpookyFlow.
raw_gray(repo / 'art/stage.jpg', stage / 'stage.rgba')
raw_rgba(repo / 'art/stage_shapes.png', stage / 'shapes.rgba')
raw_gray(repo / 'art/stage_rib.jpg', stage / 'rib.rgba')
raw_gray(repo / 'art/stage_glow.jpg', stage / 'glow.rgba')
raw_gray(repo / 'art/stage_fx.png', stage / 'fx.rgba', alpha=True)

# Tiny dummy case textures only to enter the preview's Stage test block.
for p in (1, 2, 3):
    im = Image.new('RGBA', (8, 8), (255, 255, 255, 255))
    (cases / f'ps{p}.rgba').write_bytes(b'8 8\n' + im.tobytes())

pv = repo / 'tools/preview/preview.c'
s = pv.read_text()
needle = '''                        g_app.settings.background = BG_STAGE;\n                        render("34_stage_ps2_layered", 1280, 720);   /* the old layered drawing, to compare */'''
insert = '''                        g_app.settings.background = BG_STAGE;\n                        if (getenv("SF_PREVIEW_STAGE_VIDEO")) {\n                            int vf;\n                            char vp[512];\n                            /* Let intro-dependent Stage layers reach their normal live state. */\n                            step(0, 2.0f);\n                            set_screen(1280, 720);\n                            for (vf = 0; vf < 600; vf++) {\n                                g_soft_vertex_count = 0;\n                                g_soft_pixel_count = 0;\n                                ui_draw_background_only(&g_app, BG_STAGE);\n                                snprintf(vp, sizeof(vp), "%s/stage_%04d.ppm", g_outdir, vf);\n                                if (soft_write_ppm(vp) != 0) {\n                                    fprintf(stderr, "cannot write %s\\n", vp);\n                                    return 3;\n                                }\n                                g_app.time += DT;\n                            }\n                            return 0;\n                        }\n                        render("34_stage_ps2_layered", 1280, 720);   /* the old layered drawing, to compare */'''
if needle not in s:
    raise SystemExit('preview insertion point not found')
pv.write_text(s.replace(needle, insert, 1))
print('Prepared exact SpookyFlow Stage exporter')
