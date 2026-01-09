"""
SatLink Web User Management - Fixed Version

Additional Flask routes for user management, sharing features, and item management.
Modified to work with the main app's db instance and login_required decorator.
"""

from flask import Blueprint, request, jsonify, render_template, redirect, url_for, flash, session
from models.updated_db_manager import SatLinkDatabaseUser

# Create blueprint
user_management_bp = Blueprint('user_management', __name__, url_prefix='/manage')


def require_login(f):
    """Runtime login check that doesn't require decorator at import time"""
    def decorated_function(*args, **kwargs):
        if 'username' not in session:
            return redirect(url_for('login'))
        return f(*args, **kwargs)
    return decorated_function


def get_db():
    """Get database instance at runtime"""
    return getattr(user_management_bp, 'db', None)


@user_management_bp.route('/satellites')
def manage_satellites():
    """Manage satellite positions"""
    # Check if user is logged in
    if 'username' not in session:
        return redirect(url_for('login'))

    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    satellites = db.list_satellite_positions(user_id=db.current_user_id, include_shared=False)
    return render_template('manage_satellites.html', satellites=satellites)


@user_management_bp.route('/satellites/add', methods=['GET', 'POST'])
def add_satellite():
    """Add new satellite position"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    if request.method == 'POST':
        try:
            name = request.form['name']
            sat_long = float(request.form['sat_long'])
            sat_lat = float(request.form.get('sat_lat', 0))
            h_sat = float(request.form.get('h_sat', 35786))
            orbit_type = request.form.get('orbit_type', 'GEO')
            description = request.form.get('description', '')
            is_shared = 'is_shared' in request.form

            sat_id = db.add_satellite_position(
                name, sat_long, sat_lat, h_sat, orbit_type,
                description, is_shared
            )

            flash('Satellite added successfully!', 'success')
            return redirect(url_for('user_management.manage_satellites'))

        except Exception as e:
            flash(f'Error adding satellite: {str(e)}', 'error')
            return render_template('add_satellite.html')

    return render_template('add_satellite.html')


@user_management_bp.route('/satellites/<int:sat_id>/edit', methods=['GET', 'POST'])
def edit_satellite(sat_id):
    """Edit satellite position"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    # Get satellite details
    satellite = None
    for sat in db.list_satellite_positions():
        if sat['id'] == sat_id and sat['user_id'] == db.current_user_id:
            satellite = sat
            break

    if not satellite:
        flash('Satellite not found or access denied.', 'error')
        return redirect(url_for('user_management.manage_satellites'))

    if request.method == 'POST':
        try:
            updates = {
                'name': request.form['name'],
                'sat_long': float(request.form['sat_long']),
                'sat_lat': float(request.form.get('sat_lat', 0)),
                'h_sat': float(request.form.get('h_sat', 35786)),
                'orbit_type': request.form.get('orbit_type', 'GEO'),
                'description': request.form.get('description', ''),
                'is_shared': 'is_shared' in request.form
            }

            success = db.update_satellite_position(sat_id, **updates)
            if success:
                flash('Satellite updated successfully!', 'success')
                return redirect(url_for('user_management.manage_satellites'))
            else:
                flash('Error updating satellite.', 'error')

        except Exception as e:
            flash(f'Error updating satellite: {str(e)}', 'error')

    return render_template('edit_satellite.html', satellite=satellite)


