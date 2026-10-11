#include <stdio.h>
#include <stdlib.h>
#include <string.h>
#include <strings.h>
#include <vector>
#include <string>
#include <algorithm>
#include <fcntl.h>
#include <sys/stat.h>

#include <ppu-types.h>
#include "rsxutil.h"
#include "ntfs.h"
extern "C" {
#include "udfread.h"
#include "blockinput.h"
}

#define STB_IMAGE_IMPLEMENTATION
#define STBI_NO_STDIO
#include "stb_image.h"

#define COVER_W 180
#define COVER_H 250
#define COVER_CACHE_DIR "/dev_hdd0/game/3DISO0001/USRDIR/COVERCACHE"

struct NtfsInput {
    udfread_block_input input;
    int fd;
    uint64_t bytes;
};

struct Candidate {
    std::string path;
    int score;
    int64_t size;
};

struct CoverEntry {
    std::string key;
    int state; /* 0 pendiente, 1 lista, 2 sin portada */
    std::vector<u32> pixels;
};

static std::vector<CoverEntry> g_covers;

extern "C" udfread_block_input *block_input_new(const char *path)
{
    (void)path;
    return NULL;
}

static int ntfs_input_close(udfread_block_input *base)
{
    NtfsInput *in=(NtfsInput*)base;
    if(!in) return -1;
    if(in->fd>=0) ps3ntfs_close(in->fd);
    free(in);
    return 0;
}

static int ntfs_input_read(udfread_block_input *base, uint32_t lba, void *buf, uint32_t nblocks, int flags)
{
    (void)flags;
    NtfsInput *in=(NtfsInput*)base;
    if(!in || in->fd<0 || !buf || nblocks==0) return -1;
    s64 pos=(s64)lba*2048LL;
    if(ps3ntfs_seek64(in->fd,pos,SEEK_SET)!=pos) return -1;
    size_t need=(size_t)nblocks*2048u;
    size_t got=0;
    while(got<need) {
        int r=ps3ntfs_read(in->fd,(char*)buf+got,need-got);
        if(r<=0) break;
        got+=(size_t)r;
    }
    return (int)(got/2048u);
}

static uint32_t ntfs_input_size(udfread_block_input *base)
{
    NtfsInput *in=(NtfsInput*)base;
    if(!in) return 0;
    uint64_t blocks=in->bytes/2048ULL;
    if(blocks>0xFFFFFFFFULL) blocks=0xFFFFFFFFULL;
    return (uint32_t)blocks;
}

static udfread_block_input *open_ntfs_input(const char *path)
{
    int fd=ps3ntfs_open(path,O_RDONLY,0);
    if(fd<0) return NULL;
    struct stat st;
    memset(&st,0,sizeof(st));
    if(ps3ntfs_fstat(fd,&st)<0) { ps3ntfs_close(fd); return NULL; }
    NtfsInput *in=(NtfsInput*)calloc(1,sizeof(NtfsInput));
    if(!in) { ps3ntfs_close(fd); return NULL; }
    in->fd=fd;
    in->bytes=(uint64_t)st.st_size;
    in->input.close=ntfs_input_close;
    in->input.read=ntfs_input_read;
    in->input.size=ntfs_input_size;
    return &in->input;
}

static bool image_ext(const char *name)
{
    if(!name) return false;
    const char *dot=strrchr(name,'.');
    if(!dot) return false;
    return !strcasecmp(dot,".jpg") || !strcasecmp(dot,".jpeg") || !strcasecmp(dot,".png");
}

static int image_score(const std::string &path, int64_t size)
{
    std::string s=path;
    std::transform(s.begin(),s.end(),s.begin(),::tolower);
    int score=0;
    if(s.find("cover")!=std::string::npos) score+=120;
    if(s.find("poster")!=std::string::npos) score+=110;
    if(s.find("front")!=std::string::npos) score+=100;
    if(s.find("jacket")!=std::string::npos) score+=95;
    if(s.find("main")!=std::string::npos) score+=45;
    if(s.find("menu")!=std::string::npos) score+=30;
    if(s.find("background")!=std::string::npos || s.find("bg")!=std::string::npos) score+=25;
    if(s.find("thumbnail")!=std::string::npos || s.find("thumb")!=std::string::npos) score+=15;
    if(size>150000 && size<5000000) score+=20;
    if(size>=5000000 && size<12000000) score+=5;
    return score;
}

