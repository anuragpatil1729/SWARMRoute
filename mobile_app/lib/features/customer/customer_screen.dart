import 'package:flutter/material.dart';
import 'package:flutter_map/flutter_map.dart';
import 'package:latlong2/latlong.dart';
import '../../models/order_model.dart';
import '../../services/api_service.dart';
import '../../services/routing_service.dart';
import '../auth/login_screen.dart';

class CustomerScreen extends StatefulWidget {
  final String customerId;
  final String customerName;

  const CustomerScreen({
    super.key,
    required this.customerId,
    required this.customerName,
  });

  @override
  State<CustomerScreen> createState() => _CustomerScreenState();
}

class _CustomerScreenState extends State<CustomerScreen> {
  final ApiService _api = ApiService();
  final RoutingService _routing = RoutingService();
  final MapController _mapController = MapController();

  List<OrderModel> _orders = [];
  OrderModel? _selectedOrder;
  Map<String, dynamic>? _trackingData;
  List<LatLng> _routePoints = [];
  bool _isLoading = false;

  // New Order Creation Form
  final _pickupController = TextEditingController(text: 'BKC Freight Gateway, Mumbai');
  final _deliveryController = TextEditingController(text: 'Hinjawadi Phase 1 Hub, Pune');
  final _weightController = TextEditingController(text: '15.0');
  final LatLng _pickupCoord = const LatLng(19.0674, 72.8689);
  final LatLng _deliveryCoord = const LatLng(18.5913, 73.7389);

  @override
  void initState() {
    super.initState();
    _loadOrders();
  }

  Future<void> _loadOrders() async {
    setState(() => _isLoading = true);
    try {
      final list = await _api.getCustomerOrders(widget.customerId);
      setState(() {
        _orders = list;
        if (_orders.isNotEmpty && _selectedOrder == null) {
          _selectOrder(_orders.first);
        }
      });
    } catch (_) {}
    setState(() => _isLoading = false);
  }

  Future<void> _selectOrder(OrderModel order) async {
    setState(() {
      _selectedOrder = order;
      _isLoading = true;
    });

    try {
      final track = await _api.trackOrder(order.id);
      _trackingData = track;

      final p1 = LatLng(order.pickupLat, order.pickupLon);
      final p2 = LatLng(order.deliveryLat, order.deliveryLon);
      final res = await _routing.getRoadRoute(p1, p2);

      setState(() {
        _routePoints = res.points;
      });

      if (_routePoints.isNotEmpty) {
        _mapController.move(p1, 13.0);
      }
    } catch (_) {}
    setState(() => _isLoading = false);
  }

