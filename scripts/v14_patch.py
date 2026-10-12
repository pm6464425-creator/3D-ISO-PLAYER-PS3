from pathlib import Path

# ---------- main.cpp ----------
p=Path('source/main.cpp')
s=p.read_text()

s=s.replace('#include <sys/stat.h>','#include <sys/stat.h>\n#include <dirent.h>',1)
s=s.replace('static const char *APP_ROOT = "3D_ISO_PLAYER";','static const char *APP_ROOT = "FLOWPS3";',1)
s=s.replace('"3D ISO PLAYER"','"FLOWPS3"')
s=s.replace('"PORTADA   ISO / INTERNET 3D"','"ARTE      LOCAL / INTERNET"')

# Carpetas adicionales para juegos PS3 en formato carpeta y estados/cache futuros.
needle='''        ps3ntfs_mkdir((base+"/"+rel).c_str(),0777);\n    }\n}\n'''
rep='''        ps3ntfs_mkdir((base+"/"+rel).c_str(),0777);\n    }\n    ps3ntfs_mkdir((base+"/GAMES").c_str(),0777);\n    ps3ntfs_mkdir((base+"/SAVESTATES").c_str(),0777);\n    ps3ntfs_mkdir((base+"/ART").c_str(),0777);\n    ps3ntfs_mkdir((base+"/ART/COVERS").c_str(),0777);\n    ps3ntfs_mkdir((base+"/ART/BACKGROUNDS").c_str(),0777);\n}\n\nstatic void mkdir_fat(const std::string &p) { mkdir(p.c_str(),0777); }\n\nstatic void ensure_fat_folders(int usb)\n{\n    char dev[32]; snprintf(dev,sizeof(dev),"/dev_usb%03d",usb);\n    std::string base=std::string(dev)+"/"+APP_ROOT;\n    mkdir_fat(base); mkdir_fat(base+"/ROMS");\n    for(int i=0;i<CATEGORY_COUNT;i++) {\n        if(!strcmp(g_categories[i].folder,"FAVORITES")) continue;\n        std::string rel=g_categories[i].folder;\n        size_t slash=rel.find('/');\n        if(slash!=std::string::npos) mkdir_fat(base+"/"+rel.substr(0,slash));\n        mkdir_fat(base+"/"+rel);\n    }\n    mkdir_fat(base+"/GAMES"); mkdir_fat(base+"/SAVESTATES"); mkdir_fat(base+"/ART");\n    mkdir_fat(base+"/ART/COVERS"); mkdir_fat(base+"/ART/BACKGROUNDS");\n}\n'''
if needle not in s: raise SystemExit('ensure_root_folders anchor no encontrado')
s=s.replace(needle,rep,1)

