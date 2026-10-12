from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# Fuente HD: bitmap mayor para texto mas fino/limpio.
s=s.replace('#define FONT_W 16\n#define FONT_H 24','#define FONT_W 24\n#define FONT_H 36',1)
s=s.replace('return g_font ? 13*scale : 6*scale;','return g_font ? 18*scale : 6*scale;',1)

# Escaneo adicional de HDD interno por plataforma.
marker='static void rebuild_movies()\n{\n'
helpers=r'''static void v17_add_dir_files(std::vector<Movie> &fresh,const char *root,const char *tag)
{
    DIR *d=opendir(root); if(!d) return;
    struct dirent *de;
    while((de=readdir(d))!=NULL) {
        if(de->d_name[0]=='.') continue;
        if(!matches_category(de->d_name)) continue;
        std::string full=std::string(root)+"/"+de->d_name;
        struct stat st; if(stat(full.c_str(),&st)!=0) continue;
        Movie m; m.name=de->d_name; m.path=full; m.source=tag; m.title_id=""; m.usb_id=-1; m.bytes=(uint64_t)st.st_size; m.content_type=0;
        fresh.push_back(m);
    }
    closedir(d);
}

static void v17_add_internal_for_category(std::vector<Movie> &fresh)
{
    switch(g_category) {
        case 0:
            v17_add_dir_files(fresh,"/dev_hdd0/packages","HDD INTERNO");
            v17_add_dir_files(fresh,"/dev_hdd0/PKG","HDD INTERNO");
            break;
        case 1:
            v17_add_dir_files(fresh,"/dev_hdd0/FLOWPS3/BLURAY3D","HDD INTERNO");
            break;
        case 2:
            v17_add_dir_files(fresh,"/dev_hdd0/BDISO","HDD INTERNO");
            break;
        case 3:
            v17_add_dir_files(fresh,"/dev_hdd0/DVDISO","HDD INTERNO");
            break;
        case 4:
            v17_add_dir_files(fresh,"/dev_hdd0/FLOWPS3/VIDEOS","HDD INTERNO");
            break;
        case 6:
            v17_add_dir_files(fresh,"/dev_hdd0/PS2ISO","HDD INTERNO");
            break;
        case 7:
            v17_add_dir_files(fresh,"/dev_hdd0/PSXISO","HDD INTERNO");
            break;
        case 8:
            v17_add_dir_files(fresh,"/dev_hdd0/PSPISO","HDD INTERNO");
            break;
        default:
            if(g_category>=9 && g_category<27) {
                std::string root=std::string("/dev_hdd0/")+APP_ROOT+"/"+g_categories[g_category].folder;
                v17_add_dir_files(fresh,root.c_str(),"HDD INTERNO");
            }
            break;
    }
}

static bool v17_ps2_external(const Movie &m)
{
    if(g_category!=6) return false;
    if(m.source.find("USB")!=std::string::npos) return true;
    if(m.path.find("/dev_usb") == 0) return true;
    if(m.path.find(":/") != std::string::npos) return true;
    return false;
}

'''
if marker not in s: raise SystemExit('rebuild marker no encontrado')
s=s.replace(marker,helpers+marker,1)

# Añadir escaneo interno justo antes del sort generado por V15.
needle='    std::sort(fresh.begin(),fresh.end(),[](const Movie&a,const Movie&b){int n=strcasecmp(a.name.c_str(),b.name.c_str());return n? n<0:a.source<b.source;});'
if needle not in s: raise SystemExit('sort V15 no encontrado')
s=s.replace(needle,'    v17_add_internal_for_category(fresh);\n\n'+needle,1)

# Evitar congelamiento: PS2 externo nunca se monta directamente.
old='''static int mount_selected_image(const Movie &movie)
{
    int mode=category_emu_mode(); if(mode<0) return -210;
    if(is_ntfs_movie(movie)) return mount_image_ntfs(movie,mode);
    return mount_image_fat(movie,mode);
}'''
new='''static int mount_selected_image(const Movie &movie)
{
    int mode=category_emu_mode(); if(mode<0) return -210;
    if(v17_ps2_external(movie)) return -260;
    if(is_ntfs_movie(movie)) return mount_image_ntfs(movie,mode);
    return mount_image_fat(movie,mode);
}'''
if old not in s: raise SystemExit('mount_selected_image no encontrado')
s=s.replace(old,new,1)

