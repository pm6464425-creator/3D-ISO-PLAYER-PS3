from pathlib import Path

# FLOW MOVIE V2.9
# Keep V2.8 HARD PERF renderer, but make the coverflow transition slower and
# more cinematic.  The spring remains critically damped, so it stays smooth
# and does not overshoot/bounce.

p = Path('source/main.cpp')
s = p.read_text()

old = '    const float w=21.0f;'
new = '''    /* V2.9: slower cinematic transition.  With critical damping, w=8.5
       gives roughly 0.55 s to reach 95% and ~0.7 s to visually settle,
       while still updating every rendered frame. */
    const float w=8.5f;'''

if old not in s:
    raise SystemExit('spring constant anchor not found')

s = s.replace(old, new, 1)
p.write_text(s)
print('FLOW MOVIE V2.9: slower smooth cinematic cover transition (w=8.5)')