@user_management_bp.route('/satellites/<int:sat_id>/delete', methods=['POST'])
def delete_satellite(sat_id):
    """Delete satellite position"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    try:
        success = db.delete_satellite_position(sat_id)
        if success:
            flash('Satellite deleted successfully!', 'success')
        else:
            flash('Error deleting satellite.', 'error')
    except Exception as e:
        flash(f'Error deleting satellite: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_satellites'))


@user_management_bp.route('/satellites/<int:sat_id>/share', methods=['POST'])
def toggle_satellite_share(sat_id):
    """Toggle satellite sharing status"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    try:
        # Check ownership
        satellite = None
        for sat in db.list_satellite_positions():
            if sat['id'] == sat_id:
                satellite = sat
                break

        if not satellite or satellite['user_id'] != db.current_user_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Toggle sharing
        if satellite['is_shared']:
            success = db.make_satellite_private(sat_id)
            action = 'unshared'
        else:
            success = db.make_satellite_public(sat_id)
            action = 'shared'

        if success:
            return jsonify({'success': True, 'action': action})
        else:
            return jsonify({'success': False, 'error': 'Failed to update sharing'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@user_management_bp.route('/transponders')
def manage_transponders():
    """Manage transponders"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    transponders = db.list_transponders(user_id=db.current_user_id, include_shared=False)
    satellites = db.list_satellite_positions()
    return render_template('manage_transponders.html',
                         transponders=transponders,
                         satellites=satellites)


@user_management_bp.route('/transponders/add', methods=['GET', 'POST'])
def add_transponder():
    """Add new transponder"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    satellites = db.list_satellite_positions(user_id=db.current_user_id, include_shared=True)

    if request.method == 'POST':
        try:
            name = request.form['name']
            freq = float(request.form['freq'])
            freq_band = request.form.get('freq_band')
            eirp_max = float(request.form.get('eirp_max', 0))
            b_transp = float(request.form.get('b_transp', 36))
            back_off = float(request.form.get('back_off', 0))
            contorno = float(request.form.get('contorno', 0))
            polarization = request.form.get('polarization')
            satellite_id = int(request.form['satellite_id'])
            is_shared = 'is_shared' in request.form

            tp_id = db.add_transponder(
                name, freq, freq_band, eirp_max, b_transp,
                back_off, contorno, polarization, satellite_id, is_shared
            )

            flash('Transponder added successfully!', 'success')
            return redirect(url_for('user_management.manage_transponders'))

        except Exception as e:
            flash(f'Error adding transponder: {str(e)}', 'error')
            return render_template('add_transponder.html', satellites=satellites)

    return render_template('add_transponder.html', satellites=satellites)


@user_management_bp.route('/transponders/<int:tp_id>/share', methods=['POST'])
def toggle_transponder_share(tp_id):
    """Toggle transponder sharing status"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    try:
        # Check ownership
        transponder = None
        for tp in db.list_transponders():
            if tp['id'] == tp_id:
                transponder = tp
                break

        if not transponder or transponder['user_id'] != db.current_user_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Toggle sharing
        if transponder['is_shared']:
            success = db.make_transponder_private(tp_id)
            action = 'unshared'
        else:
            success = db.make_transponder_public(tp_id)
            action = 'shared'

        if success:
            # Get updated status
            for tp in db.list_transponders():
                if tp['id'] == tp_id:
                    return jsonify({
                        'success': True,
                        'action': action,
                        'is_shared': tp['is_shared'],
                        'message': f'Transponder {action} successfully'
                    })

        return jsonify({'success': False, 'error': 'Failed to update sharing'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@user_management_bp.route('/transponders/<int:tp_id>/delete', methods=['POST'])
def delete_transponder(tp_id):
    """Delete transponder"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_transponders'))

    # Check ownership first
    transponder = None
    for tp in db.list_transponders():
        if tp['id'] == tp_id:
            transponder = tp
            break

    if not transponder or transponder['user_id'] != db.current_user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('user_management.manage_transponders'))

    try:
        # Delete transponder
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM transponders WHERE id = ?", (tp_id,))
            conn.commit()

        flash('Transponder deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting transponder: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_transponders'))


