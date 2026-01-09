"""
Test script for SatLink web interface calculation
This simulates what happens when you click "Run Calculations" in the web interface
"""

import pickle
import sys
import os

# Add the SatLink directory to Python path
sys.path.insert(0, 'F:\\SharedFile\\80.soft_dev\\cfagoas_SatLink\\SatLink')

# Sample data based on single_point_example.py
# Format: [site_lat, site_long, sat_long, freq, max_eirp, sat_height, max_bw, bw_util,
#          modcod, pol, roll_off, ant_size, ant_eff, lnb_gain, lnb_temp, aditional_losses,
#          cable_loss, max_depoint, snr_relaxation, margin]

test_data = [
    -3.7,          # site_lat (degrees) - Brazil location
    -45.9,         # site_long (degrees)
    -70,           # sat_long (degrees) - GEO satellite
    15,            # freq (GHz) - Ku band
    54,            # max_eirp (dBW)
    35800,         # sat_height (km) - GEO altitude
    36,            # max_bw (MHz) - transponder bandwidth
    9,             # bw_util (MHz) - effective used bandwidth
    '8PSK 120/180', # modcod - modulation and coding
    'Horizontal',  # pol - polarization
    0.2,           # roll_off
    1.2,           # ant_size (m) - receiving antenna diameter
    0.6,           # ant_eff - antenna efficiency
    55,            # lnb_gain (dB)
    20,            # lnb_temp (K) - LNB noise temperature
    0,             # aditional_losses (dB)
    4,             # cable_loss (dB)
    0.1,           # max_depoint (degrees)
    1,             # snr_relaxation (internal parameter)
    0              # margin (dB)
]

print("Test Data for SatLink Web Interface Calculation")
print("=" * 50)
print("Ground Station:")
print(f"  Latitude: {test_data[0]} degrees")
print(f"  Longitude: {test_data[1]} degrees")
print()
print("Satellite:")
print(f"  Longitude: {test_data[2]} degrees")
print(f"  Frequency: {test_data[3]} GHz")
print(f"  EIRP: {test_data[4]} dBW")
print(f"  Altitude: {test_data[5]} km")
print(f"  Max Bandwidth: {test_data[6]} MHz")
print(f"  Effective Bandwidth: {test_data[7]} MHz")
print(f"  Modulation: {test_data[8]}")
print(f"  Polarization: {test_data[9]}")
print(f"  Roll-off: {test_data[10]}")
print()
print("Reception:")
print(f"  Antenna Size: {test_data[11]} m")
print(f"  Antenna Efficiency: {test_data[12]}")
print(f"  LNB Gain: {test_data[13]} dB")
print(f"  LNB Noise Temp: {test_data[14]} K")
print(f"  Additional Losses: {test_data[15]} dB")
print(f"  Cable Loss: {test_data[16]} dB")
print(f"  Max Depointing: {test_data[17]} degrees")
print()

# Save the pickle file (simulating what the web interface does)
path = 'F:\\SharedFile\\80.soft_dev\\cfagoas_SatLink\\SatLink\\temp\\args.pkl'
with open(path, 'wb') as f:
    pickle.dump(test_data, f)
    f.close()

print("Pickle file created at: temp/args.pkl")
print()
print("Running calculation...")

# Import and run the calculation function
from link_performance import sp_link_performance

# Save original stdout
import sys
original_stdout = sys.stdout

sp_link_performance()

# Restore stdout
sys.stdout = original_stdout

# Read and display the results
result_path = 'F:\\SharedFile\\80.soft_dev\\cfagoas_SatLink\\SatLink\\temp\\out.txt'
if os.path.exists(result_path):
    print()
    print("=" * 50)
    print("CALCULATION RESULTS")
    print("=" * 50)
    with open(result_path, 'r', encoding='utf-8', errors='replace') as f:
        print(f.read())
    os.remove(result_path)
else:
    print("Error: No output file generated!")
