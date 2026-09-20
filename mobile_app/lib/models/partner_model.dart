import 'vehicle_model.dart';

class PartnerModel {
  final String partnerId;
  final String name;
  final String phone;
  final String status;
  final VehicleModel vehicle;
  final double? latitude;
  final double? longitude;
  final String locationSource;
  final double speedKmh;
  final String internetStatus;
  final String bleStatus;
  final int blePeerCount;
  final List<String> assignedOrders;

  PartnerModel({
    required this.partnerId,
    required this.name,
    required this.phone,
    required this.status,
    required this.vehicle,
    this.latitude,
    this.longitude,
    required this.locationSource,
    required this.speedKmh,
    required this.internetStatus,
    required this.bleStatus,
    required this.blePeerCount,
    required this.assignedOrders,
  });

  factory PartnerModel.fromJson(Map<String, dynamic> json) {
    final loc = json['location'] as Map<String, dynamic>? ?? {};
    final veh = json['vehicle'] as Map<String, dynamic>? ?? {};
    final ordersList = (json['assigned_orders'] as List?)?.map((e) => e.toString()).toList() ?? [];

    final lat = (loc['latitude'] as num?)?.toDouble();
    final lon = (loc['longitude'] as num?)?.toDouble();
    final source = loc['source']?.toString() ?? (lat != null ? 'REAL_GPS' : 'NO_GPS');

    return PartnerModel(
      partnerId: json['partner_id']?.toString() ?? '',
      name: json['name']?.toString() ?? '',
      phone: json['phone']?.toString() ?? '',
      status: json['status']?.toString() ?? 'IDLE',
      vehicle: VehicleModel.fromJson(veh),
      latitude: lat,
      longitude: lon,
      locationSource: source,
      speedKmh: (json['speed_kmh'] as num?)?.toDouble() ?? 0.0,
      internetStatus: json['internet_status']?.toString() ?? 'ONLINE',
      bleStatus: json['ble_status']?.toString() ?? 'ACTIVE',
      blePeerCount: (json['ble_peer_count'] as num?)?.toInt() ?? 0,
      assignedOrders: ordersList,
    );
  }
}

