"""
SatLink Web Interface

Flask web application for satellite link calculations with user authentication.
"""

import os
import json
from flask import Flask, render_template, request, redirect, url_for, flash, session, jsonify
from flask_bcrypt import Bcrypt
from functools import wraps
import datetime
import sqlite3
import numpy as np
import logging
import traceback

# Import our modules
from models.updated_db_manager import SatLinkDatabaseUser
from models.updated_satlink_db_schema import UPDATED_SQL_SCHEMA
from models.user_auth import UserAuth
from models.satellite_components import SatellitePosition, Transponder, Carrier

# Import user management blueprint
from web_user_management import user_management_bp

# Make db instance available to the blueprint
user_management_bp.db = None  # Will be set after db is initialized


app = Flask(__name__)
app.secret_key = os.environ.get('SECRET_KEY', 'your-secret-key-here')
bcrypt = Bcrypt(app)

# Configure logging to include timestamps and level
logging.basicConfig(
    level=logging.DEBUG,
    format='%(asctime)s %(levelname)s %(message)s',
    handlers=[
        logging.FileHandler('satlink_app.log'),
        logging.StreamHandler()
    ]
)

# Global database instance
db = None


def init_db(db_path='satlink.db'):
    """Initialize database with schema"""
    global db
    db = SatLinkDatabaseUser(db_path)

    # Make db available to user management blueprint
    user_management_bp.db = db

    # Create tables if they don't exist
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Check if users table exists
    cursor.execute("SELECT name FROM sqlite_master WHERE type='table' AND name='users'")
    if cursor.fetchone() is None:
        # Database is empty, create all tables
        cursor.executescript(UPDATED_SQL_SCHEMA)
    else:
        # Database already exists, just check/add admin user
        pass

    conn.commit()
    conn.close()

    # Create default admin user if not exists
    if not db.user_auth.authenticate_user('admin', 'admin123'):
        db.user_auth.register_user('admin', 'admin@satlink.com', 'admin123')


def login_required(f):
    """Decorator to require login"""
    @wraps(f)
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            flash('Please login to access this page.', 'error')
            return redirect(url_for('login'))

        # Re-authenticate user on each request
        username = session.get('username')
        user_id = session.get('user_id')

        if username and user_id:
            # Set current user in database
            db.current_user_id = user_id
            db.session_token = None  # We don't track session token in web context

        return f(*args, **kwargs)
    return decorated_function


def init_db_clean(db_path='satlink.db'):
    """Initialize database with clean schema"""
    conn = sqlite3.connect(db_path)
    cursor = conn.cursor()

    # Drop all tables
    cursor.execute("DROP TABLE IF EXISTS link_calculations")
    cursor.execute("DROP TABLE IF EXISTS reception_simple")
    cursor.execute("DROP TABLE IF EXISTS reception_complex")
    cursor.execute("DROP TABLE IF EXISTS ground_stations")
    cursor.execute("DROP TABLE IF EXISTS carriers")
    cursor.execute("DROP TABLE IF EXISTS transponders")
    cursor.execute("DROP TABLE IF EXISTS satellite_positions")
    cursor.execute("DROP TABLE IF EXISTS user_sessions")
    cursor.execute("DROP TABLE IF EXISTS users")

    # Create tables
    cursor.executescript(UPDATED_SQL_SCHEMA)
    conn.commit()
    conn.close()


# Routes
@app.route('/')
def index():
    """Home page"""
    if 'username' in session:
        return redirect(url_for('dashboard'))
    return render_template('index.html')


@app.route('/login', methods=['GET', 'POST'])
def login():
    """Login page"""
    if request.method == 'POST':
        username = request.form['username']
        password = request.form['password']

        success = db.login(username, password)
        if success:
            session['username'] = username
            session['user_id'] = db.current_user_id
            flash('Login successful!', 'success')
            return redirect(url_for('dashboard'))
        else:
            flash('Invalid username or password.', 'error')

    return render_template('login.html')


@app.route('/register', methods=['GET', 'POST'])
def register():
    """Registration page"""
    if request.method == 'POST':
        username = request.form['username']
        email = request.form['email']
        password = request.form['password']
        confirm_password = request.form['confirm_password']

        if password != confirm_password:
            flash('Passwords do not match.', 'error')
            return render_template('register.html')

        success = db.user_auth.register_user(username, email, password)
        if success:
            flash('Registration successful! Please login.', 'success')
            return redirect(url_for('login'))
        else:
            flash('Username or email already exists.', 'error')

    return render_template('register.html')


@app.route('/logout')
def logout():
    """Logout"""
    # Only call logout if user is logged in
    if 'username' in session:
        db.logout()
    session.clear()
    flash('You have been logged out.', 'info')
    return redirect(url_for('index'))


@app.route('/dashboard')
@login_required
def dashboard():
    """User dashboard"""
    user_info = db.get_current_user_info()
    stats = db.get_user_statistics()

    # Get recent calculations
    calculations = db.list_link_calculations()[:5]

    # Get reception systems and ground stations
    reception_simple = db.list_reception_simple(user_id=db.current_user_id, include_shared=False)
    reception_complex = db.list_reception_complex(user_id=db.current_user_id, include_shared=False)
    ground_stations = db.list_ground_stations(user_id=db.current_user_id, include_shared=False)

    return render_template('dashboard.html',
                         user_info=user_info,
                         stats=stats,
                         calculations=calculations,
                         reception_simple=reception_simple,
                         reception_complex=reception_complex,
                         ground_stations=ground_stations)