# Escaneo de categoría: NTFS + FAT32. FAT32 usa /dev_usb00x nativo de PSL1GHT.
start=s.find('static void rebuild_movies()')
end=s.find('\nstatic bool refresh_usb_state',start)
if start<0 or end<0: raise SystemExit('rebuild_movies no encontrado')
new=r'''static void rebuild_movies()
{
    std::string previous_path;
    if(!g_movies.empty() && g_selected>=0 && g_selected<(int)g_movies.size()) previous_path=g_movies[g_selected].path;
    std::vector<Movie> fresh;

    for(int usb=0;usb<8;++usb) {
        if(!g_present[usb]) continue;

        /* NTFS */
        if(g_mounts[usb] && g_mount_count[usb]>0) {
            for(int p=0;p<g_mount_count[usb];++p) {
                if(!g_mounts[usb][p].name[0]) continue;
                std::string mount=g_mounts[usb][p].name;
                ensure_root_folders(mount);
                std::string root=mount+":/"+APP_ROOT+"/"+g_categories[g_category].folder;
                DIR_ITER *dir=ps3ntfs_diropen(root.c_str());
                if(!dir) continue;
                char filename[1024]; struct stat st;
                while(ps3ntfs_dirnext(dir,filename,&st)==0) {
                    if(filename[0]=='.'||!matches_category(filename)) continue;
                    Movie m; m.name=filename; m.path=root+"/"+filename; m.usb_id=usb; m.bytes=(uint64_t)st.st_size;
                    fresh.push_back(m); if(fresh.size()>=1536) break;
                }
                ps3ntfs_dirclose(dir);
            }
        }

        /* FAT32 */
        char dev[32]; snprintf(dev,sizeof(dev),"/dev_usb%03d",usb);
        struct stat dst;
        if(stat(dev,&dst)==0) {
            ensure_fat_folders(usb);
            std::string root=std::string(dev)+"/"+APP_ROOT+"/"+g_categories[g_category].folder;
            DIR *d=opendir(root.c_str());
            if(d) {
                struct dirent *de;
                while((de=readdir(d))!=NULL) {
                    if(de->d_name[0]=='.'||!matches_category(de->d_name)) continue;
                    std::string full=root+"/"+de->d_name; struct stat st;
                    if(stat(full.c_str(),&st)!=0) continue;
                    Movie m; m.name=de->d_name; m.path=full; m.usb_id=usb; m.bytes=(uint64_t)st.st_size;
                    fresh.push_back(m); if(fresh.size()>=1536) break;
                }
                closedir(d);
            }
        }
    }

    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.usb_id<b.usb_id;});
    /* Evita duplicados cuando una unidad pudiera verse por más de una ruta. */
    std::vector<Movie> unique;
    for(size_t i=0;i<fresh.size();++i) {
        bool dup=false;
        for(size_t j=0;j<unique.size();++j) if(unique[j].path==fresh[i].path){dup=true;break;}
        if(!dup) unique.push_back(fresh[i]);
    }
    g_movies.swap(unique); g_selected=0;
    if(!previous_path.empty()) for(size_t i=0;i<g_movies.size();++i) if(g_movies[i].path==previous_path){g_selected=(int)i;break;}
    if(!g_movies.empty()&&g_selected>=(int)g_movies.size()) g_selected=(int)g_movies.size()-1;
}
'''
s=s[:start]+new+s[end:]

# Convertir el montador NTFS Blu-ray en montador genérico rawseciso.
s=s.replace('static int mount_bd_iso(const Movie &movie)','static int mount_image_ntfs(const Movie &movie, int emu_mode)',1)
s=s.replace('args->emu_mode = EMU_BD;','args->emu_mode = (uint32_t)emu_mode;',1)

# Añadir montaje FAT32/directo y selector de modo Cobra por categoría.
anchor='''static void cleanup_ntfs()\n{\n'''
extra=r'''static bool is_ntfs_movie(const Movie &m)
{
    return m.path.find(":/")!=std::string::npos;
}

static int category_emu_mode()
{
    if(g_category==1 || g_category==2) return EMU_BD;
    if(g_category==3) return EMU_DVD;
    if(g_category==5) return EMU_PS3;
    if(g_category==6) return EMU_PS2_DVD;
    if(g_category==7) return EMU_PSX;
    if(g_category==8) return EMU_PSP;
    return -1;
}

static int collect_split_files(const std::string &path, char storage[64][MAX_PATH], char *files[64])
{
    int count=0;
    size_t pos=std::string::npos; int width=0;
    if(path.size()>=6 && !strcasecmp(path.c_str()+path.size()-6,".iso.0")) { pos=path.size()-1; width=1; }
    else if(path.size()>=7 && !strcasecmp(path.c_str()+path.size()-7,".iso.00")) { pos=path.size()-2; width=2; }
    if(pos==std::string::npos) {
        strncpy(storage[0],path.c_str(),MAX_PATH-1); storage[0][MAX_PATH-1]=0; files[0]=storage[0]; return 1;
    }
    std::string base=path.substr(0,pos);
    for(int i=0;i<64;i++) {
        if(width==1) snprintf(storage[i],MAX_PATH,"%s%d",base.c_str(),i);
        else snprintf(storage[i],MAX_PATH,"%s%02d",base.c_str(),i);
        struct stat st; if(stat(storage[i],&st)!=0) break;
        files[count++]=storage[i];
    }
    return count;
}

static int mount_image_fat(const Movie &movie, int emu_mode)
{
    char storage[64][MAX_PATH]; char *files[64]; memset(storage,0,sizeof(storage)); memset(files,0,sizeof(files));
    int n=collect_split_files(movie.path,storage,files); if(n<=0) return -201;
    cobra_umount_disc_image(); cobra_send_fake_disc_eject_event(); usleep(120000);
    int ret=-1;
    TrackDef track; track.lba=0; track.is_audio=0;
    if(emu_mode==EMU_PS3) ret=cobra_mount_ps3_disc_image(files,n);
    else if(emu_mode==EMU_BD) ret=cobra_mount_bd_disc_image(files,n);
    else if(emu_mode==EMU_DVD) ret=cobra_mount_dvd_disc_image(files,n);
    else if(emu_mode==EMU_PS2_DVD) ret=cobra_mount_ps2_disc_image(files,n,&track,1);
    else if(emu_mode==EMU_PSX) ret=cobra_mount_psx_disc_image(files[0],&track,1);
    else if(emu_mode==EMU_PSP) ret=cobra_set_psp_umd2(files[0],NULL,NULL,2);
    if(ret==0) cobra_send_fake_disc_insert_event();
    return ret;
}

static int mount_selected_image(const Movie &movie)
{
    int mode=category_emu_mode(); if(mode<0) return -210;
    if(is_ntfs_movie(movie)) return mount_image_ntfs(movie,mode);
    return mount_image_fat(movie,mode);
}

'''
if anchor not in s: raise SystemExit('cleanup anchor no encontrado')
s=s.replace(anchor,extra+anchor,1)