@user_management_bp.route('/carriers')
def manage_carriers():
    """Manage carrier configurations"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    carriers = db.list_carriers(user_id=db.current_user_id, include_shared=False)
    return render_template('manage_carriers.html', carriers=carriers)


@user_management_bp.route('/carriers/add', methods=['GET', 'POST'])
def add_carrier():
    """Add new carrier configuration"""
    if request.method == 'POST':
        db = get_db()
        if not db:
            flash('Database not initialized', 'error')
            return redirect(url_for('dashboard'))

        try:
            name = request.form['name']
            modcod = request.form['modcod']
            modulation = request.form['modulation']
            fec = request.form['fec']
            roll_off = float(request.form['roll_off'])
            b_util = float(request.form.get('b_util', 36))
            snr_threshold = float(request.form.get('snr_threshold', 0)) if request.form.get('snr_threshold') else None
            spectral_efficiency = float(request.form.get('spectral_efficiency', 0)) if request.form.get('spectral_efficiency') else None
            standard = request.form.get('standard')
            description = request.form.get('description', '')
            is_shared = 'is_shared' in request.form

            car_id = db.add_carrier(
                name, modcod, modulation, fec, roll_off, b_util,
                snr_threshold, spectral_efficiency, standard, description, is_shared
            )

            flash('Carrier configuration added successfully!', 'success')
            return redirect(url_for('user_management.manage_carriers'))

        except Exception as e:
            flash(f'Error adding carrier: {str(e)}', 'error')
            return render_template('add_carrier.html')

    return render_template('add_carrier.html')


@user_management_bp.route('/carriers/<int:car_id>/share', methods=['POST'])
def toggle_carrier_share(car_id):
    """Toggle carrier sharing status"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    try:
        # Check ownership
        carrier = None
        for car in db.list_carriers():
            if car['id'] == car_id:
                carrier = car
                break

        if not carrier or carrier['user_id'] != db.current_user_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Toggle sharing
        if carrier['is_shared']:
            success = db.make_carrier_private(car_id)
            action = 'unshared'
        else:
            success = db.make_carrier_public(car_id)
            action = 'shared'

        if success:
            # Get updated status
            for car in db.list_carriers():
                if car['id'] == car_id:
                    return jsonify({
                        'success': True,
                        'action': action,
                        'is_shared': car['is_shared'],
                        'message': f'Carrier {action} successfully'
                    })

        return jsonify({'success': False, 'error': 'Failed to update sharing'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@user_management_bp.route('/carriers/<int:car_id>/delete', methods=['POST'])
def delete_carrier(car_id):
    """Delete carrier configuration"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_carriers'))

    # Check ownership first
    carrier = None
    for car in db.list_carriers():
        if car['id'] == car_id:
            carrier = car
            break

    if not carrier or carrier['user_id'] != db.current_user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('user_management.manage_carriers'))

    try:
        # Delete carrier
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM carriers WHERE id = ?", (car_id,))
            conn.commit()

        flash('Carrier configuration deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting carrier: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_carriers'))


@user_management_bp.route('/ground_stations')
def manage_ground_stations():
    """Manage ground stations"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    ground_stations = db.list_ground_stations(user_id=db.current_user_id, include_shared=False)
    countries = sorted(set(gs['country'] for gs in ground_stations if gs['country']))
    return render_template('manage_ground_stations.html',
                         ground_stations=ground_stations,
                         countries=countries)


@user_management_bp.route('/ground_stations/add', methods=['GET', 'POST'])
def add_ground_station():
    """Add new ground station"""
    if request.method == 'POST':
        db = get_db()
        if not db:
            flash('Database not initialized', 'error')
            return redirect(url_for('dashboard'))

        try:
            name = request.form['name']
            site_lat = float(request.form['site_lat'])
            site_long = float(request.form['site_long'])
            site_name = request.form.get('site_name')
            altitude = float(request.form.get('altitude', 0))
            country = request.form.get('country')
            region = request.form.get('region')
            city = request.form.get('city')
            climate_zone = request.form.get('climate_zone')
            itu_region = request.form.get('itu_region')
            description = request.form.get('description', '')
            is_shared = 'is_shared' in request.form

            gs_id = db.add_ground_station(
                name, site_lat, site_long, site_name, altitude,
                country, region, city, climate_zone, itu_region,
                description, is_shared
            )

            flash('Ground station added successfully!', 'success')
            return redirect(url_for('user_management.manage_ground_stations'))

        except Exception as e:
            flash(f'Error adding ground station: {str(e)}', 'error')
            return render_template('add_ground_station.html')

    return render_template('add_ground_station.html')


@user_management_bp.route('/ground_stations/<int:gs_id>/share', methods=['POST'])
def toggle_ground_station_share(gs_id):
    """Toggle ground station sharing status"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    try:
        # Check ownership
        ground_station = None
        for gs in db.list_ground_stations():
            if gs['id'] == gs_id:
                ground_station = gs
                break

        if not ground_station or ground_station['user_id'] != db.current_user_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Toggle sharing
        if ground_station['is_shared']:
            success = db.make_ground_station_private(gs_id)
            action = 'unshared'
        else:
            success = db.make_ground_station_public(gs_id)
            action = 'shared'

        if success:
            # Get updated status
            for gs in db.list_ground_stations():
                if gs['id'] == gs_id:
                    return jsonify({
                        'success': True,
                        'action': action,
                        'is_shared': gs['is_shared'],
                        'message': f'Ground station {action} successfully'
                    })

        return jsonify({'success': False, 'error': 'Failed to update sharing'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@user_management_bp.route('/ground_stations/<int:gs_id>/delete', methods=['POST'])
def delete_ground_station(gs_id):
    """Delete ground station"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_ground_stations'))

    # Check ownership first
    gs = None
    for ground_station in db.list_ground_stations():
        if ground_station['id'] == gs_id:
            gs = ground_station
            break

    if not gs or gs['user_id'] != db.current_user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('user_management.manage_ground_stations'))

    try:
        # Delete ground station and related reception systems
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()

            # Delete reception systems
            cursor.execute("DELETE FROM reception_complex WHERE ground_station_id = ?", (gs_id,))
            cursor.execute("DELETE FROM reception_simple WHERE ground_station_id = ?", (gs_id,))

            # Delete ground station
            cursor.execute("DELETE FROM ground_stations WHERE id = ?", (gs_id,))
            conn.commit()

        flash('Ground station deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting ground station: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_ground_stations'))


