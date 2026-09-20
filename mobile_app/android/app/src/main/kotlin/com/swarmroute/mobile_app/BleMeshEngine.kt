package com.swarmroute.mobile_app

import android.bluetooth.*
import android.bluetooth.le.*
import android.content.Context
import android.net.ConnectivityManager
import android.net.Network
import android.net.NetworkCapabilities
import android.net.NetworkRequest
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
 * Production Android Smartphone BLE Multi-Hop Mesh Engine for SWARMRoute.
 * 
 * Hardware Role:
 * Every delivery driver's Android smartphone acts simultaneously as:
 * 1. BLE Central: Scans for nearby SWARMRoute driver phones
 * 2. BLE Peripheral/GATT Server: Advertises service and accepts connections
 * 3. Mesh Relay Node: Validates, decrements TTL, increments hop count, deduplicates, store-and-forward
 * 4. GPS Source: Captured via native device location
 * 5. Internet Gateway: When cellular/Wi-Fi is available, bridges mesh packets to SWARMRoute cloud backend
 */
class BleMeshEngine(private val context: Context, private val channel: MethodChannel) {

    companion object {
        private const val TAG = "SWARMRoute_BLE"
        val MESH_SERVICE_UUID: UUID = UUID.fromString("0000FE26-0000-1000-8000-00805F9B34FB")
        val RX_CHAR_UUID: UUID = UUID.fromString("0000FE27-0000-1000-8000-00805F9B34FB")
        val TX_CHAR_UUID: UUID = UUID.fromString("0000FE28-0000-1000-8000-00805F9B34FB")
        
        private const val MAX_SEEN_MESSAGES = 2000
        private const val PEER_STALE_TIMEOUT_MS = 45000L
        private const val CHUNK_PREFIX = "CHK:"
        private const val DEFAULT_MTU = 512
        private const val PACKET_EXPIRY_SECONDS = 3600.0
    }

    private var bluetoothManager: BluetoothManager? = null
    private var bluetoothAdapter: BluetoothAdapter? = null
    private var bleAdvertiser: BluetoothLeAdvertiser? = null
    private var bleScanner: BluetoothLeScanner? = null
    private var gattServer: BluetoothGattServer? = null
    private var connectivityManager: ConnectivityManager? = null

    private var myDeviceId: String = "DEV_UNKNOWN"
    private var myDriverId: String = "DRIVER_UNKNOWN"
    private var isRunning: Boolean = false
    private var isAdvertising: Boolean = false
    private var isScanning: Boolean = false
    private var backendBaseUrl: String = "http://10.0.2.2:8000"

    // Deduplication cache: message_id -> timestamp ms
    private val seenMessageIds = ConcurrentHashMap<String, Long>()
    // Peer table: device_id -> PeerInfo
    private val discoveredPeers = ConcurrentHashMap<String, PeerInfo>()
    // Store-and-forward message queue for unreachable destinations or offline recovery
    private val storeAndForwardQueue = ConcurrentLinkedQueue<JSONObject>()
    // Incoming chunk assembly buffer: msgId -> Map<chunkIndex, dataString>
    private val chunkBuffers = ConcurrentHashMap<String, ConcurrentHashMap<Int, String>>()
    private val chunkExpectedTotal = ConcurrentHashMap<String, Int>()

    private val mainHandler = Handler(Looper.getMainLooper())

    data class PeerInfo(
        val deviceId: String,
        val bluetoothAddress: String,
        var rssi: Int,
        var lastSeenTimestamp: Long
    )

    // Periodic peer table maintenance
    private val pruneStalePeersRunnable = object : Runnable {
        override fun run() {
            if (!isRunning) return
            val now = System.currentTimeMillis()
            val it = discoveredPeers.entries.iterator()
            var pruned = false
            while (it.hasNext()) {
                val entry = it.next()
                if (now - entry.value.lastSeenTimestamp > PEER_STALE_TIMEOUT_MS) {
                    it.remove()
                    pruned = true
                    logEvent("PEER_PRUNED_STALE", mapOf("peer_id" to entry.key))
                }
            }
            if (pruned) {
                notifyPeerTableChanged()
            }
            mainHandler.postDelayed(this, 15000L)
        }
    }

