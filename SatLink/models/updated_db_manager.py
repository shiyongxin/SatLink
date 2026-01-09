"""
Updated SatLink Database Manager with User System

This module provides a database manager class for interacting with the
SatLink database with user authentication and sharing capabilities.
"""

import sqlite3
import json
import os
from datetime import datetime, timedelta
from typing import Optional, Dict, List, Union, Any
from .user_auth import UserAuth


class SatLinkDatabaseUser:
    """
    Updated SatLink Database Manager with User System

    Handles all database operations with user authentication and sharing support.
    """

    def __init__(self, db_path: str = 'satlink.db'):
        """
        Initialize the database manager

        Parameters
        ----------
        db_path : str
            Path to the SQLite database file
        """
        self.db_path = db_path
        self.user_auth = UserAuth(db_path)
        self.current_user_id = None
        self.session_token = None

    def login(self, username: str, password: str) -> bool:
        """
        User login and set current user

        Parameters
        ----------
        username : str
            Username or email
        password : str
            Password

        Returns
        -------
        bool
            True if login successful, False otherwise
        """
        user_id = self.user_auth.authenticate_user(username, password)
        if user_id:
            self.current_user_id = user_id
            self.session_token = self.user_auth.create_session(user_id)
            return True
        return False

    def logout(self):
        """Logout current user"""
        if self.session_token:
            self.user_auth.logout_user(self.session_token)
            self.session_token = None
        self.current_user_id = None

    def validate_current_session(self) -> bool:
        """Validate current user session"""
        if self.session_token:
            self.current_user_id = self.user_auth.validate_session(self.session_token)
            return self.current_user_id is not None
        return False

    def get_current_user_info(self) -> Optional[Dict]:
        """Get current user information"""
        if self.current_user_id:
            return self.user_auth.get_user_info(self.current_user_id)
        return None

    # =========================================================================
    # Satellite Positions
    # =========================================================================

    def add_satellite_position(self, name: str, sat_long: float, sat_lat: float = 0,
                              h_sat: float = 35786, orbit_type: str = 'GEO',
                              description: str = '', is_shared: bool = False) -> int:
        """
        Add satellite position (requires login)

        Parameters
        ----------
        name : str
            Satellite name
        sat_long : float
            Satellite longitude (degrees)
        sat_lat : float
            Satellite latitude (degrees)
        h_sat : float
            Satellite height (km)
        orbit_type : str
            Orbit type (GEO, MEO, LEO)
        description : str
            Description
        is_shared : bool
            Whether to share publicly

        Returns
        -------
        int
            Satellite ID
        """
        if not self.current_user_id:
            raise PermissionError("Login required to add satellite position")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO satellite_positions
                (name, sat_long, sat_lat, h_sat, orbit_type, description, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, sat_long, sat_lat, h_sat, orbit_type, description,
                  self.current_user_id, is_shared))
            conn.commit()
            return cursor.lastrowid

    def list_satellite_positions(self, user_id: Optional[int] = None,
                               include_shared: bool = True) -> List[Dict]:
        """
        List satellite positions

        Parameters
        ----------
        user_id : int, optional
            User ID to filter by. If None, uses current user
        include_shared : bool
            Whether to include shared items from other users

        Returns
        -------
        list
            List of satellite positions
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id is None:
                user_id = self.current_user_id

            if user_id and include_shared:
                cursor.execute("""
                    SELECT sp.*, u.username as owner
                    FROM satellite_positions sp
                    JOIN users u ON sp.user_id = u.id
                    WHERE sp.user_id = ? OR sp.is_shared = 1
                    ORDER BY sp.name
                """, (user_id,))
            elif user_id:
                cursor.execute("""
                    SELECT sp.*, u.username as owner
                    FROM satellite_positions sp
                    JOIN users u ON sp.user_id = u.id
                    WHERE sp.user_id = ?
                    ORDER BY sp.name
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT sp.*, u.username as owner
                    FROM satellite_positions sp
                    JOIN users u ON sp.user_id = u.id
                    WHERE sp.is_shared = 1
                    ORDER BY sp.name
                """)

            satellites = []
            for row in cursor.fetchall():
                sat = dict(row)
                satellites.append(sat)

            return satellites

    def update_satellite_position(self, sat_id: int, **kwargs) -> bool:
        """
        Update satellite position (requires ownership)

        Parameters
        ----------
        sat_id : int
            Satellite ID
        **kwargs
            Fields to update

        Returns
        -------
        bool
            True if successful
        """
        if not self.current_user_id:
            raise PermissionError("Login required")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check ownership
            cursor.execute("""
                SELECT user_id FROM satellite_positions WHERE id = ?
            """, (sat_id,))
            result = cursor.fetchone()
            if not result or result[0] != self.current_user_id:
                raise PermissionError("Only owner can update satellite")

            # Build update query
            update_fields = []
            values = []
            for field, value in kwargs.items():
                if field in ['name', 'sat_long', 'sat_lat', 'h_sat', 'orbit_type',
                           'description', 'is_shared']:
                    update_fields.append(f"{field} = ?")
                    values.append(value)

            if not update_fields:
                return False

            values.append(sat_id)
            cursor.execute(f"""
                UPDATE satellite_positions
                SET {', '.join(update_fields)}, updated_at = CURRENT_TIMESTAMP
                WHERE id = ?
            """, values)
            conn.commit()
            return cursor.rowcount > 0

    def delete_satellite_position(self, sat_id: int) -> bool:
        """
        Delete satellite position (requires ownership)

        Parameters
        ----------
        sat_id : int
            Satellite ID

        Returns
        -------
        bool
            True if successful
        """
        if not self.current_user_id:
            raise PermissionError("Login required")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check ownership and delete related transponders
            cursor.execute("""
                SELECT user_id FROM satellite_positions WHERE id = ?
            """, (sat_id,))
            result = cursor.fetchone()
            if not result or result[0] != self.current_user_id:
                raise PermissionError("Only owner can delete satellite")

            # Delete related transponders first
            cursor.execute("""
                DELETE FROM transponders WHERE satellite_id = ?
            """, (sat_id,))

            # Delete satellite
            cursor.execute("""
                DELETE FROM satellite_positions WHERE id = ?
            """, (sat_id,))
            conn.commit()
            return cursor.rowcount > 0

    def make_satellite_public(self, sat_id: int) -> bool:
        """Make satellite position public"""
        return self.update_satellite_position(sat_id, is_shared=True)

    def make_satellite_private(self, sat_id: int) -> bool:
        """Make satellite position private"""
        return self.update_satellite_position(sat_id, is_shared=False)

    # =========================================================================
    # Transponders
    # =========================================================================

    def add_transponder(self, name: str, freq: float, freq_band: str = None,
                       eirp_max: float = 0, b_transp: float = 36,
                       back_off: float = 0, contorno: float = 0,
                       polarization: str = None, satellite_id: int = None,
                       is_shared: bool = False) -> int:
        """
        Add transponder (requires login)

        Parameters
        ----------
        name : str
            Transponder name
        freq : float
            Frequency (GHz)
        freq_band : str, optional
            Frequency band (C, Ku, Ka, Q)
        eirp_max : float
            Maximum EIRP (dBW)
        b_transp : float
            Transponder bandwidth (MHz)
        back_off : float
            Output back-off (dB)
        contorno : float
            Contour factor (dB)
        polarization : str, optional
            Polarization
        satellite_id : int, optional
            Associated satellite ID
        is_shared : bool
            Whether to share publicly

        Returns
        -------
        int
            Transponder ID
        """
        if not self.current_user_id:
            raise PermissionError("Login required to add transponder")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO transponders
                (name, freq, freq_band, eirp_max, b_transp, back_off, contorno,
                 polarization, satellite_id, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, freq, freq_band, eirp_max, b_transp, back_off, contorno,
                  polarization, satellite_id, self.current_user_id, is_shared))
            conn.commit()
            return cursor.lastrowid

    def list_transponders(self, satellite_id: int = None, user_id: int = None,
                         include_shared: bool = True) -> List[Dict]:
        """
        List transponders

        Parameters
        ----------
        satellite_id : int, optional
            Filter by satellite ID
        user_id : int, optional
            User ID to filter by
        include_shared : bool
            Whether to include shared items

        Returns
        -------
        list
            List of transponders
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id is None:
                user_id = self.current_user_id

            query = """
                SELECT t.*, u.username as owner, sp.name as satellite_name,
                       sp.sat_long as sat_long, sp.sat_lat as sat_lat
                FROM transponders t
                JOIN users u ON t.user_id = u.id
                LEFT JOIN satellite_positions sp ON t.satellite_id = sp.id
            """

            conditions = []
            params = []

            if satellite_id:
                conditions.append("t.satellite_id = ?")
                params.append(satellite_id)

            if user_id and include_shared:
                conditions.append("(t.user_id = ? OR t.is_shared = 1)")
                params.append(user_id)
            elif user_id:
                conditions.append("t.user_id = ?")
                params.append(user_id)
            elif include_shared:
                conditions.append("t.is_shared = 1")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY t.name"

            cursor.execute(query, params)

            transponders = []
            for row in cursor.fetchall():
                tp = dict(row)
                transponders.append(tp)

            return transponders

    def update_transponder(self, tp_id: int, **kwargs) -> bool:
        """
        Update transponder

        Parameters
        ----------
        tp_id : int
            Transponder ID
        **kwargs
            Fields to update (name, freq, freq_band, eirp_max, b_transp,
            back_off, contorno, polarization, satellite_id, is_shared)

        Returns
        -------
        bool
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Build UPDATE query dynamically
            allowed_fields = ['name', 'freq', 'freq_band', 'eirp_max', 'b_transp',
                            'back_off', 'contorno', 'polarization', 'satellite_id',
                            'is_shared']
            updates = []
            params = []

            for field in allowed_fields:
                if field in kwargs:
                    updates.append(f"{field} = ?")
                    params.append(kwargs[field])

            if not updates:
                return False

            params.append(tp_id)
            query = f"UPDATE transponders SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    def make_transponder_public(self, tp_id: int) -> bool:
        """Make transponder public"""
        return self.update_transponder(tp_id, is_shared=True)

    def make_transponder_private(self, tp_id: int) -> bool:
        """Make transponder private"""
        return self.update_transponder(tp_id, is_shared=False)

    # =========================================================================
    # Carriers
    # =========================================================================

    def add_carrier(self, name: str, modcod: str, modulation: str, fec: str,
                   roll_off: float, b_util: float = 36, snr_threshold: float = None,
                   spectral_efficiency: float = None, standard: str = None,
                   description: str = '', is_shared: bool = False) -> int:
        """
        Add carrier configuration (requires login)

        Parameters
        ----------
        name : str
            Carrier name
        modcod : str
            MODCOD string
        modulation : str
            Modulation type
        fec : str
            FEC rate
        roll_off : float
            Roll-off factor
        b_util : float
            Utilized bandwidth (MHz)
        snr_threshold : float, optional
            SNR threshold (dB)
        spectral_efficiency : float, optional
            Spectral efficiency (bits/s/Hz)
        standard : str, optional
            Standard (DVB-S, S2, S2X)
        description : str
            Description
        is_shared : bool
            Whether to share publicly

        Returns
        -------
        int
            Carrier ID
        """
        if not self.current_user_id:
            raise PermissionError("Login required to add carrier")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO carriers
                (name, modcod, modulation, fec, roll_off, b_util, snr_threshold,
                 spectral_efficiency, standard, description, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, modcod, modulation, fec, roll_off, b_util, snr_threshold,
                  spectral_efficiency, standard, description,
                  self.current_user_id, is_shared))
            conn.commit()
            return cursor.lastrowid

    def list_carriers(self, user_id: int = None, include_shared: bool = True) -> List[Dict]:
        """
        List carrier configurations

        Parameters
        ----------
        user_id : int, optional
            User ID to filter by
        include_shared : bool
            Whether to include shared items

        Returns
        -------
        list
            List of carriers
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id is None:
                user_id = self.current_user_id

            if user_id and include_shared:
                cursor.execute("""
                    SELECT c.*, u.username as owner
                    FROM carriers c
                    JOIN users u ON c.user_id = u.id
                    WHERE c.user_id = ? OR c.is_shared = 1
                    ORDER BY c.name
                """, (user_id,))
            elif user_id:
                cursor.execute("""
                    SELECT c.*, u.username as owner
                    FROM carriers c
                    JOIN users u ON c.user_id = u.id
                    WHERE c.user_id = ?
                    ORDER BY c.name
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT c.*, u.username as owner
                    FROM carriers c
                    JOIN users u ON c.user_id = u.id
                    WHERE c.is_shared = 1
                    ORDER BY c.name
                """)

            carriers = []
            for row in cursor.fetchall():
                car = dict(row)
                carriers.append(car)

            return carriers

    def update_carrier(self, car_id: int, **kwargs) -> bool:
        """
        Update carrier

        Parameters
        ----------
        car_id : int
            Carrier ID
        **kwargs
            Fields to update (name, modcod, modulation, fec, roll_off, b_util,
            snr_threshold, spectral_efficiency, standard, description, is_shared)

        Returns
        -------
        bool
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Build UPDATE query dynamically
            allowed_fields = ['name', 'modcod', 'modulation', 'fec', 'roll_off',
                            'b_util', 'snr_threshold', 'spectral_efficiency',
                            'standard', 'description', 'is_shared']
            updates = []
            params = []

            for field in allowed_fields:
                if field in kwargs:
                    updates.append(f"{field} = ?")
                    params.append(kwargs[field])

            if not updates:
                return False

            params.append(car_id)
            query = f"UPDATE carriers SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    def make_carrier_public(self, car_id: int) -> bool:
        """Make carrier public"""
        return self.update_carrier(car_id, is_shared=True)

    def make_carrier_private(self, car_id: int) -> bool:
        """Make carrier private"""
        return self.update_carrier(car_id, is_shared=False)

    # =========================================================================
    # Ground Stations
    # =========================================================================

    def add_ground_station(self, name: str, site_lat: float, site_long: float,
                          site_name: str = None, altitude: float = 0,
                          country: str = None, region: str = None,
                          city: str = None, climate_zone: str = None,
                          itu_region: str = None, description: str = '',
                          is_shared: bool = False) -> int:
        """
        Add ground station (requires login)

        Parameters
        ----------
        name : str
            Ground station name
        site_lat : float
            Site latitude (degrees)
        site_long : float
            Site longitude (degrees)
        site_name : str, optional
            Site identifier/code
        altitude : float
            Altitude (m)
        country : str, optional
            Country
        region : str, optional
            Region/state
        city : str, optional
            City
        climate_zone : str, optional
            Climate zone
        itu_region : str, optional
            ITU region
        description : str
            Description
        is_shared : bool
            Whether to share publicly

        Returns
        -------
        int
            Ground station ID
        """
        if not self.current_user_id:
            raise PermissionError("Login required to add ground station")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO ground_stations
                (name, site_lat, site_long, site_name, altitude, country, region,
                 city, climate_zone, itu_region, description, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, site_lat, site_long, site_name, altitude, country, region,
                  city, climate_zone, itu_region, description,
                  self.current_user_id, is_shared))
            conn.commit()
            return cursor.lastrowid

    def list_ground_stations(self, country: str = None, user_id: int = None,
                           include_shared: bool = True) -> List[Dict]:
        """
        List ground stations

        Parameters
        ----------
        country : str, optional
            Filter by country
        user_id : int, optional
            User ID to filter by
        include_shared : bool
            Whether to include shared items

        Returns
        -------
        list
            List of ground stations
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id is None:
                user_id = self.current_user_id

            query = """
                SELECT gs.*, u.username as owner
                FROM ground_stations gs
                JOIN users u ON gs.user_id = u.id
            """

            conditions = []
            params = []

            if country:
                conditions.append("gs.country = ?")
                params.append(country)

            if user_id and include_shared:
                conditions.append("(gs.user_id = ? OR gs.is_shared = 1)")
                params.append(user_id)
            elif user_id:
                conditions.append("gs.user_id = ?")
                params.append(user_id)
            elif include_shared:
                conditions.append("gs.is_shared = 1")

            if conditions:
                query += " WHERE " + " AND ".join(conditions)

            query += " ORDER BY gs.name"

            cursor.execute(query, params)

            ground_stations = []
            for row in cursor.fetchall():
                gs = dict(row)
                ground_stations.append(gs)

            return ground_stations

    def update_ground_station(self, gs_id: int, **kwargs) -> bool:
        """
        Update ground station

        Parameters
        ----------
        gs_id : int
            Ground station ID
        **kwargs
            Fields to update (name, site_lat, site_long, site_name, altitude,
            country, region, city, climate_zone, itu_region, description, is_shared)

        Returns
        -------
        bool
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Build UPDATE query dynamically
            allowed_fields = ['name', 'site_lat', 'site_long', 'site_name', 'altitude',
                            'country', 'region', 'city', 'climate_zone', 'itu_region',
                            'description', 'is_shared']
            updates = []
            params = []

            for field in allowed_fields:
                if field in kwargs:
                    updates.append(f"{field} = ?")
                    params.append(kwargs[field])

            if not updates:
                return False

            params.append(gs_id)
            query = f"UPDATE ground_stations SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    def make_ground_station_public(self, gs_id: int) -> bool:
        """Make ground station public"""
        return self.update_ground_station(gs_id, is_shared=True)

    def make_ground_station_private(self, gs_id: int) -> bool:
        """Make ground station private"""
        return self.update_ground_station(gs_id, is_shared=False)

    # =========================================================================
    # Reception Systems - Complex
    # =========================================================================

    def add_reception_complex(self, name: str, ant_size: float, ant_eff: float, lnb_gain: float,
                             lnb_temp: float, coupling_loss: float = 0,
                             cable_loss: float = 0, polarization_loss: float = 3,
                             max_depoint: float = 0, manufacturer: str = None,
                             model: str = None, description: str = '',
                             is_shared: bool = False) -> int:
        """
        Add complex reception system (requires login)

        Parameters
        ----------
        name : str
            System name
        ant_size : float
            Antenna size (m)
        ant_eff : float
            Antenna efficiency
        lnb_gain : float
            LNB gain (dB)
        lnb_temp : float
            LNB temperature (K)
        coupling_loss : float
            Coupling loss (dB)
        cable_loss : float
            Cable loss (dB)
        polarization_loss : float
            Polarization loss (dB)
        max_depoint : float
            Maximum de-pointing loss (dB)
        manufacturer : str, optional
            Manufacturer
        model : str, optional
            Model
        description : str
            Description
        is_shared : bool
            Whether to share publicly

        Returns
        -------
        int
            Reception system ID
        """
        if not self.current_user_id:
            raise PermissionError("Login required to add reception system")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reception_complex
                (name, ant_size, ant_eff, lnb_gain, lnb_temp,
                 coupling_loss, cable_loss, polarization_loss, max_depoint,
                 manufacturer, model, description, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, ant_size, ant_eff, lnb_gain, lnb_temp,
                  coupling_loss, cable_loss, polarization_loss, max_depoint,
                  manufacturer, model, description,
                  self.current_user_id, is_shared))
            conn.commit()
            return cursor.lastrowid

    # =========================================================================
    # Reception Systems - Simple
    # =========================================================================

    def add_reception_simple(self, name: str, gt_value: float, depoint_loss: float = 0,
                           frequency: float = None, measurement_method: str = None,
                           manufacturer: str = None, model: str = None,
                           description: str = '', is_shared: bool = False) -> int:
        """
        Add simple reception system (requires login)

        Parameters
        ----------
        name : str
            System name
        gt_value : float
            G/T value (dB/K)
        depoint_loss : float
            De-pointing loss (dB)
        frequency : float, optional
            Reference frequency (GHz)
        measurement_method : str, optional
            Measurement method
        manufacturer : str, optional
            Manufacturer
        model : str, optional
            Model
        description : str
            Description
        is_shared : bool
            Whether to share publicly

        Returns
        -------
        int
            Reception system ID
        """
        if not self.current_user_id:
            raise PermissionError("Login required to add reception system")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO reception_simple
                (name, gt_value, depoint_loss, frequency,
                 measurement_method, manufacturer, model, description, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, gt_value, depoint_loss, frequency,
                  measurement_method, manufacturer, model, description,
                  self.current_user_id, is_shared))
            conn.commit()
            return cursor.lastrowid

    def list_reception_complex(self, user_id: int = None, include_shared: bool = True) -> List[Dict]:
        """
        List complex reception systems

        Parameters
        ----------
        user_id : int, optional
            User ID to filter by
        include_shared : bool
            Whether to include shared items

        Returns
        -------
        list
            List of complex reception systems
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id is None:
                user_id = self.current_user_id

            if user_id and include_shared:
                cursor.execute("""
                    SELECT rc.*, u.username as owner
                    FROM reception_complex rc
                    JOIN users u ON rc.user_id = u.id
                    WHERE rc.user_id = ? OR rc.is_shared = 1
                    ORDER BY rc.name
                """, (user_id,))
            elif user_id:
                cursor.execute("""
                    SELECT rc.*, u.username as owner
                    FROM reception_complex rc
                    JOIN users u ON rc.user_id = u.id
                    WHERE rc.user_id = ?
                    ORDER BY rc.name
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT rc.*, u.username as owner
                    FROM reception_complex rc
                    JOIN users u ON rc.user_id = u.id
                    WHERE rc.is_shared = 1
                    ORDER BY rc.name
                """)

            return [dict(row) for row in cursor.fetchall()]

    def list_reception_simple(self, user_id: int = None, include_shared: bool = True) -> List[Dict]:
        """
        List simple reception systems

        Parameters
        ----------
        user_id : int, optional
            User ID to filter by
        include_shared : bool
            Whether to include shared items

        Returns
        -------
        list
            List of simple reception systems
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id is None:
                user_id = self.current_user_id

            if user_id and include_shared:
                cursor.execute("""
                    SELECT rs.*, u.username as owner
                    FROM reception_simple rs
                    JOIN users u ON rs.user_id = u.id
                    WHERE rs.user_id = ? OR rs.is_shared = 1
                    ORDER BY rs.name
                """, (user_id,))
            elif user_id:
                cursor.execute("""
                    SELECT rs.*, u.username as owner
                    FROM reception_simple rs
                    JOIN users u ON rs.user_id = u.id
                    WHERE rs.user_id = ?
                    ORDER BY rs.name
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT rs.*, u.username as owner
                    FROM reception_simple rs
                    JOIN users u ON rs.user_id = u.id
                    WHERE rs.is_shared = 1
                    ORDER BY rs.name
                """)

            return [dict(row) for row in cursor.fetchall()]

    def update_reception_complex(self, rc_id: int, **kwargs) -> bool:
        """
        Update complex reception system

        Parameters
        ----------
        rc_id : int
            Reception system ID
        **kwargs
            Fields to update (name, ant_size, ant_eff,
            lnb_gain, lnb_temp, coupling_loss, cable_loss, polarization_loss,
            max_depoint, manufacturer, model, description, is_shared)

        Returns
        -------
        bool
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            allowed_fields = ['name', 'ant_size', 'ant_eff',
                            'lnb_gain', 'lnb_temp', 'coupling_loss', 'cable_loss',
                            'polarization_loss', 'max_depoint', 'manufacturer',
                            'model', 'description', 'is_shared']
            updates = []
            params = []

            for field in allowed_fields:
                if field in kwargs:
                    updates.append(f"{field} = ?")
                    params.append(kwargs[field])

            if not updates:
                return False

            params.append(rc_id)
            query = f"UPDATE reception_complex SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    def update_reception_simple(self, rs_id: int, **kwargs) -> bool:
        """
        Update simple reception system

        Parameters
        ----------
        rs_id : int
            Reception system ID
        **kwargs
            Fields to update (name, gt_value, depoint_loss,
            frequency, measurement_method, manufacturer, model, description, is_shared)

        Returns
        -------
        bool
            True if successful
        """
        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            allowed_fields = ['name', 'gt_value', 'depoint_loss',
                            'frequency', 'measurement_method', 'manufacturer',
                            'model', 'description', 'is_shared']
            updates = []
            params = []

            for field in allowed_fields:
                if field in kwargs:
                    updates.append(f"{field} = ?")
                    params.append(kwargs[field])

            if not updates:
                return False

            params.append(rs_id)
            query = f"UPDATE reception_simple SET {', '.join(updates)} WHERE id = ?"

            cursor.execute(query, params)
            conn.commit()
            return cursor.rowcount > 0

    def make_reception_complex_public(self, rc_id: int) -> bool:
        """Make complex reception system public"""
        return self.update_reception_complex(rc_id, is_shared=True)

    def make_reception_complex_private(self, rc_id: int) -> bool:
        """Make complex reception system private"""
        return self.update_reception_complex(rc_id, is_shared=False)

    def make_reception_simple_public(self, rs_id: int) -> bool:
        """Make simple reception system public"""
        return self.update_reception_simple(rs_id, is_shared=True)

    def make_reception_simple_private(self, rs_id: int) -> bool:
        """Make simple reception system private"""
        return self.update_reception_simple(rs_id, is_shared=False)

    def get_public_reception_complex(self) -> List[Dict]:
        """Get all publicly available complex reception systems"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT rc.*, u.username as owner
                FROM reception_complex rc
                JOIN users u ON rc.user_id = u.id
                WHERE rc.is_shared = 1
                ORDER BY rc.name
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_public_reception_simple(self) -> List[Dict]:
        """Get all publicly available simple reception systems"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT rs.*, u.username as owner
                FROM reception_simple rs
                JOIN users u ON rs.user_id = u.id
                WHERE rs.is_shared = 1
                ORDER BY rs.name
            """)
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Link Calculations
    # =========================================================================

    def add_link_calculation(self, name: str, satellite_id: int, transponder_id: int,
                          carrier_id: int, ground_station_id: int,
                          reception_type: str, reception_id: int,
                          margin: float = 0, snr_relaxation: float = 0.1,
                          **results) -> int:
        """
        Add link calculation result (requires login)

        Parameters
        ----------
        name : str
            Calculation name
        satellite_id : int
            Satellite ID
        transponder_id : int
            Transponder ID
        carrier_id : int
            Carrier ID
        ground_station_id : int
            Ground station ID
        reception_type : str
            Reception type ('complex' or 'simple')
        reception_id : int
            Reception system ID
        margin : float
            Margin parameter
        snr_relaxation : float
            SNR relaxation parameter
        **results
            Calculation results (elevation_angle, azimuth_angle, distance,
            a_fs, a_g, a_c, a_r, a_s, a_t, a_tot, cn0, snr, snr_threshold,
            link_margin, availability, gt_value, notes)

        Returns
        -------
        int
            Link calculation ID
        """
        if not self.current_user_id:
            raise PermissionError("Login required to add link calculation")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("""
                INSERT INTO link_calculations
                (name, satellite_id, transponder_id, carrier_id, ground_station_id,
                 reception_type, reception_id, margin, snr_relaxation, user_id, is_shared,
                 elevation_angle, azimuth_angle, distance, a_fs, a_g, a_c, a_r, a_s,
                 a_t, a_tot, cn0, snr, snr_threshold, link_margin, availability,
                 gt_value, notes)
                VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """, (name, satellite_id, transponder_id, carrier_id, ground_station_id,
                  reception_type, reception_id, margin, snr_relaxation,
                  self.current_user_id, False,  # Default is_private
                  results.get('elevation_angle'), results.get('azimuth_angle'),
                  results.get('distance'), results.get('a_fs'), results.get('a_g'),
                  results.get('a_c'), results.get('a_r'), results.get('a_s'),
                  results.get('a_t'), results.get('a_tot'), results.get('cn0'),
                  results.get('snr'), results.get('snr_threshold'),
                  results.get('link_margin'), results.get('availability'),
                  results.get('gt_value'), results.get('notes')))
            conn.commit()
            return cursor.lastrowid

    def list_link_calculations(self, user_id: int = None,
                             include_shared: bool = True) -> List[Dict]:
        """
        List link calculations

        Parameters
        ----------
        user_id : int, optional
            User ID to filter by
        include_shared : bool
            Whether to include shared items

        Returns
        -------
        list
            List of link calculations
        """
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            if user_id is None:
                user_id = self.current_user_id

            if user_id and include_shared:
                cursor.execute("""
                    SELECT lc.*, u.username as owner
                    FROM link_calculations lc
                    JOIN users u ON lc.user_id = u.id
                    WHERE lc.user_id = ? OR lc.is_shared = 1
                    ORDER BY lc.calculation_date DESC
                """, (user_id,))
            elif user_id:
                cursor.execute("""
                    SELECT lc.*, u.username as owner
                    FROM link_calculations lc
                    JOIN users u ON lc.user_id = u.id
                    WHERE lc.user_id = ?
                    ORDER BY lc.calculation_date DESC
                """, (user_id,))
            else:
                cursor.execute("""
                    SELECT lc.*, u.username as owner
                    FROM link_calculations lc
                    JOIN users u ON lc.user_id = u.id
                    WHERE lc.is_shared = 1
                    ORDER BY lc.calculation_date DESC
                """)

            calculations = []
            for row in cursor.fetchall():
                calc = dict(row)
                calculations.append(calc)

            return calculations

    def make_link_public(self, calc_id: int) -> bool:
        """Make link calculation public"""
        if not self.current_user_id:
            raise PermissionError("Login required")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            # Check ownership
            cursor.execute("""
                SELECT user_id FROM link_calculations WHERE id = ?
            """, (calc_id,))
            result = cursor.fetchone()
            if not result or result[0] != self.current_user_id:
                raise PermissionError("Only owner can share calculation")

            cursor.execute("""
                UPDATE link_calculations
                SET is_shared = 1
                WHERE id = ?
            """, (calc_id,))
            conn.commit()
            return cursor.rowcount > 0

    # =========================================================================
    # Public Access Methods
    # =========================================================================

    def get_public_satellites(self) -> List[Dict]:
        """Get all publicly available satellites"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT sp.*, u.username as owner
                FROM satellite_positions sp
                JOIN users u ON sp.user_id = u.id
                WHERE sp.is_shared = 1
                ORDER BY sp.name
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_public_transponders(self, satellite_id: int = None) -> List[Dict]:
        """Get all publicly available transponders"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT t.*, u.username as owner, sp.name as satellite_name
                FROM transponders t
                JOIN users u ON t.user_id = u.id
                JOIN satellite_positions sp ON t.satellite_id = sp.id
                WHERE t.is_shared = 1
            """

            params = []
            if satellite_id:
                query += " AND t.satellite_id = ?"
                params.append(satellite_id)

            query += " ORDER BY t.name"
            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_public_carriers(self) -> List[Dict]:
        """Get all publicly available carriers"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT c.*, u.username as owner
                FROM carriers c
                JOIN users u ON c.user_id = u.id
                WHERE c.is_shared = 1
                ORDER BY c.name
            """)
            return [dict(row) for row in cursor.fetchall()]

    def get_public_ground_stations(self, country: str = None) -> List[Dict]:
        """Get all publicly available ground stations"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()

            query = """
                SELECT gs.*, u.username as owner
                FROM ground_stations gs
                JOIN users u ON gs.user_id = u.id
                WHERE gs.is_shared = 1
            """

            params = []
            if country:
                query += " AND gs.country = ?"
                params.append(country)

            query += " ORDER BY gs.name"
            cursor.execute(query, params)

            return [dict(row) for row in cursor.fetchall()]

    def get_public_link_calculations(self) -> List[Dict]:
        """Get all publicly available link calculations"""
        with sqlite3.connect(self.db_path) as conn:
            conn.row_factory = sqlite3.Row
            cursor = conn.cursor()
            cursor.execute("""
                SELECT lc.*, u.username as owner
                FROM link_calculations lc
                JOIN users u ON lc.user_id = u.id
                WHERE lc.is_shared = 1
                ORDER BY lc.calculation_date DESC
                LIMIT 100
            """)
            return [dict(row) for row in cursor.fetchall()]

    # =========================================================================
    # Statistics
    # =========================================================================

    def get_user_statistics(self, user_id: int = None) -> Dict:
        """
        Get user statistics

        Parameters
        ----------
        user_id : int, optional
            User ID. If None, uses current user

        Returns
        -------
        dict
            Statistics dictionary
        """
        if user_id is None:
            user_id = self.current_user_id

        if not user_id:
            raise PermissionError("Login required")

        with sqlite3.connect(self.db_path) as conn:
            cursor = conn.cursor()

            stats = {}

            # Count for each table
            tables = ['satellite_positions', 'transponders', 'carriers',
                     'ground_stations', 'reception_complex', 'reception_simple',
                     'link_calculations']

            for table in tables:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE user_id = ?
                """, (user_id,))
                stats[table] = cursor.fetchone()[0]

            # Shared items count
            shared_tables = ['satellite_positions', 'transponders', 'carriers',
                           'ground_stations', 'reception_complex', 'reception_simple',
                           'link_calculations']

            shared_count = 0
            for table in shared_tables:
                cursor.execute(f"""
                    SELECT COUNT(*) FROM {table}
                    WHERE user_id = ? AND is_shared = 1
                """, (user_id,))
                shared_count += cursor.fetchone()[0]

            stats['shared_items'] = shared_count

            # Account creation date
            cursor.execute("""
                SELECT created_at FROM users WHERE id = ?
            """, (user_id,))
            result = cursor.fetchone()
            if result:
                stats['account_created'] = result[0]

            return stats

    def close(self):
        """Close database connection"""
        self.logout()


