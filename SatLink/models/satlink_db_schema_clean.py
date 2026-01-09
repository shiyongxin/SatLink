"""
SatLink Database Schema - Clean Version (no sample data)

This module defines the database schema for storing satellite link calculation components.
This is the clean version without sample data.
"""

# ============================================================================
# SQL SCHEMA DEFINITION (Clean - No Sample Data)
# ============================================================================

SQL_SCHEMA_CLEAN = """
-- ============================================================================
-- SatLink Database Schema (Clean Version)
-- ============================================================================

-- Drop existing tables
DROP TABLE IF EXISTS link_calculations;
DROP TABLE IF EXISTS reception_simple;
DROP TABLE IF EXISTS reception_complex;
DROP TABLE IF EXISTS ground_stations;
DROP TABLE IF EXISTS carriers;
DROP TABLE IF EXISTS transponders;
DROP TABLE IF EXISTS satellite_positions;
DROP TABLE IF EXISTS satellites;

-- ============================================================================
-- Table: satellite_positions
-- 存储卫星位置信息
-- ============================================================================
CREATE TABLE satellite_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    sat_long REAL NOT NULL,
    sat_lat REAL DEFAULT 0,
    h_sat REAL DEFAULT 35786,
    orbit_type VARCHAR(20) DEFAULT 'GEO',
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, sat_long)
);

-- ============================================================================
-- Table: transponders
-- 存储转发器信息
-- ============================================================================
CREATE TABLE transponders (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    satellite_id INTEGER,
    freq REAL NOT NULL,
    freq_band VARCHAR(10),
    eirp_max REAL DEFAULT 0,
    b_transp REAL DEFAULT 36,
    back_off REAL DEFAULT 0,
    contorno REAL DEFAULT 0,
    polarization VARCHAR(20),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (satellite_id) REFERENCES satellite_positions(id),
    UNIQUE(name, satellite_id, freq)
);

-- ============================================================================
-- Table: carriers (MODCOD configurations)
-- 存储载波/调制配置
-- ============================================================================
CREATE TABLE carriers (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    modcod VARCHAR(50) NOT NULL,
    modulation VARCHAR(20) NOT NULL,
    fec VARCHAR(20) NOT NULL,
    roll_off REAL NOT NULL,
    b_util REAL DEFAULT 36,
    snr_threshold REAL,
    spectral_efficiency REAL,
    standard VARCHAR(20),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(modcod)
);

-- ============================================================================
-- Table: ground_stations
-- 存储地面站位置信息
-- ============================================================================
CREATE TABLE ground_stations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    site_name VARCHAR(100),
    site_lat REAL NOT NULL,
    site_long REAL NOT NULL,
    altitude REAL DEFAULT 0,
    country VARCHAR(50),
    region VARCHAR(50),
    city VARCHAR(50),
    climate_zone VARCHAR(20),
    itu_region VARCHAR(10),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    UNIQUE(name, site_lat, site_long)
);

-- ============================================================================
-- Table: reception_complex
-- 存储复杂接收系统配置（详细硬件参数）
-- ============================================================================
CREATE TABLE reception_complex (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    ground_station_id INTEGER,
    ant_size REAL NOT NULL,
    ant_eff REAL NOT NULL,
    lnb_gain REAL NOT NULL,
    lnb_temp REAL NOT NULL,
    coupling_loss REAL DEFAULT 0,
    cable_loss REAL DEFAULT 0,
    polarization_loss REAL DEFAULT 3,
    max_depoint REAL DEFAULT 0,
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    description TEXT,
    calculated_gt REAL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ground_station_id) REFERENCES ground_stations(id),
    UNIQUE(name, ground_station_id)
);

-- ============================================================================
-- Table: reception_simple
-- 存储简化接收系统配置（直接使用G/T值）
-- ============================================================================
CREATE TABLE reception_simple (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    ground_station_id INTEGER,
    gt_value REAL NOT NULL,
    depoint_loss REAL DEFAULT 0,
    frequency REAL,
    measurement_method VARCHAR(50),
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    description TEXT,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ground_station_id) REFERENCES ground_stations(id),
    UNIQUE(name, ground_station_id)
);

-- ============================================================================
-- Table: link_calculations
-- 存储链路计算结果
-- ============================================================================
CREATE TABLE link_calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    satellite_id INTEGER NOT NULL,
    transponder_id INTEGER NOT NULL,
    carrier_id INTEGER NOT NULL,
    ground_station_id INTEGER NOT NULL,
    reception_type VARCHAR(10) NOT NULL,
    reception_id INTEGER NOT NULL,

    margin REAL DEFAULT 0,
    snr_relaxation REAL DEFAULT 0.1,

    elevation_angle REAL,
    azimuth_angle REAL,
    distance REAL,

    a_fs REAL,
    a_g REAL,
    a_c REAL,
    a_r REAL,
    a_s REAL,
    a_t REAL,
    a_tot REAL,

    cn0 REAL,
    snr REAL,
    snr_threshold REAL,
    link_margin REAL,
    availability REAL,
    gt_value REAL,

    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    FOREIGN KEY (satellite_id) REFERENCES satellite_positions(id),
    FOREIGN KEY (transponder_id) REFERENCES transponders(id),
    FOREIGN KEY (carrier_id) REFERENCES carriers(id),
    FOREIGN KEY (ground_station_id) REFERENCES ground_stations(id)
);

-- ============================================================================
-- INDEXES
-- ============================================================================

CREATE INDEX idx_satellite_orbit ON satellite_positions(orbit_type);
CREATE INDEX idx_transponder_freq ON transponders(freq);
CREATE INDEX idx_transponder_band ON transponders(freq_band);
CREATE INDEX idx_carrier_modulation ON carriers(modulation);
CREATE INDEX idx_ground_station_location ON ground_stations(site_lat, site_long);
CREATE INDEX idx_reception_complex_gs ON reception_complex(ground_station_id);
CREATE INDEX idx_reception_simple_gs ON reception_simple(ground_station_id);
CREATE INDEX idx_link_calc_sat ON link_calculations(satellite_id);
CREATE INDEX idx_link_calc_gs ON link_calculations(ground_station_id);
CREATE INDEX idx_link_calc_date ON link_calculations(calculation_date);

-- ============================================================================
-- VIEWS
-- ============================================================================

CREATE VIEW v_satellite_summary AS
SELECT
    sp.id,
    sp.name,
    sp.sat_long,
    sp.sat_lat,
    sp.h_sat,
    sp.orbit_type,
    COUNT(DISTINCT t.id) as transponder_count
FROM satellite_positions sp
LEFT JOIN transponders t ON sp.id = t.satellite_id
GROUP BY sp.id;

CREATE VIEW v_carriers_available AS
SELECT
    id,
    name,
    modcod,
    modulation,
    fec,
    roll_off,
    b_util,
    snr_threshold,
    spectral_efficiency,
    standard
FROM carriers
ORDER BY modulation, fec;

CREATE VIEW v_reception_systems AS
SELECT
    'complex' as type,
    rc.id,
    rc.name,
    rc.ground_station_id,
    gs.site_name,
    gs.city,
    gs.country,
    rc.ant_size,
    rc.calculated_gt as gt_value
FROM reception_complex rc
JOIN ground_stations gs ON rc.ground_station_id = gs.id
UNION ALL
SELECT
    'simple' as type,
    rs.id,
    rs.name,
    rs.ground_station_id,
    gs.site_name,
    gs.city,
    gs.country,
    NULL as ant_size,
    rs.gt_value
FROM reception_simple rs
JOIN ground_stations gs ON rs.ground_station_id = gs.id;
"""
