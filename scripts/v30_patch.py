from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# FLOWPS3 V30
# Corrige SNES: los ZIP se extraen automaticamente a CACHE/SNES y se lanza
# directamente la ROM .sfc/.smc con Snes9x2010. No toca el backend PS2 V24.

if '#include <zlib.h>' not in s:
    anchor='#include <sys/stat.h>\n'
    if anchor not in s:
        raise SystemExit('include sys/stat no encontrado')
    s=s.replace(anchor, anchor+'#include <zlib.h>\n', 1)

start=s.find('static int v29_launch_snes(const Movie &movie)')
if start < 0:
    raise SystemExit('v29_launch_snes no encontrado')
end=s.find('\n}\n', start)
if end < 0:
    raise SystemExit('fin v29_launch_snes no encontrado')
end += 3

helpers=r'''static unsigned int v30_rd16(const unsigned char *p)
{
    return (unsigned int)p[0] | ((unsigned int)p[1]<<8);
}

static unsigned int v30_rd32(const unsigned char *p)
{
    return (unsigned int)p[0] | ((unsigned int)p[1]<<8) |
           ((unsigned int)p[2]<<16) | ((unsigned int)p[3]<<24);
}

static bool v30_snes_ext(const std::string &n)
{
    return ends_with_ci(n.c_str(),".sfc") || ends_with_ci(n.c_str(),".smc");
}

static std::string v30_inner_basename(const std::string &name)
{
    size_t p=name.find_last_of("/\\");
    std::string n=(p==std::string::npos)?name:name.substr(p+1);
    for(size_t i=0;i<n.size();i++) {
        char c=n[i];
        if(!((c>='a'&&c<='z')||(c>='A'&&c<='Z')||(c>='0'&&c<='9')||c=='.'||c=='_'||c=='-')) n[i]='_';
    }
    return n;
}

static int v30_extract_snes_zip(const std::string &zip_path,std::string &rom_out)
{
    FILE *f=fopen(zip_path.c_str(),"rb");
    if(!f) return -450;

    if(fseek(f,0,SEEK_END)!=0) { fclose(f); return -451; }
    long fsize=ftell(f);
    if(fsize<22) { fclose(f); return -452; }

    long tail_size=fsize;
    if(tail_size>(0x10000+22)) tail_size=(0x10000+22);
    unsigned char *tail=(unsigned char*)memalign(16,(size_t)tail_size);
    if(!tail) { fclose(f); return -453; }
    if(fseek(f,fsize-tail_size,SEEK_SET)!=0 || fread(tail,1,(size_t)tail_size,f)!=(size_t)tail_size) {
        free(tail); fclose(f); return -454;
    }

    long eocd=-1;
    for(long i=tail_size-22;i>=0;i--) {
        if(v30_rd32(tail+i)==0x06054b50U) { eocd=i; break; }
    }
    if(eocd<0) { free(tail); fclose(f); return -455; }

    unsigned int entries=v30_rd16(tail+eocd+10);
    unsigned int cd_offset=v30_rd32(tail+eocd+16);
    free(tail);

    if(fseek(f,(long)cd_offset,SEEK_SET)!=0) { fclose(f); return -456; }

    unsigned int chosen_method=0, chosen_flags=0, chosen_comp=0, chosen_uncomp=0, chosen_local=0;
    std::string chosen_name;

    for(unsigned int i=0;i<entries;i++) {
        unsigned char h[46];
        if(fread(h,1,sizeof(h),f)!=sizeof(h)) { fclose(f); return -457; }
        if(v30_rd32(h)!=0x02014b50U) { fclose(f); return -458; }

        unsigned int flags=v30_rd16(h+8);
        unsigned int method=v30_rd16(h+10);
        unsigned int comp=v30_rd32(h+20);
        unsigned int uncomp=v30_rd32(h+24);
        unsigned int fnlen=v30_rd16(h+28);
        unsigned int exlen=v30_rd16(h+30);
        unsigned int comlen=v30_rd16(h+32);
        unsigned int local=v30_rd32(h+42);

        char *name=(char*)memalign(16,fnlen+1);
        if(!name) { fclose(f); return -459; }
        if(fnlen && fread(name,1,fnlen,f)!=fnlen) { free(name); fclose(f); return -460; }
        name[fnlen]=0;
        std::string n=name;
        free(name);

        if(fseek(f,(long)exlen+(long)comlen,SEEK_CUR)!=0) { fclose(f); return -461; }

        if(chosen_name.empty() && v30_snes_ext(n)) {
            chosen_name=n;
            chosen_method=method;
            chosen_flags=flags;
            chosen_comp=comp;
            chosen_uncomp=uncomp;
            chosen_local=local;
        }
    }

    if(chosen_name.empty()) { fclose(f); return -462; }
    if(chosen_flags & 1U) { fclose(f); return -463; } /* ZIP cifrado no soportado */
    if(chosen_method!=0 && chosen_method!=8) { fclose(f); return -464; }

    if(fseek(f,(long)chosen_local,SEEK_SET)!=0) { fclose(f); return -465; }
    unsigned char lh[30];
    if(fread(lh,1,sizeof(lh),f)!=sizeof(lh) || v30_rd32(lh)!=0x04034b50U) { fclose(f); return -466; }
    unsigned int lfn=v30_rd16(lh+26), lex=v30_rd16(lh+28);
    if(fseek(f,(long)lfn+(long)lex,SEEK_CUR)!=0) { fclose(f); return -467; }

    std::string outname=v30_inner_basename(chosen_name);
    if(outname.empty()) { fclose(f); return -468; }
    rom_out=std::string("/dev_hdd0/FLOWPS3/CACHE/SNES/")+outname;
    FILE *o=fopen(rom_out.c_str(),"wb");
    if(!o) { fclose(f); return -469; }

    const unsigned int BS=64*1024;
    unsigned char *inbuf=(unsigned char*)memalign(16,BS);
    unsigned char *outbuf=(unsigned char*)memalign(16,BS);
    if(!inbuf || !outbuf) {
        if(inbuf) free(inbuf); if(outbuf) free(outbuf);
        fclose(o); fclose(f); unlink(rom_out.c_str()); return -470;
    }

    int ret=0;
    unsigned int remain=chosen_comp;
    unsigned long total_out=0;

    if(chosen_method==0) {
        while(remain>0) {
            unsigned int want=remain>BS?BS:remain;
            size_t r=fread(inbuf,1,want,f);
            if(r!=want) { ret=-471; break; }
            if(fwrite(inbuf,1,r,o)!=r) { ret=-472; break; }
            remain-=(unsigned int)r;
            total_out+=r;
        }
    } else {
        z_stream zs; memset(&zs,0,sizeof(zs));
        if(inflateInit2(&zs,-MAX_WBITS)!=Z_OK) ret=-473;
        while(ret==0 && remain>0) {
            unsigned int want=remain>BS?BS:remain;
            size_t r=fread(inbuf,1,want,f);
            if(r!=want) { ret=-474; break; }
            remain-=(unsigned int)r;
            zs.next_in=inbuf; zs.avail_in=(uInt)r;
            do {
                zs.next_out=outbuf; zs.avail_out=BS;
                int zr=inflate(&zs,Z_NO_FLUSH);
                if(zr!=Z_OK && zr!=Z_STREAM_END) { ret=-475; break; }
                unsigned int have=BS-zs.avail_out;
                if(have && fwrite(outbuf,1,have,o)!=have) { ret=-476; break; }
                total_out+=have;
                if(zr==Z_STREAM_END) { remain=0; break; }
            } while(zs.avail_in>0 && ret==0);
        }
        inflateEnd(&zs);
    }

    free(inbuf); free(outbuf); fclose(o); fclose(f);
    if(ret==0 && chosen_uncomp!=0 && total_out!=chosen_uncomp) ret=-477;
    if(ret!=0) { unlink(rom_out.c_str()); rom_out.clear(); }
    return ret;
}

static int v30_launch_snes(const Movie &movie)
{
    const char *core="/dev_hdd0/game/3DISO0001/USRDIR/cores/snes9x2010_libretro_ps3.SELF";
    struct stat st; if(stat(core,&st)!=0 || st.st_size<=0) return -430;

    std::string rom=movie.path;

    /* NTFS primero se copia a cache porque fopen/zlib trabajan sobre rutas nativas. */
    if(is_ntfs_movie(movie)) {
        std::string cached;
        int cr=v29_copy_ntfs_rom(movie.path,cached);
        if(cr!=0) return cr;
        rom=cached;
    }

    /* ZIP es formato de uso normal en SNES: extraer automaticamente .sfc/.smc. */
    if(ends_with_ci(rom.c_str(),".zip")) {
        std::string extracted;
        int zr=v30_extract_snes_zip(rom,extracted);
        if(zr!=0) return zr;
        rom=extracted;
    }

    if(!v30_snes_ext(rom)) return -478;

    int cfg=v29_write_snes_cfg(rom);
    if(cfg!=0) return cfg;

    /* El launcher PS3 probado pasa la ruta del contenido como argv[0]. */
    char *launcharg=(char*)memalign(16,rom.size()+1);
    if(!launcharg) return -479;
    memcpy(launcharg,rom.c_str(),rom.size()+1);
    const char *argv[2]; argv[0]=launcharg; argv[1]=NULL;

    close_status();
    ioPadEnd();
    sysUtilUnregisterCallback(SYSUTIL_EVENT_SLOT0);
    sysProcessExitSpawn2(core,argv,NULL,NULL,0,3071,SYS_PROCESS_SPAWN_STACK_SIZE_1M);

    /* Sólo se ejecuta si el firmware devuelve el control. */
    free(launcharg);
    ioPadInit(7);
    sysUtilRegisterCallback(SYSUTIL_EVENT_SLOT0,sysutil_callback,NULL);
    return -480;
}
'''

s=s[:start]+helpers+s[end:]

s=s.replace('int sr=v29_launch_snes(movie);','int sr=v30_launch_snes(movie);',1)
s=s.replace('"V29"','"V30"')

p.write_text(s)
print('FLOWPS3 V30 aplicado: SNES ZIP auto-extract + direct launch')