@app.route('/calculate')
@login_required
def calculate():
    """Link calculation page"""
    # Get all available components
    satellites = db.list_satellite_positions()
    transponders = db.list_transponders()
    carriers = db.list_carriers()
    ground_stations = db.list_ground_stations()

    # Group transponders by satellite
    transponders_by_sat = {}
    for tp in transponders:
        sat_id = tp['satellite_id']
        if sat_id not in transponders_by_sat:
            transponders_by_sat[sat_id] = []
        transponders_by_sat[sat_id].append(tp)

    # Get reception systems
    reception_simple = db.get_reception_simple_list()
    reception_complex = db.get_reception_complex_list()

    return render_template('calculate.html',
                         satellites=satellites,
                         transponders_by_sat=transponders_by_sat,
                         carriers=carriers,
                         ground_stations=ground_stations,
                         reception_simple=reception_simple,
                         reception_complex=reception_complex)


@app.route('/api/calculate_link', methods=['POST'])
@login_required
def api_calculate_link():
    """API endpoint for link calculation"""
    try:
        logging.info("Starting link calculation API call")
        data = request.json
        logging.info(f"Received calculation data: {data}")

        # Get selected component IDs (coerce to ints when possible)
        def _to_int(val):
            try:
                if val is None or val == '':
                    return None
                return int(val)
            except Exception:
                return None

        satellite_id = _to_int(data.get('satellite_id'))
        transponder_id = _to_int(data.get('transponder_id'))
        carrier_id = _to_int(data.get('carrier_id'))
        ground_station_id = _to_int(data.get('ground_station_id'))
        reception_type = data.get('reception_type')
        reception_id = _to_int(data.get('reception_id'))

        # Load components from database
        sat = None
        satellites = db.list_satellite_positions()
        if not satellites:
            # Add default satellite if none exist
            # Use system user ID (1) for default satellite
            temp_user_id = db.current_user_id or 1
            db.current_user_id = temp_user_id  # Temporarily set user ID
            db.add_satellite_position(
                name="Default GEO Satellite",
                sat_long=0.0,  # 0° longitude (prime meridian)
                sat_lat=0.0,   # 0° latitude (equator)
                h_sat=35786,   # GEO altitude in km
                is_shared=True
            )
            db.current_user_id = None  # Reset user ID
            satellites = db.list_satellite_positions()

        for s in satellites:
            if s['id'] == satellite_id:
                sat = SatellitePosition(s['sat_long'], s['sat_lat'], s['h_sat'])
                sat.name = s['name']
                logging.info(f"Found satellite: {sat.name}")
                break

        tp = None
        for t in db.list_transponders():
            if t['id'] == transponder_id:
                tp = Transponder(t['freq'], t['eirp_max'], t['b_transp'],
                              t['back_off'], t['contorno'])
                tp.name = t['name']
                tp.polarization = t.get('polarization')
                logging.info(f"Found transponder: {tp.name}")
                break

        car = None
        for c in db.list_carriers():
            if c['id'] == carrier_id:
                car = Carrier(c['modulation'], c['roll_off'], c['fec'], c['b_util'])
                car.name = c['name']
                car.modcod = c['modcod']
                car.standard = c.get('standard')
                logging.info(f"Found carrier: {car.name}")
                break

        gs = None
        for g in db.list_ground_stations():
            if g['id'] == ground_station_id:
                gs = {'site_lat': g['site_lat'], 'site_long': g['site_long']}
                gs['name'] = g['name']
                gs['altitude'] = g.get('altitude', 0)
                logging.info(f"Found ground station: {gs['name']}")
                break

        # Load reception system
        reception = None
        if reception_type == 'complex':
            for r in db.get_reception_complex_list():
                if r['id'] == reception_id:
                    reception = {
                        'ant_size': r['ant_size'],
                        'ant_eff': r['ant_eff'],
                        'lnb_gain': r['lnb_gain'],
                        'lnb_temp': r['lnb_temp'],
                        'coupling_loss': r.get('coupling_loss', 0),
                        'cable_loss': r.get('cable_loss', 0),
                        'polarization_loss': r.get('polarization_loss', 3),
                        'max_depoint': r.get('max_depoint', 0)
                    }
                    break
        else:
            for r in db.get_reception_simple_list():
                if r['id'] == reception_id:
                    reception = {
                        'gt_value': r['gt_value'],
                        'depoint_loss': r.get('depoint_loss', 0)
                    }
                    break

        # Perform link calculation
        try:
            # Import calculation modules
            from link_performance import sp_link_performance
            import pickle
            import os
            import datetime
            import sys

            # Add the current directory to sys.path to ensure modules can be found
            current_dir = os.path.dirname(os.path.abspath(__file__))
            if current_dir not in sys.path:
                sys.path.insert(0, current_dir)

            # Prepare calculation parameters
            if not all([satellite_id, transponder_id, carrier_id, ground_station_id, reception_type]):
                raise ValueError("Please fill in all required parameters")

            # Check if components were found
            if sat is None:
                raise ValueError("Satellite not found")
            if tp is None:
                raise ValueError("Transponder not found")
            if car is None:
                raise ValueError("Carrier not found")
            if gs is None:
                raise ValueError("Ground station not found")
            if reception is None:
                raise ValueError("Reception system not found")

            # Calculate satellite position and angles (simplified)
            # For GEO satellite
            earth_radius = 6371  # km
            satellite_radius = earth_radius + sat.h_sat

            # Convert to radians
            gs_lat_rad = np.radians(gs['site_lat'])
            gs_long_rad = np.radians(gs['site_long'])
            sat_long_rad = np.radians(sat.sat_long)

            # Calculate the difference in longitude
            delta_long = abs(gs_long_rad - sat_long_rad)

            # Calculate the angle between ground station and satellite
            beta = np.arccos(np.cos(gs_lat_rad) * np.cos(delta_long))

            # Calculate distance using law of cosines
            distance = np.sqrt(satellite_radius**2 + earth_radius**2 -
                              2 * satellite_radius * earth_radius * np.cos(beta))

            # Calculate elevation angle
            elevation = np.degrees(np.arcsin((satellite_radius * np.cos(beta) - earth_radius) / distance))

            # Calculate azimuth angle
            azimuth = np.degrees(np.arctan2(np.tan(gs_long_rad - sat_long_rad),
                                           np.tan(gs_lat_rad))) % 360

            # Ensure valid angle values
            elevation = max(0, min(90, elevation))

            # Calculate free space loss
            freq = tp.freq * 1000  # Convert GHz to MHz
            # Protect against zero bandwidths that would cause division errors
            if getattr(tp, 'b_transp', None) in (None, 0):
                tp.b_transp = 36
            if getattr(car, 'b_util', None) in (None, 0):
                car.b_util = 36

            a_fs = 20 * 2.6 + 20 * np.log10(freq) + 20 * np.log10(distance)

            # Get modulation data
            from models.satellite_components import get_modulation_params
            mod_params = get_modulation_params(car.modcod)

            # Calculate carrier power
            eirp = tp.eirp_max
            # Avoid division by zero in gain calculation
            b_transp_hz = tp.b_transp * 1e6 if tp.b_transp else 36 * 1e6
            g_sat = 10 * np.log10((4 * np.pi * sat.calculate_distance() * 1000)**2 / (b_transp_hz))
            c = eirp - a_fs + g_sat

            # Calculate noise
            if reception_type == 'simple':
                gt = reception['gt_value']
                t_system = 10**((gt - 20) / 10)  # Convert G/T to T
            else:
                # Complex system noise calculation
                t_system = 10**(reception.get('lnb_temp', 290) / 10) + 10**(reception.get('coupling_loss', 0) / 10)

                # Estimate G/T for complex reception if not provided
                ant_size = reception.get('ant_size', 1.0)  # meters
                ant_eff = reception.get('ant_eff', 0.55)
                # frequency available in transponder (tp.freq in GHz)
                try:
                    freq_hz = tp.freq * 1e9
                    wavelength = 3e8 / freq_hz
                    g_lin = (np.pi * ant_size / wavelength) ** 2 * ant_eff
                    g_dbi = 10 * np.log10(g_lin) if g_lin > 0 else 0.0
                except Exception:
                    g_dbi = 0.0

                # Ensure t_system positive
                t_sys_for_gt = t_system if t_system > 0 else 290.0
                gt = g_dbi - 10 * np.log10(t_sys_for_gt)

            k = 1.38e-23  # Boltzmann constant
            b = car.b_util * 1e6  # Bandwidth
            if b == 0:
                b = 36 * 1e6
                car.b_util = 36
            n = k * t_system * b
            n0 = n / b

            # Calculate C/N0 and SNR
            cn0 = c - 10 * np.log10(n0)
            snr = cn0 - 10 * np.log10(b)

            # Calculate atmospheric losses (simplified)
            a_g = 0.5  # Gas loss
            a_c = 0.2  # Cloud loss
            a_r = 2.1  # Rain loss
            a_s = 0.3  # Scintillation
            a_t = a_g + a_c + a_r + a_s
            a_tot = a_fs + a_t

            # Calculate SNR threshold and margin
            snr_threshold = 9.8  # Depends on modulation
            link_margin = snr - snr_threshold

            # Calculate availability (simplified)
            if link_margin > 0:
                availability = min(99.99, 99.9 + (link_margin / 10))
            else:
                availability = max(0, 99.9 - abs(link_margin) / 10)

            # Prepare results
            results = {
                'elevation_angle': elevation,
                'azimuth_angle': azimuth,
                'distance': distance,
                'a_fs': a_fs,
                'a_g': a_g,
                'a_c': a_c,
                'a_r': a_r,
                'a_s': a_s,
                'a_t': a_t,
                'a_tot': a_tot,
                'cn0': cn0,
                'snr': snr,
                'snr_threshold': snr_threshold,
                'link_margin': link_margin,
                'availability': availability,
                'gt_value': reception.get('gt_value') if reception_type == 'simple' else gt
            }

        except Exception as calc_error:
            logging.error(f"Calculation error: {str(calc_error)}", exc_info=True)
            # Return error results
            results = {
                'elevation_angle': 0,
                'azimuth_angle': 0,
                'distance': 0,
                'a_fs': 0,
                'a_g': 0,
                'a_c': 0,
                'a_r': 0,
                'a_s': 0,
                'a_t': 0,
                'a_tot': 0,
                'cn0': 0,
                'snr': 0,
                'snr_threshold': 0,
                'link_margin': 0,
                'availability': 0,
                'gt_value': 0
            }

        # Save calculation to database
        try:
            calc_id = db.add_link_calculation(
                name=f"Calculation - {datetime.datetime.now().strftime('%Y-%m-%d %H:%M')}",
                satellite_id=satellite_id,
                transponder_id=transponder_id,
                carrier_id=carrier_id,
                ground_station_id=ground_station_id,
                reception_type=reception_type,
                reception_id=reception_id,
                margin=0,
                snr_relaxation=0.1,
                **results
            )
            logging.info(f"Calculation saved to database with ID: {calc_id}")
        except Exception as db_error:
            logging.error(f"Database save error: {str(db_error)}", exc_info=True)
            calc_id = None

        return jsonify({
            'success': True,
            'calculation_id': calc_id,
            'results': results
        })

    except Exception as e:
        logging.error(f"Calculation API error: {str(e)}", exc_info=True)
        return jsonify({
            'success': False,
            'error': str(e),
            'message': 'Failed to perform calculation. Please check all parameters are selected correctly.'
        }), 500


