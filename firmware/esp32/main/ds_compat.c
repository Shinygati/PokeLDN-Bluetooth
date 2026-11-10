/* FFF0 DS sender compatibility. Beacon layout follows the user's DS sender source.
 * EU Gen IV GGIDs remain provisional, as in that source. */
#include "ds_compat.h"
#include "advert.h"
#include <string.h>
static uint16_t u16(const uint8_t *p) { return p[0] | (uint16_t)p[1]<<8; }
static void p16(uint8_t *p, uint16_t v) { p[0]=v; p[1]=v>>8; }
static void p32(uint8_t *p, uint32_t v) { p16(p,v); p16(p+2,v>>16); }
static uint16_t crc16(const uint8_t *p, size_t n) {
    uint16_t c=0xffff;
    while(n--) { c^=(uint16_t)*p++<<8; for(unsigned i=0;i<8;i++) c=c&0x8000?(c<<1)^0x1021:c<<1; }
    return c;
}
static unsigned count(const ds_upload_t *s) { return s->generation==4?10:s->generation==5?9:0; }
static bool complete(const ds_upload_t *s) { unsigned n=count(s); return n && s->received==((1u<<n)-1); }
int ds_receive(ds_upload_t *s, unsigned which, const uint8_t *p, size_t n) {
    if(which==1) {
        if(n!=113 || p[0]>=count(s)) return -1;
        unsigned slot=p[0]; const uint8_t *f=p+1;
        if(s->generation==4) {
            if(u16(f+2)!=(slot==9?0xffff:slot) || u16(f+4)!=0x3a8 || u16(f+6)) return -1;
        } else if(u16(f)!=crc16(f+2,110) || u16(f+8)!=crc16(f+16,84) ||
                  f[4]!=9 || f[100]!=slot+1 || f[101]!=9) return -1;
        memcpy(s->fragments[slot],f,112); s->received|=1u<<slot; return 0;
    }
    if(which!=2 || !n) return -1;
    if(n==1 && p[0]==0) return 1;
    if(n==1 && p[0]==2) { memset(s,0,sizeof(*s)); return 1; }
    if(n==3 && p[0]==3 && (p[1]==4||p[1]==5) && p[2]<7) {
        memset(s,0,sizeof(*s)); s->generation=p[1]; s->language=p[2]; return 1;
    }
    if(n==1 && p[0]==1 && complete(s)) return 2;
    return -1;
}
size_t ds_image(const ds_upload_t *s, uint8_t *out, size_t capacity) {
    static const uint32_t gen4_ggid[]={0x00400318,0x00000345,0x008000cd,0x008000ce,0x008000cf,0x008000d0,0x00c00018};
    static const uint8_t mac[]={2,0,0,0,0,1};
    unsigned n=count(s); size_t length=128+n*166+4;
    if(!complete(s)||s->language>=7||capacity<length) return 0;
    memset(out,0,length); memcpy(out,"PKSA",4); out[4]=1; out[5]=ADVERT_KIND_3DS;
    p16(out+6,length); out[8]=7; memcpy(out+9,mac,6); memcpy(out+15,"PokeLDN-DS",10);
    out[63]=1; out[113]=ADVERT_FORMAT_PLAIN;
    p16(out+120,s->generation==4?10:21); p16(out+122,s->generation==4?10:21); out[124]=n;
    for(unsigned i=0;i<n;i++) {
        uint8_t *p=out+128+i*166; p16(p,164); p+=2;
        p16(p+8,s->generation==4?10:20); p16(p+10,0x21);
        static const uint8_t tags[]={1,2,0x82,0x84,3,1,7,5,5,1,2,0,0,0,0xdd,0x88,0,9,0xbf,0};
        memcpy(p+12,tags,sizeof(tags));
        p32(p+32,10); p16(p+36,1); p16(p+38,1);
        p32(p+40,s->generation==4?gen4_ggid[s->language]:0x1380);
        p[46]=112; p[47]=s->generation==4?0:1; p16(p+48,0x28); p16(p+50,0x0c);
        memcpy(p+52,s->fragments[i],112);
    }
    p32(out+length-4,advert_crc32(out,length-4)); return length;
}