# Fondo XMB mas suave, continuo y sin cajas pesadas.
start=s.find('static void draw_background()')
end=s.find('\nstatic void draw_poster',start)
if start<0 or end<0: raise SystemExit('draw_background no encontrado')
new_bg=r'''static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    for(int y=0;y<sh;y+=3) {
        double t=(double)y/(double)sh;
        int r=(int)(8 + 8*t), g=(int)(41 + 42*t), b=(int)(103 + 55*t);
        fill_rect(0,y,sw,3,0xFF000000|((u32)r<<16)|((u32)g<<8)|(u32)b);
    }
    double tm=(double)g_frame*0.0075;
    for(int layer=0;layer<4;layer++) {
        int base=(int)(sh*0.54)+layer*16;
        double a1=13.0+layer*4.0, a2=7.0+layer*2.0;
        u32 col=(layer==0)?0xFFD4ECFB:(layer==1)?0xFF9CCDEE:(layer==2)?0xFF6AA6D2:0xFF477FAE;
        for(int x=0;x<sw;x+=3) {
            double yv=sin(x/255.0+tm+layer*.65)*a1 + sin(x/540.0-tm*.68+layer*.45)*a2;
            int y=base+(int)yv;
            fill_rect(x,y,4,1,col);
            if(layer==0) fill_rect(x,y+2,4,1,0xFFAFCFE6);
        }
    }
    for(int i=0;i<14;i++) {
        int x=(i*227+(int)(g_frame*(0.45+(i%3)*0.12)))%sw;
        int y=58+(i*91)%(sh-120);
        blend_pixel(x,y,0xFFFFFFFF,100);
    }
}
'''
s=s[:start]+new_bg+s[end:]

