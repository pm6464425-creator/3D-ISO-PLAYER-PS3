from pathlib import Path
from PIL import Image,ImageDraw,ImageFont,ImageFilter
import random
Path('pkgfiles/USRDIR').mkdir(parents=True,exist_ok=True)
font_path='/usr/share/fonts/truetype/dejavu/DejaVuSansCondensed-Bold.ttf'
FW,FH=16,24
fnt=ImageFont.truetype(font_path,18)
raw=bytearray()
for code in range(32,127):
    im=Image.new('L',(FW,FH),0)
    d=ImageDraw.Draw(im)
    ch=chr(code)
    box=d.textbbox((0,0),ch,font=fnt)
    d.text((max(0,(FW-(box[2]-box[0]))//2-box[0]),max(0,(FH-(box[3]-box[1]))//2-box[1]-1)),ch,font=fnt,fill=255)
    raw.extend(im.tobytes())
Path('pkgfiles/USRDIR/FONT.RAW').write_bytes(raw)

def grad(w,h,a,b):
    im=Image.new('RGB',(w,h))
    px=im.load()
    for y in range(h):
        t=y/(h-1)
        c=tuple(int(a[i]*(1-t)+b[i]*t) for i in range(3))
        for x in range(w): px[x,y]=c
    return im

random.seed(12)
pic=grad(1920,1080,(4,20,45),(245,108,32))
d=ImageDraw.Draw(pic,'RGBA')
for i in range(38):
    x=i*52; h=random.randint(110,390)
    d.rectangle((x,1080-h,x+42,1080),fill=(5,16,28,235))
glow=Image.new('RGBA',pic.size,(0,0,0,0)); gd=ImageDraw.Draw(glow)
parts=[(145,155,510,380),(205,350,450,660),(155,620,290,1030),(350,620,490,1030),(65,330,185,720),(465,330,585,720)]
for box in parts:
    gd.rounded_rectangle(box,25,fill=(30,105,220,180),outline=(90,220,255,240),width=12)
gd.polygon([(245,70),(410,70),(455,170),(205,170)],fill=(18,45,88,255),outline=(90,220,255,255))
gd.polygon([(315,55),(338,10),(365,70)],fill=(90,220,255,255))
glow=glow.filter(ImageFilter.GaussianBlur(8))
pic=Image.alpha_composite(pic.convert('RGBA'),glow)
d=ImageDraw.Draw(pic,'RGBA')
for box in parts:
    d.rounded_rectangle(box,25,fill=(28,40,58,255),outline=(70,170,255,255),width=5)
d.polygon([(245,70),(410,70),(455,170),(205,170)],fill=(34,49,68,255),outline=(75,190,255,255))
d.rectangle((275,105,385,122),fill=(45,220,255,255))
ft=ImageFont.truetype(font_path,128); fs=ImageFont.truetype(font_path,42)
d.text((720,310),'3D ISO PLAYER',font=ft,fill=(245,250,255,255),stroke_width=3,stroke_fill=(25,70,130,255))
d.text((735,475),'CINEMA LIBRARY',font=fs,fill=(90,220,255,255))
pic.convert('RGB').save('pkgfiles/PIC1.PNG',optimize=True)

icon=grad(320,176,(4,12,26),(20,52,90)); d=ImageDraw.Draw(icon,'RGBA')
f1=ImageFont.truetype(font_path,32); f2=ImageFont.truetype(font_path,14)
d.text((38,50),'3D ISO PLAYER',font=f1,fill=(245,250,255,255))
d.text((92,112),'V12 CINEMA',font=f2,fill=(80,220,255,255))
icon.save('pkgfiles/ICON0.PNG',optimize=True)
print('arte V12 listo')
