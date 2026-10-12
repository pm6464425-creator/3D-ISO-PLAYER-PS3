from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter

Path('pkgfiles/USRDIR').mkdir(parents=True,exist_ok=True)
font_candidates=[
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
]
font_path=next((x for x in font_candidates if Path(x).exists()),font_candidates[-1])

# Fuente HD RAW 24x36, con antialiasing.
FW,FH=24,36
fnt=ImageFont.truetype(font_path,29)
raw=bytearray()
for code in range(32,127):
    im=Image.new('L',(FW,FH),0)
    d=ImageDraw.Draw(im)
    ch=chr(code)
    box=d.textbbox((0,0),ch,font=fnt)
    w,h=box[2]-box[0],box[3]-box[1]
    x=max(0,(FW-w)//2-box[0])
    y=max(0,(FH-h)//2-box[1]-1)
    d.text((x,y),ch,font=fnt,fill=255)
    raw.extend(im.tobytes())
Path('pkgfiles/USRDIR/FONT.RAW').write_bytes(raw)

# Fondo sobrio y original inspirado en la fluidez de interfaces de consola.
def bg(w,h):
    im=Image.new('RGB',(w,h))
    p=im.load()
    for y in range(h):
        t=y/max(1,h-1)
        c=(int(9+8*t),int(42+44*t),int(103+52*t))
        for x in range(w): p[x,y]=c
    ov=Image.new('RGBA',(w,h),(0,0,0,0)); d=ImageDraw.Draw(ov)
    pts=[]
    for x in range(0,w+20,20):
        import math
        y=int(h*.56 + math.sin(x/210.0)*22 + math.sin(x/490.0)*11)
        pts.append((x,y))
    d.line(pts,fill=(190,226,248,165),width=max(1,w//700))
    d.line([(x,y+16) for x,y in pts],fill=(108,173,220,130),width=max(1,w//900))
    return Image.alpha_composite(im.convert('RGBA'),ov).convert('RGB')

# ICON0.PNG: dimensión estándar habitual de aplicaciones PS3.
icon=bg(320,176)
d=ImageDraw.Draw(icon)
f1=ImageFont.truetype(font_path,30)
f2=ImageFont.truetype(font_path,15)
d.text((28,49),'FLOWPS3',font=f1,fill='white')
d.text((30,102),'XMB LIBRARY',font=f2,fill=(205,229,245))
icon.save('pkgfiles/ICON0.PNG',optimize=True)

# PIC0.PNG mantiene 1000x560 y PIC1.PNG 1920x1080 sin deformación.
pic0=bg(1000,560)
d=ImageDraw.Draw(pic0)
f=ImageFont.truetype(font_path,48)
d.text((62,70),'FLOWPS3',font=f,fill='white')
pic0.save('pkgfiles/PIC0.PNG',optimize=True)

pic1=bg(1920,1080)
d=ImageDraw.Draw(pic1)
f=ImageFont.truetype(font_path,72)
d.text((98,96),'FLOWPS3',font=f,fill='white')
pic1.save('pkgfiles/PIC1.PNG',optimize=True)

# Fondo interno base, sin Spider-Man.
bg(1920,1080).save('pkgfiles/USRDIR/APPBG.JPG',quality=94,optimize=True)
print('arte y fuente HD V17 listos')
