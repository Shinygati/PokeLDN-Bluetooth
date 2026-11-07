package org.pokeldn.usbprobe;

import java.nio.charset.StandardCharsets;
import java.util.Arrays;

/** Same 720-byte record and nine 112-byte beacon fragments as sender's gen5_crypto.py. */
public final class Gen5 {
    public static final String[] LANG = {"ENG","JPN","FRE","GER","ITA","SPA","KOR"};
    public static final int[] LANG_ID = {2,1,3,4,5,7,8};
    public static final String[] GAMES = {"Diamond", "Pearl", "Platinum", "Heart Gold", "Soul Silver", "Black", "White", "Black 2", "White 2"};
    public static final int[] GAME_ID = {10,11,12,7,8,21,20,23,22};
    private Gen5(){}
    static int u16(byte[] b,int o){return (b[o]&255)|((b[o+1]&255)<<8);}
    static long u32(byte[] b,int o){return ((long)(b[o]&255))|((long)(b[o+1]&255)<<8)|((long)(b[o+2]&255)<<16)|((long)(b[o+3]&255)<<24);}
    static void p16(byte[] b,int o,int v){b[o]=(byte)v;b[o+1]=(byte)(v>>>8);}
    static void p32(byte[] b,int o,long v){p16(b,o,(int)v);p16(b,o+2,(int)(v>>>16));}
    static int crc(byte[] b,int off,int count){int c=65535;for(int i=off;i<off+count;i++){c^=(b[i]&255)<<8;for(int j=0;j<8;j++)c=(c&0x8000)!=0?((c<<1)^0x1021)&65535:(c<<1)&65535;}return c;}
    public static int versionMask(String title,byte[] raw){
        if(raw.length==720)return (int)u32(raw,0xCC);
        // The filename/game designation is metadata for 204-byte PGFs, not present inside the PGF itself.
        String s=title.toUpperCase();int hyphen=s.indexOf(" - ");String prefix=hyphen>=0?s.substring(0,hyphen):s;
        if(prefix.contains("BWB2W2"))return (1<<20)|(1<<21)|(1<<22)|(1<<23);
        if(prefix.contains("B2W2"))return (1<<22)|(1<<23);
        if(prefix.contains("BW"))return (1<<20)|(1<<21);
        if(prefix.contains("B2"))return 1<<23;
        if(prefix.contains("W2"))return 1<<22;
        if(prefix.contains("B"))return 1<<21;
        if(prefix.contains("W"))return 1<<20;
        return 0; // Unknown compatibility: don't offer to send.
    }
    public static byte[][] prepare(String title,byte[] raw,int language){return prepare(title,raw,language,-1);}
    /** For imported PGF cards the selected game determines the missing distribution mask. */
    public static byte[][] prepare(String title,byte[] raw,int language,int gameId){
        byte[] record;
        if(raw.length==720){record=Arrays.copyOf(raw,720);}
        else if(raw.length==204){
            record=new byte[720];System.arraycopy(raw,0,record,0,204);
            p32(record,0xCC,gameId>=0?(1L<<gameId):versionMask(title,raw));
            Arrays.fill(record,0xD0,0x2CA,(byte)0xff);
            // The PGF title doubles as the distribution's short description.
            String desc="Mystery Gift";
            StringBuilder sb=new StringBuilder();
            for(int i=0x60;i+1<0xAE;i+=2){int ch=u16(raw,i);if(ch==0xffff||ch==0)break;if(ch==0xfffe)ch=' ';sb.append((char)ch);}
            if(!sb.toString().trim().isEmpty())desc=sb.toString().trim();
            int pos=0xD0;for(char c:desc.toCharArray()){if(pos+4>=0x2CA)break;p16(record,pos,c);pos+=2;}p16(record,pos,0xffff);
        }else throw new IllegalArgumentException("Use a 204-byte PGF or 720-byte WC5FULL");
        if(u32(record,0xCC)==0)throw new IllegalArgumentException("Unknown game compatibility");
        Arrays.fill(record,0xAC,0xB0,(byte)0);record[0xB4]=0;record[0x2CB]=(byte)language;
        p16(record,0x2CE,crc(record,0,0x2CE));
        byte[][] packets=new byte[9][112];long key=0x13579BDFL;
        for(int i=0;i<9;i++){
            byte[] p=packets[i];p16(p,2,0x1380);p[4]=9;
            key=(key*0x6C078965L+1)&0xffffffffL;p32(p,12,key);
            byte[] chunk=new byte[84];int start=i*84;
            if(start<720)System.arraycopy(record,start,chunk,0,Math.min(84,720-start));
            long state=key;
            for(int x=0;x<84;x+=2){state=(state*0x41C64E6DL+0x6073)&0xffffffffL;int val=u16(chunk,x)^(int)(state>>>16);p16(p,16+x,val);}
            p16(p,8,crc(p,16,84));p[100]=(byte)(i+1);p[101]=9;p[102]=0;p[103]=(byte)language;
            p32(p,104,u32(record,0xCC));p16(p,0,crc(p,2,110));
        }
        return packets;
    }
}
