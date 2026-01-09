"""
Test script demonstrating the new component-based satellite structure

This shows how to use SatellitePosition, Transponder, and Carrier classes
to create a Satellite object.
"""

import sys
import os

# Add the SatLink directory to Python path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from GrStat import GroundStation, Reception
from satellite_new import Satellite
from models.satellite_components import SatellitePosition, Transponder, Carrier, calculate_eirp

print("=" * 70)
print("NEW COMPONENT-BASED SATELLITE STRUCTURE DEMONSTRATION")
print("=" * 70)
print()

# ============================================================================
# Method 1: Using component objects (recommended new approach)
# ============================================================================
print("METHOD 1: Using Component Objects")
print("-" * 70)

# Create satellite position
sat_pos = SatellitePosition(
    sat_long=-70,    # Satellite longitude (degrees)
    sat_lat=0,       # Satellite latitude (0 for GEO)
    h_sat=35786      # Altitude (km) - standard GEO altitude
)
print(f"Satellite Position: {sat_pos}")

# Create transponder
transponder = Transponder(
    freq=15,         # Frequency (GHz) - Ku band
    eirp_max=54,     # Maximum EIRP (dBW)
    b_transp=36,     # Transponder bandwidth (MHz)
    back_off=0,      # Output back-off (dB)
    contorno=0       # Contour factor (dB)
)
print(f"Transponder: {transponder}")

# Create carrier
carrier = Carrier(
    modcod='8PSK 120/180',  # MODCOD string (will parse modulation and FEC)
    roll_off=0.2,           # Roll-off factor
    b_util=9                # Utilized bandwidth (MHz)
)
print(f"Carrier: {carrier}")
print(f"  - Modulation: {carrier.modulation}")
print(f"  - FEC: {carrier.fec}")
print(f"  - Symbol Rate: {carrier.get_symbol_rate()/1e6:.2f} Mbaud")
print(f"  - Bitrate: {carrier.get_bitrate()/1e6:.2f} Mbps")
print(f"  - SNR Threshold: {carrier.get_snr_threshold():.2f} dB")

# Calculate effective EIRP
effective_eirp = calculate_eirp(transponder, carrier)
print(f"\nEffective EIRP: {effective_eirp:.2f} dBW")
print(f"  Formula: EIRP_max - back_off - contorno + 10*log10(b_util/b_transp)")
print(f"  = {transponder.eirp_max} - {transponder.back_off} - {transponder.contorno} + 10*log10({carrier.b_util}/{transponder.b_transp})")
print(f"  = {effective_eirp:.2f} dBW")

# Create satellite using components
satellite = Satellite(sat_pos, transponder, carrier)
print(f"\nSatellite created: {satellite.__class__.__name__}")
print()

# ============================================================================
# Method 2: Using backward-compatible parameters (old approach)
# ============================================================================
print("\nMETHOD 2: Using Backward-Compatible Parameters")
print("-" * 70)

# Create satellite with individual parameters (same as old sat.py)
satellite_old_style = Satellite(
    sat_long=-70,
    freq=15,
    eirp_max=54,
    h_sat=35786,
    b_transp=36,
    b_util=9,
    back_off=0,
    contorno=0,
    modcod='8PSK 120/180',
    roll_off=0.2
)
print("Satellite created using individual parameters (backward compatible)")
print()

# ============================================================================
# Demonstrate link calculation
# ============================================================================
print("\n" + "=" * 70)
print("LINK CALCULATION DEMONSTRATION")
print("=" * 70)
print()

# Create ground station
station = GroundStation(
    site_lat=-3.7,    # Brazil location
    site_long=-45.9
)
print(f"Ground Station: Lat={station.site_lat}°, Long={station.site_long}°")

# Create reception system
reception = Reception(
    ant_size=1.2,     # Antenna diameter (m)
    ant_eff=0.6,      # Antenna efficiency
    coupling_loss=0,  # Coupling loss (dB)
    polarization_loss=3,  # Polarization loss (dB)
    lnb_gain=55,      # LNB gain (dB)
    lnb_temp=20,      # LNB noise temperature (K)
    cable_loss=4,     # Cable loss (dB)
    max_depoint=0.1   # Maximum depointing (degrees)
)
print(f"Reception: Antenna={reception.ant_size}m, LNB Gain={reception.lnb_gain}dB")

# Associate ground station and reception to satellite
satellite.set_grstation(station)
satellite.set_reception(reception)

print()
print("Link Parameters:")
print(f"  Elevation Angle: {satellite.get_elevation():.2f}°")
print(f"  Azimuth: {satellite.get_azimuth():.2f}°")
print(f"  Distance: {satellite.get_distance():.2f} km")

# Get link attenuation at 0.001% of time
print()
print("Link Attenuation at 0.001% of time:")
a_fs, a_dep, a_g, a_c, a_r, a_s, a_t, a_tot = satellite.get_link_attenuation(p=0.001)
print(f"  Free Space: {a_fs:.2f} dB")
print(f"  Gaseous: {a_g:.2f} dB")
print(f"  Cloud: {a_c:.2f} dB")
print(f"  Rain: {a_r:.2f} dB")
print(f"  Scintillation: {a_s:.2f} dB")
print(f"  Total Atmospheric: {a_t:.2f} dB")
print(f"  Depointing: {a_dep:.2f} dB")
print(f"  TOTAL: {a_tot:.2f} dB")

# Get C/N and SNR
print()
print("Link Budget:")
print(f"  C/N0: {satellite.get_c_over_n0(0.001):.2f} dB-Hz")
print(f"  SNR: {satellite.get_snr(0.001):.2f} dB")
print(f"  SNR Threshold: {satellite.get_reception_threshold():.2f} dB")
print(f"  Figure of Merit (G/T): {satellite.get_figure_of_merit():.2f} dB/K")

# Get availability
availability = satellite.get_availability(margin=0, relaxation=0.1)
print()
print(f"Availability: {availability}%")

print()
print("=" * 70)
print("TEST COMPLETED SUCCESSFULLY")
print("=" * 70)
