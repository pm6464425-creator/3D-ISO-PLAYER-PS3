from pathlib import Path

p = Path('source/main.cpp')
s = p.read_text()


def replace_once(old: str, new: str, label: str):
    global s
    if old not in s:
        raise SystemExit(f'{label} anchor not found')
    s = s.replace(old, new, 1)


# Clean-room UI recreation inspired by the motion/layout seen in SpookyFlow.
# No SpookyFlow source/assets are copied; backend mount/scan code remains untouched.
if '#include <math.h>' not in s:
    s = s.replace('#include <unistd.h>\n', '#include <unistd.h>\n#include <math.h>\n', 1)

# Proportional glyph metrics over our own anti-aliased bitmap font.
replace_once(
    'static unsigned char *g_font = NULL;\n',
    'static unsigned char *g_font = NULL;\nstatic unsigned char g_glyph_left[FONT_GLYPHS];\nstatic unsigned char g_glyph_right[FONT_GLYPHS];\nstatic unsigned char g_glyph_adv[FONT_GLYPHS];\n',
    'font globals')

replace_once(
'''    if(rd != sz) { free(g_font); g_font = NULL; return false; }\n    return true;\n}\n''',
'''    if(rd != sz) { free(g_font); g_font = NULL; return false; }\n    for(int gi=0; gi<FONT_GLYPHS; ++gi) {\n        const unsigned char *src=g_font+gi*FONT_W*FONT_H;\n        int left=FONT_W, right=-1;\n        for(int yy=0; yy<FONT_H; ++yy) {\n            for(int xx=0; xx<FONT_W; ++xx) {\n                if(src[yy*FONT_W+xx] > 18) {\n                    if(xx<left) left=xx;\n                    if(xx>right) right=xx;\n                }\n            }\n        }\n        if(right < left) { left=0; right=0; }\n        int adv=(right-left+1)+2;\n        int cp=FONT_FIRST+gi;\n        if(cp==' ') adv=6;\n        if(adv<4) adv=4;\n        if(adv>FONT_W) adv=FONT_W;\n        g_glyph_left[gi]=(unsigned char)left;\n        g_glyph_right[gi]=(unsigned char)right;\n        g_glyph_adv[gi]=(unsigned char)adv;\n    }\n    return true;\n}\n''',
    'font metrics init')

start=s.find('static void draw_char(int x, int y, char c, int scale, u32 color)')
end=s.find('\nstatic int font_height', start)
if start < 0 or end < 0:
    raise SystemExit('font renderer block not found')
new_font=r'''static int glyph_advance(char c, int scale)
{
    unsigned char uc=(unsigned char)c;
    if(g_font && uc>=FONT_FIRST && uc<=FONT_LAST) return (int)g_glyph_adv[uc-FONT_FIRST]*scale;
    return 6*scale;
}

static void draw_char(int x, int y, char c, int scale, u32 color)
{
    unsigned char uc=(unsigned char)c;
    if(g_font && uc>=FONT_FIRST && uc<=FONT_LAST) {
        int gi=uc-FONT_FIRST;
        int left=g_glyph_left[gi], right=g_glyph_right[gi];
        const unsigned char *src=g_font+gi*FONT_W*FONT_H;
        for(int yy=0; yy<FONT_H; ++yy) {
            for(int xx=left; xx<=right; ++xx) {
                unsigned int a=src[yy*FONT_W+xx];
                if(a<18) continue;
                int dx=(xx-left)*scale;
                for(int sy=0; sy<scale; ++sy)
                    for(int sx=0; sx<scale; ++sx)
                        blend_pixel(x+dx+sx,y+yy*scale+sy,color,a);
            }
        }
        return;
    }

    const u8 *g=fallback_glyph(c);
    for(int row=0; row<7; ++row)
        for(int col=0; col<5; ++col)
            if(g[row] & (1 << (4-col))) fill_rect(x+col*scale,y+row*scale,scale,scale,color);
}

static int char_advance(int scale)
{
    return g_font ? 11*scale : 6*scale;
}
'''
s=s[:start]+new_font+s[end:]