@user_management_bp.route('/reception_complex/add', methods=['POST'])
def add_reception_complex():
    """Add complex reception system via API"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    try:
        name = request.form['name']
        ant_size = float(request.form['ant_size'])
        ant_eff = float(request.form['ant_eff'])
        lnb_gain = float(request.form['lnb_gain'])
        lnb_temp = float(request.form['lnb_temp'])
        coupling_loss = float(request.form.get('coupling_loss', 0))
        cable_loss = float(request.form.get('cable_loss', 0))
        polarization_loss = float(request.form.get('polarization_loss', 3))
        max_depoint = float(request.form.get('max_depoint', 0))
        manufacturer = request.form.get('manufacturer')
        model = request.form.get('model')
        description = request.form.get('description', '')
        is_shared = 'is_shared' in request.form

        rec_id = db.add_reception_complex(
            name, ant_size, ant_eff, lnb_gain, lnb_temp,
            coupling_loss, cable_loss, polarization_loss, max_depoint,
            manufacturer, model, description, is_shared
        )

        flash('Complex reception system added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding reception system: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_reception_systems'))


@user_management_bp.route('/reception_simple/add', methods=['POST'])
def add_reception_simple():
    """Add simple reception system via API"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    try:
        name = request.form['name']
        gt_value = float(request.form['gt_value'])
        depoint_loss = float(request.form.get('depoint_loss', 0))
        frequency = float(request.form.get('frequency', 0)) if request.form.get('frequency') else None
        measurement_method = request.form.get('measurement_method')
        manufacturer = request.form.get('manufacturer')
        model = request.form.get('model')
        description = request.form.get('description', '')
        is_shared = 'is_shared' in request.form

        rec_id = db.add_reception_simple(
            name, gt_value, depoint_loss,
            frequency, measurement_method, manufacturer, model,
            description, is_shared
        )

        flash('Simple reception system added successfully!', 'success')
    except Exception as e:
        flash(f'Error adding reception system: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_reception_systems'))


# =========================================================================
# Reception Systems Management
# =========================================================================

@user_management_bp.route('/reception_systems')
def manage_reception_systems():
    """Manage all reception systems (both simple and complex)"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('dashboard'))

    simple_systems = db.list_reception_simple(user_id=db.current_user_id, include_shared=False)
    complex_systems = db.list_reception_complex(user_id=db.current_user_id, include_shared=False)

    return render_template('manage_reception_systems.html',
                         simple_systems=simple_systems,
                         complex_systems=complex_systems)


@user_management_bp.route('/reception_simple/<int:rs_id>/delete', methods=['POST'])
def delete_reception_simple(rs_id):
    """Delete simple reception system"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    # Check ownership
    rec = None
    for r in db.list_reception_simple():
        if r['id'] == rs_id:
            rec = r
            break

    if not rec or rec['user_id'] != db.current_user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    try:
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reception_simple WHERE id = ?", (rs_id,))
            conn.commit()
        flash('Simple reception system deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_reception_systems'))


