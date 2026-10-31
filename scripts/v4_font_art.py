from pathlib import Path
from PIL import Image, ImageDraw, ImageFont

Path('pkgfiles/USRDIR').mkdir(parents=True, exist_ok=True)
font_candidates=[
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
]
font_path=next((x for x in font_candidates if Path(x).exists()),font_candidates[-1])

# V4 keeps the on-screen size of the old 16x24 font but renders from a
# 2x source glyph (32x48) so Tiny3D linear filtering produces cleaner text.
FW,FH=32,48
fnt=ImageFont.truetype(font_path,38)
raw=bytearray()
for code in range(32,127):
    im=Image.new('L',(FW,FH),0)
    d=ImageDraw.Draw(im)
    ch=chr(code)
    box=d.textbbox((0,0),ch,font=fnt)
    w,h=box[2]-box[0],box[3]-box[1]
    x=max(0,(FW-w)//2-box[0])
    y=max(0,(FH-h)//2-box[1]-2)
    d.text((x,y),ch,font=fnt,fill=255)
    raw.extend(im.tobytes())

expected=95*FW*FH
assert len(raw)==expected
Path('pkgfiles/USRDIR/FONT.RAW').write_bytes(raw)
print(f'V4 FONT.RAW ready: {FW}x{FH}, {len(raw)} bytes')