start=s.find('static void draw_text(int x, int y, const std::string &text, int scale, u32 color, int max_chars)')
end=s.find('\nstatic void draw_wrapped', start)
if start < 0 or end < 0:
    raise SystemExit('draw_text block not found')
new_text=r'''static int text_width(const std::string &text, int scale, int max_chars)
{
    int w=0,n=0;
    for(size_t i=0;i<text.size() && n<max_chars;++i) {
        unsigned char ch=(unsigned char)text[i];
        if(ch>=128) continue;
        w += glyph_advance((char)ch,scale);
        n++;
    }
    return w;
}

static void draw_text(int x, int y, const std::string &text, int scale, u32 color, int max_chars)
{
    int cx=x, n=0;
    for(size_t i=0; i<text.size() && n<max_chars; ++i) {
        unsigned char ch=(unsigned char)text[i];
        if(ch>=128) continue;
        draw_char(cx,y,(char)ch,scale,color);
        cx += glyph_advance((char)ch,scale);
        n++;
    }
}

static void draw_centered(int y, const std::string &text, int scale, u32 color)
{
    int width=text_width(text,scale,256);
    int x=((int)get_screen_width()-width)/2;
    if(x<8) x=8;
    draw_text(x,y,text,scale,color,256);
}
'''
s=s[:start]+new_text+s[end:]

# Smooth continuous coverflow state (critically damped spring).
anchor='static unsigned int g_cover_stamp = 1;\n'
extra=r'''
static float g_flow_pos = 0.0f;
static float g_flow_vel = 0.0f;
static bool g_flow_ready = false;

static float flow_smoothstep(float t)
{
    if(t<0.0f) t=0.0f;
    if(t>1.0f) t=1.0f;
    return t*t*(3.0f-2.0f*t);
}

static void flow_update()
{
    float target = g_movies.empty() ? 0.0f : (float)g_selected;
    if(!g_flow_ready || fabsf(g_flow_pos-target)>6.0f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
        g_flow_ready=true;
        return;
    }
    const float dt=1.0f/60.0f;
    const float w=18.0f;
    float x0=g_flow_pos-target;
    float e=expf(-w*dt);
    float tmp=(g_flow_vel+w*x0)*dt;
    g_flow_pos=target+(x0+tmp)*e;
    g_flow_vel=(g_flow_vel-w*tmp)*e;
    if(fabsf(g_flow_pos-target)<0.0008f && fabsf(g_flow_vel)<0.002f) {
        g_flow_pos=target;
        g_flow_vel=0.0f;
    }
}
'''
if anchor not in s:
    raise SystemExit('cover stamp anchor not found')
s=s.replace(anchor,anchor+extra,1)

# Animated original stage background: drifting ribbons, particles and reflective floor.
start=s.find('static void draw_background()')
end=s.find('\nstatic void draw_rgba_scaled', start)
if start < 0 or end < 0:
    raise SystemExit('background block not found')
new_bg=r'''static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    float t=(float)g_frame*(1.0f/60.0f);
    u32 top=0xFF03060A, mid=0xFF07121E, bottom=0xFF06101A;
    for(int y=0;y<sh;y+=5) {
        u32 c = y<sh/2 ? mix_color(top,mid,y,sh/2) : mix_color(mid,bottom,y-sh/2,sh/2);
        fill_rect(0,y,sw,5,c);
    }

    /* drifting blue ribbons */
    for(int band=0; band<4; ++band) {
        float phase=t*(0.28f+0.035f*band)+(float)band*1.41f;
        for(int x=0;x<sw;x+=10) {
            float nx=((float)x-(float)sw*0.5f)/(float)sw;
            float wave=sinf((float)x*0.010f+phase)*0.016f + sinf((float)x*0.0045f-phase*0.7f)*0.012f;
            float yy=0.38f+0.050f*(float)band+wave+nx*nx*(0.17f+0.018f*band);
            int y=(int)(yy*(float)sh);
            if(y>=0 && y<sh) {
                u32 c=(band&1)?0xFF0B4E86:0xFF0E6EBA;
                fill_rect(x,y,13,band==0?3:2,c);
            }
        }
    }

    /* slow floating lights */
    for(int i=0;i<22;i++) {
        float ph=(float)i*0.73f;
        float fx=fmodf((float)(i*97%103)/103.0f + t*(0.0045f+0.00035f*(i%5)),1.0f);
        float fy=0.08f+(float)(i*37%57)/57.0f*0.46f + sinf(t*0.21f+ph)*0.012f;
        int x=(int)(fx*sw), y=(int)(fy*sh);
        int r=1+(i%3);
        draw_circle(x,y,r, (i%4==0)?0xFF2B95D8:0xFF145A89);
    }

    /* horizon + glossy floor */
    int horizon=(int)(sh*0.627f);
    fill_rect(0,horizon,sw,2,0xFF12639A);
    for(int y=horizon+2;y<sh;y+=6) {
        fill_rect(0,y,sw,6,mix_color(0xFF071725,0xFF010407,y-horizon,sh-horizon));
    }
    int sweep=(int)((0.5f+0.5f*sinf(t*0.38f))*sw);
    fill_rect(sweep-70,horizon+10,140,1,0xFF1E6FA3);
}
'''
s=s[:start]+new_bg+s[end:]

