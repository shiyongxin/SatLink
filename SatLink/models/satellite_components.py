"""
Satellite component classes for SatLink

This module provides component classes that can be combined to create a complete satellite configuration:
- SatellitePosition: position information (longitude, latitude, altitude)
- Transponder: transponder information (frequency, EIRP, bandwidth)
- Carrier: carrier/modulation information (modulation, roll-off, FEC, bandwidth)
"""

import numpy as np
import pandas as pd
import sys


class SatellitePosition:
    """
    Satellite position information

    Parameters
    ----------
    sat_long : float
        Satellite longitude in degrees
    sat_lat : float, optional
        Satellite latitude in degrees (default: 0 for GEO satellites)
    h_sat : float, optional
        Satellite altitude in km (default: 35786 for GEO satellites)
    """

    def __init__(self, sat_long, sat_lat=0, h_sat=35786):
        self.sat_long_rad = np.radians(sat_long)  # satellite longitude in radians
        self.sat_long = sat_long  # satellite longitude in degrees
        self.sat_lat = sat_lat  # satellite latitude in degrees (for non-GEO)
        self.h_sat = h_sat  # satellite altitude in km

    def __repr__(self):
        return f"SatellitePosition(long={self.sat_long}°, lat={self.sat_lat}°, alt={self.h_sat}km)"

    def calculate_distance(self):
        """Return approximate satellite distance from Earth's center in km.

        Uses a standard Earth radius of 6371 km and the satellite's altitude.
        """
        earth_radius = 6371  # km
        return earth_radius + self.h_sat


class Transponder:
    """
    Transponder information

    Parameters
    ----------
    freq : float
        Center frequency in GHz
    eirp_max : float, optional
        Maximum EIRP in dBW (default: 0)
    b_transp : float, optional
        Total transponder bandwidth in MHz (default: 36)
    back_off : float, optional
        Output back-off in dB (default: 0)
    contorno : float, optional
        Contour/shape factor in dB (default: 0)
    """

    def __init__(self, freq, eirp_max=0, b_transp=36, back_off=0, contorno=0):
        self.freq = freq  # frequency in GHz
        self.eirp_max = eirp_max  # maximum EIRP in dBW
        self.b_transp = b_transp  # transponder bandwidth in MHz
        self.back_off = back_off  # output back-off in dB
        self.contorno = contorno  # contour/shape factor in dB

    def __repr__(self):
        return f"Transponder(freq={self.freq}GHz, EIRP_max={self.eirp_max}dBW, BW={self.b_transp}MHz)"


class Carrier:
    """
    Carrier/modulation information

    Parameters
    ----------
    modulation : str
        Modulation scheme (e.g., 'QPSK', '8PSK', '16APSK')
    roll_off : float
        Roll-off factor (typically 0.2, 0.25, or 0.35)
    fec : str
        Forward Error Correction code rate (e.g., '1/2', '2/3', '3/4')
    b_util : float, optional
        Utilized bandwidth in MHz (default: 36)
    modcod : str, optional
        Full MODCOD string (e.g., '8PSK 120/180'). If provided, will extract modulation and FEC.
    """

    def __init__(self, modulation='', roll_off=None, fec='', b_util=36, modcod=''):
        # If modcod is provided, parse it to extract modulation and FEC
        if modcod and not modulation:
            self._parse_modcod(modcod)
        else:
            self.modulation = modulation
            self.fec = fec

        self.roll_off = roll_off
        self.b_util = b_util  # utilized bandwidth in MHz

        # Calculated parameters
        self.symbol_rate = None
        self.bitrate = None
        self.snr_threshold = None

    def _parse_modcod(self, modcod):
        """Parse MODCOD string to extract modulation and FEC"""
        path = 'models/Modulation_dB.csv'
        try:
            data = pd.read_csv(path, sep=';')
            line = data.loc[(data.Modcod) == modcod]
            if not line.empty:
                self.modulation = line['Modulation'].values[0]
                self.fec = line['FEC'].values[0]
            else:
                raise ValueError(f"MODCOD '{modcod}' not found in Modulation_dB.csv")
        except FileNotFoundError:
            # Fallback: try to parse from string format like "8PSK 120/180"
            parts = modcod.split()
            if len(parts) >= 2:
                self.modulation = parts[0]
                self.fec = parts[1]
            else:
                self.modulation = modcod
                self.fec = ''

    def get_symbol_rate(self):
        """Calculate symbol rate in baud"""
        if self.symbol_rate is not None:
            return self.symbol_rate
        if self.roll_off is None:
            raise ValueError('Roll-off factor must be defined to calculate symbol rate')
        self.symbol_rate = self.b_util * 10 ** 6 / (1 + self.roll_off)
        return self.symbol_rate

    def get_bitrate(self):
        """Calculate bitrate in bps"""
        if self.bitrate is not None:
            return self.bitrate
        if self.modulation == '' or self.fec == '':
            raise ValueError('Modulation and FEC must be defined to calculate bitrate')

        path = 'models/Modulation_dB.csv'
        data = pd.read_csv(path, sep=';')
        line = data.loc[(data.Modulation == self.modulation) & (data.FEC == self.fec)]
        if line.empty:
            raise ValueError(f"Modulation '{self.modulation}' with FEC '{self.fec}' not found in Modulation_dB.csv")

        self.bitrate = self.b_util * line['Inforate efficiency bps_Hz'].values[0] * 10 ** 6
        return self.bitrate

    def get_snr_threshold(self):
        """Get SNR threshold from MODCOD table"""
        if self.snr_threshold is not None:
            return self.snr_threshold
        if self.modulation == '' or self.fec == '':
            raise ValueError('Modulation and FEC must be defined to get SNR threshold')

        path = 'models/Modulation_dB.csv'
        data = pd.read_csv(path, sep=';')
        line = data.loc[(data.Modulation == self.modulation) & (data.FEC == self.fec)]
        if line.empty:
            raise ValueError(f"Modulation '{self.modulation}' with FEC '{self.fec}' not found in Modulation_dB.csv")

        self.snr_threshold = line['C_over_N'].values[0]
        return self.snr_threshold

    def __repr__(self):
        if self.modulation and self.fec:
            return f"Carrier(mod={self.modulation}, FEC={self.fec}, roll_off={self.roll_off}, BW={self.b_util}MHz)"
        return f"Carrier(BW={self.b_util}MHz, roll_off={self.roll_off})"


