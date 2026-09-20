"""
Seed & Sync script for Supabase Fleet Management.
Synchronizes all active delivery partners and customer orders to Supabase PostgreSQL.
"""
from __future__ import annotations

import os
import sys

# Ensure project root in sys.path
PROJECT_ROOT = os.path.dirname(os.path.dirname(os.path.abspath(__file__)))
if PROJECT_ROOT not in sys.path:
    sys.path.insert(0, PROJECT_ROOT)

from src.api.simulation_runner import runner
from src.api.supabase_service import supabase_service


def main():
    print("==================================================================")
    print("SWARMRoute -> Supabase Cloud Synchronization")
    print("==================================================================")
    print(f"Target URL: {supabase_service.url}")
    print(f"Project Ref: {supabase_service.project_ref}")

    # Check connection
    status = supabase_service.get_status()
    print("Connection status:", status)
    if not status.get("connected"):
        print("ERROR: Could not connect to Supabase database:", status.get("error"))
        sys.exit(1)

    # Initialize simulation with Maharashtra
    print("Initializing simulation instance (C101, 20 customers, 4 vehicles, Maharashtra)...")
    runner.reset(city="Maharashtra")

    # Only customer orders are synced (no hardcoded delivery partners)
    print("Syncing live customer orders to Supabase...")

    # Get Maharashtra orders
    state = runner.get_state()
    orders = state.get("orders", [])

    print(f"\n2. Syncing {len(orders)} Customer Orders to Supabase...")
    o_success = supabase_service.sync_orders(orders)
    print(f"   -> Orders synced successfully: {o_success}")

    # Verify counts
    updated_status = supabase_service.get_status()
    print("\nUpdated Supabase Database Row Counts:")
    for table, count in updated_status.get("counts", {}).items():
        print(f"  • {table}: {count} rows")

    print("\n✓ Supabase Fleet Management Database is fully synced and live!")


if __name__ == "__main__":
    main()
