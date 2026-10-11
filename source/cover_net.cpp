#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <string>
#include <vector>
#include <algorithm>
#include <curl/curl.h>
#include <net/net.h>
#include <net/netctl.h>
#include <ppu-types.h>
#include "stb_image.h"
#include "rsxutil.h"

#define CW 180
#define CH 250
#define MAX_CHOICES 6

static bool g_net_init=false;
static std::vector< std::vector<u32> > g_choices;

struct Mem { std::vector<unsigned char> b; };
static size_t wr(void *p,size_t s,size_t n,void *u){
    Mem *m=(Mem*)u; size_t z=s*n; unsigned char *q=(unsigned char*)p;
    if(m->b.size()+z>10*1024*1024) return 0;
    m->b.insert(m->b.end(),q,q+z); return z;
}

static bool init_net(){
    if(g_net_init) return true;
    netInitialize();
    netCtlInit();
    curl_global_init(CURL_GLOBAL_DEFAULT);
    g_net_init=true;
    return true;
}

static bool get_url(const std::string &url, Mem &m, long timeout=16){
    CURL *c=curl_easy_init(); if(!c) return false;
    curl_easy_setopt(c,CURLOPT_URL,url.c_str());
    curl_easy_setopt(c,CURLOPT_FOLLOWLOCATION,1L);
    curl_easy_setopt(c,CURLOPT_CONNECTTIMEOUT,8L);
    curl_easy_setopt(c,CURLOPT_TIMEOUT,timeout);
    curl_easy_setopt(c,CURLOPT_USERAGENT,"Mozilla/5.0 (PLAYSTATION 3; 3D ISO PLAYER V12)");
    curl_easy_setopt(c,CURLOPT_SSL_VERIFYPEER,0L);
    curl_easy_setopt(c,CURLOPT_SSL_VERIFYHOST,0L);
    curl_easy_setopt(c,CURLOPT_ACCEPT_ENCODING,"");
    curl_easy_setopt(c,CURLOPT_WRITEFUNCTION,wr);
    curl_easy_setopt(c,CURLOPT_WRITEDATA,&m);
    CURLcode r=curl_easy_perform(c); long code=0;
    curl_easy_getinfo(c,CURLINFO_RESPONSE_CODE,&code);
    curl_easy_cleanup(c);
    return r==CURLE_OK && code>=200 && code<400 && !m.b.empty() && m.b.size()<10*1024*1024;
}

static std::string title_from_path(const char *p){
    std::string s=p?p:""; size_t k=s.find_last_of('/'); if(k!=std::string::npos) s=s.substr(k+1);
    if(s.size()>4 && !strcasecmp(s.c_str()+s.size()-4,".iso")) s.resize(s.size()-4);
    for(size_t i=0;i<s.size();++i) if(s[i]=='_'||s[i]=='.'||s[i]=='-') s[i]=' ';
    std::string up=s; std::transform(up.begin(),up.end(),up.begin(),::toupper);
    const char *tags[]={" 3D"," SBS"," HSBS"," FSBS"," MVC"," REMUX"," BLURAY"," BLU RAY"," 1080P"," 1080I"," 2160P"," UHD"};
    for(size_t t=0;t<sizeof(tags)/sizeof(tags[0]);++t){
        size_t pos=up.find(tags[t]); if(pos!=std::string::npos){ s.resize(pos); up.resize(pos); }
    }
    while(!s.empty() && s[s.size()-1]==' ') s.resize(s.size()-1);
    return s;
}

static std::string html_unescape(std::string u){
    size_t p=0;
    while((p=u.find("&amp;",p))!=std::string::npos) u.replace(p,5,"&");
    while((p=u.find("\\u0026",p))!=std::string::npos) u.replace(p,6,"&");
    while((p=u.find("\\/",p))!=std::string::npos) u.replace(p,2,"/");
    return u;
}

static void collect_murl(const std::string &html, std::vector<std::string> &urls){
    const char *needles[]={"murl&amp;quot;:&amp;quot;","murl&quot;:&quot;","\\\"murl\\\":\\\"","\"murl\":\""};
    for(size_t ni=0;ni<sizeof(needles)/sizeof(needles[0]) && urls.size()<24;++ni){
        const std::string n=needles[ni]; size_t p=0;
        while(urls.size()<24 && (p=html.find(n,p))!=std::string::npos){
            p+=n.size(); size_t e=p;
            while(e<html.size() && e-p<1800){
                if(html.compare(e,6,"&quot;")==0 || html.compare(e,10,"&amp;quot;")==0 || html[e]=='\"') break;
                ++e;
            }
            if(e>p){
                std::string u=html_unescape(html.substr(p,e-p));
                if((u.find("http://")==0 || u.find("https://")==0) &&
                   (u.find(".jpg")!=std::string::npos || u.find(".jpeg")!=std::string::npos || u.find(".png")!=std::string::npos || u.find("image")!=std::string::npos)){
                    bool dup=false; for(size_t i=0;i<urls.size();++i) if(urls[i]==u){dup=true;break;}
                    if(!dup) urls.push_back(u);
                }
            }
        }
    }
}

