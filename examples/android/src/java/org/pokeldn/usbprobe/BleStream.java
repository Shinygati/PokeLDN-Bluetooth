package org.pokeldn.usbprobe;

import android.annotation.SuppressLint;
import android.bluetooth.*;
import android.bluetooth.le.*;
import android.content.Context;
import android.os.Build;
import android.os.Handler;
import android.os.Looper;
import android.util.Log;
import java.io.IOException;
import java.util.Arrays;
import java.util.UUID;
import java.util.concurrent.ArrayBlockingQueue;
import java.util.concurrent.CountDownLatch;
import java.util.concurrent.TimeUnit;

/** The radio board's host link over Bluetooth LE: the Bluetooth radio firmware's service
 *  (docs/hardware_esp32.md, Bluetooth), with UsbStream's interface so pokeldn.app.android serves both
 *  as one pyserial port. The host writes the COBS stream to ...0102 without response; the board
 *  notifies its own on ...0103. Framing, CRC and CREDIT are the cable's.
 *
 *  Android allows one GATT operation at a time: the writer thread waits for each write's callback
 *  before the next. A connection survives Python closing the port (Bridge keeps it), so the Board
 *  page's checks do not reconnect every time; the board's HELLO restarts its side of the stream. */
@SuppressLint("MissingPermission")   // Bridge.bleState() checks the runtime permissions before any open
public final class BleStream implements AutoCloseable {
    static final String NAME = "POKELDN-RADIO";
    static final UUID SERVICE = UUID.fromString("7a1e0101-5d2c-4c3e-9f4b-504f4b454c44");
    static final UUID RX = UUID.fromString("7a1e0102-5d2c-4c3e-9f4b-504f4b454c44");   // host writes
    static final UUID TX = UUID.fromString("7a1e0103-5d2c-4c3e-9f4b-504f4b454c44");   // board notifies
    static final UUID CCCD = UUID.fromString("00002902-0000-1000-8000-00805f9b34fb");
    private static final String TAG = "PokeLDN";
    private static final int WANTED_MTU = 247;

    private final Context context;
    private final BluetoothAdapter adapter;
    private final ArrayBlockingQueue<byte[]> incoming = new ArrayBlockingQueue<>(4096);
    private final ArrayBlockingQueue<byte[]> outgoing = new ArrayBlockingQueue<>(4096);
    private final Object writeDone = new Object();
    private final CountDownLatch ready = new CountDownLatch(1);
    private volatile BluetoothGatt gatt;
    private volatile BluetoothGattCharacteristic rx;
    private volatile int piece = 20;
    private volatile boolean closed, writing;
    private volatile IOException failure;
    private volatile String deviceName = "", address = "";
    private volatile int rssi;
    private byte[] remainder = new byte[0];
    private Thread writer;

    private BleStream(Context context, BluetoothAdapter adapter) {
        this.context = context;
        this.adapter = adapter;
    }

    /** Scans for a board advertising `name` (the firmware advertises only its name), connects and
     *  subscribes. Blocks up to `timeoutMs`. `name` empty: POKELDN-RADIO. */
    static BleStream connect(Context context, String name, long timeoutMs) throws IOException {
        BluetoothManager manager = (BluetoothManager)context.getSystemService(Context.BLUETOOTH_SERVICE);
        BluetoothAdapter adapter = manager == null ? null : manager.getAdapter();
        if (adapter == null) throw new IOException("This phone has no Bluetooth.");
        if (!adapter.isEnabled()) throw new IOException("Bluetooth is off. Turn it on, then try again.");
        BleStream stream = new BleStream(context, adapter);
        String wanted = name == null || name.isEmpty() ? NAME : name;
        long deadline = System.nanoTime() + timeoutMs * 1000000;
        BluetoothDevice device = stream.scan(wanted, timeoutMs);
        if (device == null)
            throw new IOException("No " + wanted + " found over Bluetooth: is the board running the "
                + "Bluetooth radio firmware and powered?");
        stream.open(device);
        try {
            long left = Math.max(1, (deadline - System.nanoTime()) / 1000000);
            if (!stream.ready.await(Math.max(left, 8000), TimeUnit.MILLISECONDS)) {
                stream.close();
                throw new IOException("The board did not finish connecting over Bluetooth.");
            }
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            stream.close();
            throw new IOException(error);
        }
        if (stream.failure != null) { IOException error = stream.failure; stream.close(); throw error; }
        return stream;
    }