@app.route('/calculations')
@login_required
def calculations():
    """View all calculations"""
    calculations = db.list_link_calculations()
    return render_template('calculations.html', calculations=calculations)


@app.route('/calculations/<int:calc_id>')
@login_required
def calculation_detail(calc_id):
    """View calculation details"""
    # Get calculation from database
    calc = None
    for c in db.list_link_calculations():
        if c['id'] == calc_id:
            calc = c
            break

    if not calc:
        flash('Calculation not found.', 'error')
        return redirect(url_for('calculations'))

    # Get related components
    # (Implementation would load satellite, transponder, etc. details)

    return render_template('calculation_detail.html', calculation=calc)


@app.route('/public')
def public():
    """Public shared items"""
    public_sats = db.get_public_satellites()
    public_tps = db.get_public_transponders()
    public_cars = db.get_public_carriers()
    public_gs = db.get_public_ground_stations()
    public_calcs = db.get_public_link_calculations()

    return render_template('public.html',
                         satellites=public_sats,
                         transponders=public_tps,
                         carriers=public_cars,
                         ground_stations=public_gs,
                         calculations=public_calcs)


@app.route('/profile')
@login_required
def profile():
    """User profile"""
    user_info = db.get_current_user_info()
    stats = db.get_user_statistics()
    return render_template('profile.html', user_info=user_info, stats=stats)