    // Network callback to automatically flush store-and-forward queue when internet recovers
    private val networkCallback = object : ConnectivityManager.NetworkCallback() {
        override fun onAvailable(network: Network) {
            logEvent("INTERNET_GATEWAY_AVAILABLE", mapOf("device_id" to myDeviceId))
            mainHandler.post {
                channel.invokeMethod("onGatewayStateChanged", mapOf("has_internet" to true))
            }
            flushStoreAndForwardQueue()
        }

        override fun onLost(network: Network) {
            logEvent("INTERNET_DISCONNECTED_BLE_ONLY", mapOf("device_id" to myDeviceId))
            mainHandler.post {
                channel.invokeMethod("onGatewayStateChanged", mapOf("has_internet" to false))
            }
        }
    }

    // ==========================================
    // LIFECYCLE CONTROLS
    // ==========================================

    fun startMesh(deviceId: String, driverId: String, backendUrl: String): Boolean {
        myDeviceId = deviceId
        myDriverId = driverId
        backendBaseUrl = backendUrl.trimEnd('/')

        bluetoothManager = context.getSystemService(Context.BLUETOOTH_SERVICE) as? BluetoothManager
        bluetoothAdapter = bluetoothManager?.adapter

        if (bluetoothAdapter == null || !bluetoothAdapter!!.isEnabled) {
            Log.w(TAG, "Bluetooth adapter unavailable or disabled.")
            logEvent("BLE_START_FAILED", mapOf("reason" to "BLUETOOTH_DISABLED"))
            return false
        }

        connectivityManager = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager
        try {
            val request = NetworkRequest.Builder()
                .addCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
                .build()
            connectivityManager?.registerNetworkCallback(request, networkCallback)
        } catch (e: Exception) {
            Log.w(TAG, "Network callback registration note: ${e.message}")
        }

        isRunning = true
        startGattServer()
        startAdvertising()
        startScanning()

        mainHandler.postDelayed(pruneStalePeersRunnable, 15000L)
        logEvent("BLE_STARTED", mapOf("device_id" to myDeviceId, "driver_id" to myDriverId))
        return true
    }

    fun stopMesh() {
        isRunning = false
        stopAdvertising()
        stopScanning()
        mainHandler.removeCallbacks(pruneStalePeersRunnable)

        try {
            connectivityManager?.unregisterNetworkCallback(networkCallback)
        } catch (_: Exception) {}

        gattServer?.close()
        gattServer = null
        discoveredPeers.clear()
        chunkBuffers.clear()
        chunkExpectedTotal.clear()

        logEvent("BLE_STOPPED", mapOf("device_id" to myDeviceId))
    }

    // ==========================================
    // 1. REAL BLE ADVERTISING (Peripheral Mode)
    // ==========================================