@user_management_bp.route('/reception_complex/<int:rc_id>/delete', methods=['POST'])
def delete_reception_complex(rc_id):
    """Delete complex reception system"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    # Check ownership
    rec = None
    for r in db.list_reception_complex():
        if r['id'] == rc_id:
            rec = r
            break

    if not rec or rec['user_id'] != db.current_user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    try:
        import sqlite3
        with sqlite3.connect(db.db_path) as conn:
            cursor = conn.cursor()
            cursor.execute("DELETE FROM reception_complex WHERE id = ?", (rc_id,))
            conn.commit()
        flash('Complex reception system deleted successfully!', 'success')
    except Exception as e:
        flash(f'Error deleting: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_reception_systems'))


@user_management_bp.route('/reception_simple/<int:rs_id>/edit', methods=['POST'])
def edit_reception_simple(rs_id):
    """Edit simple reception system"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    # Check ownership
    rec = None
    for r in db.list_reception_simple():
        if r['id'] == rs_id:
            rec = r
            break

    if not rec or rec['user_id'] != db.current_user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    try:
        gt_value = float(request.form['gt_value'])
        depoint_loss = float(request.form.get('depoint_loss', 0))
        frequency = float(request.form['frequency']) if request.form.get('frequency') else None
        measurement_method = request.form.get('measurement_method')
        manufacturer = request.form.get('manufacturer')
        model = request.form.get('model')
        description = request.form.get('description', '')
        is_shared = 'is_shared' in request.form

        success = db.update_reception_simple(
            rs_id,
            gt_value=gt_value,
            depoint_loss=depoint_loss,
            frequency=frequency,
            measurement_method=measurement_method,
            manufacturer=manufacturer,
            model=model,
            description=description,
            is_shared=is_shared
        )

        if success:
            flash('Simple reception system updated successfully!', 'success')
        else:
            flash('Failed to update system.', 'error')
    except Exception as e:
        flash(f'Error updating: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_reception_systems'))


