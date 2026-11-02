from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()

old = '''        /* Slightly larger than the previous build, without changing speed:\n           most particles are radius 2, some radius 3, with a few radius 4. */\n        int r=2;\n        if((i%17)==0) r=4;\n        else if((i%5)==0) r=3;\n'''
new = '''        /* XL particles: same subpixel trajectory/speed, larger visual halo.\n           Most particles are radius 3, some radius 4, with a few radius 5. */\n        int r=3;\n        if((i%17)==0) r=5;\n        else if((i%5)==0) r=4;\n'''

if old not in s:
    raise SystemExit('Expected particle-size block not found')

s = s.replace(old, new, 1)
p.write_text(s)
print('V2.26 XL particle size applied: radius 3/4/5, motion parameters unchanged')
