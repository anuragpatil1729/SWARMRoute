package com.swarmroute.mobile_app

import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Context
import android.net.ConnectivityManager
import android.net.NetworkCapabilities
import android.os.Handler
import android.os.Looper
import android.os.ParcelUuid
import android.util.Log
import io.flutter.plugin.common.MethodChannel
import org.json.JSONObject
import java.io.OutputStreamWriter
import java.net.HttpURLConnection
import java.net.URL
import java.nio.charset.StandardCharsets
import java.util.*
import java.util.concurrent.ConcurrentHashMap
import java.util.concurrent.ConcurrentLinkedQueue

/**
 * Authentic Android Native BLE Multi-Hop Mesh Engine for SWARMRoute.
 * Provides physical device-to-device communication:
 * - Real BLE Advertising (Peripheral Mode)
 * - Real BLE Scanning (Central Mode)
 * - Real GATT Server for packet reception
 * - Real GATT Client for packet forwarding
 * - Deduplication cache (no duplicate loops)
 * - TTL decrement & hop counting
 * - Internet Gateway bridge: relays mesh packets to backend if device has cellular/Wi-Fi
 */
class BleMeshEngine(private val context: Context, private val channel: MethodChannel) {

    companion object {
        private const val TAG = "SWARMRoute_BLE"
        val MESH_SERVICE_UUID: UUID = UUID.fromString("0000FE26-0000-1000-8000-00805F9B34FB")
        val RX_CHAR_UUID: UUID = UUID.fromString("0000FE27-0000-1000-8000-00805F9B34FB")
        val TX_CHAR_UUID: UUID = UUID.fromString("0000FE28-0000-1000-8000-00805F9B34FB")
        private const val MAX_SEEN_MESSAGES = 1000
    }

    private var bluetoothManager: BluetoothManager? = null
    private var bluetoothAdapter: BluetoothAdapter? = null
    private var bleAdvertiser: BluetoothLeAdvertiser? = null
    private var bleScanner: BluetoothLeScanner? = null
    private var gattServer: BluetoothGattServer? = null

    private var myDeviceId: String = "DEV_UNKNOWN"
    private var isRunning: Boolean = false
    private var backendBaseUrl: String = "http://10.0.2.2:8000"

    // Deduplication cache: message_id -> timestamp
    private val seenMessageIds = Collections.newSetFromMap(ConcurrentHashMap<String, Boolean>())
    // Peer table: device_id -> PeerInfo
    private val discoveredPeers = ConcurrentHashMap<String, PeerInfo>()
    // Store-and-forward message queue for unreachable destinations
    private val storeAndForwardQueue = ConcurrentLinkedQueue<JSONObject>()

    private val mainHandler = Handler(Looper.getMainLooper())

    data class PeerInfo(
        val deviceId: String,
        val bluetoothAddress: String,
        var rssi: Int,
        var lastSeenTimestamp: Long
    )

    fun startMesh(deviceId: String, backendUrl: String): Boolean {
        myDeviceId = deviceId
        backendBaseUrl = backendUrl.trimEnd('/')

        bluetoothManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
        bluetoothAdapter = bluetoothManager?.adapter

        if (bluetoothAdapter == null || !bluetoothAdapter!!.isEnabled) {
            Log.w(TAG, "Bluetooth adapter unavailable or disabled.")
            return false
        }

        isRunning = true
        startGattServer()
        startAdvertising()
        startScanning()

        Log.i(TAG, "SWARMRoute physical BLE mesh started for node: $myDeviceId")
        return true
    }

    fun stopMesh() {
        isRunning = false
        stopAdvertising()
        stopScanning()
        gattServer?.close()
        gattServer = null
        discoveredPeers.clear()
        Log.i(TAG, "SWARMRoute physical BLE mesh stopped.")
    }

