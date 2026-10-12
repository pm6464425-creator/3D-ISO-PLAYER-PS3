from pathlib import Path

p=Path('source/main.cpp')
s=p.read_text()

# Fondo más limpio y cercano al XMB: azul, ondas suaves y brillo ambiental.
start=s.find('static void draw_background()')
end=s.find('\nstatic void draw_poster',start)
if start<0 or end<0: raise SystemExit('draw_background no encontrado')
new_bg=r'''static void draw_background()
{
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    for(int y=0;y<sh;y+=4) {
        int r=10 + (8*y)/sh;
        int g=50 + (55*y)/sh;
        int b=112 + (58*y)/sh;
        fill_rect(0,y,sw,4,0xFF000000 | ((u32)r<<16) | ((u32)g<<8) | (u32)b);
    }

    double t=(double)g_frame*0.010;
    for(int layer=0; layer<5; ++layer) {
        double amp1=16.0 + layer*4.0;
        double amp2=8.0 + layer*2.5;
        int base=(int)(sh*0.50) + layer*18;
        u32 col=(layer==0)?0xFF9ED0F4:(layer==1)?0xFF7FB9E6:(layer==2)?0xFF5A9FD6:(layer==3)?0xFF4387C1:0xFF3274AD;
        for(int x=0;x<sw;x+=4) {
            double yy=sin((double)x/230.0+t+layer*0.56)*amp1 + sin((double)x/510.0-t*0.62+layer)*amp2;
            int y=base+(int)yy;
            fill_rect(x,y,5,1,col);
            if(layer<2) fill_rect(x,y+2,5,1,0xFFCAE5F8);
        }
    }

    /* puntos de luz muy discretos */
    for(int i=0;i<18;i++) {
        int x=(i*211 + (int)(g_frame*(1+(i%2))))%sw;
        int y=(i*83 + 60)%sh;
        fill_rect(x,y,2,2,0xFFBEDCF3);
    }
}
'''
s=s[:start]+new_bg+s[end:]

# Sustituir el render V15 por uno con proporciones y comportamiento más cercanos al XMB de PS3.
start=s.find('static const char* cat_short')
end=s.find('\nstatic void move_selection',start)
if start<0 or end<0: raise SystemExit('bloque XMB V15 no encontrado')
new_render=r'''static const char* cat_short(int idx)
{
    static const char *a[]={"PKG","3D","BD","DVD","VID","PS3","PS2","PS1","PSP","ARC","SNES","NES","N64","MD","SMS","GG","GB","GBC","GBA","PCE","NG","NGP","WS","A26","A78","LYNX","VB","FAV"};
    return (idx>=0&&idx<CATEGORY_COUNT)?a[idx]:"?";
}

static void draw_xmb_category(int idx,int cx,int cy,bool selected)
{
    int size=selected?76:56;
    int x=cx-size/2, y=cy-size/2;

    /* sombra */
    fill_rect(x+5,y+7,size,size,0x4413263D);

    /* icono cuadrado, proporciones similares al XMB */
    u32 edge=selected?0xFFF5FAFF:0xCCB9D5EA;
    u32 body=selected?0xFF3D83BE:0xFF3977AA;
    fill_rect(x-2,y-2,size+4,size+4,edge);
    fill_rect(x,y,size,size,body);
    fill_rect(x+4,y+4,size-8,size/5,0x447ED4FF);

    std::string t=cat_short(idx);
    int tw=(int)t.size()*char_advance(1);
    draw_text(cx-tw/2,cy-font_height(1)/2,t,1,0xFFFFFFFF,8);
}

static void render_ui()
{
    const u32 WHITE=0xFFF9FCFF, MUTED=0xFFD0E1EF, SOFT=0xFFA9C7DF;
    int sw=(int)get_screen_width(), sh=(int)get_screen_height();
    draw_background();

    /* cabecera limpia tipo sistema */
    draw_text(42,24,"FLOWPS3",1,WHITE,20);
    draw_text(sw-166,24,"V16",1,SOFT,8);

    int cat_y=(sh>=900)?176:128;
    int spacing=(sw>=1600)?154:112;
    int visible=(sw>=1600)?5:4;

    /* categorías horizontales */
    for(int off=-visible;off<=visible;off++) {
        int idx=(g_category+off+CATEGORY_COUNT)%CATEGORY_COUNT;
        int cx=sw/2+off*spacing;
        bool sel=(off==0);
        draw_xmb_category(idx,cx,cat_y,sel);
        if(sel) {
            std::string name=g_categories[idx].name;
            int tw=(int)name.size()*char_advance(1);
            draw_text(cx-tw/2,cat_y+56,name,1,WHITE,40);
        }
    }

    /* lista vertical exactamente debajo de la categoría seleccionada */
    int column_x=sw/2-((sw>=1600)?210:150);
    int list_y=cat_y+104;
    int row_h=(sh>=900)?82:64;
    int max_rows=(sh-list_y-68)/row_h;
    if(max_rows<4) max_rows=4;
    int first=0;
    if(g_selected>=max_rows-1) first=g_selected-(max_rows-2);

    if(g_movies.empty()) {
        draw_text(column_x,list_y+18,"NO HAY CONTENIDO",1,WHITE,32);
        draw_text(column_x,list_y+58,"TRIANGULO PARA ACTUALIZAR",1,SOFT,34);
    } else {
        for(int i=0;i<max_rows;i++) {
            int idx=first+i;
            if(idx>=(int)g_movies.size()) break;
            bool sel=(idx==g_selected);
            int y=list_y+i*row_h;

            int iw=sel?74:54;
            int ih=iw;
            int ix=column_x;
            int iy=y+(row_h-ih)/2;

            if(sel) {
                fill_rect(ix-10,iy-10,iw+20,ih+20,0x334B9BD1);
                fill_rect(ix-4,iy-4,iw+8,ih+8,0x99E7F4FC);
            }

            if(!cover_draw(g_movies[idx].path.c_str(),ix,iy,iw,ih)) {
                fill_rect(ix,iy,iw,ih,sel?0xFFF3F8FC:0xFFB4D0E5);
                fill_rect(ix+4,iy+4,iw-8,ih-8,sel?0xFF4C8FC5:0xFF5E91B7);
                const char *lab=cat_short(g_category);
                int tw=(int)strlen(lab)*char_advance(1);
                draw_text(ix+(iw-tw)/2,iy+ih/2-font_height(1)/2,lab,1,0xFFFFFFFF,8);
            }

            int tx=ix+iw+22;
            std::string title=clean_title(g_movies[idx].name);
            if(sel) {
                draw_text(tx,y+6,title,2,WHITE,48);
                std::string src=g_movies[idx].source.empty()?"BIBLIOTECA":g_movies[idx].source;
                draw_text(tx,y+43,src,1,SOFT,34);
            } else {
                draw_text(tx,y+18,title,1,MUTED,52);
            }
        }
    }

    /* ayuda inferior minimalista */
    fill_rect(0,sh-42,sw,42,0x33243F5B);
    draw_text(38,sh-30,"X ABRIR   O VOLVER   SELECT OPCIONES   START ARTE   TRIANGULO ACTUALIZAR",1,WHITE,90);

    g_frame++;
    flip();
}
'''
s=s[:start]+new_render+s[end:]

# Mejorar el texto de información para que el menú contextual se sienta más limpio.
s=s.replace('INFORMACION\\n\\nTitulo:', 'INFORMACION DEL ELEMENTO\\n\\nTitulo:', 1)

p.write_text(s)
print('FLOWPS3 V16 XMB visual aplicado')
