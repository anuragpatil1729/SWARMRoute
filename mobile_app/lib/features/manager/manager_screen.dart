import 'package:flutter/material.dart';
import '../../models/partner_model.dart';
import '../../models/order_model.dart';
import '../../services/api_service.dart';
import '../auth/login_screen.dart';

class ManagerScreen extends StatefulWidget {
  const ManagerScreen({super.key});

  @override
  State<ManagerScreen> createState() => _ManagerScreenState();
}

class _ManagerScreenState extends State<ManagerScreen> with SingleTickerProviderStateMixin {
  final ApiService _api = ApiService();
  late TabController _tabController;

  List<PartnerModel> _fleet = [];
  List<OrderModel> _orders = [];
  bool _isLoading = false;

  @override
  void initState() {
    super.initState();
    _tabController = TabController(length: 2, vsync: this);
    _refreshData();
  }

  Future<void> _refreshData() async {
    setState(() => _isLoading = true);
    try {
      final fleetFuture = _api.getLiveFleet();
      final ordersFuture = _api.getCustomerOrders('ALL');
      final res = await Future.wait([fleetFuture, ordersFuture]);
      setState(() {
        _fleet = res[0] as List<PartnerModel>;
        _orders = res[1] as List<OrderModel>;
      });
    } catch (e) {
      debugPrint('[ManagerScreen] Refresh error: $e');
    }
    setState(() => _isLoading = false);
  }

  Future<void> _requestAiRecommendation(String orderId) async {
    setState(() => _isLoading = true);
    try {
      final rec = await _api.getAiRecommendation(orderId);
      if (!mounted) return;
      _showAiRecommendationDialog(orderId, rec);
    } catch (e) {
      if (!mounted) return;
      ScaffoldMessenger.of(context).showSnackBar(SnackBar(content: Text('AI Recommendation error: $e')));
    }
    setState(() => _isLoading = false);
  }

  void _showAiRecommendationDialog(String orderId, Map<String, dynamic> rec) {
    final best = rec['recommended_partner'] as Map<String, dynamic>?;
    showDialog(
      context: context,
      builder: (ctx) => AlertDialog(
        title: const Row(
          children: [
            Icon(Icons.auto_awesome, color: Colors.amber),
            SizedBox(width: 8),
            Text('AI Dispatch Recommendation'),
          ],
        ),
        content: best != null
            ? Column(
                mainAxisSize: MainAxisSize.min,
                crossAxisAlignment: CrossAxisAlignment.start,
                children: [
                  Text('Recommended Partner: ${best['partner_name']} (${best['partner_id']})',
                      style: const TextStyle(fontWeight: FontWeight.bold)),
                  const SizedBox(height: 8),
                  Text('Suitability Score: ${best['suitability_score']} / 100'),
                  Text('Proximity: ${best['metrics']?['distance_to_pickup_km']} km to pickup'),
                  Text('Spare Payload: ${best['metrics']?['spare_capacity_kg']} kg'),
                  Text('Fuel Level: ${best['metrics']?['fuel_level_pct']}%'),
                  const SizedBox(height: 8),
                  Text('Reason: ${best['recommendation_reason']}',
                      style: const TextStyle(fontStyle: FontStyle.italic, color: Colors.blueGrey)),
                ],
              )
            : const Text('No active delivery partners currently available for allocation.'),
        actions: [
          TextButton(onPressed: () => Navigator.pop(ctx), child: const Text('Cancel')),
          if (best != null)
            ElevatedButton(
              onPressed: () async {
                Navigator.pop(ctx);
                await _api.allocateOrder(orderId, best['partner_id']);
                if (!mounted) return;
                ScaffoldMessenger.of(context).showSnackBar(
                  SnackBar(content: Text('Order #$orderId allocated to ${best['partner_id']}')),
                );
                await _refreshData();
              },
              style: ElevatedButton.styleFrom(backgroundColor: const Color(0xFF0284C7), foregroundColor: Colors.white),
              child: const Text('Approve & Allocate'),
            ),
        ],
      ),
    );
  }

