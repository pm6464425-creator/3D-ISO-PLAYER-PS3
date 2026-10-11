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

#define CW 180
#define CH 250

static bool g_net_init=false;

struct Mem { std::vector<unsigned char> b; };
static size_t wr(void *p,size_t s,size_t n,void *u){ Mem *m=(Mem*)u; size_t z=s*n; unsigned char *q=(unsigned char*)p; m->b.insert(m->b.end(),q,q+z); return z; }

static bool init_net(){
    if(g_net_init) return true;
    netInitialize();
    netCtlInit();
    curl_global_init(CURL_GLOBAL_DEFAULT);
    g_net_init=true;
    return true;
}

static bool get_url(const std::string &url, Mem &m){
    CURL *c=curl_easy_init(); if(!c) return false;
    curl_easy_setopt(c,CURLOPT_URL,url.c_str());
    curl_easy_setopt(c,CURLOPT_FOLLOWLOCATION,1L);
    curl_easy_setopt(c,CURLOPT_CONNECTTIMEOUT,8L);
    curl_easy_setopt(c,CURLOPT_TIMEOUT,15L);
    curl_easy_setopt(c,CURLOPT_USERAGENT,"3D ISO PLAYER PS3/1.0");
    curl_easy_setopt(c,CURLOPT_SSL_VERIFYPEER,0L);
    curl_easy_setopt(c,CURLOPT_SSL_VERIFYHOST,0L);
    curl_easy_setopt(c,CURLOPT_WRITEFUNCTION,wr);
    curl_easy_setopt(c,CURLOPT_WRITEDATA,&m);
    CURLcode r=curl_easy_perform(c); long code=0; curl_easy_getinfo(c,CURLINFO_RESPONSE_CODE,&code); curl_easy_cleanup(c);
    return r==CURLE_OK && code>=200 && code<300 && !m.b.empty() && m.b.size()<8*1024*1024;
}

static std::string title_from_path(const char *p){
    std::string s=p?p:""; size_t k=s.find_last_of('/'); if(k!=std::string::npos) s=s.substr(k+1);
    if(s.size()>4 && !strcasecmp(s.c_str()+s.size()-4,".iso")) s.resize(s.size()-4);
    for(size_t i=0;i<s.size();++i) if(s[i]=='_'||s[i]=='.') s[i]=' ';
    const char *tags[]={" 3D"," SBS"," MVC"," REMUX"," BLURAY"," BLU RAY"," 1080P"," 2160P"};
    for(size_t t=0;t<sizeof(tags)/sizeof(tags[0]);++t){ size_t p=s.find(tags[t]); if(p!=std::string::npos) s.resize(p); }
    return s;
}

static std::string json_source(const std::string &j){
    size_t p=j.find("\"source\":\""); if(p==std::string::npos) return ""; p+=10; size_t e=j.find('"',p); if(e==std::string::npos) return "";
    std::string u=j.substr(p,e-p); for(size_t x=0;(x=u.find("\\/",x))!=std::string::npos;) u.replace(x,2,"/");
    return u;
}

extern "C" int cover_net_fetch(const char *iso_path, u32 *out, int count){
    if(!iso_path || !out || count<CW*CH) return 0; init_net();
    std::string title=title_from_path(iso_path);
    CURL *tmp=curl_easy_init(); if(!tmp) return 0; char *esc=curl_easy_escape(tmp,title.c_str(),0); if(!esc){ curl_easy_cleanup(tmp); return 0; }
    std::string api="https://en.wikipedia.org/w/api.php?action=query&generator=search&gsrsearch="+std::string(esc)+"%20film&gsrlimit=4&prop=pageimages&piprop=thumbnail&pithumbsize=600&format=json&origin=*";
    curl_free(esc); curl_easy_cleanup(tmp);
    Mem js; if(!get_url(api,js)) return 0; js.b.push_back(0); std::string img=json_source((char*)&js.b[0]); if(img.empty()) return 0;
    Mem pic; if(!get_url(img,pic)) return 0;
    int w=0,h=0,n=0; unsigned char *rgba=stbi_load_from_memory(&pic.b[0],(int)pic.b.size(),&w,&h,&n,4); if(!rgba||w<80||h<80){ if(rgba) stbi_image_free(rgba); return 0; }
    double sr=(double)w/h, dr=(double)CW/CH; int cx=0,cy=0,cw=w,ch=h; if(sr>dr){cw=(int)(h*dr);cx=(w-cw)/2;}else{ch=(int)(w/dr);cy=(h-ch)/2;}
    for(int y=0;y<CH;y++){int sy=cy+(long long)y*ch/CH;for(int x=0;x<CW;x++){int sx=cx+(long long)x*cw/CW;unsigned char *p=rgba+(sy*w+sx)*4;out[y*CW+x]=0xFF000000u|((u32)p[0]<<16)|((u32)p[1]<<8)|p[2];}}
    stbi_image_free(rgba); return 1;
}