# More attractive clean-room fallback covers when no JPG/PNG exists.
start=s.find('static void draw_generic_cover(int x,int y,int w,int h,const Movie &m,bool selected)')
end=s.find('\nstatic void draw_poster', start)
if start < 0 or end < 0:
    raise SystemExit('generic cover block not found')
new_generic=r'''static void draw_generic_cover(int x,int y,int w,int h,const Movie &m,bool selected)
{
    unsigned int hv=title_hash(m.name);
    int r1=36+(hv&63), g1=42+((hv>>6)&55), b1=54+((hv>>12)&70);
    int r2=r1/3, g2=g1/3, b2=b1/3;
    u32 c1=0xFF000000|((u32)r1<<16)|((u32)g1<<8)|(u32)b1;
    u32 c2=0xFF000000|((u32)r2<<16)|((u32)g2<<8)|(u32)b2;
    for(int yy=0;yy<h;yy+=4) fill_rect(x,y+yy,w,4,mix_color(c1,c2,yy,h));
    fill_rect(x,y,w,8,g_tab==TAB_BDISO?0xFF317EB0:0xFF2A8A60);

    const char *format_label=g_tab==TAB_BDISO?"BLU-RAY":"MKV";
    int fw=text_width(format_label,1,16);
    draw_text(x+(w-fw)/2,y+h/2-font_height(1)-4,format_label,1,0xFFEAF5FC,16);

    std::string title=clean_title(m.name);
    int maxc=w/8;
    if(maxc<8) maxc=8;
    if((int)title.size()>maxc) { title.resize(maxc>3?maxc-3:maxc); if(maxc>3) title += "..."; }
    int tw=text_width(title,1,64);
    if(tw>w-12) tw=w-12;
    draw_text(x+(w-tw)/2,y+h*68/100,title,1,0xFFF4F6F8,64);
    if(selected) {
        fill_rect(x,y,3,h,0xFF63C6FF);
        fill_rect(x+w-3,y,3,h,0xFF63C6FF);
    }
}
'''
s=s[:start]+new_generic+s[end:]

# Replace static seven-card UI with continuous perspective coverflow.
start=s.find('static void draw_tab_pill(int x,int y,int w,int h,const char *label,bool active)')
end=s.find('\nstatic void move_selection', start)
if start < 0 or end < 0:
    raise SystemExit('V2 render block not found')
