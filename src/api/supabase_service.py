"""
Supabase Service for SWARMRoute Fleet Management.
Provides persistent cloud synchronization for delivery partners, orders,
task allocations, and real-time telemetry.
"""
from __future__ import annotations

import os
import sys
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
                records.append({
                    "id": p["id"],
                    "name": p.get("name", p["id"]),
                    "phone": p.get("phone", ""),
                    "vehicle_model": p.get("vehicle_model", ""),
                    "registration": p.get("registration", ""),
                    "hub": p.get("hub", ""),
                    "city": p.get("city", "Bengaluru"),
                    "rating": float(p.get("rating", 4.9)),
                    "completed_deliveries": int(p.get("completed_deliveries", 0)),
                    "avatar": p.get("avatar", "🛵"),
                    "status": p.get("status", "IDLE"),
                    "current_load": float(p.get("current_load", 0.0)),
                    "max_weight": float(p.get("max_weight", 100.0)),
                    "fuel_level": float(p.get("fuel_level", 100.0)),
                    "speed_kmh": float(p.get("speed_kmh", 0.0)),
                    "location_x": float(loc.get("x", 40.0)) if isinstance(loc, dict) else 40.0,
                    "location_y": float(loc.get("y", 50.0)) if isinstance(loc, dict) else 50.0,
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
                    "city": "Bengaluru",
                    "demand_weight": float(o.get("demand", 10.0)),
                    "priority": o.get("priority", "NORMAL"),
                    "deadline": float(o.get("deadline", 120.0)),
                    "ready_time": float(o.get("ready_time", 0.0)),
                    "status": o.get("status", "PENDING"),
                    "assigned_vehicle_id": o.get("assigned_vehicle"),
                    "payout_inr": int(o.get("payout_inr", 120)),
                })
            self.client.table("orders").upsert(records).execute()
            return True
        except Exception as e:
            print(f"[SupabaseService] Error syncing orders: {e}")
            return False

    def record_task_allocation(self, order_id: str, vehicle_id: str, allocated_by: str = "Company Manager (Admin)") -> bool:
        """Records a task allocation in Supabase and updates order status."""
        if not self.client:
            return False
        try:
            # 1. Insert allocation record
            self.client.table("task_allocations").insert({
                "order_id": order_id,
                "vehicle_id": vehicle_id,
                "allocated_by": allocated_by,
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
                "lat": telemetry.get("lat", 0.0),
                "lon": telemetry.get("lon", 0.0),
                "speed_kmh": telemetry.get("speed_kmh", 0.0),
                "battery_pct": telemetry.get("battery_pct", 100.0),
                "current_load_kg": telemetry.get("current_load_kg", 0.0),
                "status": telemetry.get("status", "ACTIVE"),
            }).execute()
            return True
        except Exception as e:
            print(f"[SupabaseService] Error recording telemetry: {e}")
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


# Global Supabase service instance
supabase_service = SupabaseService()