# Frontend XMB V17: reconstruido visualmente, horizontal + columna vertical dinamica.
start=s.find('static const char* cat_short')
end=s.find('\nstatic void move_selection',start)
if start<0 or end<0: raise SystemExit('bloque render V16 no encontrado')
new_render=r'''static const char* cat_short(int idx)
{
    static const char *a[]={"PKG","3D","BD","DVD","VID","PS3","PS2","PS1","PSP","ARC","SNES","NES","N64","MD","SMS","GG","GB","GBC","GBA","PCE","NG","NGP","WS","A26","A78","LYNX","VB","FAV"};
    return (idx>=0&&idx<CATEGORY_COUNT)?a[idx]:"?";
}

static double v17_cat_slide=0.0;
static double v17_item_slide=0.0;
static int v17_last_cat=-1;
static int v17_last_item=-1;

static void v17_update_anim()
{
    if(v17_last_cat<0) v17_last_cat=g_category;
    if(v17_last_cat!=g_category) {
        int d=g_category-v17_last_cat;
        if(d>1) d=-1; else if(d<-1) d=1;
        v17_cat_slide=(double)(-d);
        v17_last_cat=g_category;
    }
    if(v17_last_item<0) v17_last_item=g_selected;
    if(v17_last_item!=g_selected) {
        int d=g_selected-v17_last_item;
        v17_item_slide=(double)(-d);
        v17_last_item=g_selected;
    }
    v17_cat_slide*=0.78;
    v17_item_slide*=0.72;
    if(v17_cat_slide>-0.01&&v17_cat_slide<0.01) v17_cat_slide=0.0;
    if(v17_item_slide>-0.01&&v17_item_slide<0.01) v17_item_slide=0.0;
}

static void draw_xmb_category(int idx,int cx,int cy,bool selected)
{
    int size=selected?70:52;
    int x=cx-size/2,y=cy-size/2;
    u32 white=selected?0xFFF9FCFF:0xCCDAE8F3;
    u32 body=selected?0xFF3E7FAF:0xAA4A7698;
    fill_rect(x+4,y+5,size,size,0x24101B2B);
    fill_rect(x-1,y-1,size+2,size+2,white);
    fill_rect(x,y,size,size,body);
    fill_rect(x+3,y+3,size-6,5,0x66FFFFFF);
    const char *lab=cat_short(idx);
    int tw=(int)strlen(lab)*char_advance(1);
    draw_text(cx-tw/2,cy-font_height(1)/2,lab,1,0xFFFFFFFF,8);
}

static void render_ui()
{
    const u32 WHITE=0xFFF9FCFF, MUTED=0xFFD5E2ED, SOFT=0xFFABC5D9, DIM=0xFF8EA9BF;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    v17_update_anim();
    draw_background();

    draw_text(38,22,"FLOWPS3",1,WHITE,18);
    draw_text(sw-88,22,"V17",1,SOFT,4);

    int cat_y=(sh>=900)?164:122;
    int spacing=(sw>=1600)?146:108;
    int visible=(sw>=1600)?5:4;
    int anim_off=(int)(v17_cat_slide*spacing);

    for(int off=-visible;off<=visible;off++) {
        int idx=(g_category+off+CATEGORY_COUNT)%CATEGORY_COUNT;
        int cx=sw/2+off*spacing+anim_off;
        bool sel=(off==0);
        draw_xmb_category(idx,cx,cat_y,sel);
        if(sel) {
            std::string name=g_categories[idx].name;
            int tw=(int)name.size()*char_advance(1);
            draw_text(cx-tw/2,cat_y+48,name,1,WHITE,42);
        }
    }

    int col_x=sw/2-((sw>=1600)?230:170);
    int list_y=cat_y+104;
    int row_h=(sh>=900)?78:62;
    int max_rows=(sh-list_y-52)/row_h;
    if(max_rows<4) max_rows=4;
    int first=0;
    if(g_selected>=max_rows-1) first=g_selected-(max_rows-2);
    int y_anim=(int)(v17_item_slide*row_h);

    if(g_movies.empty()) {
        draw_text(col_x,list_y+10,"No hay contenido",1,WHITE,30);
        draw_text(col_x,list_y+52,"Pulsa TRIANGULO para actualizar",1,SOFT,40);
    } else {
        for(int i=0;i<max_rows;i++) {
            int idx=first+i; if(idx>=(int)g_movies.size()) break;
            bool sel=(idx==g_selected);
            int y=list_y+i*row_h+y_anim;
            int iw=sel?68:50, ih=iw;
            int ix=col_x, iy=y+(row_h-ih)/2;

            if(sel) {
                fill_rect(ix-7,iy-7,iw+14,ih+14,0x22FFFFFF);
                fill_rect(ix-2,iy-2,iw+4,ih+4,0xA8F4FAFF);
            }
            if(!cover_draw(g_movies[idx].path.c_str(),ix,iy,iw,ih)) {
                fill_rect(ix,iy,iw,ih,sel?0xFFF5F9FC:0xFFC8D7E3);
                fill_rect(ix+3,iy+3,iw-6,ih-6,sel?0xFF457FAE:0xFF6389A6);
                const char *lab=cat_short(g_category);
                int tw=(int)strlen(lab)*char_advance(1);
                draw_text(ix+(iw-tw)/2,iy+ih/2-font_height(1)/2,lab,1,0xFFFFFFFF,8);
            }

            int tx=ix+iw+18;
            std::string title=clean_title(g_movies[idx].name);
            if(sel) {
                draw_text(tx,y+5,title,1,WHITE,52);
                std::string src=g_movies[idx].source.empty()?"BIBLIOTECA":g_movies[idx].source;
                bool blocked=v17_ps2_external(g_movies[idx]);
                draw_text(tx,y+34,src,1,SOFT,28);
                if(blocked) draw_text(tx,y+54,"NO JUGABLE DIRECTAMENTE - REQUIERE HDD INTERNO",1,0xFFFFD58A,58);
                else draw_text(tx,y+54,"JUGABLE",1,0xFFDCECF7,12);
            } else {
                draw_text(tx,y+18,title,1,MUTED,52);
                if(v17_ps2_external(g_movies[idx])) draw_text(tx,y+43,"NO JUGABLE DIRECTAMENTE",1,DIM,30);
            }
        }
    }

    draw_text(34,sh-32,"X Abrir   O Volver   SELECT Opciones   START Arte   TRIANGULO Actualizar",1,WHITE,92);
    g_frame++;
    flip();
}
'''
s=s[:start]+new_render+s[end:]

# Error seguro y explicito para PS2 externo.
needle='else snprintf(err,sizeof(err),"No se pudo preparar el contenido.\\n\\nError Cobra: 0x%08X",ret);'
if needle in s:
    s=s.replace(needle,'if(ret==-260) snprintf(err,sizeof(err),"PS2 externo detectado.\\n\\nNO JUGABLE DIRECTAMENTE desde USB.\\nFLOWPS3 V17 bloqueo el montaje para evitar congelamientos.\\n\\nUsa una copia en /dev_hdd0/PS2ISO/. ");\n                else snprintf(err,sizeof(err),"No se pudo preparar el contenido.\\n\\nError Cobra: 0x%08X",ret);',1)

p.write_text(s)
print('FLOWPS3 V17 patch aplicado')