@app.route('/manage')
@login_required
def manage():
    """Manage user's items"""
    satellites = db.list_satellite_positions(user_id=db.current_user_id, include_shared=False)
    transponders = db.list_transponders(user_id=db.current_user_id, include_shared=False)
    carriers = db.list_carriers(user_id=db.current_user_id, include_shared=False)
    ground_stations = db.list_ground_stations(user_id=db.current_user_id, include_shared=False)
    reception_simple = db.list_reception_simple(user_id=db.current_user_id, include_shared=False)
    reception_complex = db.list_reception_complex(user_id=db.current_user_id, include_shared=False)

    return render_template('manage.html',
                         satellites=satellites,
                         transponders=transponders,
                         carriers=carriers,
                         ground_stations=ground_stations,
                         reception_simple=reception_simple,
                         reception_complex=reception_complex)


@app.route('/api/transponders')
@login_required
def api_transponders():
    """API endpoint to get transponders for a specific satellite"""
    try:
        satellite_id = request.args.get('satellite_id', type=int)

        if satellite_id:
            # Get transponders for the specific satellite
            transponders = db.list_transponders(satellite_id=satellite_id)

            # Format the response to only include needed fields
            formatted_transponders = []
            for tp in transponders:
                formatted_transponders.append({
                    'id': tp['id'],
                    'name': tp['name'],
                    'freq': tp['freq'],
                    'eirp_max': tp['eirp_max'],
                    'b_transp': tp['b_transp']
                })
            return jsonify(formatted_transponders)
        else:
            return jsonify([])

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reception_systems')
@login_required
def api_reception_systems():
    """API endpoint to get reception systems by type"""
    try:
        reception_type = request.args.get('type')

        if reception_type == 'complex':
            systems = []
            for rs in db.get_reception_complex_list():
                systems.append({
                    'id': rs['id'],
                    'name': rs['name'],
                    'ant_size': rs['ant_size'],
                    'ant_eff': rs['ant_eff'],
                    'lnb_gain': rs['lnb_gain'],
                    'lnb_temp': rs['lnb_temp']
                })
        elif reception_type == 'simple':
            systems = []
            for rs in db.get_reception_simple_list():
                systems.append({
                    'id': rs['id'],
                    'name': rs['name'],
                    'gt_value': rs['gt_value']
                })
        else:
            systems = []

        return jsonify(systems)

    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/satellite/<int:id>')
