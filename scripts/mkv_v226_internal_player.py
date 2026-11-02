from pathlib import Path
import re

p=Path('source/main.cpp')
s=p.read_text()

# FLOW MOVIE V2.26 INTERNAL PLAYER
# V2.25 already provides the MKV -> Movian spawn path. V2.26 makes the
# bundled Movian Next executable the first/normal target, while retaining
# external Movian paths only as a compatibility fallback.

old='flow_log("SESSION_START","FLOW MOVIE V2.25 MKV MOVIAN");'
new='flow_log("SESSION_START","FLOW MOVIE V2.26 INTERNAL PLAYER");'
if old not in s:
    raise SystemExit('V2.25 session marker not found')
s=s.replace(old,new,1)

old_paths='''    static const char *paths[] = {\n        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",'''
new_paths='''    static const char *paths[] = {\n        /* Bundled FLOW MOVIE multimedia engine (Movian Next / FFmpeg core). */\n        "/dev_hdd0/game/3DISO0001/USRDIR/flow_player.self",\n        /* Compatibility fallback for users who already have Movian. */\n        "/dev_hdd0/game/HTSS00004/USRDIR/movian.self",'''
if old_paths not in s:
    raise SystemExit('V2.25 player path list not found')
s=s.replace(old_paths,new_paths,1)

# Movian expects argv[0] to be its executable path. parse_opts() then consumes
# argv[1] as the initial URL. V2.25 passed only the movie URL, which made
# ps3_early_init() treat the URL as the binary path and broke dataroot setup.
old_argv='''    const char *launchargv[2];\n    launchargv[0]=url.c_str();\n    launchargv[1]=NULL;'''
new_argv='''    const char *launchargv[3];\n    launchargv[0]=player;\n    launchargv[1]=url.c_str();\n    launchargv[2]=NULL;'''
if old_argv not in s:
    raise SystemExit('V2.25 argv block not found')
s=s.replace(old_argv,new_argv,1)

s=s.replace('''show_ok("No se encontro Movian/Showtime.\\n\\nInstala Movian (HTSS00003) o Movian Next con movian.self para reproducir MKV.");''',
            '''show_ok("No se encontro el motor multimedia interno.\\n\\nReinstala FLOW MOVIE V2.26 para restaurar flow_player.self.");''',1)
s=s.replace('''show_ok("Movian no pudo iniciarse.\\n\\nRevisa que movian.self este instalado correctamente.");''',
            '''show_ok("El motor multimedia no pudo iniciarse.\\n\\nRevisa FLOW_MOVIE.LOG para diagnostico.");''',1)

s=s.replace('/* V2.25: locate an installed Movian/Showtime plain SELF.',
            '/* V2.26: locate bundled FLOW player first, then external Movian fallback.',1)

