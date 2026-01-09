"""
SatLink Database Demo Script

This script demonstrates how to use the SatLink database for storing and retrieving
satellite link components and performing link budget calculations.
"""

import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from models.satlink_db_manager import SatLinkDatabase
from models.satlink_db_schema_clean import SQL_SCHEMA_CLEAN
import json


def init_database_clean(db_path='satlink.db'):
    """Initialize database with clean schema (no sample data)"""
    import sqlite3
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()
    cursor.executescript(SQL_SCHEMA_CLEAN)
    conn.commit()
    conn.close()
    print(f"Database initialized: {db_path}")

print("=" * 80)
print("SatLink Database Demo")
print("=" * 80)
print()

# ============================================================================
# STEP 1: Initialize Database
# ============================================================================
print("STEP 1: Initializing Database")
print("-" * 80)

db_path = 'satlink_demo.db'

# Remove existing database if it exists
if os.path.exists(db_path):
    os.remove(db_path)
    print(f"Removed existing database: {db_path}")

# Initialize new database
init_database_clean(db_path)
print()

# ============================================================================
# STEP 2: Create Database Connection
# ============================================================================
print("STEP 2: Creating Database Connection")
print("-" * 80)

db = SatLinkDatabase(db_path)
print(f"Connected to database: {db_path}")
print()

# ============================================================================
# STEP 3: Add Satellite Positions
# ============================================================================
print("STEP 3: Adding Satellite Positions")
print("-" * 80)

satellites = [
    ('StarOne C1', -70.0, 0, 35786, 'GEO', 'Brazilian GEO satellite at 70°W'),
    ('StarOne D1', -84.0, 0, 35786, 'GEO', 'Brazilian GEO satellite at 84°W'),
    ('Intelsat 21', -58.0, 0, 35786, 'GEO', 'Intelsat satellite at 58°W'),
]

sat_ids = {}
for name, long, lat, alt, orbit, desc in satellites:
    sat_id = db.add_satellite_position(name, long, lat, alt, orbit, desc)
    sat_ids[name] = sat_id
    print(f"  Added: {name} (ID: {sat_id}) at {long}°")
print()

# ============================================================================
# STEP 4: Add Transponders
# ============================================================================
print("STEP 4: Adding Transponders")
print("-" * 80)

transponders = [
    ('Ku-Band TP1', sat_ids['StarOne C1'], 14.25, 'Ku', 54, 36, 0, 0, 'Horizontal'),
    ('Ku-Band TP2', sat_ids['StarOne C1'], 14.20, 'Ku', 52, 36, 0, 0, 'Vertical'),
    ('C-Band TP1', sat_ids['StarOne C1'], 4.15, 'C', 40, 36, 0, 0, 'Horizontal'),
]

tp_ids = {}
for name, sat_id, freq, band, eirp, bw, back, cont, pol in transponders:
    tp_id = db.add_transponder(name, freq, eirp, bw, back, cont, sat_id, band, pol)
    tp_ids[name] = tp_id
    print(f"  Added: {name} (ID: {tp_id}) - {band}-Band @ {freq} GHz, EIRP: {eirp} dBW")
print()

# ============================================================================
# STEP 5: Add Carriers (MODCODs)
# ============================================================================
print("STEP 5: Adding Carrier Configurations")
print("-" * 80)

carriers = [
    ('8PSK 2/3', '8PSK 120/180', '8PSK', '2/3', 0.20, 9, 'DVB-S2'),
    ('QPSK 3/4', 'QPSK 3/4', 'QPSK', '3/4', 0.35, 9, 'DVB-S2'),
    ('16APSK 2/3', '16APSK 2/3', '16APSK', '2/3', 0.10, 18, 'DVB-S2'),
]

car_ids = {}
for name, modcod, mod, fec, roll, bw, std in carriers:
    car_id = db.add_carrier(name, modcod, mod, fec, roll, bw, std)
    car_ids[name] = car_id
    print(f"  Added: {name} (ID: {car_id}) - {modcod}, Roll-off: {roll}")
print()

# ============================================================================
# STEP 6: Add Ground Stations
# ============================================================================
print("STEP 6: Adding Ground Stations")
print("-" * 80)

ground_stations = [
    ('Brasilia Station', 'Brasilia', -15.8, -47.9, 0, 'Brazil', 'Brasilia'),
    ('Rio Station', 'Rio de Janeiro', -22.9, -43.2, 0, 'Brazil', 'Rio de Janeiro'),
    ('Sao Paulo Station', 'Sao Paulo', -23.5, -46.6, 0, 'Brazil', 'Sao Paulo'),
    ('Recife Station', 'Recife', -8.0, -34.9, 0, 'Brazil', 'Recife'),
]

gs_ids = {}
for name, site, lat, long, alt, country, city in ground_stations:
    gs_id = db.add_ground_station(name, lat, long, site, alt, country, city)
    gs_ids[name] = gs_id
    print(f"  Added: {name} (ID: {gs_id}) - {city} ({lat}°, {long}°)")
print()

# ============================================================================
# STEP 7: Add Reception Systems
# ============================================================================
print("STEP 7: Adding Reception Systems")
print("-" * 80)