# Actualizar acción X para categorías con backend Cobra real.
old='''            if(g_category!=1 && g_category!=2) {\n                show_ok("Contenido reconocido en la biblioteca.\\n\\nEste backend se integrara en la siguiente fase sin alterar el montaje Blu-ray que ya funciona.");\n                wait_buttons_release();\n                p_x=x; render_ui(); usleep(16000); continue;\n            }\n            show_status("Montando Blu-ray mediante Cobra...\\n\\nNo desconectes el disco USB.");\n            int ret=mount_bd_iso(movie);'''
new='''            int emu=category_emu_mode();\n            if(emu<0) {\n                if(g_category==0) show_ok("PKG detectado correctamente.\\n\\nFLOWPS3 V14 aun no instala paquetes directamente: esta funcion requiere validar el instalador del sistema en tu CFW para no corromper datos.");\n                else if(g_category==4) show_ok("Video detectado correctamente.\\n\\nEl reproductor multimedia integrado se activara cuando validemos el backend compatible con tu CFW.");\n                else show_ok("Contenido detectado correctamente.\\n\\nEl nucleo de esta plataforma aun no esta incluido en este PKG de prueba.");\n                wait_buttons_release(); p_x=x; render_ui(); usleep(16000); continue;\n            }\n            show_status("Preparando contenido mediante Cobra...\\n\\nNo desconectes el disco USB.");\n            int ret=mount_selected_image(movie);'''
if old not in s: raise SystemExit('bloque backend V13 no encontrado')
s=s.replace(old,new,1)

# Mensajes de éxito/error genéricos.
s=s.replace('''                show_status("ISO montada correctamente.\\n\\nVolviendo al XMB...\\n\\nNo desconectes el disco USB.");''','''                show_status("Contenido montado correctamente.\\n\\nVolviendo al XMB...\\n\\nNo desconectes el disco USB.");''',1)
s=s.replace('''                else snprintf(err,sizeof(err),"No se pudo montar la pelicula.\\n\\nError Cobra: 0x%08X",ret);''','''                else snprintf(err,sizeof(err),"No se pudo preparar el contenido.\\n\\nError Cobra: 0x%08X",ret);''',1)

# Pie y textos V14.
s=s.replace('"IZQ/DER SECCION   ARR/ABAJO NAVEGAR   X ABRIR   START ARTE   SELECT OPCIONES   O SALIR"','"IZQ/DER SECCION   ARR/ABAJO NAVEGAR   X ABRIR   START ARTE   TRIANGULO ACTUALIZAR   O SALIR"',1)
s=s.replace('"CONECTA UN USB NTFS/FAT32 O COPIA ARCHIVOS EN SU CARPETA"','"CONECTA USB FAT32/NTFS Y USA LA CARPETA FLOWPS3"',1)

p.write_text(s)

# ---------- Makefile: identidad FLOWPS3 manteniendo APPID para actualizar V13 ----------
p=Path('Makefile'); m=p.read_text()
m=m.replace('TARGET      := 3disoplayer','TARGET      := flowps3')
m=m.replace('TITLE       := 3D ISO PLAYER','TITLE       := FLOWPS3')
p.write_text(m)

print('FLOWPS3 V14 patch aplicado')