# V2.26 LIVE BACKGROUND
# Replaces only the visual draw_background() routine. The BDISO/MKV launch,
# USB hot-plug, input debounce, watchdog, RSX reset and coverflow logic remain
# exactly as produced by the existing V2.26 patch chain.
live_bg = r'''/* V226_LIVE_BG: lightweight procedural version of our custom moving background.
   Everything is rendered behind the existing UI; no BDISO/MKV/USB/input logic is touched. */
static int live_tri_wave(unsigned int tick, int period, int amp)
{
    if(period < 4 || amp <= 0) return 0;
    int p=(int)(tick % (unsigned int)period);
    int half=period/2;
    int v=(p<half)?p:(period-p);
    return (v*(amp*2))/half-amp;
}

static void live_line(int x0,int y0,int x1,int y1,int thick,u32 color)
{
    int dx=abs(x1-x0), sx=x0<x1?1:-1;
    int dy=-abs(y1-y0), sy=y0<y1?1:-1;
    int err=dx+dy;
    for(;;) {
        fill_rect(x0-thick/2,y0-thick/2,thick,thick,color);
        if(x0==x1 && y0==y1) break;
        int e2=err<<1;
        if(e2>=dy) { err+=dy; x0+=sx; }
        if(e2<=dx) { err+=dx; y0+=sy; }
    }
}

static void live_symbol_triangle(int cx,int cy,int r,u32 c)
{
    live_line(cx,cy-r,cx-r,cy+r,2,c);
    live_line(cx-r,cy+r,cx+r,cy+r,2,c);
    live_line(cx+r,cy+r,cx,cy-r,2,c);
}

static void live_symbol_square(int cx,int cy,int r,u32 c)
{
    fill_rect(cx-r,cy-r,r*2,2,c);
    fill_rect(cx-r,cy+r-2,r*2,2,c);
    fill_rect(cx-r,cy-r,2,r*2,c);
    fill_rect(cx+r-2,cy-r,2,r*2,c);
}

static void live_symbol_x(int cx,int cy,int r,u32 c)
{
    live_line(cx-r,cy-r,cx+r,cy+r,2,c);
    live_line(cx+r,cy-r,cx-r,cy+r,2,c);
}

static void live_symbol_circle(int cx,int cy,int r,u32 c)
{
    static const signed char px[16]={ 32,30,23,12,0,-12,-23,-30,-32,-30,-23,-12,0,12,23,30 };
    static const signed char py[16]={ 0,12,23,30,32,30,23,12,0,-12,-23,-30,-32,-30,-23,-12 };
    for(int i=0;i<16;++i) {
        int x=cx+(px[i]*r)/32;
        int y=cy+(py[i]*r)/32;
        fill_rect(x-1,y-1,3,3,c);
    }
}

static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    unsigned int f=g_frame;

    /* Preserve the V2.26 fast RSX clear. */
    rsx_clear_backbuffer(0xFF03070D);

    /* Moving blue ribbons / waves. */
    int base=(int)(sh*0.29f);
    for(int band=0; band<4; ++band) {
        int phase=(int)((f*(1+band)) % 240u);
        for(int x=-16; x<sw+16; x+=16) {
            int pp=(x+phase*2+band*47) % 160;
            if(pp<0) pp+=160;
            int tri=(pp<80)?pp:(160-pp);
            int wave=(tri-40)*(5+band)/10;
            int y=base+band*22+wave;
            u32 col=(band&1)?0xFF0A4C7A:0xFF0B6AA5;
            fill_rect(x,y,18,2,col);
        }
    }

    /* Independent floating PlayStation-style symbols: triangle, circle, X, square. */
    int tx=(int)((f*2u)%(unsigned int)(sw+120))-60;
    int ty=(int)(sh*0.19f)+live_tri_wave(f,180,18);
    live_symbol_triangle(tx,ty,17,0xFF1697C8);

    int cx=sw-(int)((f*3u/2u)%(unsigned int)(sw+140))+50;
    int cy=(int)(sh*0.33f)+live_tri_wave(f+51,220,20);
    live_symbol_circle(cx,cy,16,0xFF1A79B8);

    int xx=(int)((f+90u)%300u)*sw/300;
    int xy=(int)(sh*0.47f)+live_tri_wave(f+23,200,14);
    live_symbol_x(xx,xy,15,0xFF2468A5);

    int qx=sw-(int)(((f+140u)*2u)%(unsigned int)(sw+160))+70;
    int qy=(int)(sh*0.14f)+live_tri_wave(f+87,260,16);
    live_symbol_square(qx,qy,14,0xFF238BB8);

    /* Tiny moving particles. */
    for(int i=0;i<18;++i) {
        unsigned int seed=(unsigned int)(i*73+19);
        int x=(int)((seed*17u+f*(1u+(unsigned int)(i%3)))%(unsigned int)sw);
        int y=28+(int)((seed*29u+(f/(2u+(unsigned int)(i%2))))%(unsigned int)(sh/2));
        int sz=(i%6==0)?2:1;
        fill_rect(x,y,sz,sz,(i%5==0)?0xFF38B7E3:0xFF135A83);
    }

    /* Slow glints / destellos. */
    for(int i=0;i<3;++i) {
        int gx=(int)(((f*(1u+(unsigned int)i))+i*211u)%(unsigned int)sw);
        int gy=(int)(sh*(0.20f+0.11f*i));
        int gr=4+((int)((f/12u+i*3u)%5u));
        fill_rect(gx-gr,gy,gr*2+1,1,0xFF2B8FBE);
        fill_rect(gx,gy-gr,1,gr*2+1,0xFF2B8FBE);
    }

    /* Horizon, glossy floor and moving reflections. */
    int horizon=(int)(sh*0.627f);
    fill_rect(0,horizon,sw,2,0xFF12639A);
    fill_rect(0,horizon+2,sw,3,0xFF071725);
    fill_rect(0,sh-((int)(sh*0.050f)),sw,1,0xFF244B65);

    int sweep=(int)((f*3u)%(unsigned int)(sw+160))-80;
    fill_rect(sweep,horizon+12,80,1,0xFF15547C);
    fill_rect(sw-sweep-80,horizon+34,54,1,0xFF0F3653);

    /* Faint mirrored traces of the moving symbols on the floor. */
    int ry=horizon+18;
    fill_rect(tx-10,ry,20,1,0xFF0A314B);
    fill_rect(cx-8,ry+18,16,1,0xFF0A2940);
    fill_rect(xx-7,ry+35,14,1,0xFF09253A);
    fill_rect(qx-7,ry+51,14,1,0xFF082033);
}
'''

pat=re.compile(r'static void draw_background\(\)\n\{.*?\n\}\n\nstatic void draw_rgba_scaled',re.S)
m=pat.search(s)
if not m:
    raise SystemExit('V2.26 draw_background block not found')
s=s[:m.start()]+live_bg+'\nstatic void draw_rgba_scaled'+s[m.end():]

p.write_text(s)
print('FLOW MOVIE V2.26: internal player + custom live procedural background enabled')