    private fun startAdvertising() {
        bleAdvertiser = bluetoothAdapter?.bluetoothLeAdvertiser
        if (bleAdvertiser == null) {
            Log.w(TAG, "BLE Peripheral advertising not supported on this device.")
            logEvent("BLE_ADVERTISER_UNSUPPORTED", mapOf("device_id" to myDeviceId))
            return
        }

        val settings = AdvertiseSettings.Builder()
            .setAdvertiseMode(AdvertiseSettings.ADVERTISE_MODE_BALANCED)
            .setConnectable(true)
            .setTimeout(0)
            .setTxPowerLevel(AdvertiseSettings.ADVERTISE_TX_POWER_MEDIUM)
            .build()

        // Encode short device prefix in advertisement packet
        val identityBytes = myDeviceId.toByteArray(StandardCharsets.UTF_8).take(8).toByteArray()
        val data = AdvertiseData.Builder()
            .setIncludeDeviceName(false)
            .setIncludeTxPowerLevel(false)
            .addServiceUuid(ParcelUuid(MESH_SERVICE_UUID))
            .addServiceData(ParcelUuid(MESH_SERVICE_UUID), identityBytes)
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
            isAdvertising = false
        } catch (e: SecurityException) {
            Log.e(TAG, "Error stopping advertising: ${e.message}")
        }
    }

    private val advertiseCallback = object : AdvertiseCallback() {
        override fun onStartSuccess(settingsInEffect: AdvertiseSettings?) {
            isAdvertising = true
            logEvent("BLE_ADVERTISING_STARTED", mapOf("device_id" to myDeviceId))
        }

        override fun onStartFailure(errorCode: Int) {
            isAdvertising = false
            logEvent("BLE_ADVERTISING_FAILED", mapOf("error_code" to errorCode))
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
            isScanning = true
            logEvent("BLE_SCANNING_STARTED", mapOf("device_id" to myDeviceId))
        } catch (e: SecurityException) {
            Log.e(TAG, "Missing BLUETOOTH_SCAN permission: ${e.message}")
        }
    }

    private fun stopScanning() {
        try {
            bleScanner?.stopScan(scanCallback)
            isScanning = false
        } catch (e: SecurityException) {
            Log.e(TAG, "Error stopping scan: ${e.message}")
        }
    }

    private val scanCallback = object : ScanCallback() {
        override fun onScanResult(callbackType: Int, result: ScanResult?) {
            result?.let { res ->
                val serviceData = res.scanRecord?.getServiceData(ParcelUuid(MESH_SERVICE_UUID))
                val peerId = if (serviceData != null && serviceData.isNotEmpty()) {
                    String(serviceData, StandardCharsets.UTF_8).trim()
                } else {
                    res.device.address
                }

                if (peerId != myDeviceId && peerId.isNotEmpty()) {
                    val isNew = !discoveredPeers.containsKey(peerId)
                    discoveredPeers[peerId] = PeerInfo(
                        deviceId = peerId,
                        bluetoothAddress = res.device.address,
                        rssi = res.rssi,
                        lastSeenTimestamp = System.currentTimeMillis()
                    )

                    if (isNew) {
                        logEvent("PEER_DISCOVERED", mapOf("peer_id" to peerId, "rssi" to res.rssi, "address" to res.device.address))
                    }
                    notifyPeerTableChanged()
                }
            }
        }
    }

    private fun notifyPeerTableChanged() {
        mainHandler.post {
            channel.invokeMethod("onPeersUpdated", getDiscoveredPeers())
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
            logEvent("GATT_SERVER_READY", mapOf("service" to MESH_SERVICE_UUID.toString()))
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
                val chunkOrJson = String(value, StandardCharsets.UTF_8)
                handleRawIncomingBytes(chunkOrJson, device?.address ?: "UNKNOWN")
            }
        }
    }

    private fun handleRawIncomingBytes(rawPayload: String, fromAddress: String) {
        // Check if rawPayload is a chunk
        if (rawPayload.startsWith(CHUNK_PREFIX)) {
            // Format: CHK:msgId:index:total:data
            val parts = rawPayload.split(":", limit = 5)
            if (parts.size == 5) {
                val msgId = parts[1]
                val index = parts[2].toIntOrNull() ?: 0
                val total = parts[3].toIntOrNull() ?: 1
                val chunkData = parts[4]

                val buffer = chunkBuffers.computeIfAbsent(msgId) { ConcurrentHashMap() }
                buffer[index] = chunkData
                chunkExpectedTotal[msgId] = total

                if (buffer.size == total) {
                    // Reassemble full packet
                    val sb = java.lang.StringBuilder()
                    for (i in 0 until total) {
                        sb.append(buffer[i] ?: "")
                    }
                    chunkBuffers.remove(msgId)
                    chunkExpectedTotal.remove(msgId)
                    try {
                        val packet = JSONObject(sb.toString())
                        handleIncomingPacket(packet, fromAddress)
                    } catch (e: Exception) {
                        logEvent("PACKET_REJECTED", mapOf("reason" to "CHUNK_REASSEMBLY_JSON_ERROR", "error" to (e.message ?: "")))
                    }
                }
                return
            }
        }

        // Direct full JSON packet
        try {
            val packet = JSONObject(rawPayload)
            handleIncomingPacket(packet, fromAddress)
        } catch (e: Exception) {
            logEvent("PACKET_REJECTED", mapOf("reason" to "MALFORMED_JSON", "error" to (e.message ?: "")))
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
                seenMessageIds[msgId] = System.currentTimeMillis()
            }
            logEvent("PACKET_CREATED", mapOf(
                "message_id" to msgId,
                "type" to packet.optString("message_type"),
                "ttl" to packet.optInt("ttl", 5)
            ))

            // Attempt cloud upload first if internet is available
            if (isInternetAvailable()) {
                relayPacketToBackend(packet)
            } else {
                // Queue for store-and-forward
                storeAndForwardQueue.add(packet)
                logEvent("PACKET_QUEUED", mapOf("message_id" to msgId, "queue_size" to storeAndForwardQueue.size))
            }

            // Transmit across physical BLE to reachable peers
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
        val timestamp = packet.optDouble("timestamp", 0.0)

        // Security check: Payload size validation (< 4KB)
        if (packet.toString().length > 4096) {
            logEvent("PACKET_REJECTED", mapOf("message_id" to msgId, "reason" to "EXCEEDS_MAX_PAYLOAD_SIZE"))
            return
        }

        // Security check: Expiry timestamp validation (< 3600s)
        val nowSec = System.currentTimeMillis() / 1000.0
        if (timestamp > 0.0 && (nowSec - timestamp) > PACKET_EXPIRY_SECONDS) {
            logEvent("PACKET_REJECTED", mapOf("message_id" to msgId, "reason" to "TIMESTAMP_EXPIRED"))
            return
        }

        // Deduplication check: drop packet if already seen
        if (msgId.isNotEmpty()) {
            if (seenMessageIds.containsKey(msgId)) {
                logEvent("PACKET_DEDUPLICATED", mapOf("message_id" to msgId, "from_address" to fromAddress))
                return
            }
            if (seenMessageIds.size > MAX_SEEN_MESSAGES) {
                seenMessageIds.clear()
            }
            seenMessageIds[msgId] = System.currentTimeMillis()
        }

        // Decrement TTL and increment hop count
        if (ttl <= 1) {
            logEvent("PACKET_TTL_EXPIRED", mapOf("message_id" to msgId, "hop_count" to hopCount))
            return
        }
        packet.put("ttl", ttl - 1)
        packet.put("hop_count", hopCount + 1)

        logEvent("PACKET_VALIDATED", mapOf(
            "message_id" to msgId,
            "type" to packet.optString("message_type"),
            "hop_count" to (hopCount + 1),
            "remaining_ttl" to (ttl - 1)
        ))

        // Notify Flutter application layer
        mainHandler.post {
            channel.invokeMethod("onPacketReceived", packet.toString())
        }

        // Multi-hop forwarding: If this device has active internet, bridge immediately to cloud
        if (isInternetAvailable()) {
            relayPacketToBackend(packet)
        } else {
            storeAndForwardQueue.add(packet)
            logEvent("PACKET_QUEUED", mapOf("message_id" to msgId, "queue_size" to storeAndForwardQueue.size))
        }

        // Forward packet to physical BLE peers (multi-hop mesh)
        if (destId != myDeviceId) {
            forwardPacketToPeers(packet, excludeAddress = fromAddress)
        }
    }

    private fun forwardPacketToPeers(packet: JSONObject, excludeAddress: String?) {
        val rawJson = packet.toString()
        val rawBytes = rawJson.toByteArray(StandardCharsets.UTF_8)

        // Chunking if packet exceeds typical BLE MTU safe payload (200 bytes)
        val chunks = mutableListOf<ByteArray>()
        if (rawBytes.size > 200) {
            val msgId = packet.optString("message_id", UUID.randomUUID().toString())
            val chunkSize = 180
            val totalChunks = (rawBytes.size + chunkSize - 1) / chunkSize
            for (i in 0 until totalChunks) {
                val start = i * chunkSize
                val end = kotlin.math.min(rawBytes.size, (i + 1) * chunkSize)
                val chunkSlice = String(rawBytes.copyOfRange(start, end), StandardCharsets.UTF_8)
                val chunkString = "$CHUNK_PREFIX$msgId:$i:$totalChunks:$chunkSlice"
                chunks.add(chunkString.toByteArray(StandardCharsets.UTF_8))
            }
        } else {
            chunks.add(rawBytes)
        }

        // Forward to all reachable discovered peers
        for (peer in discoveredPeers.values) {
            if (peer.bluetoothAddress == excludeAddress) continue

            val device = bluetoothAdapter?.getRemoteDevice(peer.bluetoothAddress) ?: continue
            try {
                device.connectGatt(context, false, object : BluetoothGattCallback() {
                    override fun onConnectionStateChange(gatt: BluetoothGatt?, status: Int, newState: Int) {
                        if (newState == BluetoothProfile.STATE_CONNECTED) {
                            logEvent("GATT_CONNECTED", mapOf("peer_id" to peer.deviceId, "address" to peer.bluetoothAddress))
                            try {
                                gatt?.requestMtu(DEFAULT_MTU)
                            } catch (e: SecurityException) {
                                gatt?.discoverServices()
                            }
                        } else if (newState == BluetoothProfile.STATE_DISCONNECTED) {
                            logEvent("GATT_DISCONNECTED", mapOf("peer_id" to peer.deviceId))
                            try {
                                gatt?.close()
                            } catch (_: SecurityException) {}
                        }
                    }

                    override fun onMtuChanged(gatt: BluetoothGatt?, mtu: Int, status: Int) {
                        try {
                            gatt?.discoverServices()
                        } catch (e: SecurityException) {
                            Log.e(TAG, "discoverServices error: ${e.message}")
                        }
                    }

                    override fun onServicesDiscovered(gatt: BluetoothGatt?, status: Int) {
                        if (status == BluetoothGatt.GATT_SUCCESS) {
                            val service = gatt?.getService(MESH_SERVICE_UUID)
                            val rxChar = service?.getCharacteristic(RX_CHAR_UUID)
                            if (rxChar != null) {
                                rxChar.writeType = BluetoothGattCharacteristic.WRITE_TYPE_NO_RESPONSE
                                for (chunk in chunks) {
                                    rxChar.value = chunk
                                    try {
                                        gatt.writeCharacteristic(rxChar)
                                        Thread.sleep(25) // Small pause between frames
                                    } catch (e: SecurityException) {
                                        Log.e(TAG, "writeCharacteristic error: ${e.message}")
                                    }
                                }
                                logEvent("PACKET_FORWARDED", mapOf(
                                    "message_id" to packet.optString("message_id"),
                                    "target_peer" to peer.deviceId
                                ))
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
    // 5. INTERNET GATEWAY & STORE-AND-FORWARD FLUSH
    // ==========================================

    private fun isInternetAvailable(): Boolean {
        val cm = context.getSystemService(Context.CONNECTIVITY_SERVICE) as? ConnectivityManager ?: return false
        val network = cm.activeNetwork ?: return false
        val caps = cm.getNetworkCapabilities(network) ?: return false
        return caps.hasCapability(NetworkCapabilities.NET_CAPABILITY_INTERNET)
    }

    fun flushStoreAndForwardQueue() {
        if (!isInternetAvailable() || storeAndForwardQueue.isEmpty()) return

        Thread {
            while (!storeAndForwardQueue.isEmpty()) {
                val packet = storeAndForwardQueue.peek() ?: break
                val success = uploadPacketDirectly(packet)
                if (success) {
                    storeAndForwardQueue.poll()
                    logEvent("BACKEND_ACK_RECEIVED", mapOf(
                        "message_id" to packet.optString("message_id"),
                        "remaining_queue" to storeAndForwardQueue.size
                    ))
                } else {
                    // Delay retry
                    try { Thread.sleep(2000) } catch (_: InterruptedException) {}
                    break
                }
            }
        }.start()
    }

    private fun relayPacketToBackend(packet: JSONObject) {
        Thread {
            val ok = uploadPacketDirectly(packet)
            if (!ok) {
                // If upload failed, queue for store-and-forward retry
                storeAndForwardQueue.add(packet)
                logEvent("PACKET_QUEUED", mapOf(
                    "message_id" to packet.optString("message_id"),
                    "reason" to "HTTP_UPLOAD_FAILED",
                    "queue_size" to storeAndForwardQueue.size
                ))
            }
        }.start()
    }

    private fun uploadPacketDirectly(packet: JSONObject): Boolean {
        return try {
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
                put("source_driver_id", packet.optString("source_driver_id", myDriverId))
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
            val success = code in 200..299
            if (success) {
                logEvent("MESH_PACKET_UPLOADED", mapOf(
                    "message_id" to packet.optString("message_id"),
                    "http_status" to code,
                    "bridge_device" to myDeviceId
                ))
            }
            conn.disconnect()
            success
        } catch (e: Exception) {
            Log.w(TAG, "Mesh internet upload attempt: ${e.message}")
            false
        }
    }

    // ==========================================
    // 6. OBSERVABILITY & STATUS REPORTING
    // ==========================================

    private fun logEvent(eventType: String, details: Map<String, Any>) {
        val jsonDetails = JSONObject(details).toString()
        Log.i(TAG, "[$eventType] $jsonDetails")
        mainHandler.post {
            channel.invokeMethod("onBleEvent", mapOf("event" to eventType, "details" to details))
        }
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

    fun getMeshStatus(): Map<String, Any> {
        return mapOf(
            "is_running" to isRunning,
            "is_advertising" to isAdvertising,
            "is_scanning" to isScanning,
            "is_gateway" to isInternetAvailable(),
            "peer_count" to discoveredPeers.size,
            "queue_size" to storeAndForwardQueue.size,
            "device_id" to myDeviceId,
            "driver_id" to myDriverId
        )
    }
}
