package org.pokeldn.usbprobe;

import java.util.Arrays;

/** Gen IV xPCD / RC4 encoder derived from the DS sender gen4_crypto.py. */
public final class Gen4 {
    private Gen4() {}
    public static final int[] GAME_ID={10,11,12,7,8}; // Diamond Pearl Platinum HeartGold SoulSilver
    private static final byte[] MAC={2,0,0,0,0,1};
    static int u16(byte[] a,int i){return (a[i]&255)|((a[i+1]&255)<<8);}
    static long u32(byte[] a,int i){return (u16(a,i)&65535L)|((long)u16(a,i+2)<<16);}
    static void p16(byte[] a,int i,int v){a[i]=(byte)v;a[i+1]=(byte)(v>>>8);}
    static void p32(byte[] a,int i,long v){p16(a,i,(int)v);p16(a,i+2,(int)(v>>>16));}
    static int checksum(byte[] a){int c=0;for(int i=0;i<a.length-1;i+=2){c=(c+u16(a,i))&65535;c=((c<<1)|(c>>>15))&65535;}return c;}
    private static final int[][] ORDERS={
      {0,1,2,3},{0,1,3,2},{0,2,1,3},{0,2,3,1},{0,3,1,2},{0,3,2,1},
      {1,0,2,3},{1,0,3,2},{1,2,0,3},{1,2,3,0},{1,3,0,2},{1,3,2,0},
      {2,0,1,3},{2,0,3,1},{2,1,0,3},{2,1,3,0},{2,3,0,1},{2,3,1,0},
      {3,0,1,2},{3,0,2,1},{3,1,0,2},{3,1,2,0},{3,2,0,1},{3,2,1,0}};
    static void xorPrng(byte[] a,int off,int len,long state){
        for(int i=off;i<off+len;i+=2){state=(state*0x41c64e6dL+0x6073L)&0xffffffffL;p16(a,i,u16(a,i)^(int)(state>>>16));}}
    /** WC4 contains decrypted PK4 sometimes; PCD must be transmitted with PK4 encrypted. */
    static void encryptPokemonIfNeeded(byte[] pcd){
        if(pcd[0]!=1&&pcd[0]!=2&&pcd[0]!=7)return;
        int off=8,sum=0;
        for(int i=8;i<0x88;i+=2)sum=(sum+u16(pcd,off+i))&65535;
        if(sum!=u16(pcd,off+6))return; // encrypted already
        int order=(int)(((u32(pcd,off)&0x3e000L)>>>13)%24);
        byte[] blocks=Arrays.copyOfRange(pcd,off+8,off+0x88);
        for(int i=0;i<4;i++)System.arraycopy(blocks,ORDERS[order][i]*32,pcd,off+8+i*32,32);
        xorPrng(pcd,off+8,128,u16(pcd,off+6));
        xorPrng(pcd,off+0x88,236-0x88,u32(pcd,off));
    }
    private static byte[] makeKey(int c){
        byte[] k={MAC[0],MAC[1],(byte)c,(byte)(c>>>8),MAC[4],MAC[5],MAC[2],MAC[3]};
        int h=0x3fa2;
        for(int i=0;i<4;i++){int v=u16(k,2*i)^h;h=v;p16(k,i*2,v);}
        return k;
    }
    static void rc4(byte[] bytes,byte[] key){
        int[] s=new int[256];for(int i=0;i<256;i++)s[i]=i;
        int j=0;for(int i=0;i<256;i++){j=(j+s[i]+(key[i%8]&255))&255;int t=s[i];s[i]=s[j];s[j]=t;}
        int i=0;j=0;
        for(int k=0;k<bytes.length;k++){i=(i+1)&255;j=(j+s[i])&255;int t=s[i];s[i]=s[j];s[j]=t;bytes[k]^=(byte)s[(s[i]+s[j])&255];}
    }
    /** Ten 112-byte payloads; slot 9 carries the unencrypted header. */
    public static byte[][] prepare(String filename,byte[] raw){
        if(raw.length!=856)throw new IllegalArgumentException("Gen IV requires 856-byte PCD/WC4");
        String lower=filename.toLowerCase(java.util.Locale.ROOT);
        if(!lower.endsWith(".wc4")&&!lower.endsWith(".pcd"))throw new IllegalArgumentException("Use .wc4 or .pcd");
        byte[] pcd=Arrays.copyOf(raw,856);
        if(lower.endsWith(".wc4"))encryptPokemonIfNeeded(pcd);
        byte[] xpcd=new byte[0x3a8];System.arraycopy(pcd,0x104,xpcd,0,0x50);System.arraycopy(pcd,0,xpcd,0x50,856);
        int sum=checksum(xpcd);rc4(xpcd,makeKey(sum));
        byte[][] out=new byte[10][112];
        for(int i=0;i<10;i++){
            byte[] p=out[i];p16(p,0,sum);p16(p,2,i==9?0xffff:i);p32(p,4,0x3a8);
            if(i==9)System.arraycopy(pcd,0x104,p,8,0x50);
            else System.arraycopy(xpcd,i*104,p,8,104);
        }
        return out;
    }
    public static int versionMask(byte[] raw){return raw.length==856?(int)u32(raw,0x14c):0;}
}
