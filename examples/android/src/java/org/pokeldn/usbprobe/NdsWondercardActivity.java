package org.pokeldn.usbprobe;

import android.Manifest;
import android.app.Activity;
import android.bluetooth.BluetoothAdapter;
import android.bluetooth.BluetoothDevice;
import android.bluetooth.BluetoothGatt;
import android.bluetooth.BluetoothGattCallback;
import android.bluetooth.BluetoothGattCharacteristic;
import android.bluetooth.BluetoothGattService;
import android.bluetooth.BluetoothManager;
import android.bluetooth.BluetoothProfile;
import android.bluetooth.le.BluetoothLeScanner;
import android.bluetooth.le.ScanCallback;
import android.bluetooth.le.ScanResult;
import android.content.Intent;
import android.content.pm.PackageManager;
import android.net.Uri;
import android.os.Build;
import android.os.Bundle;
import android.content.res.Configuration;
import android.graphics.Color;
import android.graphics.Typeface;
import android.graphics.drawable.GradientDrawable;
import android.graphics.drawable.RippleDrawable;
import android.content.res.ColorStateList;
import android.graphics.BitmapFactory;
import android.widget.ImageView;
import android.widget.BaseAdapter;
import android.view.MotionEvent;
import android.view.Gravity;
import android.view.Window;
import android.view.WindowManager;
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.database.Cursor;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
import android.widget.AdapterView;
import android.widget.LinearLayout;
import android.widget.ListView;
import android.widget.ScrollView;
import android.widget.Spinner;
import android.widget.TextView;
import android.widget.Toast;
import java.io.ByteArrayOutputStream;
import java.io.InputStream;
import java.nio.charset.StandardCharsets;
import java.util.ArrayDeque;
import java.util.ArrayList;
import java.util.HashMap;
import java.util.List;
import java.util.Map;
import java.util.UUID;

/** Experimental Gen IV/V BLE controller; explicitly manual scan/connect/send. No auto reconnect. */
public final class NdsWondercardActivity extends Activity {
    private static final String DEVICE_NAME="Gen IV/V Wondercard Sender";
    private static final UUID SERVICE=UUID.fromString("0000fff0-0000-1000-8000-00805f9b34fb");
    private static final UUID DATA=UUID.fromString("0000fff1-0000-1000-8000-00805f9b34fb");
    private static final UUID CTRL=UUID.fromString("0000fff2-0000-1000-8000-00805f9b34fb");
    private static final int FILE_PICK=45,PERM=46;
    private final Handler handler=new Handler(Looper.getMainLooper());
    private final ArrayList<Card> allCards=new ArrayList<>(),shownCards=new ArrayList<>();
    private final ArrayList<BluetoothDevice> devices=new ArrayList<>();
    private final ArrayDeque<WriteOp> writes=new ArrayDeque<>();
    private BluetoothLeScanner scanner;
    private BluetoothGatt gatt;
    private BluetoothGattCharacteristic dataChar,ctrlChar;
    private boolean scanning=false,writing=false,connected=false,ready=false,mtuReady=false;
    private boolean stopCommandPending=false;
    private int mtu=23;
    private Spinner langSpinner,gameSpinner,cardSpinner;