static bool skip_dir(const char *name)
{
    if(!name) return true;
    if(!strcmp(name,".") || !strcmp(name,"..")) return true;
    if(!strcasecmp(name,"STREAM") || !strcasecmp(name,"CLIPINF") || !strcasecmp(name,"PLAYLIST")) return true;
    return false;
}

static void scan_dir(udfread *udf, const std::string &path, int depth, int &visited, std::vector<Candidate> &out)
{
    if(depth>7 || visited>1800 || out.size()>=80) return;
    UDFDIR *dir=udfread_opendir(udf,path.c_str());
    if(!dir) return;
    struct udfread_dirent ent;
    while(visited<=1800 && out.size()<80) {
        struct udfread_dirent *e=udfread_readdir(dir,&ent);
        if(!e) break;
        visited++;
        if(!e->d_name || !e->d_name[0]) continue;
        std::string child=path;
        if(child.empty() || child[child.size()-1]!='/') child+="/";
        child+=e->d_name;
        if(e->d_type==UDF_DT_DIR) {
            if(!skip_dir(e->d_name)) scan_dir(udf,child,depth+1,visited,out);
        } else if(e->d_type==UDF_DT_REG && image_ext(e->d_name)) {
            UDFFILE *f=udfread_file_open(udf,child.c_str());
            if(!f) continue;
            int64_t sz=udfread_file_size(f);
            udfread_file_close(f);
            if(sz<12000 || sz>12*1024*1024) continue;
            Candidate c; c.path=child; c.size=sz; c.score=image_score(child,sz);
            out.push_back(c);
        }
    }
    udfread_closedir(dir);
}

static bool decode_candidate(udfread *udf, const Candidate &c, std::vector<u32> &out)
{
    UDFFILE *f=udfread_file_open(udf,c.path.c_str());
    if(!f) return false;
    int64_t sz=udfread_file_size(f);
    if(sz<=0 || sz>12*1024*1024) { udfread_file_close(f); return false; }
    unsigned char *data=(unsigned char*)malloc((size_t)sz);
    if(!data) { udfread_file_close(f); return false; }
    ssize_t rd=udfread_file_read(f,data,(size_t)sz);
    udfread_file_close(f);
    if(rd!=sz) { free(data); return false; }

    int w=0,h=0,n=0;
    unsigned char *rgba=stbi_load_from_memory(data,(int)sz,&w,&h,&n,4);
    free(data);
    if(!rgba || w<180 || h<120 || w>7000 || h>7000) {
        if(rgba) stbi_image_free(rgba);
        return false;
    }

    /* Priorizamos una imagen con aspecto de portada, pero aceptamos fondos si no hay otra. */
    out.resize(COVER_W*COVER_H);
    double src_ratio=(double)w/(double)h;
    double dst_ratio=(double)COVER_W/(double)COVER_H;
    int crop_x=0,crop_y=0,crop_w=w,crop_h=h;
    if(src_ratio>dst_ratio) {
        crop_w=(int)(h*dst_ratio);
        crop_x=(w-crop_w)/2;
    } else {
        crop_h=(int)(w/dst_ratio);
        crop_y=(h-crop_h)/2;
    }
    for(int y=0;y<COVER_H;++y) {
        int sy=crop_y+(int)((long long)y*crop_h/COVER_H);
        for(int x=0;x<COVER_W;++x) {
            int sx=crop_x+(int)((long long)x*crop_w/COVER_W);
            unsigned char *p=rgba+(sy*w+sx)*4;
            out[y*COVER_W+x]=0xFF000000u|((u32)p[0]<<16)|((u32)p[1]<<8)|(u32)p[2];
        }
    }
    stbi_image_free(rgba);
    return true;
}

static unsigned int fnv1a(const char *s)
{
    unsigned int h=2166136261u;
    for(;s && *s;++s) { h^=(unsigned char)*s; h*=16777619u; }
    return h;
}

