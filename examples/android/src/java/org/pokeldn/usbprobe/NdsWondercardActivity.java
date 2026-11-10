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
import android.graphics.Canvas;
import android.graphics.Paint;
import android.graphics.RectF;
import android.graphics.drawable.Drawable;
import android.widget.FrameLayout;
import android.widget.HorizontalScrollView;
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

    private static final String[] LANGUAGE_LABELS={"English","Japanese","French","German","Italian","Spanish","Korean"};
    private static final String[] LANGUAGE_SHORT={"English","日本語","Français","Deutsch","Italiano","Español","한국어"};
    private static final String[] GAME_INITIALS={"D","P","Pt","HG","SS","B","W","B2","W2"};
    private static final int[] GAME_COLORS={0xFF287EDF,0xFFD14E96,0xFF757985,0xFFDDA525,0xFFAEB5C3,0xFF202127,0xFFF6F6FA,0xFF151518,0xFFF5F5F8};
    private LinearLayout languageTabRow, gameRows, connectionTools;
    private TextView connectionBadge, connectionIndicator, selectedCardText, cardChevron;
    private View connectionDot;
    private TextView[] gameChoices=new TextView[9];
    private HorizontalScrollView languageStrip;
    private boolean distributing=false;

    private TextView status, cardCount;
    private volatile boolean libraryLoading=true;
    private boolean dark;
    private int bgColor, panelColor, textColor, mutedColor, accentColor, highlightColor, outlineColor, errorColor;
    private ArrayAdapter<String> deviceAdapter,cardAdapter;
    private final ArrayList<Card> importedCards=new ArrayList<>();
    private final Map<String,Integer> importGame=new HashMap<>();
    static class Card {final String lang,name,path;final byte[] bytes;Card(String l,String n,String p,byte[] b){lang=l;name=n;path=p;bytes=b;}}
    static class WriteOp {final BluetoothGattCharacteristic characteristic;final byte[] value;WriteOp(BluetoothGattCharacteristic c,byte[] v){characteristic=c;value=v;}}
    private void log(String s){handler.post(()->setStatusVisuals(s));}

    private int dp(int value){return (int)(getResources().getDisplayMetrics().density*value+0.5f);}
    private static int color(String hex){return Color.parseColor(hex);}
    private static int blend(int a,int b,float fraction){
        float n=1-fraction;
        return Color.rgb((int)(Color.red(a)*n+Color.red(b)*fraction),(int)(Color.green(a)*n+Color.green(b)*fraction),(int)(Color.blue(a)*n+Color.blue(b)*fraction));
    }
    private GradientDrawable surface(int fill,int stroke,int radius){
        GradientDrawable d=new GradientDrawable();d.setColor(fill);d.setCornerRadius(dp(radius));
        if(stroke!=Color.TRANSPARENT)d.setStroke(dp(1),stroke);return d;
    }
    private Drawable gradient(int first,int second,int stroke,int radius){
        GradientDrawable d=new GradientDrawable(GradientDrawable.Orientation.TL_BR,new int[]{first,second});
        d.setCornerRadius(dp(radius));if(stroke!=Color.TRANSPARENT)d.setStroke(dp(1),stroke);return d;
    }
    private Drawable touchBackground(int fill,int stroke,int radius){
        android.graphics.drawable.StateListDrawable states=new android.graphics.drawable.StateListDrawable();
        states.addState(new int[]{android.R.attr.state_pressed},surface(blend(fill,highlightColor,0.27f),highlightColor,radius));
        states.addState(new int[]{},surface(fill,stroke,radius));
        return new RippleDrawable(ColorStateList.valueOf(0x55B77CFF),states,null);
    }
    private void clickResponse(View v){
        v.setOnTouchListener((w,e)->{
            int a=e.getActionMasked();
            if(a==MotionEvent.ACTION_DOWN)w.animate().scaleX(0.988f).scaleY(0.975f).setDuration(65).start();
            if(a==MotionEvent.ACTION_UP||a==MotionEvent.ACTION_CANCEL)w.animate().scaleX(1f).scaleY(1f).setDuration(115).start();
            return false;
        });
    }
    private void palette(){
        dark=(getResources().getConfiguration().uiMode & Configuration.UI_MODE_NIGHT_MASK)==Configuration.UI_MODE_NIGHT_YES;
        bgColor=color(dark?"#111020":"#F5F3FC");
        panelColor=color(dark?"#201F33":"#FFFFFF");
        textColor=color(dark?"#FAF8FF":"#201B32");
        mutedColor=color(dark?"#B8B5CF":"#5B5970");
        accentColor=color(dark?"#A66AFF":"#7336D9");
        highlightColor=color(dark?"#8847E7":"#9058E4");
        outlineColor=color(dark?"#4A476A":"#D6D0E8");
        errorColor=color(dark?"#FF777F":"#BC293D");
    }
    private TextView label(String name,int size,boolean bold){
        TextView v=new TextView(this);v.setText(name);v.setTextColor(textColor);v.setTextSize(size);
        if(bold)v.setTypeface(Typeface.DEFAULT,Typeface.BOLD);
        v.setIncludeFontPadding(true);return v;
    }
    private LinearLayout vertical(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.VERTICAL);return l;}
    private LinearLayout horizontal(){LinearLayout l=new LinearLayout(this);l.setOrientation(LinearLayout.HORIZONTAL);l.setGravity(Gravity.CENTER_VERTICAL);return l;}
    private LinearLayout.LayoutParams dims(int width,int height){return new LinearLayout.LayoutParams(width<0?width:dp(width),height<0?height:dp(height));}
    private void marginBottom(LinearLayout parent,View child,int bottom){LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(-1,-2);p.bottomMargin=dp(bottom);parent.addView(child,p);}
    private LinearLayout panel(LinearLayout root){
        LinearLayout v=vertical();v.setPadding(dp(15),dp(16),dp(15),dp(16));
        v.setBackground(gradient(panelColor,blend(panelColor,bgColor,.28f),outlineColor,18));
        LinearLayout.LayoutParams lp=new LinearLayout.LayoutParams(-1,-2);lp.bottomMargin=dp(14);root.addView(v,lp);return v;
    }
    private TextView smallHeader(String title){TextView v=label(title,17,true);v.setPadding(0,0,0,dp(12));return v;}
    private TextView interactiveLabel(String text,Runnable action,boolean primary){
        TextView b=label(text,15,true);b.setGravity(Gravity.CENTER);b.setPadding(dp(12),dp(12),dp(12),dp(12));
        b.setTextColor(primary?Color.WHITE:textColor);
        b.setBackground(primary?new RippleDrawable(ColorStateList.valueOf(0x88D2B3FF),
                gradient(color(dark?"#AF74FF":"#995DE9"),color(dark?"#6F34CF":"#7038D0"),accentColor,17),null):
                touchBackground(blend(panelColor,bgColor,.22f),outlineColor,17));
        b.setClickable(true);b.setFocusable(true);clickResponse(b);
        b.setOnClickListener(v->{v.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);action.run();});return b;
    }
    // Keep compatible button API for the BLE and import code, while using the new visual style.
    private Button button(LinearLayout root,String name,Runnable action){
        Button b=new Button(this);b.setText(name);b.setAllCaps(false);b.setTextColor(textColor);b.setTextSize(14);
        b.setBackground(touchBackground(panelColor,outlineColor,12));
        LinearLayout.LayoutParams p=dims(-1,46);p.bottomMargin=dp(7);root.addView(b,p);
        clickResponse(b);b.setOnClickListener(v->{v.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);action.run();});return b;
    }
    private Spinner hiddenSpinner(String[] values){
        Spinner s=new Spinner(this);
        ArrayAdapter<String> a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_item,values);
        s.setAdapter(a);return s;
    }
    private View circle(final int fill,int diameter){
        View v=new View(this);v.setBackground(surface(fill,Color.TRANSPARENT,diameter/2));
        v.setLayoutParams(dims(diameter,diameter));return v;
    }
    private View pokeball(int size){
        return new View(this){
            final Paint paint=new Paint(3);
            @Override protected void onDraw(Canvas canvas){
                super.onDraw(canvas);float w=getWidth(),h=getHeight(),cx=w/2,cy=h/2,r=Math.min(w,h)*.46f;
                paint.setStyle(Paint.Style.FILL);paint.setColor(0xFFF45462);canvas.drawCircle(cx,cy,r,paint);
                RectF bottom=new RectF(cx-r,cy-r,cx+r,cy+r);
                canvas.save();canvas.clipRect(cx-r,cy,cx+r,cy+r);
                paint.setColor(0xFFEAF0FF);canvas.drawCircle(cx,cy,r,paint);canvas.restore();
                paint.setColor(0xFF222342);canvas.drawRect(cx-r,cy-dp(3),cx+r,cy+dp(3),paint);
                paint.setColor(0xFF222342);canvas.drawCircle(cx,cy,r*.35f,paint);
                paint.setColor(0xFFECF1FF);canvas.drawCircle(cx,cy,r*.23f,paint);
            }
        };
    }
    private void setStatusVisuals(String message){
        boolean linked=connected&&ready;
        if(connectionBadge!=null){connectionBadge.setText(linked?"◉ Connected":"♧ Connect");
            connectionBadge.setTextColor(linked?0xFF37EF84:accentColor);
            connectionBadge.setBackground(touchBackground(linked?0xFF103326:panelColor,
                    linked?0xFF24D875:outlineColor,18));}
        if(connectionIndicator!=null){connectionIndicator.setText(linked?(distributing?"Distributing":"Ready"):(connected?"Connecting":"Not connected"));}
        if(connectionDot!=null)connectionDot.setBackground(surface(linked?0xFF39E979:0xFFF45259,Color.TRANSPARENT,7));
        if(status!=null){status.setText(message);status.setTextColor(mutedColor);}
    }
    private LinearLayout createConnectionTools(){
        LinearLayout tools=vertical();tools.setPadding(dp(12),dp(13),dp(12),dp(8));
        tools.setBackground(surface(panelColor,outlineColor,14));
        TextView prompt=label("ESP32-S3 Bluetooth connection",14,true);marginBottom(tools,prompt,8);
        button(tools,"Find my ESP32-S3",()->startScan());
        button(tools,"Disconnect",()->disconnect());
        ListView deviceList=new ListView(this);deviceList.setDividerHeight(dp(1));
        deviceList.setDivider(new android.graphics.drawable.ColorDrawable(outlineColor));
        tools.addView(deviceList,dims(-1,105));
        deviceAdapter=new ArrayAdapter<String>(this,android.R.layout.simple_list_item_1,new ArrayList<>()){
            @Override public View getView(int pos,View convert,android.view.ViewGroup parent){
                TextView v=(TextView)super.getView(pos,convert,parent);v.setTextColor(textColor);v.setTextSize(12);return v;
            }
        };deviceList.setAdapter(deviceAdapter);
        deviceList.setOnItemClickListener((parent,view,pos,id)->{if(pos<devices.size())connect(devices.get(pos));});
        return tools;
    }
    private void addGameRows(LinearLayout parent){
        gameRows=vertical();
        for(int i=0;i<Gen5.GAMES.length;i++){
            final int game=i;
            LinearLayout line=horizontal();line.setPadding(dp(9),dp(7),dp(9),dp(7));
            TextView tile=label(GAME_INITIALS[i],14,true);tile.setGravity(Gravity.CENTER);
            tile.setTextColor(i==6||i==8?0xFF12121C:Color.WHITE);
            tile.setBackground(gradient(blend(GAME_COLORS[i],Color.WHITE,.17f),GAME_COLORS[i],
                    i==6||i==8?0xFFBFC0C9:Color.TRANSPARENT,9));
            line.addView(tile,dims(45,37));
            TextView text=label("Pokémon "+Gen5.GAMES[i].replace("Heart Gold","HeartGold").replace("Soul Silver","SoulSilver"),15,false);
            LinearLayout.LayoutParams nameP=new LinearLayout.LayoutParams(0,-2,1);nameP.leftMargin=dp(12);
            line.addView(text,nameP);
            TextView radio=label("○",24,false);radio.setGravity(Gravity.CENTER);
            line.addView(radio,dims(27,42));gameChoices[i]=radio;
            line.setBackground(touchBackground(Color.TRANSPARENT,Color.TRANSPARENT,13));
            line.setClickable(true);line.setFocusable(true);clickResponse(line);
            line.setOnClickListener(v->{line.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);gameSpinner.setSelection(game);refreshGameRows();updateCards();});
            gameRows.addView(line,dims(-1,55));
            if(i<Gen5.GAMES.length-1){View divider=new View(this);divider.setBackgroundColor(outlineColor);
                LinearLayout.LayoutParams d=dims(-1,1);d.leftMargin=dp(9);d.rightMargin=dp(9);gameRows.addView(divider,d);}
        }
        parent.addView(gameRows,dims(-1,-2));refreshGameRows();
    }
    private void refreshGameRows(){
        if(gameRows==null||gameSpinner==null)return;
        int sel=gameSpinner.getSelectedItemPosition();
        for(int i=0;i<Gen5.GAMES.length;i++){
            LinearLayout row=(LinearLayout)gameRows.getChildAt(i*2);boolean active=i==sel;
            row.setBackground(active?gradient(dark?0xFF573272:0xFFF0DFFF,
                    dark?0xFF342351:0xFFE8D7FF,accentColor,13):touchBackground(Color.TRANSPARENT,Color.TRANSPARENT,13));
            gameChoices[i].setText(active?"✓":"○");gameChoices[i].setTextSize(active?22:24);
            gameChoices[i].setTextColor(active?accentColor:mutedColor);
            row.setSelected(active);
        }
    }
    private void addLanguageTabs(LinearLayout parent){
        TextView hint=label("LANGUAGE  ·  swipe to see all seven",11,false);hint.setTextColor(mutedColor);
        marginBottom(parent,hint,5);
        languageStrip=new HorizontalScrollView(this);languageStrip.setHorizontalScrollBarEnabled(false);
        languageStrip.setFillViewport(false);languageStrip.setHorizontalFadingEdgeEnabled(true);
        languageTabRow=horizontal();languageTabRow.setPadding(dp(2),dp(3),dp(2),dp(3));
        for(int i=0;i<Gen5.LANG.length;i++){
            final int language=i;
            TextView tab=label(LANGUAGE_SHORT[i],12,false);tab.setGravity(Gravity.CENTER);
            tab.setSingleLine(true);tab.setPadding(dp(11),dp(10),dp(11),dp(10));
            tab.setClickable(true);tab.setFocusable(true);clickResponse(tab);
            tab.setOnClickListener(v->{tab.performHapticFeedback(android.view.HapticFeedbackConstants.VIRTUAL_KEY);
                langSpinner.setSelection(language);refreshLanguageTabs();updateCards();});
            LinearLayout.LayoutParams p=dims(-2,40);p.rightMargin=dp(2);languageTabRow.addView(tab,p);
        }
        languageStrip.addView(languageTabRow);
        LinearLayout.LayoutParams sp=dims(-1,48);sp.bottomMargin=dp(8);parent.addView(languageStrip,sp);
        refreshLanguageTabs();
    }
    private void refreshLanguageTabs(){
        if(langSpinner==null||languageTabRow==null)return;
        int selected=langSpinner.getSelectedItemPosition();
        for(int i=0;i<Gen5.LANG.length;i++){
            TextView t=(TextView)languageTabRow.getChildAt(i);boolean active=i==selected;
            t.setTextColor(active?Color.WHITE:textColor);
            t.setBackground(active?gradient(0xFFAF73FF,0xFF7434D2,accentColor,11):touchBackground(panelColor,outlineColor,11));
            t.setSelected(active);t.setContentDescription(LANGUAGE_LABELS[i]+(active?", selected":""));
        }
        if(selected>=0&&selected<languageTabRow.getChildCount()){
            View tab=languageTabRow.getChildAt(selected);
            languageStrip.post(()->languageStrip.smoothScrollTo(Math.max(0,tab.getLeft()-dp(75)),0));
        }
    }
    private void addCardPicker(LinearLayout panel){
        FrameLayout frame=new FrameLayout(this);
        frame.setBackground(touchBackground(dark?0xFF1B1B2D:0xFFF8F6FC,outlineColor,11));
        cardSpinner=new Spinner(this,Spinner.MODE_DROPDOWN);
        cardSpinner.setBackgroundColor(Color.TRANSPARENT);
        cardSpinner.setDropDownWidth(-1);
        cardAdapter=new ArrayAdapter<String>(this,android.R.layout.simple_spinner_item,new ArrayList<>()){
            @Override public View getView(int pos,View convert,android.view.ViewGroup parent){
                TextView t=(TextView)super.getView(pos,convert,parent);t.setTextColor(textColor);
                t.setTextSize(15);t.setSingleLine(true);t.setEllipsize(android.text.TextUtils.TruncateAt.END);
                t.setPadding(dp(14),0,dp(31),0);return t;
            }
            @Override public View getDropDownView(int pos,View convert,android.view.ViewGroup parent){
                TextView t=(TextView)super.getDropDownView(pos,convert,parent);t.setTextColor(textColor);
                t.setBackgroundColor(panelColor);t.setPadding(dp(15),dp(13),dp(15),dp(13));return t;
            }
        };
        cardAdapter.setDropDownViewResource(android.R.layout.simple_spinner_dropdown_item);
        cardSpinner.setAdapter(cardAdapter);frame.addView(cardSpinner,new FrameLayout.LayoutParams(-1,-1));
        // Exactly one chevron on the RIGHT. No native spinner background or arrow on the left.
        cardChevron=label("⌄",23,false);cardChevron.setTextColor(textColor);cardChevron.setGravity(Gravity.CENTER);
        FrameLayout.LayoutParams c=new FrameLayout.LayoutParams(dp(33),-1,Gravity.RIGHT|Gravity.CENTER_VERTICAL);
        frame.addView(cardChevron,c);cardChevron.setClickable(true);cardChevron.setOnClickListener(v->cardSpinner.performClick());
        LinearLayout.LayoutParams f=dims(-1,51);f.bottomMargin=dp(5);panel.addView(frame,f);
    }
    private void addStatusLegend(LinearLayout panel){
        panel.addView(smallHeader("ⓘ  ESP32-S3 LED Indicator"));
        String[] lines={"Red — No phone connected","Green — Phone connected (ready)","Blinking green — Distributing a Wonder Card"};
        int[] colors={0xFFF45259,0xFF4FE958,0xFF5DEA55};
        for(int i=0;i<lines.length;i++){
            LinearLayout line=horizontal();View led=circle(colors[i],13);line.addView(led,dims(13,13));
            TextView name=label(lines[i],12,false);LinearLayout.LayoutParams p=new LinearLayout.LayoutParams(0,-2,1);p.leftMargin=dp(12);
            line.addView(name,p);LinearLayout.LayoutParams lp=dims(-1,-2);lp.bottomMargin=dp(9);panel.addView(line,lp);
        }
    }
    private void addDistributionButton(LinearLayout parent,String text,boolean primary,Runnable action){
        TextView b=interactiveLabel(text,action,primary);
        LinearLayout.LayoutParams p=dims(-1,62);p.bottomMargin=dp(10);parent.addView(b,p);
    }
    private void addHero(LinearLayout root){
        boolean wide=getResources().getConfiguration().screenWidthDp>=600;
        LinearLayout hero=wide?horizontal():vertical();hero.setGravity(Gravity.CENTER_VERTICAL);
        ImageView image=new ImageView(this);image.setScaleType(ImageView.ScaleType.FIT_CENTER);
        image.setContentDescription("Original white Nintendo DS Phat console");
        try(InputStream in=getAssets().open("nds-phat.png")){image.setImageBitmap(BitmapFactory.decodeStream(in));}catch(Exception ignored){}
        if(wide){LinearLayout.LayoutParams ip=dims(245,224);ip.rightMargin=dp(22);hero.addView(image,ip);}
        else{LinearLayout.LayoutParams ip=dims(-1,178);ip.bottomMargin=dp(11);hero.addView(image,ip);}
        LinearLayout words=vertical();
        TextView title=label("Send Wonder Cards to your DS",wide?24:22,true);marginBottom(words,title,9);
        TextView desc=label("Send Wonder Cards to compatible Nintendo DS games using any Nintendo DS family console, including the original DS, DS Lite, DSi, and 3DS family.",wide?15:13,false);
        desc.setTextColor(mutedColor);marginBottom(words,desc,14);
        LinearLayout indicator=horizontal();indicator.setPadding(dp(13),dp(11),dp(13),dp(11));
        indicator.setBackground(surface(blend(panelColor,bgColor,.1f),outlineColor,13));
        connectionDot=circle(0xFFF45259,13);indicator.addView(connectionDot,dims(13,13));
        LinearLayout inner=vertical();LinearLayout.LayoutParams ii=new LinearLayout.LayoutParams(0,-2,1);ii.leftMargin=dp(12);indicator.addView(inner,ii);
        connectionIndicator=label("Not connected",16,true);inner.addView(connectionIndicator);
        status=label("Tap Connect above to find the ESP32-S3",12,false);status.setTextColor(mutedColor);inner.addView(status);
        words.addView(indicator,dims(-1,-2));
        if(wide)hero.addView(words,new LinearLayout.LayoutParams(0,-2,1));else hero.addView(words,dims(-1,-2));
        LinearLayout.LayoutParams hp=dims(-1,-2);hp.bottomMargin=dp(17);root.addView(hero,hp);
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
        super.onCreate(saved);palette();
        Window window=getWindow();window.setStatusBarColor(bgColor);window.setNavigationBarColor(bgColor);
        window.getDecorView().setSystemUiVisibility(dark?0:(View.SYSTEM_UI_FLAG_LIGHT_STATUS_BAR|View.SYSTEM_UI_FLAG_LIGHT_NAVIGATION_BAR));
        window.clearFlags(WindowManager.LayoutParams.FLAG_FULLSCREEN);
        ScrollView scroller=new ScrollView(this);scroller.setFillViewport(true);scroller.setVerticalScrollBarEnabled(false);
        scroller.setFitsSystemWindows(true);scroller.setBackgroundColor(bgColor);
        LinearLayout root=vertical();root.setPadding(dp(14),dp(12),dp(14),dp(26));scroller.addView(root);
        setContentView(scroller);
        root.setAlpha(0);root.animate().alpha(1).setDuration(160).start();

        // PokéLDN app header, status button and inline connection controls.
        LinearLayout top=horizontal();top.addView(pokeball(40),dims(40,40));
        LinearLayout appName=vertical();LinearLayout.LayoutParams a=new LinearLayout.LayoutParams(0,-2,1);a.leftMargin=dp(9);top.addView(appName,a);
        appName.addView(label("PokéLDN",22,true));TextView subtitle=label("Gift Sender",13,false);subtitle.setTextColor(mutedColor);appName.addView(subtitle);
        connectionBadge=label("♧ Connect",12,true);connectionBadge.setGravity(Gravity.CENTER);
        connectionBadge.setPadding(dp(12),dp(8),dp(12),dp(8));connectionBadge.setBackground(touchBackground(panelColor,outlineColor,17));
        connectionBadge.setClickable(true);clickResponse(connectionBadge);
        connectionBadge.setOnClickListener(v->{connectionTools.setVisibility(connectionTools.getVisibility()==View.VISIBLE?View.GONE:View.VISIBLE);});
        top.addView(connectionBadge,dims(-2,42));
        TextView settings=label("⚙",23,false);settings.setGravity(Gravity.CENTER);settings.setContentDescription("Bluetooth settings");
        settings.setBackground(touchBackground(panelColor,outlineColor,12));settings.setClickable(true);
        settings.setOnClickListener(v->connectionTools.setVisibility(connectionTools.getVisibility()==View.VISIBLE?View.GONE:View.VISIBLE));
        LinearLayout.LayoutParams st=dims(39,42);st.leftMargin=dp(7);top.addView(settings,st);
        LinearLayout.LayoutParams topP=dims(-1,-2);topP.bottomMargin=dp(12);root.addView(top,topP);
        connectionTools=createConnectionTools();connectionTools.setVisibility(View.GONE);
        LinearLayout.LayoutParams connP=dims(-1,-2);connP.bottomMargin=dp(12);root.addView(connectionTools,connP);
        View sep=new View(this);sep.setBackgroundColor(outlineColor);
        LinearLayout.LayoutParams spl=dims(-1,1);spl.bottomMargin=dp(15);root.addView(sep,spl);
        addHero(root);

        // Invisible state holders are retained for the existing Gen IV/V BLE and card logic.
        gameSpinner=hiddenSpinner(Gen5.GAMES);langSpinner=hiddenSpinner(Gen5.LANG);
        boolean wide=getResources().getConfiguration().screenWidthDp>=600;
        LinearLayout content=wide?horizontal():vertical();content.setGravity(Gravity.TOP);
        LinearLayout gameCard=vertical();gameCard.setPadding(dp(14),dp(14),dp(14),dp(14));
        gameCard.setBackground(gradient(panelColor,blend(panelColor,bgColor,.28f),outlineColor,19));
        gameCard.addView(smallHeader("▣  1. Select a game"));addGameRows(gameCard);
        LinearLayout actions=vertical();
        LinearLayout selector=panel(actions);
        selector.addView(smallHeader("♧  2. Select a Wonder Card"));
        addLanguageTabs(selector);
        addCardPicker(selector);
        cardCount=label("Loading Wonder Cards…",12,false);cardCount.setTextColor(mutedColor);cardCount.setGravity(Gravity.CENTER);selector.addView(cardCount);
        addDistributionButton(actions,"▶  Start Wonder Card Distribution",true,()->sendGift());
        addDistributionButton(actions,"■  Stop Wonder Card Distribution",false,()->stopGift());
        LinearLayout legend=panel(actions);addStatusLegend(legend);
        TextView imported=interactiveLabel("＋  Import Wonder Card",()->{
            Intent intent=new Intent(Intent.ACTION_OPEN_DOCUMENT);intent.setType("*/*");
            intent.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(intent,FILE_PICK);
        },false);actions.addView(imported,dims(-1,49));
        if(wide){
            LinearLayout.LayoutParams left=new LinearLayout.LayoutParams(0,-2,1);left.rightMargin=dp(12);content.addView(gameCard,left);
            content.addView(actions,new LinearLayout.LayoutParams(0,-2,1));
        }else{
            LinearLayout.LayoutParams left=dims(-1,-2);left.bottomMargin=dp(14);content.addView(gameCard,left);
            content.addView(actions,dims(-1,-2));
        }
        root.addView(content,dims(-1,-2));

        gameSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            public void onNothingSelected(AdapterView<?> p){}
            public void onItemSelected(AdapterView<?> p,View v,int pos,long id){refreshGameRows();updateCards();}
        });
        langSpinner.setOnItemSelectedListener(new AdapterView.OnItemSelectedListener(){
            public void onNothingSelected(AdapterView<?> p){}
            public void onItemSelected(AdapterView<?> p,View v,int pos,long id){refreshLanguageTabs();updateCards();}
        });
        restoreImports();
        int initial=getIntent().getIntExtra("game_index",0);
        if(initial>=0&&initial<Gen5.GAMES.length)gameSpinner.setSelection(initial);
        refreshGameRows();refreshLanguageTabs();updateCards();setStatusVisuals("Tap Connect above to find the ESP32-S3");
        requestPermissionsIfNeeded();loadBundledCards();
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
            shownCards.size()+" Wonder Cards ("+LANGUAGE_LABELS[li]+")");
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
            if(!DEVICE_NAME.equals(name)&&!BleStream.NAME.equals(name))return;
            BluetoothDevice dev=result.getDevice();
            handler.post(()->{
                for (BluetoothDevice x : devices) if (x.getAddress().equals(dev.getAddress())) return;
                devices.add(dev);deviceAdapter.add("Wonder Card radio — "+dev.getAddress());
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
        dataChar=null;ctrlChar=null;distributing=false;log("Disconnected");
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
        WriteOp op=writes.poll();if(op==null){writing=false;distributing=!stopCommandPending;log(stopCommandPending?"Stop command acknowledged by ESP32-S3. Wireless distribution stopped.":"Gift uploaded. ESP32-S3 is now distributing until you stop it or disconnect.");stopCommandPending=false;return;}
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
            stopCommandPending=false;distributing=false;writes.clear();enqueue(ctrlChar,new byte[]{2});
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
    @Override protected void onDestroy(){disconnect();Bridge.releaseNdsBluetooth();super.onDestroy();}
}
