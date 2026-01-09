"""
SatLink Database Setup Script - Automated Version

This script initializes the database with schema and sample data.
"""

import os
import sys
import sqlite3
import shutil
from datetime import datetime

# Add current directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.updated_db_manager import SatLinkDatabaseUser
from models.updated_satlink_db_schema import UPDATED_SQL_SCHEMA
from web_app import init_db_clean


def setup_database(db_path='satlink.db', clean=False):
    """
    Setup the database with schema and optional sample data

    Parameters
    ----------
    db_path : str
        Path to the database file
    clean : bool
        Whether to clean existing database
    """
    print(f"\nSetting up database at: {db_path}")

    # Clean existing database if requested
    if clean and os.path.exists(db_path):
        print("Removing existing database...")
        os.remove(db_path)

    # Initialize database
    init_db_clean(db_path)
    db = SatLinkDatabaseUser(db_path)

    # Create admin user
    print("Creating admin user...")
    if not db.user_auth.authenticate_user('admin', 'admin123'):
        db.user_auth.register_user('admin', 'admin@satlink.com', 'admin123')
        print("Admin user created: admin/admin123")
    else:
        print("Admin user already exists")

    # Create sample user
    print("Creating sample user...")
    if not db.user_auth.authenticate_user('demo', 'demo123'):
        db.user_auth.register_user('demo', 'demo@satlink.com', 'demo123')
        print("Demo user created: demo/demo123")
    else:
        print("Demo user already exists")

    # Add sample data as demo user
    print("\nAdding sample data...")
    try:
        # Login as demo user
        db.login('demo', 'demo123')

        # Sample satellites
        satellites = [
            ('StarOne C1', -70.0, 0, 35786, 'GEO', 'Brazilian GEO satellite at 70°W', True),
            ('StarOne D1', -84.0, 0, 35786, 'GEO', 'Brazilian GEO satellite at 84°W', True),
            ('Intelsat 21', -58.0, 0, 35786, 'GEO', 'Intelsat satellite at 58°W', True),
            ('StarLink 1', 0, 0, 550, 'LEO', 'LEO satellite', True),
        ]

        sat_ids = {}
        for name, long, lat, alt, orbit, desc, shared in satellites:
            sat_id = db.add_satellite_position(name, long, lat, alt, orbit, desc, shared)
            sat_ids[name] = sat_id
            print(f"  Added satellite: {name}")

        # Sample transponders
        transponders = [
            ('Ku-Band TP1', sat_ids['StarOne C1'], 14.25, 'Ku', 54, 36, 0, 0, 'Horizontal', True),
            ('Ku-Band TP2', sat_ids['StarOne C1'], 14.20, 'Ku', 52, 36, 0, 0, 'Vertical', True),
            ('C-Band TP1', sat_ids['StarOne C1'], 4.15, 'C', 40, 36, 0, 0, 'Horizontal', True),
            ('Ku-Band TP', sat_ids['StarOne D1'], 14.10, 'Ku', 50, 36, 0, 0, 'Vertical', True),
        ]

        tp_ids = {}
        for name, sat_id, freq, band, eirp, bw, back, cont, pol, shared in transponders:
            tp_id = db.add_transponder(name, freq, eirp, bw, back, cont, pol, sat_id, shared)
            tp_ids[name] = tp_id
            print(f"  Added transponder: {name}")

        # Sample carriers
        carriers = [
            ('8PSK 2/3', '8PSK 2/3', '8PSK', '2/3', 0.20, 9, 9.8, 2.4, 'DVB-S2', 'Standard DVB-S2 2/3', True),
            ('QPSK 3/4', 'QPSK 3/4', 'QPSK', '3/4', 0.35, 9, 8.5, 1.8, 'DVB-S2', 'Standard DVB-S2 3/4', True),
            ('16APSK 2/3', '16APSK 2/3', '16APSK', '2/3', 0.10, 18, 13.2, 3.2, 'DVB-S2X', 'High efficiency DVB-S2X', True),
            ('QPSK 4/5', 'QPSK 4/5', 'QPSK', '4/5', 0.35, 9, 8.0, 1.6, 'DVB-S2', 'High rate QPSK', True),
        ]

        car_ids = {}
        for name, modcod, mod, fec, roll, bw, snr, eff, std, desc, shared in carriers:
            car_id = db.add_carrier(name, modcod, mod, fec, roll, bw, snr, eff, std, desc, shared)
            car_ids[name] = car_id
            print(f"  Added carrier: {name}")

        # Sample ground stations
        ground_stations = [
            ('Brasilia Station', 'Brasilia', -15.8, -47.9, 0, 'Brazil', 'DF', 'Brasilia', 'Tropical', None, 'Main station', True),
            ('Rio Station', 'Rio de Janeiro', -22.9, -43.2, 0, 'Brazil', 'RJ', 'Rio de Janeiro', 'Tropical', None, 'Coastal station', True),
            ('Sao Paulo Station', 'Sao Paulo', -23.5, -46.6, 0, 'Brazil', 'SP', 'Sao Paulo', 'Tropical', None, 'Metropolitan station', True),
            ('Recife Station', 'Recife', -8.0, -34.9, 0, 'Brazil', 'PE', 'Recife', 'Tropical', None, 'Northeast station', True),
            ('London Station', 'London', 51.5, -0.1, 35, 'United Kingdom', 'England', 'London', 'Temperate', 1, 'European station', True),
        ]

        gs_ids = {}
        for name, site, lat, long, alt, country, region, city, climate, itu, desc, shared in ground_stations:
            gs_id = db.add_ground_station(name, lat, long, site, alt, country, region, city, climate, itu, desc, shared)
            gs_ids[name] = gs_id
            print(f"  Added ground station: {name}")

        # Sample reception systems
        # Complex systems
        complex_receptions = [
            ('1.2m Ku System', gs_ids['Brasilia Station'], 1.2, 0.60, 55, 20, 0, 4, 3, 0.1, 'Andrew', 'ANT1200', 'Compact Ku system', True),
            ('1.8m Ku System', gs_ids['Rio Station'], 1.8, 0.65, 58, 15, 0, 4, 3, 0.1, 'Gilat', 'SK1800', 'Standard Ku system', True),
            ('2.4m C System', gs_ids['Sao Paulo Station'], 2.4, 0.70, 60, 25, 0, 3, 3, 0.1, 'Vertex', 'RA2400', 'Large C system', True),
        ]

        for name, gs_id, ant, eff, lnb_g, lnb_t, coup, cable, pol, dep, man, model, desc, shared in complex_receptions:
            rec_id = db.add_reception_complex(name, gs_id, ant, eff, lnb_g, lnb_t, coup, cable, pol, dep, man, model, desc, shared)
            print(f"  Added complex reception: {name}")

        # Simple reception systems
        simple_receptions = [
            ('High-Gain Terminal', gs_ids['Brasilia Station'], 20.5, 0.5, 14.25, 'Measured', 'Gilat', 'SkyLite Pro', 'Premium terminal', True),
            ('Standard Terminal', gs_ids['Rio Station'], 18.0, 0.5, 14.25, 'Measured', 'ViaSat', 'Surfer', 'Standard terminal', True),
            ('Low-Cost Terminal', gs_ids['Recife Station'], 15.5, 0.8, 14.25, 'Calculated', 'Hughes', 'HN9000', 'Economy terminal', True),
            ('European Terminal', gs_ids['London Station'], 22.0, 0.4, 11.75, 'Measured', 'Eutelsat', 'Power', 'High performance terminal', True),
        ]

        for name, gs_id, gt, dep, freq, method, man, model, desc, shared in simple_receptions:
            rec_id = db.add_reception_simple(name, gs_id, gt, dep, freq, method, man, model, desc, shared)
            print(f"  Added simple reception: {name}")

        # Sample link calculations
        calculations = [
            ('Brasilia to StarOne C1', sat_ids['StarOne C1'], tp_ids['Ku-Band TP1'],
             car_ids['8PSK 2/3'], gs_ids['Brasilia Station'], 'simple',
             simple_receptions[0][8], 0, 0.1, True),
            ('Rio to StarOne C1', sat_ids['StarOne C1'], tp_ids['Ku-Band TP2'],
             car_ids['QPSK 3/4'], gs_ids['Rio Station'], 'complex',
             complex_receptions[1][8], 0, 0.1, True),
            ('Sao Paulo to StarOne D1', sat_ids['StarOne D1'], tp_ids['Ku-Band TP'],
             car_ids['16APSK 2/3'], gs_ids['Sao Paulo Station'], 'complex',
             complex_receptions[2][8], 0, 0.1, True),
            ('London to Intelsat 21', sat_ids['Intelsat 21'], tp_ids['C-Band TP1'],
             car_ids['QPSK 4/5'], gs_ids['London Station'], 'simple',
             simple_receptions[3][8], 0, 0.1, True),
        ]

        for name, sat_id, tp_id, car_id, gs_id, rec_type, rec_id, margin, relax, shared in calculations:
            # Simulate calculation results
            results = {
                'elevation_angle': 45 + (sat_id % 10),
                'azimuth_angle': 180 + (sat_id % 5),
                'distance': 35786 + (sat_id % 100),
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
                'gt_value': 20.5 if rec_type == 'simple' else 32.5,
                'notes': 'Sample calculation'
            }
            calc_id = db.add_link_calculation(name, sat_id, tp_id, car_id, gs_id, rec_type, rec_id, margin, relax, **results)
            print(f"  Added calculation: {name}")

        # Add some private items as admin
        db.login('admin', 'admin123')
        private_sat_id = db.add_satellite_position('Private Test Satellite', -65.0, 0, 35786, 'GEO', 'Private satellite for admin only')
        private_gs_id = db.add_ground_station('Private Test Station', -10.0, -55.0, 'PRIVATE', 0, 'Brazil', 'AM', 'Manaus', 'Tropical', None, 'Private station')

        print(f"\n  Added {len(satellites)} satellites")
        print(f"  Added {len(transponders)} transponders")
        print(f"  Added {len(carriers)} carriers")
        print(f"  Added {len(ground_stations)} ground stations")
        print(f"  Added {len(complex_receptions)} complex reception systems")
        print(f"  Added {len(simple_receptions)} simple reception systems")
        print(f"  Added {len(calculations)} link calculations")
        print(f"  Added 2 private items")

    except Exception as e:
        print(f"Error adding sample data: {e}")
    finally:
        db.logout()
        print("\nDatabase setup completed successfully!")


def main():
    """Main setup function"""
    print("SatLink Database Setup")
    print("=" * 50)

    db_path = 'satlink.db'
    clean = False  # Set to True to clean existing database

    setup_database(db_path, clean)


if __name__ == "__main__":
    main()