@login_required
def api_satellite_detail(id):
    """API endpoint to get satellite details"""
    try:
        satellites = db.list_satellite_positions()
        sat = next((s for s in satellites if s['id'] == id), None)
        if sat:
            return jsonify({
                'id': sat['id'],
                'name': sat['name'],
                'sat_long': sat['sat_long'],
                'sat_lat': sat.get('sat_lat', 0),
                'altitude': sat.get('altitude', 35786),
                'orbit_type': sat.get('orbit_type', 'GEO')
            })
        return jsonify({'error': 'Satellite not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/transponder/<int:id>')
@login_required
def api_transponder_detail(id):
    """API endpoint to get transponder details"""
    try:
        transponders = db.list_transponders()
        tp = next((t for t in transponders if t['id'] == id), None)
        if tp:
            return jsonify({
                'id': tp['id'],
                'name': tp['name'],
                'freq': tp['freq'],
                'band': tp.get('band', ''),
                'eirp_max': tp['eirp_max'],
                'b_transp': tp['b_transp'],
                'back_off': tp.get('back_off', 0),
                'polarization': tp.get('polarization', ''),
                'satellite_id': tp.get('satellite_id')
            })
        return jsonify({'error': 'Transponder not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/carrier/<int:id>')
@login_required
def api_carrier_detail(id):
    """API endpoint to get carrier details"""
    try:
        carriers = db.list_carriers()
        car = next((c for c in carriers if c['id'] == id), None)
        if car:
            return jsonify({
                'id': car['id'],
                'name': car['name'],
                'modcod': car['modcod'],
                'modulation': car.get('modulation', ''),
                'fec': car.get('fec', ''),
                'roll_off': car.get('roll_off', 0),
                'spectral_efficiency': car.get('spectral_efficiency', 0)
            })
        return jsonify({'error': 'Carrier not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/ground_station/<int:id>')
@login_required
def api_ground_station_detail(id):
    """API endpoint to get ground station details"""
    try:
        ground_stations = db.list_ground_stations()
        gs = next((g for g in ground_stations if g['id'] == id), None)
        if gs:
            return jsonify({
                'id': gs['id'],
                'name': gs['name'],
                'city': gs.get('city', ''),
                'country': gs.get('country', ''),
                'site_lat': gs['site_lat'],
                'site_long': gs['site_long'],
                'altitude': gs.get('altitude', 0),
                'climate_zone': gs.get('climate_zone', '')
            })
        return jsonify({'error': 'Ground station not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reception_complex/<int:id>')
@login_required
def api_reception_complex_detail(id):
    """API endpoint to get complex reception system details"""
    try:
        systems = db.list_reception_complex()
        rec = next((r for r in systems if r['id'] == id), None)
        if rec:
            return jsonify({
                'id': rec['id'],
                'name': rec['name'],
                'ant_size': rec['ant_size'],
                'ant_eff': rec['ant_eff'],
                'coupling_loss': rec.get('coupling_loss', 0),
                'polarization_loss': rec.get('polarization_loss', 0),
                'lnb_gain': rec['lnb_gain'],
                'lnb_temp': rec['lnb_temp'],
                'cable_loss': rec.get('cable_loss', 0),
                'calculated_gt': rec.get('calculated_gt', 0)
            })
        return jsonify({'error': 'Reception system not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/reception_simple/<int:id>')
@login_required
def api_reception_simple_detail(id):
    """API endpoint to get simple reception system details"""
    try:
        systems = db.list_reception_simple()
        rec = next((r for r in systems if r['id'] == id), None)
        if rec:
            return jsonify({
                'id': rec['id'],
                'name': rec['name'],
                'gt_value': rec['gt_value'],
                'frequency': rec.get('frequency', 0),
                'ground_station_id': rec.get('ground_station_id')
            })
        return jsonify({'error': 'Reception system not found'}), 404
    except Exception as e:
        return jsonify({'error': str(e)}), 500


@app.route('/api/share_item', methods=['POST'])
@login_required
def api_share_item():
    """API to share an item"""
    try:
        data = request.json
        item_type = data.get('type')
        item_id = data.get('id')

        success = False

        if item_type == 'satellite':
            success = db.make_satellite_public(item_id)
        elif item_type == 'calculation':
            success = db.make_link_public(item_id)

        if success:
            return jsonify({'success': True})
        else:
            return jsonify({'success': False, 'error': 'Item not found'}), 404

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/add_parameter', methods=['POST'])
@login_required
def api_add_parameter():
    """API endpoint to add new parameter"""
    try:
        data = request.json
        param_type = data.get('type')
        param_name = data.get('name')
        param_data = data.get('data', {})

        if not param_type or not param_name:
            return jsonify({'success': False, 'message': 'Parameter type and name are required'}), 400

        # Insert into appropriate table
        if param_type == 'satellite':
            db.cursor.execute("""
                INSERT INTO satellite_positions (name, sat_long, sat_lat, h_sat, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (param_name, param_data.get('sat_long'), param_data.get('sat_lat'),
                  param_data.get('h_sat'), db.current_user_id))
        elif param_type == 'transponder':
            # For transponder, we need a satellite_id - use the first available
            db.cursor.execute("SELECT id FROM satellite_positions LIMIT 1", ())
            sat_row = db.cursor.fetchone()
            if not sat_row:
                return jsonify({'success': False, 'message': 'No satellite available for transponder'}), 400

            db.cursor.execute("""
                INSERT INTO transponders (name, satellite_id, freq, eirp_max, b_transp, polarization, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, ?, 0)
            """, (param_name, sat_row[0], param_data.get('freq'), param_data.get('eirp_max'),
                  param_data.get('b_transp'), param_data.get('polarization'), db.current_user_id))
        elif param_type == 'carrier':
            db.cursor.execute("""
                INSERT INTO carriers (name, modulation, roll_off, fec, b_util, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, ?, 0)
            """, (param_name, param_data.get('modulation'), param_data.get('roll_off'),
                  param_data.get('fec'), param_data.get('b_util'), db.current_user_id))
        elif param_type == 'ground_station':
            db.cursor.execute("""
                INSERT INTO ground_stations (name, site_lat, site_long, altitude, user_id, is_shared)
                VALUES (?, ?, ?, ?, ?, 0)
            """, (param_name, param_data.get('site_lat'), param_data.get('site_long'),
                  param_data.get('altitude'), db.current_user_id))
        else:
            return jsonify({'success': False, 'message': 'Invalid parameter type'}), 400

        db.conn.commit()
        return jsonify({'success': True, 'message': 'Parameter added successfully'})

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# API endpoints for adding components via AJAX
@app.route('/api/satellites/add', methods=['POST'])
@login_required
def api_add_satellite():
    """API to add a new satellite via AJAX"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'sat_long']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        # Add satellite
        sat_id = db.add_satellite_position(
            name=data['name'],
            sat_long=float(data['sat_long']),
            sat_lat=float(data.get('sat_lat', 0)),
            altitude=float(data.get('altitude', 35786)),
            orbit_type=data.get('orbit_type', 'GEO'),
            is_shared=data.get('is_shared', False)
        )

        if sat_id:
            return jsonify({
                'success': True,
                'satellite_id': sat_id,
                'message': 'Satellite added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add satellite'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/transponders/add', methods=['POST'])
@login_required
def api_add_transponder():
    """API to add a new transponder via AJAX"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'freq', 'eirp_max', 'b_transp', 'satellite_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        # Add transponder
        tp_id = db.add_transponder(
            name=data['name'],
            freq=float(data['freq']),
            band=data.get('freq_band', ''),
            eirp_max=float(data['eirp_max']),
            b_transp=float(data['b_transp']),
            back_off=float(data.get('back_off', 0)),
            polarization=data.get('polarization', ''),
            satellite_id=int(data['satellite_id']),
            is_shared=data.get('is_shared', False)
        )

        if tp_id:
            return jsonify({
                'success': True,
                'transponder_id': tp_id,
                'message': 'Transponder added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add transponder'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/carriers/add', methods=['POST'])
@login_required
def api_add_carrier():
    """API to add a new carrier via AJAX"""
    try:
        data = request.get_json()

        # Validate required fields
        if 'name' not in data or not data['name']:
            return jsonify({'success': False, 'error': 'Missing required field: name'}), 400

        # Add carrier
        car_id = db.add_carrier(
            name=data['name'],
            modcod=data.get('modcod', data['name']),
            modulation=data.get('modulation', ''),
            fec=data.get('fec', ''),
            roll_off=float(data.get('roll_off', 0)),
            spectral_efficiency=float(data.get('spectral_efficiency', 0)),
            is_shared=data.get('is_shared', False)
        )

        if car_id:
            return jsonify({
                'success': True,
                'carrier_id': car_id,
                'message': 'Carrier added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add carrier'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/ground_stations/add', methods=['POST'])
@login_required
def api_add_ground_station():
    """API to add a new ground station via AJAX"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'site_lat', 'site_long']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        # Add ground station
        gs_id = db.add_ground_station(
            name=data['name'],
            site_lat=float(data['site_lat']),
            site_long=float(data['site_long']),
            altitude=float(data.get('altitude', 0)),
            city=data.get('city', ''),
            country=data.get('country', ''),
            climate_zone=data.get('climate_zone', ''),
            is_shared=data.get('is_shared', False)
        )

        if gs_id:
            return jsonify({
                'success': True,
                'ground_station_id': gs_id,
                'message': 'Ground station added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add ground station'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reception_complex/add', methods=['POST'])
@login_required
def api_add_reception_complex():
    """API to add a new complex reception system via AJAX"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'ground_station_id', 'ant_size', 'ant_eff', 'lnb_gain', 'lnb_temp']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        # Add complex reception system
        rec_id = db.add_reception_complex(
            name=data['name'],
            ground_station_id=int(data['ground_station_id']),
            ant_size=float(data['ant_size']),
            ant_eff=float(data['ant_eff']),
            coupling_loss=float(data.get('coupling_loss', 0)),
            polarization_loss=float(data.get('polarization_loss', 0)),
            lnb_gain=float(data['lnb_gain']),
            lnb_temp=float(data['lnb_temp']),
            cable_loss=float(data.get('cable_loss', 0)),
            is_shared=data.get('is_shared', False)
        )

        if rec_id:
            return jsonify({
                'success': True,
                'reception_id': rec_id,
                'message': 'Reception system added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add reception system'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@app.route('/api/reception_simple/add', methods=['POST'])
@login_required
def api_add_reception_simple():
    """API to add a new simple reception system via AJAX"""
    try:
        data = request.get_json()

        # Validate required fields
        required_fields = ['name', 'gt_value', 'frequency', 'ground_station_id']
        for field in required_fields:
            if field not in data or not data[field]:
                return jsonify({'success': False, 'error': f'Missing required field: {field}'}), 400

        # Add simple reception system
        rec_id = db.add_reception_simple(
            name=data['name'],
            ground_station_id=int(data['ground_station_id']),
            gt_value=float(data['gt_value']),
            frequency=float(data['frequency']),
            is_shared=data.get('is_shared', False)
        )

        if rec_id:
            return jsonify({
                'success': True,
                'reception_id': rec_id,
                'message': 'Reception system added successfully'
            })
        else:
            return jsonify({'success': False, 'error': 'Failed to add reception system'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


# Helper methods for database manager
def get_reception_complex_list(self):
    """Get list of complex reception systems"""
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rc.*, u.username as owner
            FROM reception_complex rc
            JOIN users u ON rc.user_id = u.id
            WHERE rc.user_id = ? OR rc.is_shared = 1
        """, (self.current_user_id,))
        return [dict(row) for row in cursor.fetchall()]

def get_reception_simple_list(self):
    """Get list of simple reception systems"""
    with sqlite3.connect(self.db_path) as conn:
        conn.row_factory = sqlite3.Row
        cursor = conn.cursor()
        cursor.execute("""
            SELECT rs.*, u.username as owner
            FROM reception_simple rs
            JOIN users u ON rs.user_id = u.id
            WHERE rs.user_id = ? OR rs.is_shared = 1
        """, (self.current_user_id,))
        return [dict(row) for row in cursor.fetchall()]


# Add helper methods to database manager
SatLinkDatabaseUser.get_reception_complex_list = get_reception_complex_list
SatLinkDatabaseUser.get_reception_simple_list = get_reception_simple_list


# Create templates directory if it doesn't exist
os.makedirs('templates', exist_ok=True)
os.makedirs('static', exist_ok=True)
os.makedirs('static/css', exist_ok=True)
os.makedirs('static/js', exist_ok=True)


# Create basic templates
index_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SatLink - Satellite Link Calculator</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">SatLink</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/login">Login</a>
                <a class="nav-link" href="/register">Register</a>
            </div>
        </div>
    </nav>

    <div class="container mt-5">
        <div class="row">
            <div class="col-md-8 mx-auto">
                <div class="card">
                    <div class="card-body">
                        <h1 class="card-title text-center">SatLink Satellite Link Calculator</h1>
                        <p class="card-text text-center">
                            Calculate satellite link budgets with user authentication and sharing capabilities.
                        </p>
                        <div class="text-center mt-4">
                            <a href="/login" class="btn btn-primary btn-lg me-3">Login</a>
                            <a href="/register" class="btn btn-outline-primary btn-lg">Register</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

login_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - SatLink</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">SatLink</a>
        </div>
    </nav>

    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h2 class="card-title text-center">Login</h2>

                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show">
                                        {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}

                        <form method="POST">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Login</button>
                        </form>

                        <div class="text-center mt-3">
                            <p>Don't have an account? <a href="/register">Register here</a></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

register_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - SatLink</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">SatLink</a>
        </div>
    </nav>

    <div class="container mt-5">
        <div class="row justify-content-center">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-body">
                        <h2 class="card-title text-center">Register</h2>

                        {% with messages = get_flashed_messages(with_categories=true) %}
                            {% if messages %}
                                {% for category, message in messages %}
                                    <div class="alert alert-{{ 'danger' if category == 'error' else 'success' }} alert-dismissible fade show">
                                        {{ message }}
                                        <button type="button" class="btn-close" data-bs-dismiss="alert"></button>
                                    </div>
                                {% endfor %}
                            {% endif %}
                        {% endwith %}

                        <form method="POST">
                            <div class="mb-3">
                                <label for="username" class="form-label">Username</label>
                                <input type="text" class="form-control" id="username" name="username" required>
                            </div>
                            <div class="mb-3">
                                <label for="email" class="form-label">Email</label>
                                <input type="email" class="form-control" id="email" name="email" required>
                            </div>
                            <div class="mb-3">
                                <label for="password" class="form-label">Password</label>
                                <input type="password" class="form-control" id="password" name="password" required>
                            </div>
                            <div class="mb-3">
                                <label for="confirm_password" class="form-label">Confirm Password</label>
                                <input type="password" class="form-control" id="confirm_password" name="confirm_password" required>
                            </div>
                            <button type="submit" class="btn btn-primary w-100">Register</button>
                        </form>

                        <div class="text-center mt-3">
                            <p>Already have an account? <a href="/login">Login here</a></p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

dashboard_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Dashboard - SatLink</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">SatLink</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/dashboard">Dashboard</a>
                <a class="nav-link" href="/calculate">Calculate</a>
                <a class="nav-link" href="/calculations">Calculations</a>
                <a class="nav-link" href="/manage">Manage</a>
                <a class="nav-link" href="/public">Public</a>
                <a class="nav-link" href="/profile">Profile</a>
                <a class="nav-link" href="/logout">Logout</a>
            </div>
        </div>
    </nav>

    <div class="container mt-5">
        <h1>Welcome, {{ user_info.username }}!</h1>

        <div class="row mt-4">
            <div class="col-md-3">
                <div class="card bg-primary text-white">
                    <div class="card-body">
                        <h5 class="card-title">Satellites</h5>
                        <h3>{{ stats.satellite_positions }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-success text-white">
                    <div class="card-body">
                        <h5 class="card-title">Transponders</h5>
                        <h3>{{ stats.transponders }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-info text-white">
                    <div class="card-body">
                        <h5 class="card-title">Carriers</h5>
                        <h3>{{ stats.carriers }}</h3>
                    </div>
                </div>
            </div>
            <div class="col-md-3">
                <div class="card bg-warning text-white">
                    <div class="card-body">
                        <h5 class="card-title">Calculations</h5>
                        <h3>{{ stats.link_calculations }}</h3>
                    </div>
                </div>
            </div>
        </div>

        <div class="row mt-4">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Recent Calculations</h5>
                    </div>
                    <div class="card-body">
                        {% if calculations %}
                            <div class="list-group">
                                {% for calc in calculations %}
                                    <a href="/calculations/{{ calc.id }}" class="list-group-item list-group-item-action">
                                        <h6 class="mb-1">{{ calc.name }}</h6>
                                        <small class="text-muted">{{ calc.calculation_date }}</small>
                                    </a>
                                {% endfor %}
                            </div>
                        {% else %}
                            <p>No calculations yet. <a href="/calculate">Create one</a>.</p>
                        {% endif %}
                    </div>
                </div>
            </div>
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Quick Links</h5>
                    </div>
                    <div class="card-body">
                        <div class="d-grid gap-2">
                            <a href="/calculate" class="btn btn-primary">New Calculation</a>
                            <a href="/manage" class="btn btn-secondary">Manage Items</a>
                            <a href="/public" class="btn btn-info">Browse Public Items</a>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>
</body>
</html>"""

calculate_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Link Calculation - SatLink</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.1.3/dist/css/bootstrap.min.css" rel="stylesheet">
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-primary">
        <div class="container">
            <a class="navbar-brand" href="/">SatLink</a>
            <div class="navbar-nav ms-auto">
                <a class="nav-link" href="/dashboard">Dashboard</a>
                <a class="nav-link" href="/calculate">Calculate</a>
                <a class="nav-link" href="/calculations">Calculations</a>
                <a class="nav-link" href="/manage">Manage</a>
                <a class="nav-link" href="/public">Public</a>
                <a class="nav-link" href="/profile">Profile</a>
                <a class="nav-link" href="/logout">Logout</a>
            </div>
        </div>
    </nav>

    <div class="container mt-5">
        <h1>Link Calculation</h1>

        <div class="row">
            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Input Parameters</h5>
                    </div>
                    <div class="card-body">
                        <form id="calculationForm">
                            <div class="mb-3">
                                <label for="satellite" class="form-label">Satellite</label>
                                <select class="form-select" id="satellite" name="satellite_id" required>
                                    <option value="">Select Satellite</option>
                                    {% for sat in satellites %}
                                        <option value="{{ sat.id }}">{{ sat.name }} ({{ sat.sat_long }}°)</option>
                                    {% endfor %}
                                </select>
                            </div>

                            <div class="mb-3">
                                <label for="transponder" class="form-label">Transponder</label>
                                <select class="form-select" id="transponder" name="transponder_id" required>
                                    <option value="">Select Transponder</option>
                                </select>
                            </div>

                            <div class="mb-3">
                                <label for="carrier" class="form-label">Carrier</label>
                                <select class="form-select" id="carrier" name="carrier_id" required>
                                    <option value="">Select Carrier</option>
                                    {% for car in carriers %}
                                        <option value="{{ car.id }}">{{ car.name }} ({{ car.modcod }})</option>
                                    {% endfor %}
                                </select>
                            </div>

                            <div class="mb-3">
                                <label for="ground_station" class="form-label">Ground Station</label>
                                <select class="form-select" id="ground_station" name="ground_station_id" required>
                                    <option value="">Select Ground Station</option>
                                    {% for gs in ground_stations %}
                                        <option value="{{ gs.id }}">{{ gs.name }} ({{ gs.city }}, {{ gs.country }})</option>
                                    {% endfor %}
                                </select>
                            </div>

                            <div class="mb-3">
                                <label for="reception_type" class="form-label">Reception System Type</label>
                                <select class="form-select" id="reception_type" name="reception_type" required>
                                    <option value="">Select Type</option>
                                    <option value="complex">Complex (Detailed Hardware)</option>
                                    <option value="simple">Simple (G/T Value)</option>
                                </select>
                            </div>

                            <div class="mb-3" id="reception_system" style="display: none;">
                                <label for="reception_id" class="form-label">Reception System</label>
                                <select class="form-select" id="reception_id" name="reception_id" required>
                                    <option value="">Select System</option>
                                </select>
                            </div>

                            <button type="submit" class="btn btn-primary">Calculate</button>
                        </form>
                    </div>
                </div>
            </div>

            <div class="col-md-6">
                <div class="card">
                    <div class="card-header">
                        <h5>Calculation Results</h5>
                    </div>
                    <div class="card-body">
                        <div id="results" class="text-center">
                            <p class="text-muted">Complete the form to see results</p>
                        </div>
                    </div>
                </div>
            </div>
        </div>
    </div>

    <script>
        // Load transponders based on satellite selection
        document.getElementById('satellite').addEventListener('change', function() {
            const satId = this.value;
            const transponderSelect = document.getElementById('transponder');

            if (satId) {
                transponderSelect.innerHTML = '<option value="">Loading...</option>';

                fetch(`/api/transponders?satellite_id=${satId}`)
                    .then(response => response.json())
                    .then(data => {
                        transponderSelect.innerHTML = '<option value="">Select Transponder</option>';
                        data.forEach(tp => {
                            transponderSelect.innerHTML += `<option value="${tp.id}">${tp.name} (${tp.freq} GHz)</option>`;
                        });
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        transponderSelect.innerHTML = '<option value="">Error loading transponders</option>';
                    });
            } else {
                transponderSelect.innerHTML = '<option value="">Select Transponder</option>';
            }
        });

        // Load reception systems based on type
        document.getElementById('reception_type').addEventListener('change', function() {
            const type = this.value;
            const receptionDiv = document.getElementById('reception_system');

            if (type) {
                receptionDiv.style.display = 'block';
                const receptionSelect = document.getElementById('reception_id');
                receptionSelect.innerHTML = '<option value="">Loading...</option>';

                fetch(`/api/reception_systems?type=${type}`)
                    .then(response => response.json())
                    .then(data => {
                        receptionSelect.innerHTML = '<option value="">Select System</option>';
                        data.forEach(rs => {
                            receptionSelect.innerHTML += `<option value="${rs.id}">${rs.name}</option>`;
                        });
                    })
                    .catch(error => {
                        console.error('Error:', error);
                        receptionSelect.innerHTML = '<option value="">Error loading systems</option>';
                    });
            } else {
                receptionDiv.style.display = 'none';
            }
        });

        // Handle form submission
        document.getElementById('calculationForm').addEventListener('submit', function(e) {
            e.preventDefault();

            const formData = new FormData(this);
            const data = Object.fromEntries(formData);

            fetch('/api/calculate_link', {
                method: 'POST',
                headers: {
                    'Content-Type': 'application/json',
                },
                body: JSON.stringify(data)
            })
            .then(response => response.json())
            .then(data => {
                if (data.success) {
                    displayResults(data.results, data.calculation_id);
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred during calculation');
            });
        });

        function displayResults(results, calcId) {
            const resultsDiv = document.getElementById('results');
            resultsDiv.innerHTML = `
                <table class="table table-striped">
                    <tr><th>Parameter</th><th>Value</th></tr>
                    <tr><td>Elevation Angle</td><td>${results.elevation_angle?.toFixed(2) || 'N/A'}°</td></tr>
                    <tr><td>Azimuth Angle</td><td>${results.azimuth_angle?.toFixed(2) || 'N/A'}°</td></tr>
                    <tr><td>Distance</td><td>${results.distance?.toFixed(0) || 'N/A'} km</td></tr>
                    <tr><td>Free Space Loss</td><td>${results.a_fs?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Gas Attenuation</td><td>${results.a_g?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Cloud Attenuation</td><td>${results.a_c?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Rain Attenuation</td><td>${results.a_r?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Scintillation</td><td>${results.a_s?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Total Atmospheric Loss</td><td>${results.a_t?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Total Loss</td><td>${results.a_tot?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>C/N0</td><td>${results.cn0?.toFixed(2) || 'N/A'} dB-Hz</td></tr>
                    <tr><td>SNR</td><td>${results.snr?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>SNR Threshold</td><td>${results.snr_threshold?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Link Margin</td><td>${results.link_margin?.toFixed(2) || 'N/A'} dB</td></tr>
                    <tr><td>Availability</td><td>${results.availability?.toFixed(1) || 'N/A'}%</td></tr>
                    <tr><td>G/T</td><td>${results.gt_value?.toFixed(2) || 'N/A'} dB/K</td></tr>
                </table>
                <div class="mt-3">
                    ${calcId ? `<a href="/calculations/${calcId}" class="btn btn-info">View Details</a>` : ''}
                </div>
            `;
        }
    </script>
</body>
</html>"""

# Make login_required available to blueprint
user_management_bp.login_required = login_required

# Register user management blueprint
app.register_blueprint(user_management_bp)

# Write templates
with open('templates/index.html', 'w') as f:
    f.write(index_html)
with open('templates/login.html', 'w') as f:
    f.write(login_html)
with open('templates/register.html', 'w') as f:
    f.write(register_html)
with open('templates/dashboard.html', 'w') as f:
    f.write(dashboard_html)
with open('templates/calculate.html', 'w') as f:
    f.write(calculate_html)


if __name__ == '__main__':
    # Initialize database
    init_db('satlink.db')

    # Run the app
    app.run(debug=True, host='0.0.0.0', port=5001)