  Future<void> _createNewOrder() async {
    final weight = double.tryParse(_weightController.text) ?? 1.0;
    setState(() => _isLoading = true);
    try {
      final res = await _api.createOrder(
        customerId: widget.customerId,
        customerName: widget.customerName,
        pickupAddress: _pickupController.text,
        pickupLat: _pickupCoord.latitude,
        pickupLon: _pickupCoord.longitude,
        deliveryAddress: _deliveryController.text,
        deliveryLat: _deliveryCoord.latitude,
        deliveryLon: _deliveryCoord.longitude,
        demandWeight: weight,
      );
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Order Created: ${res['order']?['id']}')),
      );
      await _loadOrders();
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(
        SnackBar(content: Text('Error: $e')),
      );
    }
    setState(() => _isLoading = false);
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 1,
        title: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            const Text(
              'SWARMRoute Customer Portal',
              style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF0F172A)),
            ),
            Text(
              'Authenticated as ${widget.customerName} (${widget.customerId})',
              style: const TextStyle(fontSize: 11, color: Color(0xFF64748B)),
            ),
          ],
        ),
        actions: [
          IconButton(
            icon: const Icon(Icons.logout_rounded, color: Color(0xFF64748B)),
            onPressed: () {
              Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
            },
          ),
        ],
      ),
      body: Column(
        children: [
          // OpenStreetMap Basemap
          Expanded(
            flex: 3,
            child: FlutterMap(
              mapController: _mapController,
              options: MapOptions(
                initialCenter: _pickupCoord,
                initialZoom: 13.0,
              ),
              children: [
                TileLayer(
                  urlTemplate: 'https://tile.openstreetmap.org/{z}/{x}/{y}.png',
                  userAgentPackageName: 'com.swarmroute.mobile_app',
                ),
                if (_routePoints.isNotEmpty)
                  PolylineLayer(
                    polylines: [
                      Polyline(
                        points: _routePoints,
                        strokeWidth: 4.5,
                        color: const Color(0xFF0284C7),
                      ),
                    ],
                  ),
                MarkerLayer(
                  markers: [
                    Marker(
                      point: _pickupCoord,
                      width: 40,
                      height: 40,
                      child: const Icon(Icons.store_mall_directory_rounded, color: Colors.indigo, size: 32),
                    ),
                    Marker(
                      point: _deliveryCoord,
                      width: 40,
                      height: 40,
                      child: const Icon(Icons.location_pin, color: Colors.redAccent, size: 34),
                    ),
                    if (_trackingData?['driver_telemetry'] != null)
                      Marker(
                        point: LatLng(
                          (_trackingData!['driver_telemetry']['latitude'] as num).toDouble(),
                          (_trackingData!['driver_telemetry']['longitude'] as num).toDouble(),
                        ),
                        width: 44,
                        height: 44,
                        child: Container(
                          decoration: const BoxDecoration(
                            color: Colors.green,
                            shape: BoxShape.circle,
                          ),
                          child: const Icon(Icons.delivery_dining_rounded, color: Colors.white, size: 24),
                        ),
                      ),
                  ],
                ),
              ],
            ),
          ),

          // Order Tracking & Actions Sheet
          Expanded(
            flex: 4,
            child: Container(
              padding: const EdgeInsets.all(16),
              decoration: const BoxDecoration(
                color: Colors.white,
                borderRadius: BorderRadius.vertical(top: Radius.circular(20)),
                boxShadow: [
                  BoxShadow(color: Colors.black12, blurRadius: 10, offset: Offset(0, -4)),
                ],
              ),
              child: SingleChildScrollView(
                child: Column(
                  crossAxisAlignment: CrossAxisAlignment.start,
                  children: [
                    Row(
                      mainAxisAlignment: MainAxisAlignment.spaceBetween,
                      children: [
                        Text(
                          _selectedOrder != null ? 'Tracking #${_selectedOrder!.id}' : 'No Orders Placed',
                          style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 16),
                        ),
                        if (_selectedOrder != null)
                          Container(
                            padding: const EdgeInsets.symmetric(horizontal: 10, vertical: 4),
                            decoration: BoxDecoration(
                              color: _selectedOrder!.status == 'DELIVERED'
                                  ? Colors.green.shade50
                                  : Colors.blue.shade50,
                              borderRadius: BorderRadius.circular(8),
                            ),
                            child: Text(
                              _selectedOrder!.status,
                              style: TextStyle(
                                fontSize: 12,
                                fontWeight: FontWeight.bold,
                                color: _selectedOrder!.status == 'DELIVERED' ? Colors.green : Colors.blue,
                              ),
                            ),
                          ),
                      ],
                    ),
                    const SizedBox(height: 12),

                    if (_selectedOrder != null) ...[
                      _buildInfoRow('Pickup', _selectedOrder!.pickupAddress),
                      _buildInfoRow('Delivery', _selectedOrder!.deliveryAddress),
                      _buildInfoRow('Distance', '${_selectedOrder!.estimatedDistanceKm.toStringAsFixed(1)} km (OSRM Road Network)'),
                      _buildInfoRow('ETA', '${_selectedOrder!.estimatedEtaMins.toStringAsFixed(0)} mins'),
                      _buildInfoRow('Driver', _selectedOrder!.assignedVehicleId ?? 'Awaiting Dispatch'),
                      const Divider(height: 24),
                    ],

                    // Order Creation Expander
                    ExpansionTile(
                      title: const Text('Create New Parcel Order', style: TextStyle(fontSize: 14, fontWeight: FontWeight.bold)),
                      initiallyExpanded: _orders.isEmpty,
                      children: [
                        TextField(
                          controller: _pickupController,
                          decoration: const InputDecoration(labelText: 'Pickup Address', prefixIcon: Icon(Icons.home)),
                        ),
                        const SizedBox(height: 8),
                        TextField(
                          controller: _deliveryController,
                          decoration: const InputDecoration(labelText: 'Delivery Address', prefixIcon: Icon(Icons.pin_drop)),
                        ),
                        const SizedBox(height: 8),
                        TextField(
                          controller: _weightController,
                          keyboardType: TextInputType.number,
                          decoration: const InputDecoration(labelText: 'Parcel Weight (kg)', prefixIcon: Icon(Icons.scale)),
                        ),
                        const SizedBox(height: 12),
                        SizedBox(
                          width: double.infinity,
                          child: ElevatedButton.icon(
                            onPressed: _isLoading ? null : _createNewOrder,
                            icon: const Icon(Icons.add_shopping_cart),
                            label: const Text('Place Live Order'),
                            style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0284C7), foregroundColor: Colors.white),
                          ),
                        ),
                      ],
                    ),
                  ],
                ),
              ),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildInfoRow(String label, String value) {
    return Padding(
      padding: const EdgeInsets.symmetric(vertical: 3.0),
      child: Row(
        crossAxisAlignment: CrossAxisAlignment.start,
        children: [
          SizedBox(
            width: 75,
            child: Text(label, style: const TextStyle(fontSize: 12, color: Color(0xFF64748B))),
          ),
          Expanded(
            child: Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.w600, color: Color(0xFF0F172A))),
          ),
        ],
      ),
    );
  }
}