    private BluetoothDevice scan(String wanted, long timeoutMs) throws IOException {
        BluetoothLeScanner scanner = adapter.getBluetoothLeScanner();
        if (scanner == null) throw new IOException("Bluetooth scanning is unavailable.");
        final BluetoothDevice[] found = new BluetoothDevice[1];
        final CountDownLatch done = new CountDownLatch(1);
        ScanCallback callback = new ScanCallback() {
            @Override public void onScanResult(int type, ScanResult result) {
                ScanRecord record = result.getScanRecord();
                String advertised = record == null ? null : record.getDeviceName();
                if (advertised == null) advertised = result.getDevice().getName();
                if (wanted.equals(advertised) && found[0] == null) {
                    found[0] = result.getDevice();
                    rssi = result.getRssi();
                    done.countDown();
                }
            }
            @Override public void onScanFailed(int code) {
                failure = new IOException("Bluetooth scan failed (" + code + ")");
                done.countDown();
            }
        };
        // No service filter: the board advertises its name alone (docs/hardware_esp32.md, Bluetooth).
        ScanSettings settings = new ScanSettings.Builder().setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY).build();
        scanner.startScan(null, settings, callback);
        try {
            done.await(timeoutMs, TimeUnit.MILLISECONDS);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
        } finally {
            try { scanner.stopScan(callback); } catch (RuntimeException ignored) { }
        }
        if (failure != null) throw failure;
        return found[0];
    }

    private void open(BluetoothDevice device) {
        deviceName = device.getName() == null ? NAME : device.getName();
        address = device.getAddress();
        Handler main = new Handler(Looper.getMainLooper());
        // The 2M PHY doubles the air rate on Bluetooth 5 boards (S3, C6); a 4.2 board stays on 1M.
        main.post(() -> {
            if (Build.VERSION.SDK_INT >= 26)
                gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE,
                    adapter.isLe2MPhySupported()
                        ? BluetoothDevice.PHY_LE_1M_MASK | BluetoothDevice.PHY_LE_2M_MASK
                        : BluetoothDevice.PHY_LE_1M_MASK);
            else
                gatt = device.connectGatt(context, false, callback, BluetoothDevice.TRANSPORT_LE);
        });
    }

    private final BluetoothGattCallback callback = new BluetoothGattCallback() {
        @Override public void onConnectionStateChange(BluetoothGatt g, int status, int state) {
            if (state == BluetoothProfile.STATE_CONNECTED) {
                gatt = g;
                // High priority asks for the shortest interval Android allows (about 11.25 to 15 ms);
                // the board asks for 15 ms itself once subscribed.
                g.requestConnectionPriority(BluetoothGatt.CONNECTION_PRIORITY_HIGH);
                if (Build.VERSION.SDK_INT >= 26 && adapter.isLe2MPhySupported())
                    g.setPreferredPhy(BluetoothDevice.PHY_LE_1M_MASK | BluetoothDevice.PHY_LE_2M_MASK,
                        BluetoothDevice.PHY_LE_1M_MASK | BluetoothDevice.PHY_LE_2M_MASK,
                        BluetoothDevice.PHY_OPTION_NO_PREFERRED);
                if (!g.requestMtu(WANTED_MTU)) g.discoverServices();
            } else if (state == BluetoothProfile.STATE_DISCONNECTED) {
                lost(new IOException("The board's Bluetooth link dropped (status " + status + ")."));
            }
        }

        @Override public void onMtuChanged(BluetoothGatt g, int mtu, int status) {
            if (status == BluetoothGatt.GATT_SUCCESS) piece = Math.max(20, mtu - 3);
            g.discoverServices();
        }

        @Override public void onServicesDiscovered(BluetoothGatt g, int status) {
            BluetoothGattService service = g.getService(SERVICE);
            if (status != BluetoothGatt.GATT_SUCCESS || service == null) {
                lost(new IOException("The Bluetooth device is not a pokeldn radio board."));
                return;
            }
            BluetoothGattCharacteristic write = service.getCharacteristic(RX);
            BluetoothGattCharacteristic notify = service.getCharacteristic(TX);
            if (write == null || notify == null) {
                lost(new IOException("The board's Bluetooth service is missing its stream."));
                return;
            }
            rx = write;
            g.setCharacteristicNotification(notify, true);
            BluetoothGattDescriptor descriptor = notify.getDescriptor(CCCD);
            if (descriptor == null) { lost(new IOException("The board's stream cannot notify.")); return; }
            if (Build.VERSION.SDK_INT >= 33)
                g.writeDescriptor(descriptor, BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
            else {
                descriptor.setValue(BluetoothGattDescriptor.ENABLE_NOTIFICATION_VALUE);
                g.writeDescriptor(descriptor);
            }
        }

        @Override public void onDescriptorWrite(BluetoothGatt g, BluetoothGattDescriptor d, int status) {
            if (!CCCD.equals(d.getUuid())) return;
            if (status != BluetoothGatt.GATT_SUCCESS) {
                lost(new IOException("Subscribing to the board's stream failed (" + status + ")."));
                return;
            }
            // Subscribed: the board's wire now reads and writes over Bluetooth, the cable falls silent.
            writer = new Thread(BleStream.this::writeLoop, "android-ble-writer");
            writer.start();
            ready.countDown();
        }

        @Override public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c, byte[] value) {
            received(c, value);   // Android 13 and later
        }

        @SuppressWarnings("deprecation")
        @Override public void onCharacteristicChanged(BluetoothGatt g, BluetoothGattCharacteristic c) {
            if (Build.VERSION.SDK_INT < 33) received(c, c.getValue());
        }

        @Override public void onCharacteristicWrite(BluetoothGatt g, BluetoothGattCharacteristic c, int status) {
            synchronized (writeDone) {
                writing = false;
                if (status != BluetoothGatt.GATT_SUCCESS)
                    failure = new IOException("A Bluetooth write to the board failed (" + status + ").");
                writeDone.notifyAll();
            }
        }

        @Override public void onReadRemoteRssi(BluetoothGatt g, int value, int status) {
            if (status == BluetoothGatt.GATT_SUCCESS) rssi = value;
        }
    };

    private void received(BluetoothGattCharacteristic c, byte[] value) {
        if (!TX.equals(c.getUuid()) || value == null || value.length == 0) return;
        if (!incoming.offer(value.clone())) lost(new IOException("Android Bluetooth receive queue overflow"));
    }

    private void lost(IOException error) {
        if (failure == null) failure = error;
        ready.countDown();
        synchronized (writeDone) { writeDone.notifyAll(); }
        Log.w(TAG, "Bluetooth: " + error.getMessage());
        Bridge.refresh();
    }

    private void writeLoop() {
        try {
            while (!closed && failure == null) {
                byte[] bytes = outgoing.take();
                for (int at = 0; at < bytes.length && !closed; at += piece) {
                    byte[] part = Arrays.copyOfRange(bytes, at, Math.min(bytes.length, at + piece));
                    writeOne(part);
                }
            }
        } catch (InterruptedException ignored) {
        } catch (IOException error) {
            lost(error);
        }
    }

    @SuppressWarnings("deprecation")
    private void writeOne(byte[] part) throws IOException, InterruptedException {
        BluetoothGatt g = gatt;
        BluetoothGattCharacteristic c = rx;
        if (g == null || c == null) throw new IOException("The board is not connected over Bluetooth.");
        // A write the stack is not ready for is refused (busy): wait a little and retry.
        long deadline = System.nanoTime() + 5_000_000_000L;
        while (true) {
            boolean queued;
            synchronized (writeDone) {
                writing = true;
                if (Build.VERSION.SDK_INT >= 33)
                    queued = g.writeCharacteristic(c, part, BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE)
                        == BluetoothStatusCodes.SUCCESS;
                else {
                    c.setWriteType(BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE);
                    c.setValue(part);
                    queued = g.writeCharacteristic(c);
                }
                if (queued) {
                    while (writing && failure == null && !closed) {
                        long left = deadline - System.nanoTime();
                        if (left <= 0) throw new IOException("A Bluetooth write to the board timed out.");
                        TimeUnit.NANOSECONDS.timedWait(writeDone, left);
                    }
                    if (failure != null) throw failure;
                    return;
                }
                writing = false;
            }
            if (System.nanoTime() > deadline) throw new IOException("The Bluetooth stack refused a write.");
            Thread.sleep(2);
        }
    }

    // UsbStream's interface, as pokeldn.app.android uses it.

    public synchronized byte[] read(int size) throws IOException {
        if (closed) throw new IOException("Bluetooth stream closed");
        if (failure != null && incoming.isEmpty() && remainder.length == 0) throw failure;
        try {
            byte[] bytes = remainder.length > 0 ? remainder : incoming.poll(20, TimeUnit.MILLISECONDS);
            if (bytes == null) return new byte[0];
            int count = Math.min(size, bytes.length);
            remainder = Arrays.copyOfRange(bytes, count, bytes.length);
            return Arrays.copyOf(bytes, count);
        } catch (InterruptedException error) {
            Thread.currentThread().interrupt();
            throw new IOException(error);
        }
    }

    public synchronized int available() {
        int count = remainder.length;
        for (byte[] chunk : incoming) count += chunk.length;
        return count;
    }

    /** Clears what the board sent before this port was opened: a reopened connection starts clean. */
    public synchronized void discardInput() {
        remainder = new byte[0];
        incoming.clear();
    }

    public int write(byte[] bytes) throws IOException {
        if (closed) throw new IOException("Bluetooth stream closed");
        if (failure != null) throw failure;
        if (!outgoing.offer(bytes.clone())) throw new IOException("Bluetooth write queue overflow");
        return bytes.length;
    }

    /** Bluetooth has no line rate and no DTR or RTS: a board on it cannot be reset or flashed. */
    public void setBaud(int baud) { }
    public void setLines(boolean dtr, boolean rts) { }

    public boolean isClosed() { return closed || failure != null; }
    public String name() { return deviceName; }
    public String address() { return address; }

    /** The last signal strength, refreshed in the background. */
    public int rssi() {
        BluetoothGatt g = gatt;
        if (g != null && !closed) g.readRemoteRssi();
        return rssi;
    }

    @Override public void close() {
        if (closed) return;
        closed = true;
        if (writer != null) writer.interrupt();
        BluetoothGatt g = gatt;
        if (g != null) {
            try { g.disconnect(); g.close(); } catch (RuntimeException ignored) { }
        }
        ready.countDown();
    }
}
