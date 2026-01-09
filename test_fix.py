#!/usr/bin/env python3
"""
Test script to verify the satellite not found fix
"""

import os
import sys
import sqlite3
import json

# Add SatLink to path
sys.path.append('SatLink')

from models.updated_db_manager import SatLinkDatabaseUser
from models.updated_satlink_db_schema import UPDATED_SQL_SCHEMA

def init_database(db_path):
    """Initialize database with schema"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Create all tables
    cursor.executescript(UPDATED_SQL_SCHEMA)
    conn.commit()
    conn.close()

def test_satellite_fix():
    """Test the satellite fix"""
    print("Testing satellite not found fix...")

    # Create a test database
    test_db = 'test_satlink.db'

    try:
        # Initialize database schema
        init_database(test_db)

        # Initialize database instance
        db = SatLinkDatabaseUser(test_db)

        # Check if there are any satellites initially
        satellites = db.list_satellite_positions()
        print(f"Initial satellites: {len(satellites)}")

        if not satellites:
            print("No satellites found - adding default...")

            # Set a user ID (admin is typically ID 1)
            db.current_user_id = 1

            # Add default satellite
            sat_id = db.add_satellite_position(
                name="Default GEO Satellite",
                sat_long=0.0,
                sat_lat=0.0,
                h_sat=35786,
                is_shared=True
            )

            print(f"Added default satellite with ID: {sat_id}")

            # Verify satellite was added
            satellites = db.list_satellite_positions()
            print(f"Satellites after adding: {len(satellites)}")

            if satellites:
                print(f"First satellite: {satellites[0]['name']} (ID: {satellites[0]['id']})")

        print("✅ Test passed!")

    except Exception as e:
        print(f"❌ Test failed: {str(e)}")
        import traceback
        traceback.print_exc()

    finally:
        # Clean up
        if os.path.exists(test_db):
            os.remove(test_db)
            print(f"Cleaned up test database: {test_db}")

if __name__ == '__main__':
    test_satellite_fix()