    private static final String[] LANGUAGE_LABELS={"English","日本語","Français","Deutsch","Italiano","Español","한국어"};
    private LinearLayout languageTabRow;
    private void refreshLanguageTabs(){
        if(languageTabRow==null||langSpinner==null)return;
        int selected=langSpinner.getSelectedItemPosition();
        for(int i=0;i<languageTabRow.getChildCount();i++){
            TextView chip=(TextView)languageTabRow.getChildAt(i);
            boolean active=i==selected;
            chip.setTextColor(active?(dark?0xFF102138:Color.WHITE):textColor);
            chip.setBackground(touchBackground(active?accentColor:panelColor,active?accentColor:outlineColor,10));
            chip.setContentDescription(LANGUAGE_LABELS[i]+(active?", selected":""));
            chip.setSelected(active);
        }
    }
    private void addLanguageTabs(LinearLayout parent){
        android.widget.HorizontalScrollView scroll=new android.widget.HorizontalScrollView(this);
        scroll.setHorizontalScrollBarEnabled(false);
        scroll.setFillViewport(false);
        languageTabRow=new LinearLayout(this);
        languageTabRow.setOrientation(LinearLayout.HORIZONTAL);
        for(int i=0;i<LANGUAGE_LABELS.length;i++){
            final int language=i;
            TextView chip=label(LANGUAGE_LABELS[i],13,true);
            chip.setGravity(Gravity.CENTER);
            chip.setPadding(dp(14),dp(11),dp(14),dp(11));
            chip.setClickable(true);
            chip.setFocusable(true);
            chip.setOnClickListener(v->{
                chip.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);
                langSpinner.setSelection(language);
                refreshLanguageTabs();
                updateCards();
            });
            LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-2,dp(45));
            lp.rightMargin=dp(8);
            languageTabRow.addView(chip,lp);
        }
        scroll.addView(languageTabRow);
        LinearLayout.LayoutParams rowLp=new LinearLayout.LayoutParams(-1,dp(51));
        rowLp.topMargin=dp(7);rowLp.bottomMargin=dp(12);
        parent.addView(scroll,rowLp);
        refreshLanguageTabs();
    }

    private TextView status, cardCount;
    private volatile boolean libraryLoading=true;
    private boolean dark;
    private int bgColor, panelColor, textColor, mutedColor, accentColor, outlineColor, errorColor;
    private ArrayAdapter<String> deviceAdapter,cardAdapter;
    private final ArrayList<Card> importedCards=new ArrayList<>();
    private final Map<String,Integer> importGame=new HashMap<>();
    static class Card {final String lang,name,path;final byte[] bytes;Card(String l,String n,String p,byte[] b){lang=l;name=n;path=p;bytes=b;}}
    static class WriteOp {final BluetoothGattCharacteristic characteristic;final byte[] value;WriteOp(BluetoothGattCharacteristic c,byte[] v){characteristic=c;value=v;}}
    private void log(String s){handler.post(()->{if(status!=null)status.setText(s);});}

    private int dp(int value){return (int)(getResources().getDisplayMetrics().density*value+0.5f);}
    private static int color(String hex){return Color.parseColor(hex);}
    private GradientDrawable background(int background,int stroke,int radius){
        GradientDrawable drawable=new GradientDrawable();
        drawable.setColor(background);
        drawable.setCornerRadius(dp(radius));
        if(stroke!=Color.TRANSPARENT)drawable.setStroke(dp(1),stroke);
        return drawable;
    }
    private android.graphics.drawable.Drawable touchBackground(int surface,int border,int radius){
        GradientDrawable normal=background(surface,border,radius);
        GradientDrawable pressed=background(blend(surface,accentColor,0.18f),accentColor,radius);
        android.graphics.drawable.StateListDrawable states=new android.graphics.drawable.StateListDrawable();
        states.addState(new int[]{android.R.attr.state_pressed},pressed);
        states.addState(new int[]{},normal);
        return new RippleDrawable(ColorStateList.valueOf(blend(accentColor,Color.WHITE,0.15f)),states,null);
    }
    private static int blend(int from,int to,float mix){
        float inv=1f-mix;
        return Color.rgb((int)(Color.red(from)*inv+Color.red(to)*mix),
                         (int)(Color.green(from)*inv+Color.green(to)*mix),
                         (int)(Color.blue(from)*inv+Color.blue(to)*mix));
    }
    private void touchFeedback(View v){
        v.setOnTouchListener((view,event)->{
            if(event.getActionMasked()==MotionEvent.ACTION_DOWN){
                view.animate().cancel();view.animate().scaleX(0.985f).scaleY(0.985f).setDuration(75).start();
            } else if(event.getActionMasked()==MotionEvent.ACTION_UP||event.getActionMasked()==MotionEvent.ACTION_CANCEL){
                view.animate().cancel();view.animate().scaleX(1f).scaleY(1f).setDuration(120).start();
            }
            return false; // Let the normal Android click, accessibility and scrolling behavior work.
        });
    }
    private void palette(){
        dark=(getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        bgColor=color(dark?"#0B1120":"#F3F6FB");
        panelColor=color(dark?"#172235":"#FFFFFF");
        textColor=color(dark?"#F2F6FF":"#18243A");
        mutedColor=color(dark?"#AABAD0":"#52647D");
        accentColor=color(dark?"#76C9FF":"#1667C7");
        outlineColor=color(dark?"#33445E":"#D9E2ED");
        errorColor=color(dark?"#FFB3AC":"#A4342D");
    }
    private TextView label(String text,int size,boolean heavy){
        TextView v=new TextView(this);v.setText(text);v.setTextSize(size);v.setTextColor(textColor);
        if(heavy)v.setTypeface(null,Typeface.BOLD);
        return v;
    }
    private void section(LinearLayout root,String text){
        TextView v=label(text,14,true);v.setTextColor(mutedColor);
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.topMargin=dp(18);lp.bottomMargin=dp(8);root.addView(v,lp);
    }
    private LinearLayout panel(LinearLayout root){
        LinearLayout v=new LinearLayout(this);v.setOrientation(LinearLayout.VERTICAL);v.setPadding(dp(16),dp(14),dp(16),dp(14));
        v.setBackground(background(panelColor,outlineColor,16));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(12);
        root.addView(v,lp);return v;
    }
    private Button button(LinearLayout root,String name,Runnable action){
        return actionButton(root,name,false,action);
    }
    private Button actionButton(LinearLayout root,String name,boolean primary,Runnable action){
        Button b=new Button(this);b.setText(name);b.setAllCaps(false);b.setTextSize(14);
        b.setTypeface(null,Typeface.BOLD);b.setTextColor(primary?bgColor:textColor);
        b.setBackground(touchBackground(primary?accentColor:panelColor,
                primary?Color.TRANSPARENT:outlineColor,12));
        b.setElevation(dp(1));b.setMinHeight(dp(52));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(52));lp.bottomMargin=dp(10);
        root.addView(b,lp);touchFeedback(b);
        b.setOnClickListener(v->{b.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);action.run();});
        return b;
    }
    private Spinner spinner(LinearLayout root,String[] choices){
        Spinner s=new Spinner(this);
        ArrayAdapter<String> a=new ArrayAdapter<String>(this,android.R.layout.simple_spinner_item,choices){
            @Override public View getView(int pos,View convert,android.view.ViewGroup parent){
                TextView t=(TextView)super.getView(pos,convert,parent);t.setTextColor(textColor);t.setTextSize(15);t.setPadding(dp(12),dp(10),dp(8),dp(10));return t;
            }
            @Override public View getDropDownView(int pos,View convert,android.view.ViewGroup parent){
                TextView t=(TextView)super.getDropDownView(pos,convert,parent);t.setTextColor(textColor);t.setBackgroundColor(panelColor);t.setPadding(dp(16),dp(12),dp(16),dp(12));return t;
            }
        };
        a.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        s.setAdapter(a);s.setBackground(touchBackground(bgColor,outlineColor,10));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(54));lp.bottomMargin=dp(12);root.addView(s,lp);return s;
    }
    private static final String[] GAME_INITIALS={"D","P","PT","HG","SS","B","W","B2","W2"};
    private static final int[] GAME_COLORS={
        0xFF1663D8,0xFFE66EAE,0xFF68707C,0xFFE4B442,0xFFBBC0C5,
        0xFF191A1E,0xFFF6F8FC,0xFF151619,0xFFF5F7FB
    };
    private LinearLayout gameRow(int index,boolean dropdown){
        LinearLayout row=new LinearLayout(this);row.setOrientation(LinearLayout.HORIZONTAL);
        row.setGravity(Gravity.CENTER_VERTICAL);
        row.setPadding(dp(12),dp(dropdown?8:6),dp(12),dp(dropdown?8:6));
        if(dropdown)row.setBackground(touchBackground(panelColor,Color.TRANSPARENT,8));
        TextView tile=label(GAME_INITIALS[index],14,true);
        tile.setGravity(Gravity.CENTER);
        tile.setTextColor((index==6||index==8)?0xFF182235:Color.WHITE);
        tile.setBackground(background(GAME_COLORS[index],index==6||index==8?0xFFAFB9C9:Color.TRANSPARENT,9));
        row.addView(tile,new LinearLayout.LayoutParams(dp(45),dp(36)));
        TextView name=label("Pokémon "+Gen5.GAMES[index],15,true);
        LinearLayout.LayoutParams np=new LinearLayout.LayoutParams(0,-2,1f);
        np.leftMargin=dp(13);row.addView(name,np);
        return row;
    }
    private Spinner gamePicker(LinearLayout root){
        Spinner spinner=new Spinner(this);
        spinner.setAdapter(new BaseAdapter(){
            @Override public int getCount(){return Gen5.GAMES.length;}
            @Override public Object getItem(int index){return Gen5.GAMES[index];}
            @Override public long getItemId(int index){return index;}
            @Override public View getView(int index,View old,android.view.ViewGroup parent){return gameRow(index,false);}
            @Override public View getDropDownView(int index,View old,android.view.ViewGroup parent){return gameRow(index,true);}
        });
        spinner.setBackground(touchBackground(bgColor,outlineColor,10));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,dp(60));lp.bottomMargin=dp(12);
        root.addView(spinner,lp);
        return spinner;
    }
    private void loadBundledCards(){
        new Thread(()->{
            ArrayList<Card> loaded=new ArrayList<>();
            String failure=null;
            try(InputStream in=getAssets().open("catalog.tsv")){
                String txt=new String(readAll(in),StandardCharsets.UTF_8);
                for(String line:txt.split("\n")){
                    String[] c=line.split("\t",3);
                    if(c.length==3)loaded.add(new Card(c[0],c[1],c[2],readAsset(c[2])));
                }
            }catch(Exception e){failure=e.getMessage();}
            final String error=failure;
            handler.post(()->{
                if(isFinishing()||isDestroyed())return;
                allCards.clear();allCards.addAll(loaded);
                libraryLoading=false;updateCards();
                if(error!=null)log("Could not read built-in cards: "+error);
            });
        },"wondercard-library").start();
    }
    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        palette();
        Window window=getWindow();
        window.setStatusBarColor(bgColor);window.setNavigationBarColor(bgColor);
        window.getDecorView().setSystemUiVisibility(dark?0:(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR));
        window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        // Keep content below the clock, camera cut-out and status bar on modern phones.
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);
        root.setPadding(dp(18),dp(18),dp(18),dp(30));root.setBackgroundColor(bgColor);
        ScrollView scroll=new ScrollView(this);scroll.setFillViewport(true);
        scroll.setClipToPadding(false);scroll.setFitsSystemWindows(true);
        scroll.setVerticalScrollBarEnabled(false);
        scroll.addView(root);setContentView(scroll);
        root.setAlpha(0f);
        root.animate().alpha(1f).setDuration(180).start();

        LinearLayout hero=new LinearLayout(this);hero.setGravity(Gravity.CENTER_VERTICAL);
        LinearLayout words=new LinearLayout(this);words.setOrientation(LinearLayout.VERTICAL);
        hero.addView(words,new LinearLayout.LayoutParams(0,-2,1f));
        TextView kicker=label("DS  /  MYSTERY GIFT",11,true);kicker.setTextColor(accentColor);
        words.addView(kicker);
        TextView heading=label("Wonder Card Sender",24,true);
        LinearLayout.LayoutParams hl=new LinearLayout.LayoutParams(-1,-2);hl.topMargin=dp(6);words.addView(heading,hl);
        TextView intro=label("Wonder Cards for compatible DS family systems  •  ESP32-S3",13,false);intro.setTextColor(mutedColor);
        LinearLayout.LayoutParams il=new LinearLayout.LayoutParams(-1,-2);il.topMargin=dp(6);words.addView(intro,il);
        try(InputStream in=getAssets().open("nds-phat.png")){
            ImageView ds=new ImageView(this);
            ds.setImageBitmap(BitmapFactory.decodeStream(in));
            ds.setScaleType(ImageView.ScaleType.FIT_CENTER);
            ds.setContentDescription("White original Nintendo DS console");
            LinearLayout.LayoutParams dpImg=new LinearLayout.LayoutParams(dp(104),dp(108));
            dpImg.leftMargin=dp(6);hero.addView(ds,dpImg);
        }catch(Exception ignored){} // A missing illustration never prevents the sender from running.
        LinearLayout.LayoutParams heroLp=new LinearLayout.LayoutParams(-1,-2);
        heroLp.bottomMargin=dp(18);root.addView(hero,heroLp);

        LinearLayout connectionPanel=panel(root);
        TextView connectionTitle=label("Connection",16,true);connectionPanel.addView(connectionTitle);
        status=label("Not connected",13,false);status.setTextColor(mutedColor);status.setPadding(0,dp(8),0,dp(12));connectionPanel.addView(status);
        actionButton(connectionPanel,"Find my ESP32-S3",true,()->startScan());
        button(connectionPanel,"Disconnect",()->disconnect());
        ListView deviceList=new ListView(this);deviceList.setDividerHeight(dp(1));
        deviceList.setDivider(new android.graphics.drawable.ColorDrawable(outlineColor));
        connectionPanel.addView(deviceList,new LinearLayout.LayoutParams(-1,dp(100)));
        deviceAdapter=new ArrayAdapter<String>(this,android.R.layout.simple_list_item_1,new ArrayList<>()){
            @Override public View getView(int pos,View convert,android.view.ViewGroup parent){
                TextView v=(TextView)super.getView(pos,convert,parent);v.setTextColor(textColor);v.setTextSize(12);return v;
            }
        };deviceList.setAdapter(deviceAdapter);
        deviceList.setOnItemClickListener((parent,view,pos,id)->{if(pos<devices.size())connect(devices.get(pos));});

        section(root,"CHOOSE YOUR GIFT");
        LinearLayout selectionPanel=panel(root);
        selectionPanel.addView(label("Game",13,true));
        gameSpinner=gamePicker(selectionPanel);
        selectionPanel.addView(label("Language",13,true));
        langSpinner=spinner(selectionPanel,Gen5.LANG);
        langSpinner.setVisibility(View.GONE);
        addLanguageTabs(selectionPanel);
        selectionPanel.addView(label("Wonder Card",13,true));
        cardSpinner=spinner(selectionPanel,new String[]{"Loading Wonder Cards..."});
        cardAdapter=new ArrayAdapter<String>(this,android.R.layout.simple_spinner_item,new ArrayList<>()){
            @Override public View getView(int pos,View convert,android.view.ViewGroup parent){
                TextView v=(TextView)super.getView(pos,convert,parent);v.setTextColor(textColor);v.setPadding(dp(12),dp(10),dp(8),dp(10));return v;
            }
            @Override public View getDropDownView(int pos,View convert,android.view.ViewGroup parent){
                TextView v=(TextView)super.getDropDownView(pos,convert,parent);v.setTextColor(textColor);
                v.setBackgroundColor(panelColor);v.setPadding(dp(12),dp(12),dp(8),dp(12));return v;
            }
        };cardAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);cardSpinner.setAdapter(cardAdapter);
        cardCount=label("Loading library...",12,false);cardCount.setTextColor(mutedColor);selectionPanel.addView(cardCount);
        langSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onNothingSelected(AdapterView<?> p){}public void onItemSelected(AdapterView<?> p,View v,int pos,long id){refreshLanguageTabs();updateCards();}});
        gameSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){public void onNothingSelected(AdapterView<?> p){}public void onItemSelected(AdapterView<?> p,View v,int pos,long id){updateCards();}});
        button(selectionPanel,"Import a Wonder Card",()->{
            Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.setType("*/*");i.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,FILE_PICK);
        });

        section(root,"DISTRIBUTION CONTROL");
        LinearLayout sendPanel=panel(root);
        actionButton(sendPanel,"Start Wonder Card Distribution",true,()->sendGift());
        button(sendPanel,"Stop Wonder Card Distribution",()->stopGift());
        TextView help=label("Start uploads the selected gift and tells the ESP32-S3 to broadcast it. Stop sends a command to end the ESP32-S3 wireless broadcast — not just the phone upload.",12,false);
        help.setTextColor(mutedColor);sendPanel.addView(help);
        TextView footer=label("Experimental wireless distribution  •  Keep your ESP32-S3 powered during use.",12,false);
        footer.setTextColor(mutedColor);root.addView(footer);
        restoreImports();
        int initialGame=getIntent().getIntExtra("game_index",0);
        if(initialGame>=0&&initialGame<Gen5.GAMES.length)gameSpinner.setSelection(initialGame);
        updateCards();requestPermissionsIfNeeded();
        loadBundledCards();
    }
    private byte[] readAsset(String name)throws Exception{try(InputStream in=getAssets().open(name)){return readAll(in);}}
    private static byte[] readAll(InputStream in)throws Exception{ByteArrayOutputStream o=new ByteArrayOutputStream();byte[] buf=new byte[4096];for(int n;(n=in.read(buf))!=-1;)o.write(buf,0,n);return o.toByteArray();}
    private void updateCards(){if(langSpinner==null||gameSpinner==null||cardAdapter==null)return;
        int li=langSpinner.getSelectedItemPosition(),gi=gameSpinner.getSelectedItemPosition();if(li<0||gi<0)return;
        String lang=Gen5.LANG[li];int bit=1<<Gen5.GAME_ID[gi];
        shownCards.clear();cardAdapter.clear();
        for(Card c:importedCards)if(c.lang.equals(lang) && importGame.getOrDefault(c.path,-1)==gi)addCard(c);
        for(Card c:allCards){if(c.lang.equals(lang) && compatible(c,gi,bit))addCard(c);}
        cardAdapter.notifyDataSetChanged();
        if(cardCount!=null)cardCount.setText(libraryLoading?
            "Loading Wonder Card library…":shownCards.size()==0?
            "No matching Wonder Cards for this game and language":
            shownCards.size()+" compatible Wonder Cards available");
    }
    private boolean compatible(Card c,int gi,int bit){
        try {return gi<5 ? c.bytes.length==856 && (Gen4.versionMask(c.bytes)&bit)!=0
                          : (c.bytes.length==204||c.bytes.length==720) && (Gen5.versionMask(c.name,c.bytes)&bit)!=0;}
        catch(Exception e){return false;}
    }
    // Generation IV uses its own 16-bit glyph indices (not regular UTF-16).
    // The international glyph table below follows PKHeX's StringConverter4Util.
    private static final String GEN4_GLYPHS="\u0000\u3000\u3041\u3042\u3043\u3044\u3045\u3046\u3047\u3048\u3049\u304A\u304B\u304C\u304D\u304E\u304F\u3050\u3051\u3052\u3053\u3054\u3055\u3056\u3057\u3058\u3059\u305A\u305B\u305C"
            + "\u305D\u305E\u305F\u3060\u3061\u3062\u3063\u3064\u3065\u3066\u3067\u3068\u3069\u306A\u306B\u306C\u306D\u306E\u306F\u3070\u3071\u3072\u3073\u3074\u3075\u3076\u3077\u3078\u3079\u307A"
            + "\u307B\u307C\u307D\u307E\u307F\u3080\u3081\u3082\u3083\u3084\u3085\u3086\u3087\u3088\u3089\u308A\u308B\u308C\u308D\u308F\u3092\u3093\u30A1\u30A2\u30A3\u30A4\u30A5\u30A6\u30A7\u30A8"
            + "\u30A9\u30AA\u30AB\u30AC\u30AD\u30AE\u30AF\u30B0\u30B1\u30B2\u30B3\u30B4\u30B5\u30B6\u30B7\u30B8\u30B9\u30BA\u30BB\u30BC\u30BD\u30BE\u30BF\u30C0\u30C1\u30C2\u30C3\u30C4\u30C5\u30C6"
            + "\u30C7\u30C8\u30C9\u30CA\u30CB\u30CC\u30CD\u30CE\u30CF\u30D0\u30D1\u30D2\u30D3\u30D4\u30D5\u30D6\u30D7\u30D8\u30D9\u30DA\u30DB\u30DC\u30DD\u30DE\u30DF\u30E0\u30E1\u30E2\u30E3\u30E4"
            + "\u30E5\u30E6\u30E7\u30E8\u30E9\u30EA\u30EB\u30EC\u30ED\u30EF\u30F2\u30F3\uFF10\uFF11\uFF12\uFF13\uFF14\uFF15\uFF16\uFF17\uFF18\uFF19\uFF21\uFF22\uFF23\uFF24\uFF25\uFF26\uFF27\uFF28"
            + "\uFF29\uFF2A\uFF2B\uFF2C\uFF2D\uFF2E\uFF2F\uFF30\uFF31\uFF32\uFF33\uFF34\uFF35\uFF36\uFF37\uFF38\uFF39\uFF3A\uFF41\uFF42\uFF43\uFF44\uFF45\uFF46\uFF47\uFF48\uFF49\uFF4A\uFF4B\uFF4C"
            + "\uFF4D\uFF4E\uFF4F\uFF50\uFF51\uFF52\uFF53\uFF54\uFF55\uFF56\uFF57\uFF58\uFF59\uFF5A\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000"
            + "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000"
            + "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0030\u0031\u0032\u0033\u0034\u0035\u0036\u0037\u0038\u0039\u0041"
            + "\u0042\u0043\u0044\u0045\u0046\u0047\u0048\u0049\u004A\u004B\u004C\u004D\u004E\u004F\u0050\u0051\u0052\u0053\u0054\u0055\u0056\u0057\u0058\u0059\u005A\u0061\u0062\u0063\u0064\u0065"
            + "\u0066\u0067\u0068\u0069\u006A\u006B\u006C\u006D\u006E\u006F\u0070\u0071\u0072\u0073\u0074\u0075\u0076\u0077\u0078\u0079\u007A\u007A\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000"
            + "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000"
            + "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000"
            + "\u0000\u0000\u0000\u0000\u0024\u00A1\u00BF\u0021\u003F\u002C\u002E\u0000\u0000\u002F\u2018\u0027\u201C\u201D\u0000\u0000\u0000\u0000\u0000\u002B\u002D\u002A\u0000\u0000\u0023\u003D"
            + "\u0026\u0000\u003A\u003B\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0025\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0020\u0000"
            + "\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u0000\u00B0\u005F\u0000\u0000\u0000";

    private static String decodeGen4Title(byte[] bytes){
        if(bytes.length!=856)return "";
        final int offset=0x104, limit=0x104+0x48;
        // Some archived PCDs (including the English Ranger Manaphy Egg)
        // store a literal UTF-16LE title instead of DS character indices.
        StringBuilder raw=new StringBuilder();
        boolean plain=true, hasAsciiSpace=false;
        for(int i=offset;i<limit;i+=2){
            int value=(bytes[i]&255)|((bytes[i+1]&255)<<8);
            if(value==0||value==0xffff)break;
            if(value<' '||value>0x7e)plain=false;
            if(value==0x20)hasAsciiSpace=true;
            raw.append((char)value);
        }
        if(plain&&hasAsciiSpace&&raw.length()>=4)return raw.toString().trim();
        StringBuilder title=new StringBuilder();
        int unknown=0;
        for(int i=offset;i<limit;i+=2){
            int glyph=(bytes[i]&255)|((bytes[i+1]&255)<<8);
            if(glyph==0||glyph==0xffff)break;
            char c=(glyph<GEN4_GLYPHS.length())?GEN4_GLYPHS.charAt(glyph):0;
            if(c==0){unknown++;continue;}
            title.append(c);
        }
        // Korean card glyphs are above the international table. Until a Korean
        // decoder is available, keep the existing catalog name rather than garble it.
        return unknown>0||title.length()==0?"":title.toString().trim();
    }

    private static String decodeGen5Title(byte[] bytes){
        if(bytes.length!=204&&bytes.length!=720)return "";
        // PGF at the start of PGF and WC5Full; title is at 0x60, 37 UTF-16 units.
        StringBuilder title=new StringBuilder();
        for(int i=0x60;i<0x60+74;i+=2){
            int cp=(bytes[i]&255)|((bytes[i+1]&255)<<8);
            if(cp==0||cp==0xffff||cp==0xfffe)break;
            if(Character.isISOControl((char)cp))return "";
            title.append((char)cp);
        }
        return title.toString().trim();
    }

    private static String wonderCardDisplayName(Card card){
        String embedded=card.bytes.length==856?decodeGen4Title(card.bytes):decodeGen5Title(card.bytes);
        // Do not alter any card bytes or its catalog name: only the spinner label.
        String label=embedded.isEmpty()?card.name:embedded;
        label=label.replaceFirst("(?i)^\\s*mystery\\s+gift\\s*[:：]\\s*", "");
        return label.isEmpty()?card.name:label;
    }

    private void addCard(Card c){shownCards.add(c);cardAdapter.add(wonderCardDisplayName(c));}
    private boolean permissionsOk(){if(Build.VERSION.SDK_INT>=31)return checkSelfPermission(Manifest.permission.BLUETOOTH_SCAN)==PackageManager.PERMISSION_GRANTED&&checkSelfPermission(Manifest.permission.BLUETOOTH_CONNECT)==PackageManager.PERMISSION_GRANTED;
        return checkSelfPermission(Manifest.permission.ACCESS_FINE_LOCATION)==PackageManager.PERMISSION_GRANTED;}
    private void requestPermissionsIfNeeded(){if(!permissionsOk())requestPermissions(Build.VERSION.SDK_INT>=31?new String[]{Manifest.permission.BLUETOOTH_SCAN,Manifest.permission.BLUETOOTH_CONNECT}:new String[]{Manifest.permission.ACCESS_FINE_LOCATION},PERM);}
    @Override public void onRequestPermissionsResult(int requestCode,String[] permissions,int[] grants){super.onRequestPermissionsResult(requestCode,permissions,grants);if(requestCode==PERM&&!permissionsOk())log("Bluetooth scan permission required");}
    private final ScanCallback callback=new ScanCallback(){
        @Override public void onScanResult(int type,ScanResult result){String name=null;
            if(result.getScanRecord()!=null)name=result.getScanRecord().getDeviceName();
            if(!DEVICE_NAME.equals(name))return;
            BluetoothDevice dev=result.getDevice();
            handler.post(()->{
                for (BluetoothDevice x : devices) if (x.getAddress().equals(dev.getAddress())) return;
                devices.add(dev);deviceAdapter.add(DEVICE_NAME+" — "+dev.getAddress());
            });
        }
        @Override public void onScanFailed(int error){log("BLE scan error "+error);}
    };
    private void stopScan(){if(scanner!=null&&scanning){try{scanner.stopScan(callback);}catch(SecurityException ignored){}scanning=false;}}
    private void startScan(){
        if(!permissionsOk()){requestPermissionsIfNeeded();return;}
        stopScan();devices.clear();deviceAdapter.clear();
        BluetoothManager mgr=getSystemService(BluetoothManager.class);BluetoothAdapter adapter=mgr.getAdapter();
        if(adapter==null||!adapter.isEnabled()){log("Enable Bluetooth on your phone first");return;}
        scanner=adapter.getBluetoothLeScanner();
        if(scanner==null){log("BLE scanner unavailable");return;}
        try{scanner.startScan(callback);scanning=true;log("Scanning... tap the ESP32 when it appears");
            handler.postDelayed(()->{if(scanning){stopScan();log("Scan complete. Tap a listed ESP32 to connect.");}},12000);
        }catch(SecurityException e){log("Bluetooth permission missing");}
    }
    private void connect(BluetoothDevice device){
        stopScan();disconnect();
        log("Connecting to "+DEVICE_NAME+"...");
        try{gatt=device.connectGatt(this,false,gattCb,BluetoothDevice.TRANSPORT_LE);}catch(SecurityException e){log("Cannot connect: Bluetooth permission missing");}
    }
    private void disconnect(){stopScan();writes.clear();writing=false;ready=false;connected=false;mtuReady=false;
        if(gatt!=null){try{gatt.disconnect();gatt.close();}catch(SecurityException ignored){}gatt=null;}
        dataChar=null;ctrlChar=null;log("Disconnected");
    }
    private final BluetoothGattCallback gattCb=new BluetoothGattCallback(){
        @Override public void onConnectionStateChange(BluetoothGatt g,int statusCode,int newState){
            if(g!=gatt)return;
            if(newState==BluetoothProfile.STATE_CONNECTED&&statusCode==BluetoothGatt.GATT_SUCCESS){connected=true;log("Connected. Discovering services...");try{g.discoverServices();}catch(SecurityException e){log("Discovery permission denied");}}
            else{connected=false;ready=false;writes.clear();writing=false;log("Disconnected (status "+statusCode+"). No automatic reconnect.");}
        }
        @Override public void onServicesDiscovered(BluetoothGatt g,int statusCode){if(g!=gatt)return;
            if(statusCode!=BluetoothGatt.GATT_SUCCESS){log("GATT discovery failed");return;}
            BluetoothGattService service=g.getService(SERVICE);
            if(service==null){log("Sender service not found. Flash updated BLE firmware.");return;}
            dataChar=service.getCharacteristic(DATA);ctrlChar=service.getCharacteristic(CTRL);
            if(dataChar==null||ctrlChar==null){log("Sender write characteristics missing");return;}
            try{g.requestMtu(185);}catch(SecurityException e){log("Unable to negotiate MTU");}
        }
        @Override public void onMtuChanged(BluetoothGatt g,int result,int statusCode){if(g!=gatt)return;
            mtu=result;mtuReady=true;ready=statusCode==BluetoothGatt.GATT_SUCCESS&&result>=116;
            log(ready?"Ready — manually select a gift and press Send":"BLE MTU too small ("+result+"). Need MTU at least 116.");
        }
        @Override public void onCharacteristicWrite(BluetoothGatt g,BluetoothGattCharacteristic c,int statusCode){if(g!=gatt)return;
            if(statusCode!=BluetoothGatt.GATT_SUCCESS){writes.clear();writing=false;log("BLE write failed: "+statusCode+". Try sending again.");return;}
            handler.post(()->nextWrite());
        }
    };
    private void enqueue(BluetoothGattCharacteristic c,byte[] packet){writes.add(new WriteOp(c,packet));}
    private void nextWrite(){
        if(gatt==null||!connected){writes.clear();writing=false;return;}
        WriteOp op=writes.poll();if(op==null){writing=false;log(stopCommandPending?"Stop command acknowledged by ESP32-S3. Wireless distribution stopped.":"Gift uploaded. ESP32-S3 is now distributing until you stop it or disconnect.");stopCommandPending=false;return;}
        try{
            boolean ok;
            if(Build.VERSION.SDK_INT>=33)ok=gatt.writeCharacteristic(op.characteristic,op.value,BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT)==0;
            else {op.characteristic.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_DEFAULT);op.characteristic.setValue(op.value);ok=gatt.writeCharacteristic(op.characteristic);}
            if(!ok){writes.clear();writing=false;log("Could not queue BLE write");}
        }catch(SecurityException e){writes.clear();writing=false;log("Bluetooth permission denied");}
    }
    private void sendGift(){
        if(!ready||!connected){log("Connect to your ESP32 first (scan and tap device)");return;}
        if(writing){log("Already uploading. Please wait.");return;}
        int selected=cardSpinner.getSelectedItemPosition();if(selected<0||selected>=shownCards.size()){log("No compatible card in this game/language");return;}
        Card c=shownCards.get(selected);
        try{
            int gi=gameSpinner.getSelectedItemPosition();
            int generation=gi<5?4:5;
            byte[][] frags=generation==4?Gen4.prepare(c.name,c.bytes)
                :Gen5.prepare(c.name,c.bytes,Gen5.LANG_ID[langSpinner.getSelectedItemPosition()],
                        importGame.containsKey(c.path)?Gen5.GAME_ID[gi]:-1);
            stopCommandPending=false;writes.clear();enqueue(ctrlChar,new byte[]{2});
            enqueue(ctrlChar,new byte[]{3,(byte)generation,(byte)langSpinner.getSelectedItemPosition()});
            for(int i=0;i<frags.length;i++){byte[] pkt=new byte[113];pkt[0]=(byte)i;System.arraycopy(frags[i],0,pkt,1,112);enqueue(dataChar,pkt);}
            enqueue(ctrlChar,new byte[]{1});writing=true;
            log("Uploading "+frags.length+" Gen "+generation+" fragments for "+c.name+"...");nextWrite();
        }catch(Exception e){log("Card rejected: "+e.getMessage());}
    }
    private void stopGift(){
        writes.clear();writing=false;
        if(!connected||ctrlChar==null){log("Not connected");return;}
        stopCommandPending=true;enqueue(ctrlChar,new byte[]{0});writing=true;log("Requesting ESP32-S3 to stop wireless distribution...");nextWrite();
    }
    @Override protected void onActivityResult(int req,int result,Intent data){super.onActivityResult(req,result,data);
        if(req!=FILE_PICK||result!=RESULT_OK||data==null||data.getData()==null)return;
        Uri uri=data.getData();String name="Imported card";
        try(Cursor cursor=getContentResolver().query(uri,null,null,null,null)){if(cursor!=null&&cursor.moveToFirst()){int i=cursor.getColumnIndex(OpenableColumns.DISPLAY_NAME);if(i>=0)name=cursor.getString(i);}}
        try(InputStream in=getContentResolver().openInputStream(uri)){
            byte[] bytes=readAll(in);
            int gi=gameSpinner.getSelectedItemPosition();
            String suffix=name.toLowerCase(java.util.Locale.ROOT);
            boolean gen4=gi<5;
            if(gen4 ? !(bytes.length==856&&(suffix.endsWith(".wc4")||suffix.endsWith(".pcd")))
                    : !((bytes.length==204&&suffix.endsWith(".pgf"))||(bytes.length==720&&suffix.endsWith(".wc5full")))){
                log("Unsupported format for "+Gen5.GAMES[gi]+". Gen IV: .wc4/.pcd (856 bytes); Gen V: .pgf (204) or .wc5full (720).");return;
            }
            // Save into app-private storage, preserving the selected game's identity.
            String filename="import_"+System.currentTimeMillis()+"_"+name.replaceAll("[^a-zA-Z0-9._-]","_");
            try(java.io.FileOutputStream out=openFileOutput(filename,MODE_PRIVATE)){out.write(bytes);}
            String lang=Gen5.LANG[langSpinner.getSelectedItemPosition()];
            getPreferences(MODE_PRIVATE).edit().putString("card:"+filename,lang+"|"+gi+"|"+name).apply();
            importedCards.add(new Card(lang,name,filename,bytes));importGame.put(filename,gi);updateCards();
            log("Imported and saved "+name+" for "+Gen5.GAMES[gi]+" / "+lang);
        }catch(Exception e){log("Import failed: "+e.getMessage());}
    }
    private void restoreImports(){
        for(Map.Entry<String,?> e:getPreferences(MODE_PRIVATE).getAll().entrySet()){
            if(!e.getKey().startsWith("card:")||!(e.getValue() instanceof String))continue;
            String[] parts=((String)e.getValue()).split("\\|",3);if(parts.length!=3)continue;
            try {int gi=Integer.parseInt(parts[1]);if(gi<0||gi>=Gen5.GAMES.length)continue;
                String filename=e.getKey().substring(5);
                byte[] b;try(InputStream in=openFileInput(filename)){b=readAll(in);}
                importedCards.add(new Card(parts[0],parts[2],filename,b));importGame.put(filename,gi);
            }catch(Exception ignored){}
        }
    }
    @Override protected void onDestroy(){disconnect();super.onDestroy();}
}
