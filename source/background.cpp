#include <stdio.h>
#include <stdlib.h>
#include <vector>
#include <ppu-types.h>
#include "rsxutil.h"
#include "stb_image.h"

#define BG_PATH "/dev_hdd0/game/3DISO0001/USRDIR/APPBG.JPG"
static std::vector<u32> g_bg;
static int g_w=0,g_h=0;

extern "C" int background_load(){
    FILE *f=fopen(BG_PATH,"rb"); if(!f) return 0;
    fseek(f,0,SEEK_END); long sz=ftell(f); fseek(f,0,SEEK_SET); if(sz<=0||sz>8*1024*1024){fclose(f);return 0;}
    unsigned char *buf=(unsigned char*)malloc(sz); if(!buf){fclose(f);return 0;} if(fread(buf,1,sz,f)!=(size_t)sz){free(buf);fclose(f);return 0;} fclose(f);
    int w=0,h=0,n=0; unsigned char *rgba=stbi_load_from_memory(buf,(int)sz,&w,&h,&n,4); free(buf); if(!rgba) return 0;
    g_w=(int)get_screen_width(); g_h=(int)get_screen_height(); g_bg.resize((size_t)g_w*g_h);
    for(int y=0;y<g_h;++y){int sy=(long long)y*h/g_h;for(int x=0;x<g_w;++x){int sx=(long long)x*w/g_w;unsigned char *p=rgba+(sy*w+sx)*4;unsigned r=p[0]*55/100,g=p[1]*55/100,b=p[2]*55/100;g_bg[(size_t)y*g_w+x]=0xFF000000u|(r<<16)|(g<<8)|b;}}
    stbi_image_free(rgba); return 1;
}
extern "C" int background_draw(){ if(g_bg.empty()||g_w!=(int)get_screen_width()||g_h!=(int)get_screen_height()) return 0; u32 *fb=get_back_buffer(); for(size_t i=0;i<g_bg.size();++i) fb[i]=g_bg[i]; return 1; }
extern "C" void background_free(){ g_bg.clear(); g_w=g_h=0; }