static std::string cache_file(const char *iso_path)
{
    const char *base=strrchr(iso_path,'/');
    base=base?base+1:iso_path;
    char p[256];
    snprintf(p,sizeof(p),COVER_CACHE_DIR "/%08X.bin",fnv1a(base));
    return std::string(p);
}

static bool load_disk_cache(const char *iso_path, std::vector<u32> &pixels)
{
    std::string p=cache_file(iso_path);
    FILE *f=fopen(p.c_str(),"rb");
    if(!f) return false;
    uint32_t hdr[3]={0,0,0};
    if(fread(hdr,sizeof(uint32_t),3,f)!=3 || hdr[0]!=0x434F5631 || hdr[1]!=COVER_W || hdr[2]!=COVER_H) { fclose(f); return false; }
    pixels.resize(COVER_W*COVER_H);
    size_t rd=fread(&pixels[0],sizeof(u32),pixels.size(),f);
    fclose(f);
    if(rd!=pixels.size()) { pixels.clear(); return false; }
    return true;
}

static void save_disk_cache(const char *iso_path, const std::vector<u32> &pixels)
{
    mkdir(COVER_CACHE_DIR,0777);
    std::string p=cache_file(iso_path);
    FILE *f=fopen(p.c_str(),"wb");
    if(!f) return;
    uint32_t hdr[3]={0x434F5631,COVER_W,COVER_H};
    fwrite(hdr,sizeof(uint32_t),3,f);
    fwrite(&pixels[0],sizeof(u32),pixels.size(),f);
    fclose(f);
}

static CoverEntry *find_entry(const char *path)
{
    for(size_t i=0;i<g_covers.size();++i) if(g_covers[i].key==path) return &g_covers[i];
    return NULL;
}

extern "C" int cover_prepare(const char *iso_path)
{
    if(!iso_path || !*iso_path) return 0;
    CoverEntry *existing=find_entry(iso_path);
    if(existing) return existing->state==1;

    if(g_covers.size()>=40) g_covers.erase(g_covers.begin());
    CoverEntry e; e.key=iso_path; e.state=0; g_covers.push_back(e);
    CoverEntry &entry=g_covers.back();

    if(load_disk_cache(iso_path,entry.pixels)) { entry.state=1; return 1; }

    udfread_block_input *input=open_ntfs_input(iso_path);
    if(!input) { entry.state=2; return 0; }
    udfread *udf=udfread_init();
    if(!udf) { input->close(input); entry.state=2; return 0; }
    if(udfread_open_input(udf,input)<0) { udfread_close(udf); entry.state=2; return 0; }

    std::vector<Candidate> candidates;
    int visited=0;
    scan_dir(udf,"/",0,visited,candidates);
    std::sort(candidates.begin(),candidates.end(),[](const Candidate &a,const Candidate &b){
        if(a.score!=b.score) return a.score>b.score;
        return a.size>b.size;
    });

    bool ok=false;
    for(size_t i=0;i<candidates.size() && i<24;++i) {
        if(decode_candidate(udf,candidates[i],entry.pixels)) { ok=true; break; }
    }
    udfread_close(udf);

    if(ok) { entry.state=1; save_disk_cache(iso_path,entry.pixels); return 1; }
    entry.pixels.clear();
    entry.state=2;
    return 0;
}

extern "C" int cover_draw(const char *iso_path, int x, int y, int w, int h)
{
    CoverEntry *e=find_entry(iso_path);
    if(!e || e->state!=1 || e->pixels.empty()) return 0;
    u32 sw=get_screen_width(), sh=get_screen_height();
    u32 *fb=get_back_buffer();
    if(!fb || w<=0 || h<=0) return 0;
    for(int dy=0;dy<h;++dy) {
        int py=y+dy; if(py<0 || py>=(int)sh) continue;
        int sy=(int)((long long)dy*COVER_H/h);
        for(int dx=0;dx<w;++dx) {
            int px=x+dx; if(px<0 || px>=(int)sw) continue;
            int sx=(int)((long long)dx*COVER_W/w);
            fb[py*sw+px]=e->pixels[sy*COVER_W+sx];
        }
    }
    return 1;
}

extern "C" int cover_state(const char *iso_path)
{
    CoverEntry *e=find_entry(iso_path);
    return e?e->state:0;
}
