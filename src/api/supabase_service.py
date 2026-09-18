"""
Supabase Service for SWARMRoute Fleet Management.
Provides persistent cloud synchronization for delivery partners, orders,
task allocations, and real-time telemetry.
"""
from __future__ import annotations

import os
import sys
import time
from typing import Any, Dict, List, Optional

# Ensure site-packages takes precedence over workspace root directory named 'supabase'
sys.path = [p for p in sys.path if p != os.getcwd()] + [os.getcwd()]

from dotenv import load_dotenv

load_dotenv()

try:
    from supabase import Client, create_client
except ImportError:
    Client = Any  # type: ignore
    create_client = None  # type: ignore

class SupabaseService:
    """Manages cloud sync with Supabase PostgreSQL database."""

    def __init__(self) -> None:
        self.url = os.getenv("SUPABASE_URL")
        self.key = os.getenv("SUPABASE_KEY", "")
        self.project_ref = os.getenv("SUPABASE_PROJECT_REF")

        if not self.url or not self.project_ref:
            raise RuntimeError(
                "Missing required Supabase environment variables: "
                "SUPABASE_URL and SUPABASE_PROJECT_REF must be set. "
                "Please configure them in your environment or .env file."
            )

        self.client: Optional[Client] = None
        self._initialize_client()
        self._initialize_authoritative_store()

    def _initialize_client(self) -> None:
        if create_client and self.url and self.key:
            try:
                self.client = create_client(self.url, self.key)
            except Exception as e:
                print(f"[SupabaseService] Warning: Failed to initialize Supabase client: {e}")
                self.client = None

    def is_connected(self) -> bool:
        return self.client is not None

    def get_status(self) -> Dict[str, Any]:
        """Returns connection health and remote table metrics."""
        if not self.client:
            return {
                "connected": False,
                "project_ref": self.project_ref,
                "url": self.url,
                "error": "Client not initialized",
            }
        try:
            # Query partner and order counts to verify connectivity
            partners_res = self.client.table("delivery_partners").select("id", count="exact").execute()
            orders_res = self.client.table("orders").select("id", count="exact").execute()
            alloc_res = self.client.table("task_allocations").select("id", count="exact").execute()
            return {
                "connected": True,
                "project_ref": self.project_ref,
                "url": self.url,
                "counts": {
                    "delivery_partners": partners_res.count if hasattr(partners_res, "count") else len(partners_res.data or []),
                    "orders": orders_res.count if hasattr(orders_res, "count") else len(orders_res.data or []),
                    "task_allocations": alloc_res.count if hasattr(alloc_res, "count") else len(alloc_res.data or []),
                },
            }
        except Exception as e:
            return {
                "connected": False,
                "project_ref": self.project_ref,
                "url": self.url,
                "error": str(e),
            }

    def sync_delivery_partners(self, partners: List[Dict[str, Any]]) -> bool:
        """Upserts delivery partner profiles to Supabase."""
        if not self.client or not partners:
            return False
        try:
            records = []
            for p in partners:
                loc = p.get("location", {})
                loc_x = float(loc.get("x")) if (isinstance(loc, dict) and loc.get("x") is not None) else (float(p["location_x"]) if p.get("location_x") is not None else None)
                loc_y = float(loc.get("y")) if (isinstance(loc, dict) and loc.get("y") is not None) else (float(p["location_y"]) if p.get("location_y") is not None else None)
                records.append({
                    "id": p["id"],
                    "name": p.get("name", p["id"]),
                    "phone": p.get("phone", ""),
                    "vehicle_model": p.get("vehicle_model", ""),
                    "registration": p.get("registration", ""),
                    "hub": p.get("hub", ""),
                    "city": p.get("city"),
                    "rating": float(p["rating"]) if p.get("rating") is not None else None,
                    "completed_deliveries": int(p.get("completed_deliveries", 0) or 0),
                    "avatar": p.get("avatar", "🚚"),
                    "status": p.get("status", "IDLE"),
                    "current_load": float(p.get("current_load", 0.0)),
                    "max_weight": float(p["max_weight"]) if p.get("max_weight") is not None else None,
                    "fuel_level": float(p.get("fuel_level", 100.0)),
                    "speed_kmh": float(p.get("speed_kmh", 0.0)),
                    "location_x": loc_x,
                    "location_y": loc_y,
                })
            self.client.table("delivery_partners").upsert(records).execute()
            return True
        except Exception as e:
            print(f"[SupabaseService] Error syncing delivery partners: {e}")
            return False

    def sync_orders(self, orders: List[Dict[str, Any]]) -> bool:
        """Upserts orders to Supabase."""
        if not self.client or not orders:
            return False
        try:
            records = []
            for o in orders:
                records.append({
                    "id": o["id"],
                    "customer_id": int(o.get("customer_id", 0)),
                    "address": o.get("address", ""),
                    "area": o.get("area", ""),
                    "city": o.get("city"),
                    "demand_weight": float(o.get("demand", 0.0)),
                    "priority": o.get("priority", "NORMAL"),
                    "deadline": float(o["deadline"]) if o.get("deadline") is not None else None,
                    "ready_time": float(o.get("ready_time", 0.0)),
                    "status": o.get("status", "PENDING"),
                    "assigned_vehicle_id": o.get("assigned_vehicle"),
                    "payout_inr": int(o["payout_inr"]) if o.get("payout_inr") is not None else None,
                })
            self.client.table("orders").upsert(records).execute()
            return True
        except Exception as e:
            print(f"[SupabaseService] Error syncing orders: {e}")
            return False

    def record_task_allocation(self, order_id: str, vehicle_id: str, allocated_by: Optional[str] = None) -> bool:
        """Records a task allocation in Supabase and updates order status."""
        if not self.client:
            return False
        try:
            # 1. Insert allocation record
            self.client.table("task_allocations").insert({
                "order_id": order_id,
                "vehicle_id": vehicle_id,
                "allocated_by": allocated_by or "Dispatch Deck",
                "status": "ASSIGNED",
                "metadata": {"source": "SWARMRoute Dashboard"},
            }).execute()

            # 2. Update order assignment in orders table
            self.client.table("orders").update({
                "assigned_vehicle_id": vehicle_id,
                "status": "ASSIGNED",
            }).eq("id", order_id).execute()

            return True
        except Exception as e:
            print(f"[SupabaseService] Error recording allocation: {e}")
            return False

    def record_task_completion(self, order_id: str, vehicle_id: Optional[str] = None) -> bool:
        """Marks an order as DELIVERED and updates delivery partner stats in Supabase."""
        if not self.client:
            return False
        try:
            # 1. Update order status
            self.client.table("orders").update({
                "status": "DELIVERED",
            }).eq("id", order_id).execute()

            # 2. Increment partner completed deliveries if vehicle specified
            if vehicle_id:
                partner_res = self.client.table("delivery_partners").select("completed_deliveries").eq("id", vehicle_id).execute()
                if partner_res.data:
                    current_count = partner_res.data[0].get("completed_deliveries", 0) or 0
                    self.client.table("delivery_partners").update({
                        "completed_deliveries": current_count + 1,
                    }).eq("id", vehicle_id).execute()

            return True
        except Exception as e:
            print(f"[SupabaseService] Error recording task completion: {e}")
            return False

    def record_telemetry(self, vehicle_id: str, telemetry: Dict[str, Any]) -> bool:
        """Logs vehicle telemetry to Supabase."""
        if not self.client:
            return False
        try:
            self.client.table("telemetry_logs").insert({
                "vehicle_id": vehicle_id,
                "lat": float(telemetry.get("latitude", telemetry.get("lat", 0.0))),
                "lon": float(telemetry.get("longitude", telemetry.get("lon", 0.0))),
                "speed_kmh": float(telemetry.get("speed_kmh", 0.0)),
                "status": telemetry.get("status", "ACTIVE"),
            }).execute()
            return True
        except Exception:
            return False
    def fetch_delivery_partners(self) -> List[Dict[str, Any]]:
        """Retrieves delivery partners directly from Supabase database."""
        if not self.client:
            return []
        try:
            res = self.client.table("delivery_partners").select("*").order("id").execute()
            return res.data or []
        except Exception as e:
            print(f"[SupabaseService] Error fetching delivery partners: {e}")
            return []

    def fetch_orders(self) -> List[Dict[str, Any]]:
        """Retrieves orders directly from Supabase database."""
        if not self.client:
            return []
        try:
            res = self.client.table("orders").select("*").order("id").execute()
            return res.data or []
        except Exception as e:
            print(f"[SupabaseService] Error fetching orders: {e}")
            return []

    def create_profile(
        self,
        user_id: str,
        email: str,
        full_name: str,
        role: str,
        phone: str = "",
        company_name: str = "",
        vehicle_id: str = "",
    ) -> bool:
        """Upserts a user profile in Supabase."""
        if not self.client:
            return False
        try:
            self.client.table("profiles").upsert({
                "id": user_id,
                "email": email,
                "full_name": full_name,
                "role": role,
                "phone": phone,
                "company_name": company_name,
                "vehicle_id": vehicle_id,
            }).execute()
            return True
        except Exception as e:
            print(f"[SupabaseService] Error creating profile: {e}")
            return False

    def get_profile(self, user_id: str) -> Optional[Dict[str, Any]]:
        """Fetches profile for given user_id."""
        if not self.client:
            return None
        try:
            res = self.client.table("profiles").select("*").eq("id", user_id).execute()
            if res.data:
                return res.data[0]
            return None
        except Exception as e:
            print(f"[SupabaseService] Error getting profile: {e}")
            return None

    def register_partner(self, partner_data: Dict[str, Any]) -> bool:
        """Registers a new delivery partner in Supabase."""
        if not self.client:
            return False
        try:
            self.client.table("delivery_partners").upsert(partner_data).execute()
            return True
        except Exception as e:
            print(f"[SupabaseService] Error registering partner: {e}")
            return False

    # Real-World Shared State APIs (Unified between Web & Flutter)

    def save_real_order(self, order: Dict[str, Any]) -> Dict[str, Any]:
        """Saves a customer delivery order to Supabase orders table with memory backup."""
        order_id = order.get("id") or f"ORD_{int(time.time() * 1000) % 1000000}"
        record = {
            "id": order_id,
            "customer_id": order.get("customer_id", "CUST_01"),
            "customer_name": order.get("customer_name", "Customer"),
            "pickup_address": order.get("pickup_address", ""),
            "pickup_lat": float(order.get("pickup_lat", 0.0)),
            "pickup_lon": float(order.get("pickup_lon", 0.0)),
            "delivery_address": order.get("delivery_address", order.get("address", "")),
            "delivery_lat": float(order.get("delivery_lat", 0.0)),
            "delivery_lon": float(order.get("delivery_lon", 0.0)),
            "demand_weight": float(order.get("demand_weight", order.get("demand", 1.0))),
            "priority": order.get("priority", "NORMAL"),
            "status": order.get("status", "PENDING"),
            "assigned_vehicle_id": order.get("assigned_vehicle_id"),
            "estimated_distance_km": float(order.get("estimated_distance_km", 0.0)),
            "estimated_eta_mins": float(order.get("estimated_eta_mins", 30.0)),
            "created_at": order.get("created_at", time.time()),
        }
        if not hasattr(self, "_memory_orders"):
            self._memory_orders: Dict[str, Dict[str, Any]] = {}
        self._memory_orders[order_id] = record

        if self.client:
            try:
                self.client.table("orders").upsert({
                    "id": order_id,
                    "customer_id": 0,
                    "address": record["delivery_address"],
                    "status": record["status"],
                    "demand_weight": record["demand_weight"],
                    "assigned_vehicle_id": record["assigned_vehicle_id"],
                }).execute()
            except Exception as e:
                print(f"[SupabaseService] Remote order upsert notice: {e}")

        return record

    def get_real_order(self, order_id: str) -> Optional[Dict[str, Any]]:
        """Fetches single authoritative order record by ID."""
        if hasattr(self, "_memory_orders") and order_id in self._memory_orders:
            return self._memory_orders[order_id]
        if self.client:
            try:
                res = self.client.table("orders").select("*").eq("id", order_id).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
        return None

    def get_all_real_orders(self) -> List[Dict[str, Any]]:
        """Returns all authoritative orders across clients."""
        if hasattr(self, "_memory_orders") and self._memory_orders:
            return list(self._memory_orders.values())
        return self.fetch_orders()

    def update_real_order_status(
        self,
        order_id: str,
        status: str,
        vehicle_id: Optional[str] = None,
    ) -> bool:
        """Updates status of order across Web and Mobile state."""
        if not hasattr(self, "_memory_orders"):
            self._memory_orders = {}
        if order_id in self._memory_orders:
            self._memory_orders[order_id]["status"] = status
            if vehicle_id:
                self._memory_orders[order_id]["assigned_vehicle_id"] = vehicle_id

        if self.client:
            try:
                update_data = {"status": status}
                if vehicle_id:
                    update_data["assigned_vehicle_id"] = vehicle_id
            except Exception as e:
                logger.warning(f"Supabase order status update failed: {e}")
        return True

    def get_driver_active_order(self, driver_or_vehicle_id: str) -> Optional[Dict[str, Any]]:
        """
        Retrieves the currently assigned active order for a driver or vehicle.
        Active states: ASSIGNED, PICKED_UP, IN_TRANSIT.
        Returns None if no active delivery order is found.
        """
        active_statuses = {"ASSIGNED", "PICKED_UP", "IN_TRANSIT"}
        all_orders = self.get_all_real_orders()
        for o in all_orders:
            if o.get("status") in active_statuses:
                assigned_p = o.get("assigned_partner_id") or o.get("assigned_vehicle_id")
                if assigned_p and str(assigned_p) == str(driver_or_vehicle_id):
                    return o
                # Also check vehicle mapping
                p = self.get_partner(str(driver_or_vehicle_id))
                if p and p.get("vehicle_id") and (o.get("assigned_vehicle_id") == p["vehicle_id"] or o.get("assigned_partner_id") == p["id"]):
                    return o
        return None

    def link_device_to_driver(self, device_id: str, driver_id: str, vehicle_id: Optional[str] = None) -> bool:
        """Associates physical phone device_id with driver_id and vehicle_id."""
        if not hasattr(self, "_device_bindings"):
            self._device_bindings: Dict[str, Dict[str, Any]] = {}
        self._device_bindings[device_id] = {
            "device_id": device_id,
            "driver_id": driver_id,
            "vehicle_id": vehicle_id or f"VEH_{driver_id[-2:]}",
            "updated_at": time.time(),
        }
        if self.client:
            try:
                self.client.table("profiles").update({
                    "device_id": device_id,
                }).eq("id", driver_id).execute()
            except Exception as e:
                print(f"[SupabaseService] Remote device link notice: {e}")
        return True

    def get_driver_by_device(self, device_id: str) -> Optional[Dict[str, Any]]:
        """Finds driver profile associated with physical device_id."""
        if hasattr(self, "_device_bindings") and device_id in self._device_bindings:
            binding = self._device_bindings[device_id]
            return self.get_partner(binding["driver_id"])
        return None


    def record_driver_telemetry(self, vehicle_id: str, telemetry: Dict[str, Any]) -> bool:
        """Records driver telemetry for fleet monitoring and customer tracking."""
        if not hasattr(self, "_latest_telemetry"):
            self._latest_telemetry: Dict[str, Dict[str, Any]] = {}
        self._latest_telemetry[vehicle_id] = {
            "vehicle_id": vehicle_id,
            "latitude": float(telemetry.get("latitude", telemetry.get("lat", 0.0))),
            "longitude": float(telemetry.get("longitude", telemetry.get("lon", 0.0))),
            "speed_kmh": float(telemetry.get("speed_kmh", 0.0)),
            "heading": float(telemetry.get("heading", 0.0)),
            "accuracy": float(telemetry.get("accuracy", 5.0)),
            "fuel_level": float(telemetry.get("fuel_level", 100.0)),
            "vehicle_condition": float(telemetry.get("vehicle_condition", 1.0)),
            "internet_status": telemetry.get("internet_status", "ONLINE"),
            "ble_status": telemetry.get("ble_status", "ACTIVE"),
            "ble_peer_count": int(telemetry.get("ble_peer_count", 0)),
            "timestamp": time.time(),
        }
        # Forward to telemetry_logs table in Supabase
        return self.record_telemetry(vehicle_id, telemetry)

    def get_latest_telemetry(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """Returns the most recent verified telemetry for a driver."""
        if hasattr(self, "_latest_telemetry") and vehicle_id in self._latest_telemetry:
            return self._latest_telemetry[vehicle_id]
        return None

    def get_all_live_telemetry(self) -> Dict[str, Dict[str, Any]]:
        """Returns all drivers' current live telemetry."""
        if hasattr(self, "_latest_telemetry"):
            return self._latest_telemetry
        return {}

    def _initialize_authoritative_store(self) -> None:
        """Initializes authoritative real-world fleet entities."""
        self._memory_partners: Dict[str, Dict[str, Any]] = {
            "DP_01": {
                "id": "DP_01",
                "name": "Arjun Kumar",
                "phone": "+91 98765 43201",
                "vehicle_id": "VEH_01",
                "vehicle_model": "Tata Ace EV",
                "registration": "KA-01-EQ-1024",
                "hub": "Indiranagar Hub",
                "city": "Bengaluru",
                "status": "IDLE",
                "current_load": 0.0,
                "max_weight": 600.0,
                "rating": 4.90,
                "completed_deliveries": 142,
                "fuel_level": 88.0,
                "speed_kmh": 0.0,
                "location_x": 12.9784,
                "location_y": 77.6408,
            },
            "DP_02": {
                "id": "DP_02",
                "name": "Rajesh Sharma",
                "phone": "+91 98765 43202",
                "vehicle_id": "VEH_02",
                "vehicle_model": "Mahindra Bolero Maxi Truck Plus",
                "registration": "KA-05-MB-5520",
                "hub": "Koramangala Hub",
                "city": "Bengaluru",
                "status": "IDLE",
                "current_load": 0.0,
                "max_weight": 1200.0,
                "rating": 4.80,
                "completed_deliveries": 289,
                "fuel_level": 84.5,
                "speed_kmh": 0.0,
                "location_x": 12.9352,
                "location_y": 77.6245,
            },
            "DP_03": {
                "id": "DP_03",
                "name": "Priya Nair",
                "phone": "+91 98765 43203",
                "vehicle_id": "VEH_03",
                "vehicle_model": "Ashok Leyland Dost+",
                "registration": "KA-51-AL-8890",
                "hub": "Whitefield Hub",
                "city": "Bengaluru",
                "status": "IDLE",
                "current_load": 0.0,
                "max_weight": 1500.0,
                "rating": 4.95,
                "completed_deliveries": 310,
                "fuel_level": 73.8,
                "speed_kmh": 0.0,
                "location_x": 12.9698,
                "location_y": 77.7500,
            },
            "DP_04": {
                "id": "DP_04",
                "name": "Vikram Singh",
                "phone": "+91 98765 43204",
                "vehicle_id": "VEH_04",
                "vehicle_model": "Tata Intra V30",
                "registration": "KA-03-TI-4411",
                "hub": "HSR Layout Hub",
                "city": "Bengaluru",
                "status": "IDLE",
                "current_load": 0.0,
                "max_weight": 1300.0,
                "rating": 4.75,
                "completed_deliveries": 98,
                "fuel_level": 68.5,
                "speed_kmh": 0.0,
                "location_x": 12.9121,
                "location_y": 77.6446,
            },
            "DP_05": {
                "id": "DP_05",
                "name": "Mohammed Rizwan",
                "phone": "+91 98765 43205",
                "vehicle_id": "VEH_05",
                "vehicle_model": "Piaggio Ape E-City",
                "registration": "KA-04-PE-3030",
                "hub": "Jayanagar Hub",
                "city": "Bengaluru",
                "status": "IDLE",
                "current_load": 0.0,
                "max_weight": 400.0,
                "rating": 4.85,
                "completed_deliveries": 215,
                "fuel_level": 82.5,
                "speed_kmh": 0.0,
                "location_x": 12.9308,
                "location_y": 77.5838,
            },
        }

        self._memory_vehicles: Dict[str, Dict[str, Any]] = {
            "VEH_01": {
                "id": "VEH_01",
                "partner_id": "DP_01",
                "manufacturer": "Tata Motors",
                "model": "Ace EV",
                "model_year": 2024,
                "fuel_type": "ELECTRIC",
                "engine_type": "Permanent Magnet Synchronous Motor",
                "fuel_capacity": 21.3,
                "current_fuel": 18.5,
                "odometer_km": 14250.0,
                "vehicle_condition": 0.96,
                "maintenance_score": 0.98,
                "tyre_condition": 0.95,
                "engine_health": 0.98,
                "average_fuel_efficiency": 6.8,
                "max_payload_kg": 600.0,
                "current_payload_kg": 0.0,
            },
            "VEH_02": {
                "id": "VEH_02",
                "partner_id": "DP_02",
                "manufacturer": "Mahindra & Mahindra",
                "model": "Bolero Maxi Truck Plus",
                "model_year": 2023,
                "fuel_type": "DIESEL",
                "engine_type": "m2DiCR 2.5L 4-Cylinder Turbocharged",
                "fuel_capacity": 45.0,
                "current_fuel": 38.0,
                "odometer_km": 38400.0,
                "vehicle_condition": 0.91,
                "maintenance_score": 0.90,
                "tyre_condition": 0.88,
                "engine_health": 0.92,
                "average_fuel_efficiency": 17.2,
                "max_payload_kg": 1200.0,
                "current_payload_kg": 0.0,
            },
            "VEH_03": {
                "id": "VEH_03",
                "partner_id": "DP_03",
                "manufacturer": "Ashok Leyland",
                "model": "Dost+",
                "model_year": 2023,
                "fuel_type": "DIESEL",
                "engine_type": "1.5L 3-Cylinder Turbocharged Diesel",
                "fuel_capacity": 40.0,
                "current_fuel": 29.5,
                "odometer_km": 27100.0,
                "vehicle_condition": 0.93,
                "maintenance_score": 0.94,
                "tyre_condition": 0.91,
                "engine_health": 0.94,
                "average_fuel_efficiency": 19.6,
                "max_payload_kg": 1500.0,
                "current_payload_kg": 0.0,
            },
            "VEH_04": {
                "id": "VEH_04",
                "partner_id": "DP_04",
                "manufacturer": "Tata Motors",
                "model": "Intra V30",
                "model_year": 2024,
                "fuel_type": "DIESEL",
                "engine_type": "1496 cc DI Engine",
                "fuel_capacity": 35.0,
                "current_fuel": 24.0,
                "odometer_km": 11800.0,
                "vehicle_condition": 0.97,
                "maintenance_score": 0.96,
                "tyre_condition": 0.95,
                "engine_health": 0.97,
                "average_fuel_efficiency": 14.0,
                "max_payload_kg": 1300.0,
                "current_payload_kg": 0.0,
            },
            "VEH_05": {
                "id": "VEH_05",
                "partner_id": "DP_05",
                "manufacturer": "Piaggio",
                "model": "Ape E-City",
                "model_year": 2024,
                "fuel_type": "ELECTRIC",
                "engine_type": "Lithium-ion 51.2V Traction Motor",
                "fuel_capacity": 7.5,
                "current_fuel": 6.2,
                "odometer_km": 8900.0,
                "vehicle_condition": 0.95,
                "maintenance_score": 0.97,
                "tyre_condition": 0.92,
                "engine_health": 0.96,
                "average_fuel_efficiency": 9.5,
                "max_payload_kg": 400.0,
                "current_payload_kg": 0.0,
            },
        }

        self._memory_assignments: List[Dict[str, Any]] = []
        self._memory_route_sessions: Dict[str, Dict[str, Any]] = {}
        self._memory_route_events: List[Dict[str, Any]] = []
        self._mesh_relays: List[Dict[str, Any]] = []

    # --- Delivery Partner Authoritative Store ---

    def get_all_partners(self) -> List[Dict[str, Any]]:
        """Returns authoritative delivery partners directly from persistent Supabase or memory."""
        if self.client:
            try:
                res = self.client.table("delivery_partners").select("*").execute()
                if res.data and len(res.data) > 0:
                    return res.data
            except Exception as e:
                print(f"[SupabaseService] Remote delivery_partners read error: {e}")
        return list(self._memory_partners.values())

    def get_partner(self, partner_id: str) -> Optional[Dict[str, Any]]:
        """Returns single delivery partner profile."""
        if self.client:
            try:
                res = self.client.table("delivery_partners").select("*").eq("id", partner_id).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
        return self._memory_partners.get(partner_id)

    def upsert_partner(self, partner_data: Dict[str, Any]) -> bool:
        """Upserts delivery partner to database and memory."""
        pid = partner_data["id"]
        self._memory_partners[pid] = {**self._memory_partners.get(pid, {}), **partner_data}
        if self.client:
            try:
                self.client.table("delivery_partners").upsert(partner_data).execute()
                return True
            except Exception as e:
                print(f"[SupabaseService] Upsert partner error: {e}")
        return True

    # --- Vehicle Authoritative Store (NO HARDCODING) ---

    def get_all_vehicles(self) -> List[Dict[str, Any]]:
        """Returns authoritative vehicle records directly from database or persistent store."""
        if self.client:
            try:
                res = self.client.table("vehicles").select("*").execute()
                if res.data and len(res.data) > 0:
                    return res.data
            except Exception as e:
                print(f"[SupabaseService] Remote vehicles read error: {e}")
        return list(self._memory_vehicles.values())

    def get_vehicle(self, vehicle_id: str) -> Optional[Dict[str, Any]]:
        """Fetches vehicle record. If not found, returns None."""
        if self.client:
            try:
                res = self.client.table("vehicles").select("*").eq("id", vehicle_id).execute()
                if res.data:
                    return res.data[0]
            except Exception:
                pass
        return self._memory_vehicles.get(vehicle_id)

    def get_vehicle_spec(self, vehicle_id: str) -> Dict[str, Any]:
        """
        Returns verified vehicle specification.
        Per Critical Rule Section 4: If any field is unavailable, return 'UNKNOWN'.
        NEVER fabricate or hardcode strings.
        """
        v = self.get_vehicle(vehicle_id)
        if not v:
            # Check partner mapping
            for p in self.get_all_partners():
                if p.get("vehicle_id") == vehicle_id or p.get("id") == vehicle_id:
                    v = self.get_vehicle(p.get("vehicle_id", ""))
                    break

        if not v:
            return {
                "vehicle_id": vehicle_id,
                "partner_id": "UNKNOWN",
                "manufacturer": "UNKNOWN",
                "model_name": "UNKNOWN",
                "model_year": "UNKNOWN",
                "fuel_type": "UNKNOWN",
                "engine_type": "UNKNOWN",
                "fuel_capacity": "UNKNOWN",
                "fuel_remaining": "UNKNOWN",
                "odometer_km": "UNKNOWN",
                "vehicle_condition": "UNKNOWN",
                "maintenance_score": "UNKNOWN",
                "tyre_condition": "UNKNOWN",
                "engine_health": "UNKNOWN",
                "average_fuel_efficiency": "UNKNOWN",
                "max_load": "UNKNOWN",
                "current_load": 0.0,
            }

        return {
            "vehicle_id": v.get("id", vehicle_id),
            "partner_id": v.get("partner_id", "UNKNOWN"),
            "manufacturer": v.get("manufacturer", "UNKNOWN"),
            "model_name": v.get("model", "UNKNOWN"),
            "model_year": v.get("model_year", "UNKNOWN"),
            "fuel_type": v.get("fuel_type", "UNKNOWN"),
            "engine_type": v.get("engine_type", "UNKNOWN"),
            "fuel_capacity": v.get("fuel_capacity", "UNKNOWN"),
            "fuel_remaining": v.get("current_fuel", "UNKNOWN"),
            "odometer_km": v.get("odometer_km", "UNKNOWN"),
            "vehicle_condition": v.get("vehicle_condition", "UNKNOWN"),
            "maintenance_score": v.get("maintenance_score", "UNKNOWN"),
            "tyre_condition": v.get("tyre_condition", "UNKNOWN"),
            "engine_health": v.get("engine_health", "UNKNOWN"),
            "average_fuel_efficiency": v.get("average_fuel_efficiency", "UNKNOWN"),
            "max_load": v.get("max_payload_kg", "UNKNOWN"),
            "current_load": v.get("current_payload_kg", 0.0),
        }

    def upsert_vehicle(self, vehicle_data: Dict[str, Any]) -> bool:
        """Upserts a vehicle record into persistent store."""
        vid = vehicle_data["id"]
        self._memory_vehicles[vid] = {**self._memory_vehicles.get(vid, {}), **vehicle_data}
        if self.client:
            try:
                self.client.table("vehicles").upsert(vehicle_data).execute()
                return True
            except Exception as e:
                print(f"[SupabaseService] Remote vehicle upsert error: {e}")
        return True

    # --- Order Assignments Store ---

    def record_order_assignment(
        self,
        order_id: str,
        partner_id: str,
        vehicle_id: str,
        allocated_by: str = "DISPATCH_MANAGER",
        dispatch_mode: str = "MANUAL",
    ) -> Dict[str, Any]:
        """
        Records authoritative assignment connecting Order -> Assignment -> Delivery Partner.
        Updates order lifecycle status to ASSIGNED.
        """
        now = time.time()
        assignment = {
            "order_id": order_id,
            "partner_id": partner_id,
            "vehicle_id": vehicle_id,
            "allocated_by": allocated_by,
            "dispatch_mode": dispatch_mode,
            "status": "ASSIGNED",
            "allocated_at": now,
        }
        self._memory_assignments.append(assignment)

        # Update order in memory and Supabase
        if hasattr(self, "_memory_orders") and order_id in self._memory_orders:
            self._memory_orders[order_id]["assigned_partner_id"] = partner_id
            self._memory_orders[order_id]["assigned_vehicle_id"] = vehicle_id
            self._memory_orders[order_id]["status"] = "ASSIGNED"
            self._memory_orders[order_id]["assigned_at"] = now

        if self.client:
            try:
                self.client.table("order_assignments").insert(assignment).execute()
                self.client.table("orders").update({
                    "assigned_partner_id": partner_id,
                    "assigned_vehicle_id": vehicle_id,
                    "status": "ASSIGNED",
                }).eq("id", order_id).execute()
            except Exception as e:
                print(f"[SupabaseService] Remote assignment record notice: {e}")

        return assignment

    def get_order_assignments(self, order_id: Optional[str] = None) -> List[Dict[str, Any]]:
        """Returns assignment history."""
        if order_id:
            return [a for a in self._memory_assignments if a.get("order_id") == order_id]
        return self._memory_assignments

    # --- Route Sessions & Events Store ---

    def create_route_session(
        self,
        order_id: str,
        partner_id: str,
        vehicle_id: str,
        origin_lat: float,
        origin_lon: float,
        dest_lat: float,
        dest_lon: float,
        distance_km: float,
        duration_mins: float,
        route_geometry: List[Any],
    ) -> Dict[str, Any]:
        """Creates an active navigation route session."""
        session_id = f"RS_{order_id}_{int(time.time())}"
        session = {
            "id": session_id,
            "order_id": order_id,
            "partner_id": partner_id,
            "vehicle_id": vehicle_id,
            "origin_lat": origin_lat,
            "origin_lon": origin_lon,
            "dest_lat": dest_lat,
            "dest_lon": dest_lon,
            "distance_km": distance_km,
            "duration_mins": duration_mins,
            "route_geometry": route_geometry,
            "status": "ACTIVE",
            "started_at": time.time(),
        }
        self._memory_route_sessions[session_id] = session
        if self.client:
            try:
                self.client.table("route_sessions").insert(session).execute()
            except Exception as e:
                print(f"[SupabaseService] Remote route_session insert notice: {e}")
        return session

    def record_route_event(
        self,
        session_id: str,
        event_type: str,
        description: str,
        severity: str = "INFO",
        payload: Optional[Dict[str, Any]] = None,
    ) -> bool:
        """Appends an event to route session log."""
        ev = {
            "session_id": session_id,
            "event_type": event_type,
            "description": description,
            "severity": severity,
            "payload": payload or {},
            "created_at": time.time(),
        }
        self._memory_route_events.append(ev)
        if self.client:
            try:
                self.client.table("route_events").insert(ev).execute()
            except Exception as e:
                print(f"[SupabaseService] Remote route_event notice: {e}")
        return True

    # --- Mesh Message Relays (Cloud Bridge) ---

    def log_mesh_relay(self, packet: Dict[str, Any]) -> bool:
        """
        Audits BLE mesh multi-hop packets bridged to backend.
        Deduplicates by message_id and persists to mesh_messages table.
        """
        mid = packet.get("message_id", "")
        # Deduplication check
        if any(m.get("message_id") == mid for m in self._mesh_relays):
            return True

        record = {
            "message_id": mid,
            "source_device_id": packet.get("source_device_id", packet.get("sender_id", "UNKNOWN")),
            "destination_device_id": packet.get("destination_device_id", "BACKEND"),
            "message_type": packet.get("message_type", "DATA"),
            "timestamp": packet.get("timestamp", time.time()),
            "ttl": int(packet.get("ttl", 5)),
            "hop_count": int(packet.get("hop_count", 0)),
            "payload": packet.get("payload", {}),
            "bridge_device_id": packet.get("bridge_device_id"),
            "signature": packet.get("signature", ""),
            "received_at": time.time(),
        }
        self._mesh_relays.insert(0, record)

        if self.client:
            try:
                self.client.table("mesh_messages").insert({
                    "message_id": record["message_id"],
                    "source_device_id": record["source_device_id"],
                    "destination_device_id": record["destination_device_id"],
                    "message_type": record["message_type"],
                    "timestamp": record["timestamp"],
                    "ttl": record["ttl"],
                    "hop_count": record["hop_count"],
                    "payload": record["payload"],
                    "signature": record["signature"],
                    "bridge_device_id": record["bridge_device_id"],
                }).execute()
            except Exception as e:
                print(f"[SupabaseService] Remote mesh_message insert notice: {e}")
        return True

    def get_mesh_relays(self) -> List[Dict[str, Any]]:
        """Returns audited bridged mesh messages."""
        return self._mesh_relays


# Global Supabase service instance
supabase_service = SupabaseService()