new_ui=r'''static void draw_round_rect(int x,int y,int w,int h,u32 color)
{
    int r=h/2;
    if(r<2) { fill_rect(x,y,w,h,color); return; }
    fill_rect(x+r,y,w-2*r,h,color);
    fill_rect(x,y+r,r,h-2*r,color);
    fill_rect(x+w-r,y+r,r,h-2*r,color);
    draw_circle(x+r,y+r,r,color);
    draw_circle(x+w-r-1,y+r,r,color);
}

static void draw_tab_pill(int x,int y,int w,int h,const char *label,bool active)
{
    u32 outer=active?0xFF2C8FD1:0xFF30383F;
    u32 inner=active?0xFF172735:0xFF11171C;
    draw_round_rect(x-2,y-2,w+4,h+4,outer);
    draw_round_rect(x,y,w,h,inner);
    int tw=text_width(label,1,24);
    draw_text(x+(w-tw)/2,y+(h-font_height(1))/2,label,1,active?0xFFFFFFFF:0xFFC1C8CE,24);
}

struct FlowDrawItem {
    int idx;
    float d;
    int x,y,w,h;
};

static void render_ui()
{
    const u32 WHITE=0xFFF7F8FA, MUTED=0xFFA8B2BA, BLUE=0xFF55BDFD;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    flow_update();
    draw_background();

    /* top navigation: compact shoulder badges + two category pills */
    int tab_h=(int)(sh*0.060f);
    if(tab_h<34) tab_h=34;
    int tab_w=(int)(sh*0.155f);
    int gap=(int)(sh*0.018f);
    int total=tab_w*2+gap;
    int tab_x=(sw-total)/2;
    int tab_y=(int)(sh*0.070f);
    draw_tab_pill(tab_x,tab_y,tab_w,tab_h,"BDISO",g_tab==TAB_BDISO);
    draw_tab_pill(tab_x+tab_w+gap,tab_y,tab_w,tab_h,"MKV",g_tab==TAB_MKV);

    int badge_h=(int)(tab_h*0.62f), badge_w=(int)(badge_h*1.45f);
    draw_round_rect(tab_x-badge_w-gap,tab_y+(tab_h-badge_h)/2,badge_w,badge_h,0xFF171D22);
    draw_text(tab_x-badge_w-gap+(badge_w-text_width("R2",1,4))/2,tab_y+(tab_h-font_height(1))/2,"R2",1,0xFFC7CED4,4);
    draw_round_rect(tab_x+total+gap,tab_y+(tab_h-badge_h)/2,badge_w,badge_h,0xFF171D22);
    draw_text(tab_x+total+gap+(badge_w-text_width("R1",1,4))/2,tab_y+(tab_h-font_height(1))/2,"R1",1,0xFFC7CED4,4);

    if(g_movies.empty()) {
        draw_centered((int)(sh*0.42f),"NO HAY PELICULAS",1,WHITE);
        std::string p=std::string("COPIA TUS ARCHIVOS EN /")+current_folder();
        draw_centered((int)(sh*0.48f),p,1,MUTED);
        draw_centered((int)(sh*0.53f),"HDD INTERNO O USB NTFS",1,BLUE);
    } else {
        const Movie &sel=g_movies[g_selected];
        std::string title=clean_title(sel.name);
        if(title.size()>70) { title.resize(67); title += "..."; }
        draw_centered((int)(sh*0.155f),title,1,WHITE);

        const float sel_h=sh*0.50f;
        const float nb_h=sh*0.32f;
        const float aspect=0.68f;
        const float sel_w=sel_h*aspect;
        const float nb_w=nb_h*aspect;
        const float x1=sel_w*0.5f+nb_w*0.30f+nb_w*0.5f;
        const float pitch=nb_w*1.12f;
        const float horizon=sh*0.627f;
        const float floor_y=sh*0.725f;

        FlowDrawItem items[11];
        int nitems=0;
        int base=(int)floorf(g_flow_pos);
        for(int idx=base-5;idx<=base+5;idx++) {
            if(idx<0 || idx>=(int)g_movies.size()) continue;
            float d=(float)idx-g_flow_pos;
            float a=fabsf(d);
            if(a>4.6f) continue;
            float hh;
            if(a<=1.0f) {
                float k=flow_smoothstep(a);
                hh=sel_h+(nb_h-sel_h)*k;
            } else {
                float shrink=1.0f-(a-1.0f)*0.045f;
                if(shrink<0.78f) shrink=0.78f;
                hh=nb_h*shrink;
            }
            float ww=hh*aspect;
            float xo;
            if(a<=1.0f) xo=a*x1;
            else xo=x1+(a-1.0f)*pitch;
            if(d<0.0f) xo=-xo;
            float bottom=horizon+(floor_y-horizon)*(hh/sel_h);
            FlowDrawItem it;
            it.idx=idx; it.d=d; it.w=(int)ww; it.h=(int)hh;
            it.x=(int)(sw*0.5f+xo-ww*0.5f);
            it.y=(int)(bottom-hh);
            items[nitems++]=it;
        }

        /* farther cards first, near-center cards last */
        for(int i=0;i<nitems;i++) {
            for(int j=i+1;j<nitems;j++) {
                if(fabsf(items[i].d)<fabsf(items[j].d)) {
                    FlowDrawItem tmp=items[i]; items[i]=items[j]; items[j]=tmp;
                }
            }
        }
        for(int i=0;i<nitems;i++) {
            bool active=fabsf(items[i].d)<0.34f;
            draw_poster(items[i].x,items[i].y,items[i].w,items[i].h,g_movies[items[i].idx],active);
        }

        char sz[48], info[180];
        format_size(sel.bytes,sz,sizeof(sz));
        snprintf(info,sizeof(info),"%s   %d / %u   %.34s",sz,g_selected+1,(unsigned)g_movies.size(),sel.source.c_str());
        int iw=text_width(info,1,100);
        int chip_h=(int)(sh*0.042f); if(chip_h<30) chip_h=30;
        int chip_w=iw+34;
        int chip_y=(int)(sh*0.845f);
        draw_round_rect((sw-chip_w)/2,chip_y,chip_w,chip_h,0xFF111A21);
        draw_text((sw-iw)/2,chip_y+(chip_h-font_height(1))/2,info,1,MUTED,100);

        /* page dots, matching the airy console-library feel */
        int dot_y=(int)(sh*0.905f);
        int shown=(int)g_movies.size(); if(shown>9) shown=9;
        int start=g_selected-shown/2; if(start<0) start=0;
        if(start+shown>(int)g_movies.size()) start=(int)g_movies.size()-shown;
        int dot_gap=14;
        int dot_x=sw/2-((shown-1)*dot_gap)/2;
        for(int i=0;i<shown;i++) {
            int idx=start+i;
            draw_circle(dot_x+i*dot_gap,dot_y,idx==g_selected?3:2,idx==g_selected?0xFF70C8FF:0xFF4A5863);
        }
    }

    int footer_h=(int)(sh*0.050f); if(footer_h<34) footer_h=34;
    int fy=sh-footer_h;
    fill_rect(0,fy,sw,footer_h,0xFF090D11);
    fill_rect(0,fy,sw,1,0xFF244B65);
    std::string help="X  ABRIR     TRIANGULO  ACTUALIZAR     R1/R2  CAMBIAR     O  SALIR";
    int hw=text_width(help,1,110);
    draw_text((sw-hw)/2,fy+(footer_h-font_height(1))/2,help,1,0xFFD5DADE,110);

    g_frame++;
    flip();
}
'''
s=s[:start]+new_ui+s[end:]

# Restore 60 Hz pacing for fluid spring motion.
replace_once('        usleep(30000);\n', '        usleep(16000);\n', '60hz pacing')

# Holding left/right now repeats after a short delay instead of requiring repeated taps.
replace_once(
'''    bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_r1=false,p_r2=false;\n    int poll_counter=0;\n''',
'''    bool p_up=false,p_down=false,p_left=false,p_right=false,p_x=false,p_o=false,p_tri=false,p_r1=false,p_r2=false;\n    int repeat_left=0, repeat_right=0;\n    int poll_counter=0;\n''',
    'repeat counters')

replace_once(
'''        if(left && !p_left) move_selection(-1,0);\n        if(right && !p_right) move_selection(1,0);\n''',
'''        if(left) {\n            if(!p_left || (repeat_left>18 && (repeat_left%4)==0)) move_selection(-1,0);\n            repeat_left++;\n        } else repeat_left=0;\n        if(right) {\n            if(!p_right || (repeat_right>18 && (repeat_right%4)==0)) move_selection(1,0);\n            repeat_right++;\n        } else repeat_right=0;\n''',
    'navigation repeat')

p.write_text(s)
print('FLOW MOVIE 3D V3: smooth spring coverflow, animated stage, proportional typography')
