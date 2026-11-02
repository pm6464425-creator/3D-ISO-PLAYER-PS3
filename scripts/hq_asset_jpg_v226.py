from pathlib import Path
import re

main=Path('source/main.cpp')
s=main.read_text()

# Keep the HQ asset naming clean and explicit.
old='APPBG_HQ.PNG'
new='APPBG_HQ.JPG'
if old not in s and new not in s:
    raise SystemExit('HQ background asset path not found')
if old in s:
    s=s.replace(old,new)

# The approved 1080p artwork already contains the PlayStation-style symbols.
# Do not draw a second moving copy on top. Preserve only the approved motion:
# blinking particles, slow glints and subtle floor reflection/sweep.
pat=re.compile(r'\n    /\* Four subtle symbols float locally instead of crossing the screen fast\. \*/.*?\n    /\* Slow glints along the wave/horizon region\. \*/', re.S)
if pat.search(s):
    s=pat.sub('\n    /* Symbols remain part of the HQ artwork; no duplicate animated overlay. */\n\n    /* Slow glints along the wave/horizon region. */',s,1)
elif 'Symbols remain part of the HQ artwork' not in s:
    raise SystemExit('animated symbol block not found')

main.write_text(s)

png=Path('pkgfiles/USRDIR/APPBG_HQ.PNG')
jpg=Path('pkgfiles/USRDIR/APPBG_HQ.JPG')
if png.exists():
    if jpg.exists():
        jpg.unlink()
    png.rename(jpg)
if not jpg.exists():
    raise SystemExit('APPBG_HQ asset missing')

print('V2.26 HQ background normalized: JPG base + particles/glints/reflection only')
