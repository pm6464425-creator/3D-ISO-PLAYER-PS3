from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter
import math

Path('pkgfiles/USRDIR').mkdir(parents=True,exist_ok=True)
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'

# FONT.RAW compatible con el render actual.
FW,FH=16,24
fnt=ImageFont.truetype(font_path,18)
raw=bytearray()
for code in range(32,127):
    im=Image.new('L',(FW,FH),0); d=ImageDraw.Draw(im); ch=chr(code)
    box=d.textbbox((0,0),ch,font=fnt)
    d.text((max(0,(FW-(box[2]-box[0]))//2-box[0]),max(0,(FH-(box[3]-box[1]))//2-box[1]-1)),ch,font=fnt,fill=255)
    raw.extend(im.tobytes())
Path('pkgfiles/USRDIR/FONT.RAW').write_bytes(raw)

# Fondo estático de respaldo, inspirado en XMB y sin Spider-Man.
w,h=1920,1080
bg=Image.new('RGB',(w,h)); px=bg.load()
for y in range(h):
    t=y/(h-1)
    c=(int(4+18*t),int(32+55*t),int(88+75*t))
    for x in range(w): px[x,y]=c
wave=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(wave,'RGBA')
for layer in range(5):
    pts=[]
    base=470+layer*50
    for x in range(0,w+8,8):
        yy=base+math.sin(x/220+layer*.7)*38+math.sin(x/520-layer*.9)*22
        pts.append((x,yy))
    d.line(pts,fill=(140,200,245,95-layer*10),width=5 if layer<2 else 3)
wave=wave.filter(ImageFilter.GaussianBlur(4))
bg=Image.alpha_composite(bg.convert('RGBA'),wave)
ft=ImageFont.truetype(font_path,110); fs=ImageFont.truetype(font_path,34)
d=ImageDraw.Draw(bg,'RGBA')
d.text((100,760),'FLOWPS3',font=ft,fill=(245,250,255,235))
d.text((108,895),'XMB LIBRARY',font=fs,fill=(180,215,245,220))
bg.convert('RGB').save('pkgfiles/USRDIR/APPBG.JPG',quality=90)
bg.convert('RGB').save('pkgfiles/PIC1.PNG',optimize=True)

icon=Image.new('RGB',(320,176),(10,48,104)); d=ImageDraw.Draw(icon,'RGBA')
for yy in range(176):
    c=(10,48+int(42*yy/175),104+int(55*yy/175)); d.line((0,yy,320,yy),fill=c)
d.arc((20,25,300,165),190,350,fill=(180,220,250,190),width=4)
f1=ImageFont.truetype(font_path,42); f2=ImageFont.truetype(font_path,18)
d.text((64,50),'FLOWPS3',font=f1,fill=(250,253,255,255))
d.text((95,112),'V15 XMB',font=f2,fill=(188,224,250,255))
icon.save('pkgfiles/ICON0.PNG',optimize=True)
print('arte FLOWPS3 V15 listo')
