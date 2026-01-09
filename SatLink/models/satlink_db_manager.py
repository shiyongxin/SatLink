"""
SatLink Database Manager

This module provides a database manager class for interacting with the SatLink database.
Supports both SQLite and PostgreSQL databases.
"""

import sqlite3
import json
from datetime import datetime
from typing import List, Dict, Optional, Tuple
import sys
import os

# Add parent directory to path
sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from GrStat import GroundStation as GrStatClass
from models.simple_reception import SimpleReception
from satellite_new import Satellite
from models.satellite_components import SatellitePosition, Transponder, Carrier, calculate_eirp


class SatLinkDatabase:
    """
    SatLink Database Manager

    Manages database operations for satellite link components and calculations.
    Supports SQLite and PostgreSQL.
    """

    def __init__(self, db_path='satlink.db', db_type='sqlite'):
        """
        Initialize database connection

        Parameters
        ----------
        db_path : str
            Path to SQLite database file or PostgreSQL connection string
        db_type : str
            Database type: 'sqlite' or 'postgresql'
        """
        self.db_path = db_path
        self.db_type = db_type
        self.conn = None
        self.connect()

    def connect(self):
        """Establish database connection"""
        if self.db_type == 'sqlite':
            self.conn = sqlite3.connect(self.db_path)
            self.conn.row_factory = sqlite3.Row  # Enable dict-like access
        elif self.db_type == 'postgresql':
            try:
                import psycopg2
                from psycopg2.extras import RealDictCursor
                self.conn = psycopg2.connect(self.db_path, cursor_factory=RealDictCursor)
            except ImportError:
                raise ImportError("psycopg2 is required for PostgreSQL support")
        else:
            raise ValueError(f"Unsupported database type: {self.db_type}")

    def close(self):
        """Close database connection"""
        if self.conn:
            self.conn.close()

    def execute_script(self, script: str):
        """Execute SQL script"""
        cursor = self.conn.cursor()
        cursor.executescript(script)
        self.conn.commit()

    # ========================================================================
    # SATELLITE POSITION OPERATIONS
    # ========================================================================

    def add_satellite_position(self, name: str, sat_long: float, sat_lat: float = 0,
                                h_sat: float = 35786, orbit_type: str = 'GEO',
                                description: str = None) -> int:
        """
        Add a satellite position to the database

        Parameters
        ----------
        name : str
            Satellite name
        sat_long : float
            Satellite longitude (degrees)
        sat_lat : float, optional
            Satellite latitude (degrees)
        h_sat : float, optional
            Satellite altitude (km)
        orbit_type : str, optional
            Orbit type: GEO, MEO, LEO
        description : str, optional
            Description

        Returns
        -------
        int
            ID of inserted satellite position
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO satellite_positions
            (name, sat_long, sat_lat, h_sat, orbit_type, description)
            VALUES (?, ?, ?, ?, ?, ?)
        """, (name, sat_long, sat_lat, h_sat, orbit_type, description))
        self.conn.commit()
        return cursor.lastrowid

    def get_satellite_position(self, sat_id: int = None, name: str = None) -> Dict:
        """
        Get satellite position from database

        Parameters
        ----------
        sat_id : int, optional
            Satellite ID
        name : str, optional
            Satellite name

        Returns
        -------
        dict
            Satellite position data
        """
        cursor = self.conn.cursor()
        if sat_id:
            cursor.execute("SELECT * FROM satellite_positions WHERE id = ?", (sat_id,))
        elif name:
            cursor.execute("SELECT * FROM satellite_positions WHERE name = ?", (name,))
        else:
            raise ValueError("Must provide either sat_id or name")

        row = cursor.fetchone()
        return dict(row) if row else None

    def list_satellite_positions(self, orbit_type: str = None) -> List[Dict]:
        """List all satellite positions, optionally filtered by orbit type"""
        cursor = self.conn.cursor()
        if orbit_type:
            cursor.execute("SELECT * FROM satellite_positions WHERE orbit_type = ?", (orbit_type,))
        else:
            cursor.execute("SELECT * FROM satellite_positions")
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # TRANSPONDER OPERATIONS
    # ========================================================================

    def add_transponder(self, name: str, freq: float, eirp_max: float = 0,
                        b_transp: float = 36, back_off: float = 0, contorno: float = 0,
                        satellite_id: int = None, freq_band: str = None,
                        polarization: str = None, description: str = None) -> int:
        """Add a transponder to the database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO transponders
            (name, satellite_id, freq, freq_band, eirp_max, b_transp, back_off, contorno, polarization, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, satellite_id, freq, freq_band, eirp_max, b_transp, back_off, contorno, polarization, description))
        self.conn.commit()
        return cursor.lastrowid

    def get_transponder(self, tp_id: int = None, name: str = None) -> Dict:
        """Get transponder from database"""
        cursor = self.conn.cursor()
        if tp_id:
            cursor.execute("SELECT * FROM transponders WHERE id = ?", (tp_id,))
        elif name:
            cursor.execute("SELECT * FROM transponders WHERE name = ?", (name,))
        else:
            raise ValueError("Must provide either tp_id or name")
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_transponders(self, satellite_id: int = None, freq_band: str = None) -> List[Dict]:
        """List transponders, optionally filtered"""
        cursor = self.conn.cursor()
        if satellite_id:
            cursor.execute("SELECT * FROM transponders WHERE satellite_id = ?", (satellite_id,))
        elif freq_band:
            cursor.execute("SELECT * FROM transponders WHERE freq_band = ?", (freq_band,))
        else:
            cursor.execute("SELECT * FROM transponders")
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # CARRIER OPERATIONS
    # ========================================================================

    def add_carrier(self, name: str, modcod: str, modulation: str, fec: str,
                    roll_off: float, b_util: float = 36, standard: str = 'DVB-S2',
                    description: str = None) -> int:
        """Add a carrier/MODCOD configuration to the database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO carriers
            (name, modcod, modulation, fec, roll_off, b_util, standard, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, modcod, modulation, fec, roll_off, b_util, standard, description))
        self.conn.commit()
        return cursor.lastrowid

    def get_carrier(self, carrier_id: int = None, modcod: str = None) -> Dict:
        """Get carrier from database"""
        cursor = self.conn.cursor()
        if carrier_id:
            cursor.execute("SELECT * FROM carriers WHERE id = ?", (carrier_id,))
        elif modcod:
            cursor.execute("SELECT * FROM carriers WHERE modcod = ?", (modcod,))
        else:
            raise ValueError("Must provide either carrier_id or modcod")
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_carriers(self, modulation: str = None) -> List[Dict]:
        """List carriers, optionally filtered by modulation"""
        cursor = self.conn.cursor()
        if modulation:
            cursor.execute("SELECT * FROM carriers WHERE modulation = ?", (modulation,))
        else:
            cursor.execute("SELECT * FROM carriers ORDER BY modulation, fec")
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # GROUND STATION OPERATIONS
    # ========================================================================

    def add_ground_station(self, name: str, site_lat: float, site_long: float,
                           site_name: str = None, altitude: float = 0,
                           country: str = None, city: str = None,
                           description: str = None) -> int:
        """Add a ground station to the database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO ground_stations
            (name, site_name, site_lat, site_long, altitude, country, city, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, site_name, site_lat, site_long, altitude, country, city, description))
        self.conn.commit()
        return cursor.lastrowid

    def get_ground_station(self, gs_id: int = None, name: str = None) -> Dict:
        """Get ground station from database"""
        cursor = self.conn.cursor()
        if gs_id:
            cursor.execute("SELECT * FROM ground_stations WHERE id = ?", (gs_id,))
        elif name:
            cursor.execute("SELECT * FROM ground_stations WHERE name = ?", (name,))
        else:
            raise ValueError("Must provide either gs_id or name")
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_ground_stations(self, country: str = None) -> List[Dict]:
        """List ground stations, optionally filtered by country"""
        cursor = self.conn.cursor()
        if country:
            cursor.execute("SELECT * FROM ground_stations WHERE country = ?", (country,))
        else:
            cursor.execute("SELECT * FROM ground_stations")
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # RECEPTION SYSTEM OPERATIONS
    # ========================================================================

    def add_reception_complex(self, name: str, ground_station_id: int,
                              ant_size: float, ant_eff: float,
                              lnb_gain: float, lnb_temp: float,
                              coupling_loss: float = 0, cable_loss: float = 0,
                              polarization_loss: float = 3, max_depoint: float = 0,
                              manufacturer: str = None, model: str = None,
                              description: str = None) -> int:
        """Add a complex reception system to the database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO reception_complex
            (name, ground_station_id, ant_size, ant_eff, lnb_gain, lnb_temp,
             coupling_loss, cable_loss, polarization_loss, max_depoint, manufacturer, model, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, ground_station_id, ant_size, ant_eff, lnb_gain, lnb_temp,
              coupling_loss, cable_loss, polarization_loss, max_depoint, manufacturer, model, description))
        self.conn.commit()
        return cursor.lastrowid

    def add_reception_simple(self, name: str, ground_station_id: int,
                             gt_value: float, depoint_loss: float = 0,
                             frequency: float = None, measurement_method: str = 'specified',
                             manufacturer: str = None, model: str = None,
                             description: str = None) -> int:
        """Add a simple reception system to the database"""
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO reception_simple
            (name, ground_station_id, gt_value, depoint_loss, frequency, measurement_method, manufacturer, model, description)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (name, ground_station_id, gt_value, depoint_loss, frequency, measurement_method, manufacturer, model, description))
        self.conn.commit()
        return cursor.lastrowid

    def get_reception_system(self, rec_id: int, rec_type: str) -> Dict:
        """Get reception system from database"""
        cursor = self.conn.cursor()
        if rec_type == 'complex':
            cursor.execute("SELECT * FROM reception_complex WHERE id = ?", (rec_id,))
        elif rec_type == 'simple':
            cursor.execute("SELECT * FROM reception_simple WHERE id = ?", (rec_id,))
        else:
            raise ValueError(f"Invalid reception type: {rec_type}. Must be 'complex' or 'simple'")
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_reception_systems(self, ground_station_id: int = None) -> List[Dict]:
        """List all reception systems for a ground station"""
        cursor = self.conn.cursor()
        result = []

        if ground_station_id:
            cursor.execute("SELECT 'complex' as type, * FROM reception_complex WHERE ground_station_id = ?", (ground_station_id,))
            result.extend([dict(row) for row in cursor.fetchall()])
            cursor.execute("SELECT 'simple' as type, * FROM reception_simple WHERE ground_station_id = ?", (ground_station_id,))
            result.extend([dict(row) for row in cursor.fetchall()])
        else:
            cursor.execute("SELECT 'complex' as type, * FROM reception_complex")
            result.extend([dict(row) for row in cursor.fetchall()])
            cursor.execute("SELECT 'simple' as type, * FROM reception_simple")
            result.extend([dict(row) for row in cursor.fetchall()])

        return result

    # ========================================================================
    # LINK CALCULATION OPERATIONS
    # ========================================================================

    def save_link_calculation(self, name: str, satellite_id: int, transponder_id: int,
                               carrier_id: int, ground_station_id: int,
                               reception_type: str, reception_id: int,
                               results: Dict, margin: float = 0,
                               snr_relaxation: float = 0.1,
                               notes: str = None) -> int:
        """
        Save link calculation results to database

        Parameters
        ----------
        name : str
            Calculation name
        satellite_id, transponder_id, carrier_id, ground_station_id : int
            Component IDs
        reception_type : str
            'complex' or 'simple'
        reception_id : int
            Reception system ID
        results : dict
            Calculation results dictionary
        margin, snr_relaxation : float
            Input parameters
        notes : str
            Additional notes

        Returns
        -------
        int
            ID of inserted calculation
        """
        cursor = self.conn.cursor()
        cursor.execute("""
            INSERT INTO link_calculations
            (name, satellite_id, transponder_id, carrier_id, ground_station_id,
             reception_type, reception_id, margin, snr_relaxation,
             elevation_angle, azimuth_angle, distance,
             a_fs, a_g, a_c, a_r, a_s, a_t, a_tot,
             cn0, snr, snr_threshold, link_margin, availability, gt_value, notes)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
        """, (
            name, satellite_id, transponder_id, carrier_id, ground_station_id,
            reception_type, reception_id, margin, snr_relaxation,
            results.get('elevation_angle'), results.get('azimuth_angle'), results.get('distance'),
            results.get('a_fs'), results.get('a_g'), results.get('a_c'), results.get('a_r'),
            results.get('a_s'), results.get('a_t'), results.get('a_tot'),
            results.get('cn0'), results.get('snr'), results.get('snr_threshold'),
            results.get('link_margin'), results.get('availability'), results.get('gt_value'),
            notes
        ))
        self.conn.commit()
        return cursor.lastrowid

    def get_link_calculation(self, calc_id: int) -> Dict:
        """Get link calculation from database"""
        cursor = self.conn.cursor()
        cursor.execute("SELECT * FROM link_calculations WHERE id = ?", (calc_id,))
        row = cursor.fetchone()
        return dict(row) if row else None

    def list_link_calculations(self, ground_station_id: int = None,
                                satellite_id: int = None,
                                limit: int = None) -> List[Dict]:
        """List link calculations, optionally filtered"""
        cursor = self.conn.cursor()
        query = "SELECT * FROM link_calculations WHERE 1=1"
        params = []

        if ground_station_id:
            query += " AND ground_station_id = ?"
            params.append(ground_station_id)
        if satellite_id:
            query += " AND satellite_id = ?"
            params.append(satellite_id)

        query += " ORDER BY calculation_date DESC"
        if limit:
            query += " LIMIT ?"
            params.append(limit)

        cursor.execute(query, params)
        return [dict(row) for row in cursor.fetchall()]

    # ========================================================================
    # HELPER METHODS
    # ========================================================================

    def load_satellite_components(self, satellite_id: int, transponder_id: int,
                                   carrier_id: int) -> Tuple[SatellitePosition, Transponder, Carrier]:
        """
        Load satellite components from database and create component objects

        Returns
        -------
        tuple
            (SatellitePosition, Transponder, Carrier) objects
        """
        # Get satellite position
        sat_data = self.get_satellite_position(satellite_id)
        sat_pos = SatellitePosition(
            sat_long=sat_data['sat_long'],
            sat_lat=sat_data['sat_lat'],
            h_sat=sat_data['h_sat']
        )

        # Get transponder
        tp_data = self.get_transponder(transponder_id)
        transponder = Transponder(
            freq=tp_data['freq'],
            eirp_max=tp_data['eirp_max'],
            b_transp=tp_data['b_transp'],
            back_off=tp_data['back_off'],
            contorno=tp_data['contorno']
        )

        # Get carrier
        car_data = self.get_carrier(carrier_id)
        carrier = Carrier(
            modcod=car_data['modcod'],
            roll_off=car_data['roll_off'],
            b_util=car_data['b_util']
        )

        return sat_pos, transponder, carrier

    def load_ground_station(self, gs_id: int) -> GrStatClass:
        """Load ground station from database and create GroundStation object"""
        gs_data = self.get_ground_station(gs_id)
        return GrStatClass(gs_data['site_lat'], gs_data['site_long'])

    def load_reception_system(self, rec_id: int, rec_type: str):
        """
        Load reception system from database and create reception object

        Returns
        -------
        Reception or SimpleReception object
        """
        rec_data = self.get_reception_system(rec_id, rec_type)

        if rec_type == 'complex':
            from GrStat import Reception
            return Reception(
                ant_size=rec_data['ant_size'],
                ant_eff=rec_data['ant_eff'],
                coupling_loss=rec_data['coupling_loss'],
                polarization_loss=rec_data['polarization_loss'],
                lnb_gain=rec_data['lnb_gain'],
                lnb_noise_temp=rec_data['lnb_temp'],
                cable_loss=rec_data['cable_loss'],
                max_depoint=rec_data['max_depoint']
            )
        else:  # simple
            return SimpleReception(
                gt_value=rec_data['gt_value'],
                depoint_loss=rec_data['depoint_loss'],
                frequency=rec_data['frequency']
            )


# ============================================================================
# DATABASE INITIALIZATION
# ============================================================================

def init_database(db_path='satlink.db', schema_file=None):
    """
    Initialize SatLink database with schema

    Parameters
    ----------
    db_path : str
        Path to database file
    schema_file : str, optional
        Path to SQL schema file. If None, uses built-in schema.
    """
    if schema_file:
        with open(schema_file, 'r') as f:
            schema = f.read()
    else:
        from models.satlink_db_schema import SQL_SCHEMA
        schema = SQL_SCHEMA

    db = SatLinkDatabase(db_path)
    db.execute_script(schema)
    db.close()
    print(f"Database initialized: {db_path}")


if __name__ == "__main__":
    # Initialize database
    init_database('satlink.db')
