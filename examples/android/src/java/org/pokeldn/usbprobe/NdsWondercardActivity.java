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
import android.os.Handler;
import android.os.Looper;
import android.provider.OpenableColumns;
import android.database.Cursor;
import android.view.View;
import android.widget.ArrayAdapter;
import android.widget.Button;
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
    private int mtu=23;
    private Spinner langSpinner,gameSpinner,cardSpinner;
    private TextView status;
    private ArrayAdapter<String> deviceAdapter,cardAdapter;
    private final ArrayList<Card> importedCards=new ArrayList<>();
    private final Map<String,Integer> importGame=new HashMap<>();
    static class Card {final String lang,name,path;final byte[] bytes;Card(String l,String n,String p,byte[] b){lang=l;name=n;path=p;bytes=b;}}
    static class WriteOp {final BluetoothGattCharacteristic characteristic;final byte[] value;WriteOp(BluetoothGattCharacteristic c,byte[] v){characteristic=c;value=v;}}
    private void log(String s){handler.post(()->status.setText(s));}

    @Override public void onCreate(Bundle saved){
        super.onCreate(saved);
        LinearLayout root=new LinearLayout(this);root.setOrientation(LinearLayout.VERTICAL);root.setPadding(22,22,22,22);
        ScrollView scroll=new ScrollView(this);scroll.addView(root);setContentView(scroll);
        TextView heading=new TextView(this);heading.setText("Gen IV/V Wondercard Sender");heading.setTextSize(22);root.addView(heading);
        TextView note=new TextView(this);note.setText("Gen IV/V controller. Scan, tap your ESP32, choose a card, then Send. Wi-Fi stays off until Send.");root.addView(note);
        status=new TextView(this);status.setPadding(0,16,0,16);root.addView(status);log("Not connected");
        Button scan=button(root,"Scan for ESP32 (manual)",()->startScan());
        Button disconnect=button(root,"Disconnect",()->disconnect());
        ListView deviceList=new ListView(this);deviceList.setMinimumHeight(145);root.addView(deviceList,new LinearLayout.LayoutParams(-1,170));
        deviceAdapter=new ArrayAdapter<>(this,android.R.layout.simple_list_item_1,new ArrayList<>());deviceList.setAdapter(deviceAdapter);
        deviceList.setOnItemClickListener((parent,view,pos,id)->{if(pos<devices.size())connect(devices.get(pos));});
        langSpinner=spinner(root,Gen5.LANG);gameSpinner=spinner(root,Gen5.GAMES);
        cardSpinner=new Spinner(this);root.addView(cardSpinner);
        cardAdapter=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,new ArrayList<>());cardSpinner.setAdapter(cardAdapter);
        langSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> p){}public void onItemSelected(android.widget.AdapterView<?> p,View v,int pos,long id){updateCards();}});
        gameSpinner.setOnItemSelectedListener(new android.widget.AdapterView.OnItemSelectedListener(){public void onNothingSelected(android.widget.AdapterView<?> p){}public void onItemSelected(android.widget.AdapterView<?> p,View v,int pos,long id){updateCards();}});
        button(root,"Import Wonder Card for selected game",()->{
            Intent i=new Intent(Intent.ACTION_OPEN_DOCUMENT);i.setType("*/*");i.addCategory(Intent.CATEGORY_OPENABLE);startActivityForResult(i,FILE_PICK);
        });
        button(root,"Send selected gift",()->sendGift());
        button(root,"STOP sending",()->stopGift());
        TextView footer=new TextView(this);footer.setPadding(0,20,0,0);
        footer.setText("Gen IV and V BLE transmission (experimental). No automatic connection. Bluetooth is unpaired: anyone nearby with compatible software could control this prototype.");root.addView(footer);
        try(InputStream in=getAssets().open("catalog.tsv")){byte[] b=readAll(in);String txt=new String(b,StandardCharsets.UTF_8);
            for(String line:txt.split("\n")){String[] c=line.split("\t",3);if(c.length==3){
                byte[] content=readAsset(c[2]);allCards.add(new Card(c[0],c[1],c[2],content));
            }}
        }catch(Exception e){log("Could not read built-in cards: "+e.getMessage());}
        restoreImports();
        int initialGame = getIntent().getIntExtra("game_index", 0);
        if (initialGame >= 0 && initialGame < Gen5.GAMES.length) gameSpinner.setSelection(initialGame);
        updateCards();
        requestPermissionsIfNeeded();
    }
    private Button button(LinearLayout root,String name,Runnable action){Button b=new Button(this);b.setText(name);root.addView(b);b.setOnClickListener(v->action.run());return b;}
    private Spinner spinner(LinearLayout root,String[] choices){Spinner s=new Spinner(this);root.addView(s);ArrayAdapter<String> a=new ArrayAdapter<>(this,android.R.layout.simple_spinner_dropdown_item,choices);s.setAdapter(a);return s;}
    private byte[] readAsset(String name)throws Exception{try(InputStream in=getAssets().open(name)){return readAll(in);}}
    private static byte[] readAll(InputStream in)throws Exception{ByteArrayOutputStream o=new ByteArrayOutputStream();byte[] buf=new byte[4096];for(int n;(n=in.read(buf))!=-1;)o.write(buf,0,n);return o.toByteArray();}
    private void updateCards(){if(langSpinner==null||gameSpinner==null||cardAdapter==null)return;
        int li=langSpinner.getSelectedItemPosition(),gi=gameSpinner.getSelectedItemPosition();if(li<0||gi<0)return;
        String lang=Gen5.LANG[li];int bit=1<<Gen5.GAME_ID[gi];
        shownCards.clear();cardAdapter.clear();
        for(Card c:importedCards)if(c.lang.equals(lang) && importGame.getOrDefault(c.path,-1)==gi)addCard(c);
        for(Card c:allCards){if(c.lang.equals(lang) && compatible(c,gi,bit))addCard(c);}
        cardAdapter.notifyDataSetChanged();
    }
    private boolean compatible(Card c,int gi,int bit){
        try {return gi<5 ? c.bytes.length==856 && (Gen4.versionMask(c.bytes)&bit)!=0
                          : (c.bytes.length==204||c.bytes.length==720) && (Gen5.versionMask(c.name,c.bytes)&bit)!=0;}
        catch(Exception e){return false;}
    }
    private void addCard(Card c){shownCards.add(c);cardAdapter.add(c.name);}
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
        WriteOp op=writes.poll();if(op==null){writing=false;log("Upload/command sequence complete. Check DS for gift.");return;}
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
            writes.clear();enqueue(ctrlChar,new byte[]{2});
            enqueue(ctrlChar,new byte[]{3,(byte)generation,(byte)langSpinner.getSelectedItemPosition()});
            for(int i=0;i<frags.length;i++){byte[] pkt=new byte[113];pkt[0]=(byte)i;System.arraycopy(frags[i],0,pkt,1,112);enqueue(dataChar,pkt);}
            enqueue(ctrlChar,new byte[]{1});writing=true;
            log("Uploading "+frags.length+" Gen "+generation+" fragments for "+c.name+"...");nextWrite();
        }catch(Exception e){log("Card rejected: "+e.getMessage());}
    }
    private void stopGift(){
        writes.clear();writing=false;
        if(!connected||ctrlChar==null){log("Not connected");return;}
        enqueue(ctrlChar,new byte[]{0});writing=true;log("Stopping transmitter...");nextWrite();
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