static bool decode_cover(const std::vector<unsigned char> &data, std::vector<u32> &out){
    if(data.empty()) return false;
    int w=0,h=0,n=0;
    unsigned char *rgba=stbi_load_from_memory(&data[0],(int)data.size(),&w,&h,&n,4);
    if(!rgba || w<120 || h<120 || w>8000 || h>8000){ if(rgba) stbi_image_free(rgba); return false; }
    double sr=(double)w/(double)h;
    if(sr>1.25 || sr<0.38){ stbi_image_free(rgba); return false; }
    double dr=(double)CW/(double)CH; int cx=0,cy=0,cw=w,ch=h;
    if(sr>dr){ cw=(int)(h*dr); cx=(w-cw)/2; } else { ch=(int)(w/dr); cy=(h-ch)/2; }
    out.resize(CW*CH);
    for(int y=0;y<CH;y++){
        int sy=cy+(int)((long long)y*ch/CH);
        for(int x=0;x<CW;x++){
            int sx=cx+(int)((long long)x*cw/CW);
            unsigned char *p=rgba+(sy*w+sx)*4;
            out[y*CW+x]=0xFF000000u|((u32)p[0]<<16)|((u32)p[1]<<8)|(u32)p[2];
        }
    }
    stbi_image_free(rgba); return true;
}

static int search_bing(const char *iso_path){
    g_choices.clear();
    if(!iso_path || !*iso_path) return 0;
    init_net();
    std::string title=title_from_path(iso_path);
    CURL *tmp=curl_easy_init(); if(!tmp) return 0;
    std::string query=title+" blu ray 3D portada espanol caratula";
    char *esc=curl_easy_escape(tmp,query.c_str(),0);
    if(!esc){ curl_easy_cleanup(tmp); return 0; }
    std::string url="https://www.bing.com/images/search?q="+std::string(esc)+"&form=HDRSC2&first=1&tsc=ImageBasicHover";
    curl_free(esc); curl_easy_cleanup(tmp);
    Mem page; if(!get_url(url,page,18)) return 0;
    page.b.push_back(0); std::string html((char*)&page.b[0]);
    std::vector<std::string> urls; collect_murl(html,urls);
    for(size_t i=0;i<urls.size() && g_choices.size()<MAX_CHOICES;++i){
        Mem pic; if(!get_url(urls[i],pic,14)) continue;
        std::vector<u32> c; if(decode_cover(pic.b,c)) g_choices.push_back(c);
    }
    return (int)g_choices.size();
}

extern "C" int cover_net_search(const char *iso_path){ return search_bing(iso_path); }
extern "C" int cover_net_count(){ return (int)g_choices.size(); }
extern "C" int cover_net_copy_choice(int index, u32 *out, int count){
    if(index<0 || index>=(int)g_choices.size() || !out || count<CW*CH) return 0;
    memcpy(out,&g_choices[index][0],CW*CH*sizeof(u32)); return 1;
}
extern "C" int cover_net_draw_choice(int index, int x, int y, int w, int h){
    if(index<0 || index>=(int)g_choices.size() || w<=0 || h<=0) return 0;
    u32 *fb=get_back_buffer(); u32 sw=get_screen_width(), sh=get_screen_height(); if(!fb) return 0;
    const std::vector<u32> &p=g_choices[index];
    for(int dy=0;dy<h;++dy){ int py=y+dy; if(py<0 || py>=(int)sh) continue; int sy=(int)((long long)dy*CH/h);
        for(int dx=0;dx<w;++dx){ int px=x+dx; if(px<0 || px>=(int)sw) continue; int sx=(int)((long long)dx*CW/w); fb[py*sw+px]=p[sy*CW+sx]; }
    }
    return 1;
}

extern "C" int cover_net_fetch(const char *iso_path, u32 *out, int count){
    if(!iso_path || !out || count<CW*CH) return 0;
    if(search_bing(iso_path)<=0) return 0;
    return cover_net_copy_choice(0,out,count);
}
