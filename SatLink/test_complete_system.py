"""
Complete System Test Script for SatLink with User Authentication

This script tests all components of the SatLink system including:
- User registration and authentication
- Database operations with user/sharing features
- Link calculations
- Web interface components
"""

import os
import sys
import tempfile
import shutil
import json
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.updated_db_manager import SatLinkDatabaseUser
from models.updated_satlink_db_schema import UPDATED_SQL_SCHEMA
from models.user_auth import UserAuth
from models.satellite_components import SatellitePosition, Transponder, Carrier
from web_app import init_db_clean
from web_user_management import user_management_bp


class SystemTester:
    """Comprehensive system tester class"""

    def __init__(self, db_path=None):
        """Initialize tester with temporary database"""
        if db_path is None:
            # Create temporary directory
            self.temp_dir = tempfile.mkdtemp()
            self.db_path = os.path.join(self.temp_dir, 'satlink_test.db')
        else:
            self.temp_dir = None
            self.db_path = db_path

        # Initialize database
        print(f"\nInitializing test database at: {self.db_path}")
        init_db_clean(self.db_path)
        self.db = SatLinkDatabaseUser(self.db_path)

        # Test results storage
        self.test_results = {
            'total_tests': 0,
            'passed': 0,
            'failed': 0,
            'details': []
        }

    def __del__(self):
        """Cleanup temporary directory"""
        if hasattr(self, 'temp_dir') and self.temp_dir:
            shutil.rmtree(self.temp_dir, ignore_errors=True)

    def log_test(self, test_name, passed, details=None):
        """Log a test result"""
        self.test_results['total_tests'] += 1
        if passed:
            self.test_results['passed'] += 1
            status = "PASS"
        else:
            self.test_results['failed'] += 1
            status = "FAIL"

        result = {
            'test': test_name,
            'status': status,
            'details': details or "No details"
        }
        self.test_results['details'].append(result)
        print(f"[{status}] {test_name}")

    def test_user_authentication(self):
        """Test user authentication system"""
        print("\n" + "="*60)
        print("Testing User Authentication System")
        print("="*60)

        # Test 1: User registration
        try:
            success = self.db.user_auth.register_user('testuser1', 'test1@example.com', 'password123')
            self.log_test("User Registration", success, "Test user created successfully")
        except Exception as e:
            self.log_test("User Registration", False, f"Error: {str(e)}")

        # Test 2: Duplicate registration
        try:
            success = self.db.user_auth.register_user('testuser1', 'test1@example.com', 'password123')
            self.log_test("Duplicate Registration", not success, "Should fail for duplicate user")
        except Exception as e:
            self.log_test("Duplicate Registration", False, f"Error: {str(e)}")

        # Test 3: User login
        try:
            success = self.db.login('testuser1', 'password123')
            self.log_test("User Login", success, "Login successful")
        except Exception as e:
            self.log_test("User Login", False, f"Error: {str(e)}")

        # Test 4: Wrong password
        try:
            success = self.db.login('testuser1', 'wrongpassword')
            self.log_test("Wrong Password", not success, "Should fail with wrong password")
        except Exception as e:
            self.log_test("Wrong Password", False, f"Error: {str(e)}")

        # Test 5: Session validation
        try:
            if self.db.current_user_id:
                valid = self.db.validate_current_session()
                self.log_test("Session Validation", valid, "Session should be valid")
        except Exception as e:
            self.log_test("Session Validation", False, f"Error: {str(e)}")

        # Test 6: User info
        try:
            user_info = self.db.get_current_user_info()
            self.log_test("Get User Info", user_info is not None, f"User: {user_info.get('username') if user_info else 'None'}")
        except Exception as e:
            self.log_test("Get User Info", False, f"Error: {str(e)}")

        # Test 7: Logout
        try:
            self.db.logout()
            self.log_test("User Logout", True, "Logout successful")
        except Exception as e:
            self.log_test("User Logout", False, f"Error: {str(e)}")

    def test_database_operations(self):
        """Test database operations with user context"""
        print("\n" + "="*60)
        print("Testing Database Operations")
        print("="*60)

        # Login first
        self.db.login('testuser1', 'password123')

        # Test 1: Add satellite
        try:
            sat_id = self.db.add_satellite_position(
                'Test Satellite', -70.0, 0, 35786, 'GEO',
                'Test satellite for database testing', is_shared=True
            )
            self.log_test("Add Satellite", sat_id > 0, f"Satellite ID: {sat_id}")
        except Exception as e:
            self.log_test("Add Satellite", False, f"Error: {str(e)}")

        # Test 2: List satellites
        try:
            satellites = self.db.list_satellite_positions()
            self.log_test("List Satellites", len(satellites) > 0, f"Found {len(satellites)} satellites")
        except Exception as e:
            self.log_test("List Satellites", False, f"Error: {str(e)}")

        # Test 3: Add transponder
        try:
            tp_id = self.db.add_transponder(
                'Test Transponder', 14.25, 'Ku', 54, 36, 0, 0,
                'Horizontal', satellite_id=sat_id, is_shared=True
            )
            self.log_test("Add Transponder", tp_id > 0, f"Transponder ID: {tp_id}")
        except Exception as e:
            self.log_test("Add Transponder", False, f"Error: {str(e)}")

        # Test 4: Add carrier
        try:
            car_id = self.db.add_carrier(
                'Test Carrier', '8PSK 2/3', '8PSK', '2/3', 0.20,
                36, None, None, 'DVB-S2', 'Test carrier', is_shared=True
            )
            self.log_test("Add Carrier", car_id > 0, f"Carrier ID: {car_id}")
        except Exception as e:
            self.log_test("Add Carrier", False, f"Error: {str(e)}")

        # Test 5: Add ground station
        try:
            gs_id = self.db.add_ground_station(
                'Test Ground Station', -15.8, -47.9, 'TEST', 0,
                'Brazil', 'DF', 'Brasilia', None, None,
                'Test ground station', is_shared=True
            )
            self.log_test("Add Ground Station", gs_id > 0, f"Ground Station ID: {gs_id}")
        except Exception as e:
            self.log_test("Add Ground Station", False, f"Error: {str(e)}")

        # Test 6: Add simple reception system
        try:
            rec_id = self.db.add_reception_simple(
                'Test Reception System', gs_id, 20.5, 0.5,
                14.25, 'Measured', None, None, 'Test system', is_shared=True
            )
            self.log_test("Add Reception System", rec_id > 0, f"Reception ID: {rec_id}")
        except Exception as e:
            self.log_test("Add Reception System", False, f"Error: {str(e)}")

        # Test 7: Add link calculation
        try:
            results = {
                'elevation_angle': 45.2,
                'azimuth_angle': 180.5,
                'distance': 35786,
                'a_fs': 196.2,
                'a_g': 0.5,
                'a_c': 0.2,
                'a_r': 2.1,
                'a_s': 0.3,
                'a_t': 3.1,
                'a_tot': 199.3,
                'cn0': 85.5,
                'snr': 12.3,
                'snr_threshold': 9.8,
                'link_margin': 2.5,
                'availability': 99.9,
                'gt_value': 20.5,
                'notes': 'Test calculation'
            }
            calc_id = self.db.add_link_calculation(
                'Test Calculation', sat_id, tp_id, car_id, gs_id,
                'simple', rec_id, 0, 0.1, **results
            )
            self.log_test("Add Link Calculation", calc_id > 0, f"Calculation ID: {calc_id}")
        except Exception as e:
            self.log_test("Add Link Calculation", False, f"Error: {str(e)}")

        # Test 8: List calculations
        try:
            calculations = self.db.list_link_calculations()
            self.log_test("List Calculations", len(calculations) > 0, f"Found {len(calculations)} calculations")
        except Exception as e:
            self.log_test("List Calculations", False, f"Error: {str(e)}")

        # Test 9: Update satellite
        try:
            success = self.db.update_satellite_position(sat_id, description='Updated description')
            self.log_test("Update Satellite", success, "Satellite updated successfully")
        except Exception as e:
            self.log_test("Update Satellite", False, f"Error: {str(e)}")

        # Test 10: Make calculation public
        try:
            success = self.db.make_link_public(calc_id)
            self.log_test("Make Calculation Public", success, "Calculation shared successfully")
        except Exception as e:
            self.log_test("Make Calculation Public", False, f"Error: {str(e)}")

        # Test 11: Get public items
        try:
            public_sats = self.db.get_public_satellites()
            self.log_test("Get Public Satellites", len(public_sats) > 0, f"Found {len(public_sats)} public satellites")
        except Exception as e:
            self.log_test("Get Public Satellites", False, f"Error: {str(e)}")

        # Test 12: Get user statistics
        try:
            stats = self.db.get_user_statistics()
            self.log_test("Get User Statistics", stats is not None, f"Stats: {stats}")
        except Exception as e:
            self.log_test("Get User Statistics", False, f"Error: {str(e)}")

        # Logout
        self.db.logout()

    def test_component_classes(self):
        """Test satellite component classes"""
        print("\n" + "="*60)
        print("Testing Component Classes")
        print("="*60)

        # Test 1: SatellitePosition
        try:
            sat = SatellitePosition(-70.0, 0, 35786)
            sat.name = "Test Satellite"
            self.log_test("SatellitePosition", sat.sat_long == -70.0, f"Created satellite: {sat.name}")
        except Exception as e:
            self.log_test("SatellitePosition", False, f"Error: {str(e)}")

        # Test 2: Transponder
        try:
            tp = Transponder(14.25, 54, 36)
            tp.name = "Test Transponder"
            self.log_test("Transponder", tp.freq == 14.25, f"Created transponder: {tp.name}")
        except Exception as e:
            self.log_test("Transponder", False, f"Error: {str(e)}")

        # Test 3: Carrier
        try:
            car = Carrier('8PSK', 0.20, '2/3', 36)
            car.name = "Test Carrier"
            car.modcod = '8PSK 2/3'
            self.log_test("Carrier", car.modulation == '8PSK', f"Created carrier: {car.name}")
        except Exception as e:
            self.log_test("Carrier", False, f"Error: {str(e)}")

    def test_permission_system(self):
        """Test permission system"""
        print("\n" + "="*60)
        print("Testing Permission System")
        print("="*60)

        # Create second user
        try:
            success = self.db.user_auth.register_user('testuser2', 'test2@example.com', 'password456')
            self.log_test("Register User 2", success, "Second user created")
        except Exception as e:
            self.log_test("Register User 2", False, f"Error: {str(e)}")

        # Login as first user and add items
        self.db.login('testuser1', 'password123')
        sat_id = self.db.add_satellite_position('Private Satellite', -75.0, 0, 35786, 'GEO', 'Private')
        tp_id = self.db.add_transponder('Private TP', 14.20, 'Ku', 52, 36, 0, 0, 'Vertical', satellite_id=sat_id)

        # Login as second user
        self.db.login('testuser2', 'password456')

        # Test 1: User should not see private items
        try:
            satellites = self.db.list_satellite_positions(user_id=self.db.current_user_id, include_shared=True)
            private_satellites = [s for s in satellites if s['name'] == 'Private Satellite']
            self.log_test("Private Access", len(private_satellites) == 0, "Should not see private items")
        except Exception as e:
            self.log_test("Private Access", False, f"Error: {str(e)}")

        # Test 2: Check public items
        try:
            public_sats = self.db.get_public_satellites()
            self.log_test("Public Access", len(public_sats) > 0, "Should see public items")
        except Exception as e:
            self.log_test("Public Access", False, f"Error: {str(e)}")

        # Test 3: Permission denied for update
        try:
            success = self.db.update_satellite_position(sat_id, description='Should fail')
            self.log_test("Update Permission", not success, "Should not update others' items")
        except Exception as e:
            self.log_test("Update Permission", True, f"Correctly denied: {str(e)}")

        self.db.logout()

    def test_error_handling(self):
        """Test error handling"""
        print("\n" + "="*60)
        print("Testing Error Handling")
        print("="*60)

        # Test 1: Database operations without login
        try:
            self.db.logout()  # Ensure logged out
            sat_id = self.db.add_satellite_position('Should Fail', -70.0, 0, 35786, 'GEO')
            self.log_test("No Login Error", False, "Should fail without login")
        except PermissionError as e:
            self.log_test("No Login Error", True, f"Correctly denied: {str(e)}")
        except Exception as e:
            self.log_test("No Login Error", False, f"Unexpected error: {str(e)}")

        # Test 2: Invalid database operations
        try:
            satellites = self.db.list_satellite_positions(user_id=999999)
            self.log_test("Invalid User ID", True, f"Should return empty list: {len(satellites)}")
        except Exception as e:
            self.log_test("Invalid User ID", False, f"Error: {str(e)}")

    def generate_test_report(self):
        """Generate comprehensive test report"""
        print("\n" + "="*60)
        print("SYSTEM TEST REPORT")
        print("="*60)

        print(f"Total Tests: {self.test_results['total_tests']}")
        print(f"Passed: {self.test_results['passed']}")
        print(f"Failed: {self.test_results['failed']}")
        print(f"Success Rate: {(self.test_results['passed'] / self.test_results['total_tests'] * 100):.1f}%")

        print("\nTest Details:")
        print("-" * 60)
        for result in self.test_results['details']:
            print(f"[{result['status']:4s}] {result['test']}")
            if result['details'] != 'No details':
                print(f"        -> {result['details']}")

        # Export detailed report
        report_file = 'satlink_system_test_report.json'
        with open(report_file, 'w') as f:
            json.dump(self.test_results, f, indent=2)

        print(f"\nDetailed report saved to: {report_file}")
        print(f"Test database: {self.db_path}")

        # Export sample data
        self.export_sample_data()

    def export_sample_data(self):
        """Export sample data for documentation"""
        self.db.login('testuser1', 'password123')

        sample_data = {
            'users': [],
            'satellites': [],
            'transponders': [],
            'carriers': [],
            'ground_stations': [],
            'link_calculations': []
        }

        # Get user info
        user_info = self.db.get_current_user_info()
        sample_data['users'].append({
            'username': user_info['username'],
            'email': user_info['email'],
            'created_at': user_info['created_at']
        })

        # Get all data
        for sat in self.db.list_satellite_positions():
            sample_data['satellites'].append({
                'id': sat['id'],
                'name': sat['name'],
                'sat_long': sat['sat_long'],
                'sat_lat': sat['sat_lat'],
                'h_sat': sat['h_sat'],
                'orbit_type': sat['orbit_type'],
                'description': sat['description'],
                'is_shared': sat['is_shared'],
                'owner': sat['owner']
            })

        for tp in self.db.list_transponders():
            sample_data['transponders'].append({
                'id': tp['id'],
                'name': tp['name'],
                'freq': tp['freq'],
                'freq_band': tp.get('freq_band'),
                'eirp_max': tp.get('eirp_max'),
                'b_transp': tp.get('b_transp'),
                'polarization': tp.get('polarization'),
                'satellite_id': tp['satellite_id'],
                'is_shared': tp['is_shared'],
                'owner': tp['owner']
            })

        for car in self.db.list_carriers():
            sample_data['carriers'].append({
                'id': car['id'],
                'name': car['name'],
                'modcod': car['modcod'],
                'modulation': car['modulation'],
                'fec': car['fec'],
                'roll_off': car['roll_off'],
                'b_util': car['b_util'],
                'standard': car.get('standard'),
                'is_shared': car['is_shared'],
                'owner': car['owner']
            })

        for gs in self.db.list_ground_stations():
            sample_data['ground_stations'].append({
                'id': gs['id'],
                'name': gs['name'],
                'site_lat': gs['site_lat'],
                'site_long': gs['site_long'],
                'country': gs.get('country'),
                'city': gs.get('city'),
                'is_shared': gs['is_shared'],
                'owner': gs['owner']
            })

        for calc in self.db.list_link_calculations():
            sample_data['link_calculations'].append({
                'id': calc['id'],
                'name': calc['name'],
                'elevation_angle': calc.get('elevation_angle'),
                'azimuth_angle': calc.get('azimuth_angle'),
                'distance': calc.get('distance'),
                'cn0': calc.get('cn0'),
                'snr': calc.get('snr'),
                'link_margin': calc.get('link_margin'),
                'availability': calc.get('availability'),
                'is_shared': calc['is_shared'],
                'owner': calc['owner']
            })

        # Export to JSON
        sample_file = 'satlink_sample_data.json'
        with open(sample_file, 'w') as f:
            json.dump(sample_data, f, indent=2)

        print(f"Sample data exported to: {sample_file}")

        self.db.logout()


def main():
    """Run complete system tests"""
    print("SatLink Complete System Test Suite")
    print("=" * 60)
    print("Testing all components of the SatLink system...")
    print()

    # Create tester
    tester = SystemTester()

    # Run all test suites
    tester.test_user_authentication()
    tester.test_database_operations()
    tester.test_component_classes()
    tester.test_permission_system()
    tester.test_error_handling()

    # Generate report
    tester.generate_test_report()

    print("\n" + "="*60)
    print("TEST SUITE COMPLETED")
    print("="*60)

    return tester.test_results['passed'], tester.test_results['total_tests']


if __name__ == "__main__":
    passed, total = main()
    sys.exit(0 if passed == total else 1)