package com.swarmroute.mobile_app

import io.flutter.embedding.android.FlutterActivity
import io.flutter.embedding.engine.FlutterEngine
import io.flutter.plugin.common.MethodChannel

class MainActivity : FlutterActivity() {
    private val CHANNEL = "com.swarmroute/ble_mesh"
    private var bleMeshEngine: BleMeshEngine? = null

    override fun configureFlutterEngine(flutterEngine: FlutterEngine) {
        super.configureFlutterEngine(flutterEngine)

        val channel = MethodChannel(flutterEngine.dartExecutor.binaryMessenger, CHANNEL)
        bleMeshEngine = BleMeshEngine(context, channel)

        channel.setMethodCallHandler { call, result ->
            when (call.method) {
                "startMesh" -> {
                    val deviceId = call.argument<String>("deviceId") ?: "DEV_UNKNOWN"
                    val driverId = call.argument<String>("driverId") ?: "DRIVER_UNKNOWN"
                    val backendUrl = call.argument<String>("backendUrl") ?: "http://10.0.2.2:8000"
                    val started = bleMeshEngine?.startMesh(deviceId, driverId, backendUrl) ?: false
                    result.success(started)
                }
                "stopMesh" -> {
                    bleMeshEngine?.stopMesh()
                    result.success(true)
                }
                "broadcastPacket" -> {
                    val packetJson = call.argument<String>("packet") ?: "{}"
                    val ok = bleMeshEngine?.broadcastPacket(packetJson) ?: false
                    result.success(ok)
                }
                "getDiscoveredPeers" -> {
                    val peers = bleMeshEngine?.getDiscoveredPeers() ?: emptyList<Map<String, Any>>()
                    result.success(peers)
                }
                "getMeshStatus" -> {
                    val status = bleMeshEngine?.getMeshStatus() ?: emptyMap<String, Any>()
                    result.success(status)
                }
                "flushGatewayQueue" -> {
                    bleMeshEngine?.flushStoreAndForwardQueue()
                    result.success(true)
                }
                else -> {
                    result.notImplemented()
                }
            }
        }
    }
}