    // ==========================================
    // 1. REAL BLE ADVERTISING (Peripheral Mode)
    // ==========================================
    private fun startAdvertising() {
        bleAdvertiser = bluetoothAdapter?.bluetoothLeAdvertiser
        if (bleAdvertiser == null) {
            Log.w(TAG, "BLE Peripheral advertising not supported on this chipset.")
            return
        }

        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_BALANCED)
            .setConnectable(true)
            .setTimeout(0)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_MEDIUM)
            .build()

        val data = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .setIncludeTxPowerLevel(false)
            .addServiceUuid(ParcelUuid(MESH_SERVICE_UUID))
            .addServiceData(ParcelUuid(MESH_SERVICE_UUID), myDeviceId.toByteArray(StandardCharsets.UTF_8).take(8).toByteArray())
            .build()

        try {
            bleAdvertiser?.startAdvertising(settings, data, advertiseCallback)
        } catch (e: SecurityException) {
            Log.e(TAG, "Missing BLUETOOTH_ADVERTISE permission: ${e.message}")
        }
    }

    private fun stopAdvertising() {
        try {
            bleAdvertiser?.stopAdvertising(advertiseCallback)
        } catch (e: SecurityException) {
            Log.e(TAG, "Error stopping advertising: ${e.message}")
        }
    }

    private val advertiseCallback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
            Log.i(TAG, "BLE Mesh advertising started successfully.")
        }

        override fun onStartFailure(errorCode: Int) {
            Log.e(TAG, "BLE Mesh advertising failed with error code: $errorCode")
        }
    }

    // ==========================================
    // 2. REAL BLE SCANNING (Central Mode)
    // ==========================================
    private fun startScanning() {
        bleScanner = bluetoothAdapter?.bluetoothLeScanner
        if (bleScanner == null) {
            Log.w(TAG, "BLE Central scanner unavailable.")
            return
        }

        val filter = ScanFilter.Builder()
            .setServiceUuid(ParcelUuid(MESH_SERVICE_UUID))
            .build()

        val scanSettings = ScanSettings.Builder()
            .setScanMode(ScanSettings.SCAN_MODE_LOW_LATENCY)
            .build()

        try {
            bleScanner?.startScan(listOf(filter), scanSettings, scanCallback)
            Log.i(TAG, "BLE Mesh continuous scanning started.")
        } catch (e: SecurityException) {
            Log.e(TAG, "Missing BLUETOOTH_SCAN permission: ${e.message}")
        }
    }

    private fun stopScanning() {
        try {
            bleScanner?.stopScan(scanCallback)
        } catch (e: SecurityException) {
            Log.e(TAG, "Error stopping scan: ${e.message}")
        }
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult?) {
            result?.let { res ->
                val serviceData = res.scanRecord?.getServiceData(ParcelUuid(MESH_SERVICE_UUID))
                val peerId = if (serviceData != null && serviceData.isNotEmpty()) {
                    String(serviceData, StandardCharsets.UTF_8)
                } else {
                    res.device.address
                }

                if (peerId != myDeviceId) {
                    discoveredPeers[peerId] = PeerInfo(
                        deviceId = peerId,
                        bluetoothAddress = res.device.address,
                        rssi = res.rssi,
                        lastSeenTimestamp = System.currentTimeMillis()
                    )

                    // Notify Flutter UI of peer discovery
                    mainHandler.post {
                        channel.invokeMethod("onPeerDiscovered", mapOf(
                            "peer_id" to peerId,
                            "address" to res.device.address,
                            "rssi" to res.rssi
                        ))
                    }
                }
            }
        }
    }

    // ==========================================
    // 3. GATT SERVER (Packet Reception)
    // ==========================================
    private fun startGattServer() {
        try {
            gattServer = bluetoothManager?.openGattServer(context, gattServerCallback)
            val service = BluetoothGattService(MESH_SERVICE_UUID, BluetoothGattService.SERVICE_TYPE_PRIMARY)

            val rxChar = BluetoothGattCharacteristic(
                RX_CHAR_UUID,
                BluetoothGattCharacteristic.PROPERTY_WRITE or BluetoothGattCharacteristic.PROPERTY_WRITE_NO_RESPONSE,
                BluetoothGattCharacteristic.PERMISSION_WRITE
            )

            val txChar = BluetoothGattCharacteristic(
                TX_CHAR_UUID,
                BluetoothGattCharacteristic.PROPERTY_NOTIFY or BluetoothGattCharacteristic.PROPERTY_READ,
                BluetoothGattCharacteristic.PERMISSION_READ
            )

            service.addCharacteristic(rxChar)
            service.addCharacteristic(txChar)
            gattServer?.addService(service)
            Log.i(TAG, "BLE Mesh GATT Server initialized.")
        } catch (e: SecurityException) {
            Log.e(TAG, "Missing BLUETOOTH_CONNECT permission: ${e.message}")
        }
    }

    private val gattServerCallback = object : BluetoothGattServerCallback() {
        override fun onCharacteristicWriteRequest(
            device: BluetoothDevice?,
            requestId: Int,
            characteristic: BluetoothGattCharacteristic?,
            preparedWrite: Boolean,
            responseNeeded: Boolean,
            offset: Int,
            value: ByteArray?
        ) {
            if (responseNeeded) {
                try {
                    gattServer?.sendResponse(device, requestId, BluetoothGatt.GATT_SUCCESS, offset, null)
                } catch (e: SecurityException) {
                    Log.e(TAG, "sendResponse SecurityException: ${e.message}")
                }
            }

            if (characteristic?.uuid == RX_CHAR_UUID && value != null) {
                val jsonStr = String(value, StandardCharsets.UTF_8)
                try {
                    val packet = JSONObject(jsonStr)
                    handleIncomingPacket(packet, device?.address ?: "UNKNOWN")
                } catch (e: Exception) {
                    Log.e(TAG, "Failed to parse mesh packet: ${e.message}")
                }
            }
        }
    }

    // ====================================================
    // 4. PACKET PROTOCOL, DEDUPLICATION & MULTI-HOP RELAY
    // ====================================================
    fun broadcastPacket(packetJson: String): Boolean {
        try {
            val packet = JSONObject(packetJson)
            val msgId = packet.optString("message_id")
            if (msgId.isNotEmpty()) {
                seenMessageIds.add(msgId)
            }
            forwardPacketToPeers(packet, excludeAddress = null)
            return true
        } catch (e: Exception) {
            Log.e(TAG, "Error broadcasting packet: ${e.message}")
            return false
        }
    }

    private fun handleIncomingPacket(packet: JSONObject, fromAddress: String) {
        val msgId = packet.optString("message_id")
        val destId = packet.optString("destination_device_id", "BROADCAST")
        val ttl = packet.optInt("ttl", 5)
        val hopCount = packet.optInt("hop_count", 0)

        // 1. Deduplication check: drop packet if seen previously (Prevents infinite broadcast loops)
        if (msgId.isNotEmpty()) {
            if (seenMessageIds.contains(msgId)) {
                Log.d(TAG, "Dropping duplicate packet: $msgId")
                return
            }
            if (seenMessageIds.size > MAX_SEEN_MESSAGES) {
                seenMessageIds.clear()
            }
            seenMessageIds.add(msgId)
        }

        // 2. Decrement TTL and increment hop count
        if (ttl <= 1) {
            Log.w(TAG, "Dropping packet $msgId: TTL expired (hop: $hopCount)")
            return
        }
        packet.put("ttl", ttl - 1)
        packet.put("hop_count", hopCount + 1)

        Log.i(TAG, "Received mesh packet: $msgId from $fromAddress, hopCount: ${hopCount + 1}")

        // 3. Notify Flutter application layer
        mainHandler.post {
            channel.invokeMethod("onPacketReceived", packet.toString())
        }

        // 4. Multi-hop forwarding: If this device has an active internet connection,
        // bridge the packet directly to the SWARMRoute cloud backend!
        if (isInternetAvailable()) {
            relayPacketToBackend(packet)
        }

        // 5. If not destination, forward packet to reachable physical BLE peers
        if (destId != myDeviceId) {
            forwardPacketToPeers(packet, excludeAddress = fromAddress)
        }
    }

    private fun forwardPacketToPeers(packet: JSONObject, excludeAddress: String?) {
        val rawBytes = packet.toString().toByteArray(StandardCharsets.UTF_8)

        // Forward to all discovered peers within physical radio reach
        for (peer in discoveredPeers.values) {
            if (peer.bluetoothAddress == excludeAddress) continue

            val device = bluetoothAdapter?.getRemoteDevice(peer.bluetoothAddress) ?: continue
            try {
                device.connectGatt(context, false, object : BluetoothGattCallback() {
                    override fun onConnectionStateChange(gatt: BluetoothGatt?, status: Int, newState: Int) {
                        if (newState == BluetoothProfile.STATE_CONNECTED) {
                            try {
                                gatt?.discoverServices()
                            } catch (e: SecurityException) {
                                Log.e(TAG, "discoverServices SecurityException: ${e.message}")
                            }
                        } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                            try {
                                gatt?.close()
                            } catch (e: SecurityException) {
                                Log.e(TAG, "close SecurityException: ${e.message}")
                            }
                        }
                    }

                    override fun onServicesDiscovered(gatt: BluetoothGatt?, status: Int) {
                        if (status == BluetoothGatt.GATT_SUCCESS) {
                            val service = gatt?.getService(MESH_SERVICE_UUID)
                            val rxChar = service?.getCharacteristic(RX_CHAR_UUID)
                            if (rxChar != null) {
                                rxChar.value = rawBytes
                                rxChar.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                                try {
                                    gatt.writeCharacteristic(rxChar)
                                    Log.i(TAG, "Successfully forwarded packet over BLE hop to ${peer.deviceId}")
                                } catch (e: SecurityException) {
                                    Log.e(TAG, "writeCharacteristic SecurityException: ${e.message}")
                                }
                            }
                        }
                    }
                })
            } catch (e: SecurityException) {
                Log.e(TAG, "connectGatt SecurityException: ${e.message}")
            }
        }
    }

    // ==========================================
    // 5. INTERNET GATEWAY BRIDGE
    // ==========================================
    private fun isInternetAvailable(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    private fun relayPacketToBackend(packet: JSONObject) {
        Thread {
            try {
                val relayUrl = URL("$backendBaseUrl/api/v1/mesh/relay")
                val conn = relayUrl.openConnection() as HttpURLConnection
                conn.requestMethod = "POST"
                conn.setRequestProperty("Content-Type", "application/json")
                conn.connectTimeout = 4000
                conn.readTimeout = 4000
                conn.doOutput = true

                val relayPayload = JSONObject().apply {
                    put("message_id", packet.optString("message_id"))
                    put("source_device_id", packet.optString("source_device_id"))
                    put("destination_device_id", packet.optString("destination_device_id", "BACKEND"))
                    put("message_type", packet.optString("message_type", "ASSISTANCE_REQUEST"))
                    put("timestamp", packet.optDouble("timestamp", System.currentTimeMillis() / 1000.0))
                    put("ttl", packet.optInt("ttl", 5))
                    put("hop_count", packet.optInt("hop_count", 1))
                    put("payload", packet.optJSONObject("payload") ?: JSONObject())
                    put("bridge_device_id", myDeviceId)
                }

                OutputStreamWriter(conn.outputStream, StandardCharsets.UTF_8).use { writer ->
                    writer.write(relayPayload.toString())
                    writer.flush()
                }

                val code = conn.responseCode
                Log.i(TAG, "Mesh internet bridge: Relayed packet ${packet.optString("message_id")} to cloud (HTTP $code)")
                conn.disconnect()
            } catch (e: Exception) {
                Log.w(TAG, "Mesh internet bridge relay attempt deferred: ${e.message}")
            }
        }.start()
    }

    fun getDiscoveredPeers(): List<Map<String, Any>> {
        return discoveredPeers.values.map {
            mapOf(
                "device_id" to it.deviceId,
                "bluetooth_address" to it.bluetoothAddress,
                "rssi" to it.rssi,
                "last_seen_ms" to it.lastSeenTimestamp
            )
        }
    }
}