# Complex reception systems
complex_receptions = [
    ('1.2m Ku System', gs_ids['Brasilia Station'], 1.2, 0.60, 55, 20, 0, 4, 3, 0.1),
    ('1.8m Ku System', gs_ids['Rio Station'], 1.8, 0.65, 58, 15, 0, 4, 3, 0.1),
    ('2.4m C System', gs_ids['Sao Paulo Station'], 2.4, 0.70, 60, 25, 0, 3, 3, 0.1),
]

complex_ids = {}
for name, gs_id, ant, eff, lnb_g, lnb_t, coup, cable, pol, dep in complex_receptions:
    rec_id = db.add_reception_complex(name, gs_id, ant, eff, lnb_g, lnb_t, coup, cable, pol, dep)
    complex_ids[name] = rec_id
    print(f"  Added Complex: {name} (ID: {rec_id}) - {ant}m antenna, LNB: {lnb_g}dB/{lnb_t}K")

# Simple reception systems
simple_receptions = [
    ('High-Gain Terminal', gs_ids['Brasilia Station'], 20.5, 0.5, 14.25),
    ('Standard Terminal', gs_ids['Rio Station'], 18.0, 0.5, 14.25),
    ('Low-Cost Terminal', gs_ids['Recife Station'], 15.5, 0.8, 14.25),
]

simple_ids = {}
for name, gs_id, gt, dep, freq in simple_receptions:
    rec_id = db.add_reception_simple(name, gs_id, gt, dep, freq)
    simple_ids[name] = rec_id
    print(f"  Added Simple: {name} (ID: {rec_id}) - G/T: {gt} dB/K")
print()

# ============================================================================
# STEP 8: Query Data from Database
# ============================================================================
print("STEP 8: Querying Data from Database")
print("-" * 80)

# List all satellites
print("\nAll Satellites:")
print("-" * 40)
sats = db.list_satellite_positions()
for sat in sats:
    print(f"  {sat['name']:20s} - {sat['sat_long']:6.1f}° ({sat['orbit_type']})")

# List all transponders for a satellite
print("\nTransponders for StarOne C1:")
print("-" * 40)
tps = db.list_transponders(satellite_id=sat_ids['StarOne C1'])
for tp in tps:
    print(f"  {tp['name']:20s} - {tp['freq_band']}-Band @ {tp['freq']} GHz")

# List all ground stations in Brazil
print("\nGround Stations in Brazil:")
print("-" * 40)
gss = db.list_ground_stations(country='Brazil')
for gs in gss:
    print(f"  {gs['name']:25s} - {gs['city']:20s} ({gs['site_lat']:.1f}°, {gs['site_long']:.1f}°)")

# List reception systems for Brasilia Station
print("\nReception Systems for Brasilia Station:")
print("-" * 40)
recs = db.list_reception_systems(ground_station_id=gs_ids['Brasilia Station'])
for rec in recs:
    if rec['type'] == 'complex':
        print(f"  Complex: {rec['name']:20s} - {rec['ant_size']}m antenna")
    else:
        print(f"  Simple:  {rec['name']:20s} - G/T: {rec['gt_value']} dB/K")

print()

# ============================================================================
# STEP 9: Load Components
# ============================================================================
print("STEP 9: Loading Components for Link Calculation")
print("-" * 80)

# Load components from database
sat_pos, transponder, carrier = db.load_satellite_components(
    satellite_id=sat_ids['StarOne C1'],
    transponder_id=tp_ids['Ku-Band TP1'],
    carrier_id=car_ids['8PSK 2/3']
)

print(f"Loaded Satellite Position: {sat_pos}")
print(f"Loaded Transponder: {transponder}")
print(f"Loaded Carrier: {carrier}")
print()

# Load ground station
ground_station = db.load_ground_station(gs_ids['Brasilia Station'])
print(f"Loaded Ground Station: Lat={ground_station.site_lat}°, Long={ground_station.site_long}°")
print()

# Load reception system
reception = db.load_reception_system(simple_ids['High-Gain Terminal'], 'simple')
print(f"Loaded Reception System: {reception}")
print()

# ============================================================================
# STEP 10: Export to JSON
# ============================================================================
print("STEP 10: Exporting Database Summary to JSON")
print("-" * 80)

summary = {
    'satellites': db.list_satellite_positions(),
    'transponders': db.list_transponders(),
    'carriers': db.list_carriers(),
    'ground_stations': db.list_ground_stations(),
}

json_file = 'satlink_db_summary.json'
with open(json_file, 'w', encoding='utf-8') as f:
    json.dump(summary, f, indent=2, ensure_ascii=False)

print(f"Database summary exported to: {json_file}")
print()

# ============================================================================
# Summary
# ============================================================================
print("=" * 80)
print("DEMO COMPLETE")
print("=" * 80)
print()
print("Database Statistics:")
print(f"  Satellites: {len(summary['satellites'])}")
print(f"  Transponders: {len(summary['transponders'])}")
print(f"  Carriers: {len(summary['carriers'])}")
print(f"  Ground Stations: {len(summary['ground_stations'])}")
print()
print(f"Database file: {db_path}")
print(f"JSON summary: {json_file}")
print()

# Close database
db.close()
print("Database connection closed.")