def calculate_eirp(transponder, carrier):
    """
    Calculate the effective EIRP for a carrier on a transponder

    Parameters
    ----------
    transponder : Transponder
        Transponder object
    carrier : Carrier
        Carrier object

    Returns
    -------
    float
        Effective EIRP in dBW
    """
    # Protect against zero bandwidth values
    if getattr(transponder, 'b_transp', None) in (None, 0):
        transponder.b_transp = 36
    if getattr(carrier, 'b_util', None) in (None, 0):
        carrier.b_util = 36

    eirp = (transponder.eirp_max
            - transponder.back_off
            - transponder.contorno
            + 10 * np.log10(carrier.b_util / transponder.b_transp))
    return eirp


def get_modulation_params(modcod):
    """Return modulation parameters for a given MODCOD string.

    Looks up `models/Modulation_dB.csv` for a matching `Modcod` or
    `Modulation`+`FEC` entry. Returns a dict with keys:
    - modulation
    - fec
    - inforate (bits/s/Hz) or None
    - c_over_n (dB) or None
    """
    path = 'models/Modulation_dB.csv'
    try:
        data = pd.read_csv(path, sep=';')
    except Exception:
        # fallback to default CSV reader if separator different
        data = pd.read_csv(path)

    # Try exact Modcod match first
    if 'Modcod' in data.columns:
        line = data.loc[data.Modcod == modcod]
        if not line.empty:
            row = line.iloc[0]
            return {
                'modulation': row.get('Modulation', ''),
                'fec': row.get('FEC', ''),
                'inforate': row.get('Inforate efficiency bps_Hz', None),
                'c_over_n': row.get('C_over_N', None),
            }

    # Try parsing modcod like "8PSK 120/180" or short FEC like "8PSK 2/3"
    parts = str(modcod).split()
    if len(parts) >= 2:
        modulation = parts[0]
        fec = parts[1]

        # If fec is in short form like '2/3', convert to scaled '/180' form used in CSV
        if '/' in fec:
            nums = fec.split('/')
            try:
                num = int(nums[0])
                den = int(nums[1])
                if den != 0:
                    scaled = int(round(num / den * 180))
                    fec_scaled = f"{scaled}/180"
                else:
                    fec_scaled = fec
            except Exception:
                fec_scaled = fec
        else:
            fec_scaled = fec

        # Try exact match with provided FEC first
        line = data.loc[(data.Modulation == modulation) & (data.FEC == fec)]
        if line.empty and fec_scaled != fec:
            # Try scaled form (e.g., '2/3' -> '120/180')
            line = data.loc[(data.Modulation == modulation) & (data.FEC == fec_scaled)]

        if not line.empty:
            row = line.iloc[0]
            return {
                'modulation': row.get('Modulation', modulation),
                'fec': row.get('FEC', fec_scaled if row.get('FEC', None) is None else row.get('FEC')),
                'inforate': row.get('Inforate efficiency bps_Hz', None),
                'c_over_n': row.get('C_over_N', None),
            }

    # Last resort: try matching modulation only
    line = data.loc[data.Modulation == str(modcod)]
    if not line.empty:
        row = line.iloc[0]
        return {
            'modulation': row.get('Modulation', ''),
            'fec': row.get('FEC', ''),
            'inforate': row.get('Inforate efficiency bps_Hz', None),
            'c_over_n': row.get('C_over_N', None),
        }

    raise ValueError(f"MODCOD or modulation '{modcod}' not found in {path}")
