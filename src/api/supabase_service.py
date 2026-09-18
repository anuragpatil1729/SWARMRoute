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
                self.client.table("orders").update(update_data).eq("id", order_id).execute()
            except Exception as e:
                print(f"[SupabaseService] Remote status update error: {e}")
        return True

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

    def log_mesh_relay(self, packet: Dict[str, Any]) -> bool:
        """Audits BLE mesh multi-hop packets bridged to backend."""
        if not hasattr(self, "_mesh_relays"):
            self._mesh_relays: List[Dict[str, Any]] = []
        self._mesh_relays.insert(0, {**packet, "received_at": time.time()})
        return True

    def get_mesh_relays(self) -> List[Dict[str, Any]]:
        if hasattr(self, "_mesh_relays"):
            return self._mesh_relays
        return []


# Global Supabase service instance
supabase_service = SupabaseService()