@user_management_bp.route('/reception_complex/<int:rc_id>/edit', methods=['POST'])
def edit_reception_complex(rc_id):
    """Edit complex reception system"""
    db = get_db()
    if not db:
        flash('Database not initialized', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    # Check ownership
    rec = None
    for r in db.list_reception_complex():
        if r['id'] == rc_id:
            rec = r
            break

    if not rec or rec['user_id'] != db.current_user_id:
        flash('Access denied.', 'error')
        return redirect(url_for('user_management.manage_reception_systems'))

    try:
        ant_size = float(request.form['ant_size'])
        ant_eff = float(request.form['ant_eff'])
        lnb_gain = float(request.form['lnb_gain'])
        lnb_temp = float(request.form['lnb_temp'])
        coupling_loss = float(request.form.get('coupling_loss', 0))
        cable_loss = float(request.form.get('cable_loss', 0))
        polarization_loss = float(request.form.get('polarization_loss', 3))
        max_depoint = float(request.form.get('max_depoint', 0))
        manufacturer = request.form.get('manufacturer')
        model = request.form.get('model')
        description = request.form.get('description', '')
        is_shared = 'is_shared' in request.form

        success = db.update_reception_complex(
            rc_id,
            ant_size=ant_size,
            ant_eff=ant_eff,
            lnb_gain=lnb_gain,
            lnb_temp=lnb_temp,
            coupling_loss=coupling_loss,
            cable_loss=cable_loss,
            polarization_loss=polarization_loss,
            max_depoint=max_depoint,
            manufacturer=manufacturer,
            model=model,
            description=description,
            is_shared=is_shared
        )

        if success:
            flash('Complex reception system updated successfully!', 'success')
        else:
            flash('Failed to update system.', 'error')
    except Exception as e:
        flash(f'Error updating: {str(e)}', 'error')

    return redirect(url_for('user_management.manage_reception_systems'))


@user_management_bp.route('/reception_simple/<int:rs_id>/share', methods=['POST'])
def toggle_reception_simple_share(rs_id):
    """Toggle simple reception system sharing status"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    try:
        # Check ownership
        rec = None
        for r in db.list_reception_simple():
            if r['id'] == rs_id:
                rec = r
                break

        if not rec or rec['user_id'] != db.current_user_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Toggle sharing
        if rec['is_shared']:
            success = db.make_reception_simple_private(rs_id)
            action = 'unshared'
        else:
            success = db.make_reception_simple_public(rs_id)
            action = 'shared'

        if success:
            # Get updated status
            for r in db.list_reception_simple():
                if r['id'] == rs_id:
                    return jsonify({
                        'success': True,
                        'action': action,
                        'is_shared': r['is_shared'],
                        'message': f'Simple reception system {action} successfully'
                    })

        return jsonify({'success': False, 'error': 'Failed to update sharing'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@user_management_bp.route('/reception_complex/<int:rc_id>/share', methods=['POST'])
def toggle_reception_complex_share(rc_id):
    """Toggle complex reception system sharing status"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    try:
        # Check ownership
        rec = None
        for r in db.list_reception_complex():
            if r['id'] == rc_id:
                rec = r
                break

        if not rec or rec['user_id'] != db.current_user_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Toggle sharing
        if rec['is_shared']:
            success = db.make_reception_complex_private(rc_id)
            action = 'unshared'
        else:
            success = db.make_reception_complex_public(rc_id)
            action = 'shared'

        if success:
            # Get updated status
            for r in db.list_reception_complex():
                if r['id'] == rc_id:
                    return jsonify({
                        'success': True,
                        'action': action,
                        'is_shared': r['is_shared'],
                        'message': f'Complex reception system {action} successfully'
                    })

        return jsonify({'success': False, 'error': 'Failed to update sharing'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@user_management_bp.route('/calculations/<int:calc_id>/share', methods=['POST'])
def toggle_calculation_share(calc_id):
    """Toggle calculation sharing status"""
    db = get_db()
    if not db:
        return jsonify({'success': False, 'error': 'Database not initialized'}), 500

    try:
        # Check ownership
        calculation = None
        for calc in db.list_link_calculations():
            if calc['id'] == calc_id:
                calculation = calc
                break

        if not calculation or calculation['user_id'] != db.current_user_id:
            return jsonify({'success': False, 'error': 'Access denied'}), 403

        # Toggle sharing
        success = db.make_link_public(calc_id)

        if success:
            return jsonify({'success': True, 'action': 'shared'})
        else:
            return jsonify({'success': False, 'error': 'Failed to update sharing'}), 500

    except Exception as e:
        return jsonify({'success': False, 'error': str(e)}), 500


@user_management_bp.route('/api/transponders')
def api_get_transponders():
    """API to get transponders by satellite"""
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    satellite_id = request.args.get('satellite_id', type=int)

    transponders = []
    for tp in db.list_transponders():
        if satellite_id is None or tp['satellite_id'] == satellite_id:
            transponders.append({
                'id': tp['id'],
                'name': tp['name'],
                'freq': tp['freq'],
                'freq_band': tp.get('freq_band'),
                'eirp_max': tp.get('eirp_max'),
                'polarization': tp.get('polarization')
            })

    return jsonify(transponders)


@user_management_bp.route('/api/reception_systems')
def api_get_reception_systems():
    """API to get reception systems by type"""
    db = get_db()
    if not db:
        return jsonify({'error': 'Database not initialized'}), 500

    reception_type = request.args.get('type')

    systems = []
    if reception_type == 'complex':
        for rs in db.get_reception_complex_list():
            if rs['user_id'] == db.current_user_id or rs['is_shared']:
                systems.append({
                    'id': rs['id'],
                    'name': rs['name']
                })
    elif reception_type == 'simple':
        for rs in db.get_reception_simple_list():
            if rs['user_id'] == db.current_user_id or rs['is_shared']:
                systems.append({
                    'id': rs['id'],
                    'name': rs['name']
                })

    return jsonify(systems)