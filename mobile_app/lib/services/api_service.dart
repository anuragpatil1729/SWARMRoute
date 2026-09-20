import 'dart:convert';
import 'package:http/http.dart' as http;
import '../core/api_config.dart';
import '../models/order_model.dart';
import '../models/partner_model.dart';
import '../models/ble_packet_model.dart';

class ApiService {
  final http.Client _client = http.Client();

  Future<Map<String, dynamic>> createOrder({
    required String customerId,
    required String customerName,
    required String pickupAddress,
    required double pickupLat,
    required double pickupLon,
    required String deliveryAddress,
    required double deliveryLat,
    required double deliveryLon,
    required double demandWeight,
    String priority = 'NORMAL',
  }) async {
    final res = await _client.post(
      Uri.parse(ApiConfig.orders),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'customer_id': customerId,
        'customer_name': customerName,
        'pickup_address': pickupAddress,
        'pickup_lat': pickupLat,
        'pickup_lon': pickupLon,
        'delivery_address': deliveryAddress,
        'delivery_lat': deliveryLat,
        'delivery_lon': deliveryLon,
        'demand_weight': demandWeight,
        'priority': priority,
      }),
    );
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    throw Exception('Failed to create order: ${res.statusCode}');
  }

  Future<Map<String, dynamic>> trackOrder(String orderId) async {
    final res = await _client.get(Uri.parse(ApiConfig.trackOrder(orderId)));
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    throw Exception('Failed to track order: ${res.statusCode}');
  }

  Future<List<OrderModel>> getCustomerOrders(String customerId) async {
    final res = await _client.get(Uri.parse(ApiConfig.customerOrders(customerId)));
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body);
      final list = (data['orders'] as List?) ?? [];
      return list.map((o) => OrderModel.fromJson(o)).toList();
    }
    return [];
  }

  Future<List<PartnerModel>> getLiveFleet() async {
    final res = await _client.get(Uri.parse(ApiConfig.liveFleet));
    if (res.statusCode == 200) {
      final data = jsonDecode(res.body);
      final list = (data['fleet'] as List?) ?? [];
      return list.map((p) => PartnerModel.fromJson(p)).toList();
    }
    return [];
  }

  Future<Map<String, dynamic>> getAiRecommendation(String orderId) async {
    final res = await _client.post(
      Uri.parse(ApiConfig.dispatchRecommend),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'order_id': orderId}),
    );
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    throw Exception('AI recommendation error: ${res.statusCode}');
  }

  Future<bool> allocateOrder(String orderId, String vehicleId) async {
    final res = await _client.post(
      Uri.parse(ApiConfig.dispatchAllocate),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'order_id': orderId, 'vehicle_id': vehicleId}),
    );
    return res.statusCode == 200;
  }

  Future<Map<String, dynamic>> sendDriverTelemetry({
    required String vehicleId,
    required double latitude,
    required double longitude,
    required double speedKmh,
    required double heading,
    required double fuelLevel,
    required double vehicleCondition,
    required String internetStatus,
    required String bleStatus,
    required int blePeerCount,
    required double remainingDistanceKm,
  }) async {
    final res = await _client.post(
      Uri.parse(ApiConfig.driverTelemetry),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({
        'vehicle_id': vehicleId,
        'latitude': latitude,
        'longitude': longitude,
        'speed_kmh': speedKmh,
        'heading': heading,
        'accuracy': 5.0,
        'fuel_level': fuelLevel,
        'vehicle_condition': vehicleCondition,
        'internet_status': internetStatus,
        'ble_status': bleStatus,
        'ble_peer_count': blePeerCount,
        'remaining_distance_km': remainingDistanceKm,
      }),
    );
    if (res.statusCode == 200) {
      return jsonDecode(res.body);
    }
    throw Exception('Telemetry upload failed: ${res.statusCode}');
  }

  Future<bool> updateOrderStatus(String orderId, String status, {String? vehicleId}) async {
    final res = await _client.post(
      Uri.parse(ApiConfig.updateOrderStatus(orderId)),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode({'status': status, 'vehicle_id': vehicleId}),
    );
    return res.statusCode == 200;
  }

  Future<bool> relayMeshPacket(BlePacketModel packet) async {
    final res = await _client.post(
      Uri.parse(ApiConfig.meshRelay),
      headers: {'Content-Type': 'application/json'},
      body: jsonEncode(packet.toJson()),
    );
    return res.statusCode == 200;
  }
}
