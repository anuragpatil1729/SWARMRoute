class OrderModel {
  final String id;
  final String customerId;
  final String customerName;
  final String pickupAddress;
  final double pickupLat;
  final double pickupLon;
  final String deliveryAddress;
  final double deliveryLat;
  final double deliveryLon;
  final double demandWeight;
  final String priority;
  final String status;
  final String? assignedVehicleId;
  final double estimatedDistanceKm;
  final double estimatedEtaMins;
  final double createdAt;

  OrderModel({
    required this.id,
    required this.customerId,
    required this.customerName,
    required this.pickupAddress,
    required this.pickupLat,
    required this.pickupLon,
    required this.deliveryAddress,
    required this.deliveryLat,
    required this.deliveryLon,
    required this.demandWeight,
    required this.priority,
    required this.status,
    this.assignedVehicleId,
    required this.estimatedDistanceKm,
    required this.estimatedEtaMins,
    required this.createdAt,
  });

  factory OrderModel.fromJson(Map<String, dynamic> json) {
    return OrderModel(
      id: json['id']?.toString() ?? '',
      customerId: json['customer_id']?.toString() ?? 'CUST_01',
      customerName: json['customer_name']?.toString() ?? 'Customer',
      pickupAddress: json['pickup_address']?.toString() ?? '',
      pickupLat: (json['pickup_lat'] as num?)?.toDouble() ?? 0.0,
      pickupLon: (json['pickup_lon'] as num?)?.toDouble() ?? 0.0,
      deliveryAddress: json['delivery_address']?.toString() ?? json['address']?.toString() ?? '',
      deliveryLat: (json['delivery_lat'] as num?)?.toDouble() ?? 0.0,
      deliveryLon: (json['delivery_lon'] as num?)?.toDouble() ?? 0.0,
      demandWeight: (json['demand_weight'] as num?)?.toDouble() ?? (json['demand'] as num?)?.toDouble() ?? 1.0,
      priority: json['priority']?.toString() ?? 'NORMAL',
      status: json['status']?.toString() ?? 'PENDING',
      assignedVehicleId: json['assigned_vehicle_id']?.toString(),
      estimatedDistanceKm: (json['estimated_distance_km'] as num?)?.toDouble() ?? 0.0,
      estimatedEtaMins: (json['estimated_eta_mins'] as num?)?.toDouble() ?? 30.0,
      createdAt: (json['created_at'] as num?)?.toDouble() ?? 0.0,
    );
  }

  Map<String, dynamic> toJson() {
    return {
      'id': id,
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
      'status': status,
      'assigned_vehicle_id': assignedVehicleId,
      'estimated_distance_km': estimatedDistanceKm,
      'estimated_eta_mins': estimatedEtaMins,
      'created_at': createdAt,
    };
  }
}
