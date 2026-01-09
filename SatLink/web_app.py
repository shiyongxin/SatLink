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

    return render_template('dashboard.html',
                         user_info=user_info,
                         stats=stats,
                         calculations=calculations)


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

    return render_template('calculate.html',
                         satellites=satellites,
                         transponders_by_sat=transponders_by_sat,
                         carriers=carriers,
                         ground_stations=ground_stations)


@app.route('/api/calculate_link', methods=['POST'])
@login_required
def api_calculate_link():
    """API endpoint for link calculation"""
    try:
        data = request.json

        # Get selected component IDs
        satellite_id = data.get('satellite_id')
        transponder_id = data.get('transponder_id')
        carrier_id = data.get('carrier_id')
        ground_station_id = data.get('ground_station_id')
        reception_type = data.get('reception_type')
        reception_id = data.get('reception_id')

        # Load components from database
        sat = None
        for s in db.list_satellite_positions():
            if s['id'] == satellite_id:
                sat = SatellitePosition(s['sat_long'], s['sat_lat'], s['h_sat'])
                sat.name = s['name']
                break

        tp = None
        for t in db.list_transponders():
            if t['id'] == transponder_id:
                tp = Transponder(t['freq'], t['eirp_max'], t['b_transp'],
                              t['back_off'], t['contorno'])
                tp.name = t['name']
                tp.polarization = t.get('polarization')
                break

        car = None
        for c in db.list_carriers():
            if c['id'] == carrier_id:
                car = Carrier(c['modulation'], c['roll_off'], c['fec'], c['b_util'])
                car.name = c['name']
                car.modcod = c['modcod']
                car.standard = c.get('standard')
                break

        gs = None
        for g in db.list_ground_stations():
            if g['id'] == ground_station_id:
                gs = {'site_lat': g['site_lat'], 'site_long': g['site_long']}
                gs['name'] = g['name']
                gs['altitude'] = g.get('altitude', 0)
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

        # Perform link calculation (placeholder - implement actual calculation)
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
            'gt_value': reception.get('gt_value') if reception_type == 'simple' else 32.5
        }

        # Save calculation to database
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

        return jsonify({
            'success': True,
            'calculation_id': calc_id,
            'results': results
        })

    except Exception as e:
        return jsonify({
            'success': False,
            'error': str(e)
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

    return render_template('manage.html',
                         satellites=satellites,
                         transponders=transponders,
                         carriers=carriers,
                         ground_stations=ground_stations)


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
                    displayResults(data.results);
                } else {
                    alert('Error: ' + data.error);
                }
            })
            .catch(error => {
                console.error('Error:', error);
                alert('An error occurred during calculation');
            });
        });

        function displayResults(results) {
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
                    <a href="/calculations/${data.calculation_id}" class="btn btn-info">View Details</a>
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
    app.run(debug=True, host='0.0.0.0', port=5000)