  @override
  Widget build(BuildContext context) {
    return Scaffold(
      backgroundColor: const Color(0xFFF8FAFC),
      appBar: AppBar(
        backgroundColor: Colors.white,
        elevation: 1,
        title: const Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Text('Fleet Operations Command', style: TextStyle(fontSize: 16, fontWeight: FontWeight.bold, color: Color(0xFF0F172A))),
            Text('Operations Manager Console • Real-Time', style: TextStyle(fontSize: 11, color: Color(0xFF64748B))),
          ],
        ),
        actions: [
          IconButton(icon: const Icon(Icons.refresh), onPressed: _isLoading ? null : _refreshData),
          IconButton(
            icon: const Icon(Icons.logout),
            onPressed: () {
              Navigator.pushReplacement(context, MaterialPageRoute(builder: (_) => const LoginScreen()));
            },
          ),
        ],
        bottom: TabBar(
          controller: _tabController,
          labelColor: const Color(0xFF0284C7),
          unselectedLabelColor: const Color(0xFF64748B),
          indicatorColor: const Color(0xFF0284C7),
          tabs: [
            Tab(text: 'Fleet (${_fleet.length})', icon: const Icon(Icons.local_shipping_outlined, size: 18)),
            Tab(text: 'Live Orders (${_orders.length})', icon: const Icon(Icons.assignment_outlined, size: 18)),
          ],
        ),
      ),
      body: TabBarView(
        controller: _tabController,
        children: [
          // Fleet List Tab
          RefreshIndicator(
            onRefresh: _refreshData,
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: _fleet.length,
              itemBuilder: (ctx, i) => _buildFleetCard(_fleet[i]),
            ),
          ),

          // Orders List Tab
          RefreshIndicator(
            onRefresh: _refreshData,
            child: ListView.builder(
              padding: const EdgeInsets.all(12),
              itemCount: _orders.length,
              itemBuilder: (ctx, i) => _buildOrderCard(_orders[i]),
            ),
          ),
        ],
      ),
    );
  }

  Widget _buildFleetCard(PartnerModel p) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('${p.name} (${p.partnerId})', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 15)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 3),
                  decoration: BoxDecoration(
                    color: p.status == 'IDLE' ? Colors.blue.shade50 : Colors.green.shade50,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    p.status,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: p.status == 'IDLE' ? Colors.blue : Colors.green,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text(
              '${p.vehicle.manufacturer} ${p.vehicle.modelName} (${p.vehicle.modelYear}) • ${p.vehicle.engineType}',
              style: const TextStyle(fontSize: 12, color: Color(0xFF475569)),
            ),
            const Divider(height: 16),
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                _buildMetric('Fuel', '${p.vehicle.fuelRemaining.toStringAsFixed(0)}%'),
                _buildMetric('Load', '${p.vehicle.currentLoad}/${p.vehicle.maxLoad} kg'),
                _buildMetric('BLE Mesh', '${p.bleStatus} (${p.blePeerCount} peers)'),
                _buildMetric('Net', p.internetStatus),
              ],
            ),
          ],
        ),
      ),
    );
  }

  Widget _buildOrderCard(OrderModel o) {
    return Card(
      margin: const EdgeInsets.only(bottom: 12),
      elevation: 0,
      shape: RoundedRectangleBorder(
        borderRadius: BorderRadius.circular(12),
        side: const BorderSide(color: Color(0xFFE2E8F0)),
      ),
      child: Padding(
        padding: const EdgeInsets.all(16),
        child: Column(
          crossAxisAlignment: CrossAxisAlignment.start,
          children: [
            Row(
              mainAxisAlignment: MainAxisAlignment.spaceBetween,
              children: [
                Text('#${o.id}', style: const TextStyle(fontWeight: FontWeight.bold, fontSize: 14)),
                Container(
                  padding: const EdgeInsets.symmetric(horizontal: 8, vertical: 2),
                  decoration: BoxDecoration(
                    color: o.status == 'PENDING' ? Colors.orange.shade50 : Colors.blue.shade50,
                    borderRadius: BorderRadius.circular(6),
                  ),
                  child: Text(
                    o.status,
                    style: TextStyle(
                      fontSize: 11,
                      fontWeight: FontWeight.bold,
                      color: o.status == 'PENDING' ? Colors.orange : Colors.blue,
                    ),
                  ),
                ),
              ],
            ),
            const SizedBox(height: 6),
            Text('To: ${o.deliveryAddress}', style: const TextStyle(fontSize: 12)),
            Text('Weight: ${o.demandWeight} kg • Road Distance: ${o.estimatedDistanceKm.toStringAsFixed(1)} km',
                style: const TextStyle(fontSize: 11, color: Color(0xFF64748B))),
            if (o.status == 'PENDING') ...[
              const SizedBox(height: 10),
              SizedBox(
                width: double.infinity,
                child: OutlinedButton.icon(
                  onPressed: () => _requestAiRecommendation(o.id),
                  icon: const Icon(Icons.auto_awesome, size: 16),
                  label: const Text('AI Recommend Partner'),
                  style: OutlinedButton.styleFrom(foregroundColor: const Color(0xFF0284C7)),
                ),
              ),
            ],
          ],
        ),
      ),
    );
  }

  Widget _buildMetric(String label, String value) {
    return Column(
      crossAxisAlignment: CrossAxisAlignment.start,
      children: [
        Text(label, style: const TextStyle(fontSize: 10, color: Color(0xFF94A3B8))),
        Text(value, style: const TextStyle(fontSize: 12, fontWeight: FontWeight.bold, color: Color(0xFF0F172A))),
      ],
    );
  }
}
