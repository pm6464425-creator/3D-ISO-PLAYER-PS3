from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import math

Path('pkgfiles/USRDIR').mkdir(parents=True,exist_ok=True)
font_regular='/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
font_bold='/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf'

# Fuente RAW limpia con antialiasing, manteniendo las dimensiones esperadas por el render.
FW,FH=16,24
fnt=ImageFont.truetype(font_regular,18)
raw=bytearray()
for code in range(32,127):
    im=Image.new('L',(FW,FH),0)
    d=ImageDraw.Draw(im)
    ch=chr(code)
    box=d.textbbox((0,0),ch,font=fnt)
    tw,th=box[2]-box[0],box[3]-box[1]
    d.text(((FW-tw)//2-box[0],(FH-th)//2-box[1]-1),ch,font=fnt,fill=255)
    raw.extend(im.tobytes())
Path('pkgfiles/USRDIR/FONT.RAW').write_bytes(raw)

# Arte XMB del icono de la aplicación.
def gradient(size,top,bottom):
    w,h=size
    im=Image.new('RGB',size)
    px=im.load()
    for y in range(h):
        t=y/max(1,h-1)
        c=tuple(int(top[i]*(1-t)+bottom[i]*t) for i in range(3))
        for x in range(w): px[x,y]=c
    return im

icon=gradient((320,176),(26,83,145),(11,43,92)).convert('RGBA')
d=ImageDraw.Draw(icon,'RGBA')
for i in range(7):
    y=70+i*6
    pts=[]
    for x in range(0,321,8):
        yy=y+int(math.sin(x/46+i*.5)*8)
        pts.append((x,yy))
    d.line(pts,fill=(180,225,255,65),width=2)
fb=ImageFont.truetype(font_bold,34)
fs=ImageFont.truetype(font_regular,17)
d.text((34,46),'FLOWPS3',font=fb,fill=(247,251,255,255))
d.text((36,96),'XMB LIBRARY',font=fs,fill=(193,222,244,255))
icon.convert('RGB').save('pkgfiles/ICON0.PNG',optimize=True)

# PIC1 coherente con la interfaz, sin Spider-Man.
pic=gradient((1920,1080),(11,49,109),(19,101,161)).convert('RGBA')
d=ImageDraw.Draw(pic,'RGBA')
for layer in range(5):
    base=500+layer*30
    pts=[]
    for x in range(0,1921,10):
        y=base+int(math.sin(x/130+layer*.55)*35+math.sin(x/300-layer)*16)
        pts.append((x,y))
    d.line(pts,fill=(198,231,252,100-layer*12),width=3)
large=ImageFont.truetype(font_bold,122)
small=ImageFont.truetype(font_regular,34)
d.text((115,120),'FLOWPS3',font=large,fill=(248,252,255,255))
d.text((125,265),'XMB LIBRARY',font=small,fill=(196,224,244,255))
pic.convert('RGB').save('pkgfiles/PIC1.PNG',optimize=True)
pic.convert('RGB').save('pkgfiles/USRDIR/APPBG.JPG',quality=91,optimize=True)
print('arte FLOWPS3 V16 listo')