# Test the updated database manager
if __name__ == "__main__":
    print("Testing Updated SatLink Database Manager with User System")
    print("=" * 70)

    db = SatLinkDatabaseUser('satlink_user_test.db')

    try:
        # Test registration
        print("\n1. Testing user registration...")
        success = db.user_auth.register_user('testuser', 'test@example.com', 'password123')
        print(f"Registration: {success}")

        # Test login
        print("\n2. Testing login...")
        success = db.login('testuser', 'password123')
        print(f"Login: {success}")

        if success:
            user_info = db.get_current_user_info()
            print(f"User: {user_info['username']} ({user_info['email']})")

            # Test adding satellite
            print("\n3. Adding satellite...")
            sat_id = db.add_satellite_position('Test Satellite', -70.0, 0, 35786,
                                            'GEO', 'Test satellite', is_shared=True)
            print(f"Satellite ID: {sat_id}")

            # Test listing satellites
            print("\n4. Listing satellites...")
            satellites = db.list_satellite_positions()
            for sat in satellites:
                print(f"  {sat['name']} - Owner: {sat['owner']}, Shared: {sat['is_shared']}")

            # Test adding transponder
            print("\n5. Adding transponder...")
            tp_id = db.add_transponder('Test TP', 14.25, 'Ku', 54, 36, 0, 0,
                                    'Horizontal', satellite_id=sat_id, is_shared=True)
            print(f"Transponder ID: {tp_id}")

            # Test adding carrier
            print("\n6. Adding carrier...")
            car_id = db.add_carrier('Test Carrier', '8PSK 2/3', '8PSK', '2/3', 0.20,
                                 36, None, None, 'DVB-S2', 'Test carrier', is_shared=True)
            print(f"Carrier ID: {car_id}")

            # Test adding ground station
            print("\n7. Adding ground station...")
            gs_id = db.add_ground_station('Test GS', -15.8, -47.9, 'Test Site', 0,
                                        'Brazil', 'DF', 'Brasilia', None, None,
                                        'Test station', is_shared=True)
            print(f"Ground Station ID: {gs_id}")

            # Test listing public items
            print("\n8. Getting public items...")
            public_sats = db.get_public_satellites()
            print(f"Public satellites: {len(public_sats)}")

            public_tps = db.get_public_transponders()
            print(f"Public transponders: {len(public_tps)}")

            public_cars = db.get_public_carriers()
            print(f"Public carriers: {len(public_cars)}")

            public_gs = db.get_public_ground_stations()
            print(f"Public ground stations: {len(public_gs)}")

            # Test statistics
            print("\n9. User statistics...")
            stats = db.get_user_statistics()
            for key, value in stats.items():
                print(f"  {key}: {value}")

            # Test logout
            print("\n10. Logging out...")
            db.logout()
            print("Logged out")

    except Exception as e:
        print(f"Error: {e}")
    finally:
        db.close()
        print("\nTest completed!")