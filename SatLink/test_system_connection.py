"""
Test script to verify the SatLink system is working
"""

import os
import sys

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.updated_db_manager import SatLinkDatabaseUser


def test_system():
    """Test the complete system"""
    print("Testing SatLink System")
    print("=" * 50)

    # Test database connection
    db_path = 'satlink.db'
    if not os.path.exists(db_path):
        print("Database file not found!")
        return False

    db = SatLinkDatabaseUser(db_path)

    try:
        # Test admin login
        print("\n1. Testing admin login...")
        success = db.login('admin', 'admin123')
        print(f"Login successful: {success}")

        if not success:
            # Try with the demo user
            print("Trying demo user...")
            success = db.login('demo', 'demo123')
            print(f"Demo login successful: {success}")

        if not success:
            print("Login failed!")
            return False

        # Get user info
        user_info = db.get_current_user_info()
        print(f"User: {user_info['username']} ({user_info['email']})")

        # Test getting public satellites
        print("\n2. Testing public satellites...")
        public_sats = db.get_public_satellites()
        print(f"Public satellites: {len(public_sats)}")
        for sat in public_sats:
            print(f"  - {sat['name']} ({sat['owner']})")

        # Test user's satellites
        print("\n3. Testing user's satellites...")
        user_sats = db.list_satellite_positions()
        print(f"User's satellites: {len(user_sats)}")
        for sat in user_sats:
            print(f"  - {sat['name']} (Shared: {sat['is_shared']})")

        # Test transponders
        print("\n4. Testing transponders...")
        transponders = db.list_transponders()
        print(f"Transponders: {len(transponders)}")
        for tp in transponders:
            print(f"  - {tp['name']} @ {tp['freq']} GHz")

        # Test carriers
        print("\n5. Testing carriers...")
        carriers = db.list_carriers()
        print(f"Carriers: {len(carriers)}")
        for car in carriers:
            print(f"  - {car['name']} ({car['modcod']})")

        # Test ground stations
        print("\n6. Testing ground stations...")
        ground_stations = db.list_ground_stations()
        print(f"Ground stations: {len(ground_stations)}")
        for gs in ground_stations:
            print(f"  - {gs['name']} ({gs['city']}, {gs['country']})")

        # Test link calculations
        print("\n7. Testing link calculations...")
        calculations = db.list_link_calculations()
        print(f"Link calculations: {len(calculations)}")
        for calc in calculations:
            print(f"  - {calc['name']}: SNR={calc.get('snr', 'N/A')} dB")

        # Test user statistics
        print("\n8. Testing user statistics...")
        stats = db.get_user_statistics()
        print(f"User statistics:")
        for key, value in stats.items():
            if key != 'account_created':
                print(f"  - {key}: {value}")

        # Test logout
        print("\n9. Testing logout...")
        db.logout()
        print("Logout successful")

        print("\n" + "=" * 50)
        print("SYSTEM TEST PASSED!")
        print("=" * 50)
        print(f"\nDatabase: {db_path}")
        print(f"Admin user: admin / admin123")
        print(f"Demo user: demo / demo123")
        print(f"\nTo start the web server:")
        print(f"python web_app.py")
        print(f"\nThen visit: http://localhost:5000")

        return True

    except Exception as e:
        print(f"\nError: {e}")
        return False

    finally:
        db.close()


if __name__ == "__main__":
    success = test_system()
    sys.exit(0 if success else 1)