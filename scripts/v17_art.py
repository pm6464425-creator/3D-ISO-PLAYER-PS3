from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import math

Path('pkgfiles/USRDIR').mkdir(parents=True, exist_ok=True)
font_candidates=[
    '/usr/share/fonts/truetype/dejavu/DejaVuSans-ExtraLight.ttf',
    '/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf'
]
font_path=next((x for x in font_candidates if Path(x).exists()),font_candidates[-1])

# FONT.RAW must match source/main.cpp exactly: 16x24 per glyph.
FW,FH=16,24
fnt=ImageFont.truetype(font_path,19)
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
expected=95*FW*FH
assert len(raw)==expected
Path('pkgfiles/USRDIR/FONT.RAW').write_bytes(raw)

def bg(w,h):
    im=Image.new('RGB',(w,h),(4,8,12))
    p=im.load()
    for y in range(h):
        t=y/max(1,h-1)
        c=(int(4+3*t),int(8+17*t),int(12+28*t))
        for x in range(w): p[x,y]=c
    d=ImageDraw.Draw(im,'RGBA')
    for k in range(4):
        pts=[]
        for x in range(0,w+12,12):
            yy=int(h*(0.42+0.055*k)+math.sin(x/max(90,w/8))*h*0.018 + (x-w/2)**2/(max(1,w)*10))
            pts.append((x,yy))
        d.line(pts,fill=(20,125+18*k,220,90),width=max(1,w//600))
    for i in range(24):
        x=int((i*73 % 101)/100*w)
        y=int((i*37 % 53)/100*h*0.62)
        r=max(2,w//220)+(i%4)
        d.ellipse((x-r,y-r,x+r,y+r),fill=(50,160,240,80))
    return im

def centered(draw,xy,text,font,fill):
    x,y=xy
    box=draw.textbbox((0,0),text,font=font)
    tw=box[2]-box[0]
    draw.text((x-tw/2,y),text,font=font,fill=fill)

icon=bg(320,176)
d=ImageDraw.Draw(icon)
f1=ImageFont.truetype(font_path,27)
f2=ImageFont.truetype(font_path,14)
centered(d,(160,48),'FLOW MOVIE 3D',f1,'white')
centered(d,(160,102),'BDISO  |  MKV',f2,(185,225,250))
icon.save('pkgfiles/ICON0.PNG',optimize=True)

pic0=bg(1000,560)
d=ImageDraw.Draw(pic0)
f=ImageFont.truetype(font_path,48)
centered(d,(500,70),'FLOW MOVIE 3D',f,'white')
pic0.save('pkgfiles/PIC0.PNG',optimize=True)

pic1=bg(1920,1080)
d=ImageDraw.Draw(pic1)
f=ImageFont.truetype(font_path,72)
centered(d,(960,90),'FLOW MOVIE 3D',f,'white')
pic1.save('pkgfiles/PIC1.PNG',optimize=True)

bg(1920,1080).save('pkgfiles/USRDIR/APPBG.JPG',quality=94,optimize=True)
print('FLOW MOVIE 3D artwork and FONT.RAW ready')
