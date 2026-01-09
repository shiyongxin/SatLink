"""
Updated SatLink Database Schema with User System

This module defines the database schema for storing satellite link calculation components
with user authentication and sharing attributes.
"""

# ============================================================================
# UPDATED SQL SCHEMA WITH USER SYSTEM
# ============================================================================

UPDATED_SQL_SCHEMA = """
-- ============================================================================
-- SatLink Database Schema with User System
-- ============================================================================

-- Drop existing tables
DROP TABLE IF EXISTS link_calculations;
DROP TABLE IF EXISTS reception_simple;
DROP TABLE IF EXISTS reception_complex;
DROP TABLE IF EXISTS ground_stations;
DROP TABLE IF EXISTS carriers;
DROP TABLE IF EXISTS transponders;
DROP TABLE IF EXISTS satellite_positions;
DROP TABLE IF EXISTS user_sessions;
DROP TABLE IF EXISTS users;

-- ============================================================================
-- Table: users
-- 用户表
-- ============================================================================
CREATE TABLE users (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    username VARCHAR(50) UNIQUE NOT NULL,
    email VARCHAR(100) UNIQUE NOT NULL,
    password_hash TEXT NOT NULL,
    salt TEXT NOT NULL,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    is_active BOOLEAN DEFAULT 1
);

-- ============================================================================
-- Table: user_sessions
-- 用户会话表
-- ============================================================================
CREATE TABLE user_sessions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    user_id INTEGER NOT NULL,
    session_token TEXT NOT NULL UNIQUE,
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    expires_at TIMESTAMP NOT NULL,
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================================
-- Table: satellite_positions
-- 存储卫星位置信息 (增加了用户ID和共享属性)
-- ============================================================================
CREATE TABLE satellite_positions (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    sat_long REAL NOT NULL,
    sat_lat REAL DEFAULT 0,
    h_sat REAL DEFAULT 35786,
    orbit_type VARCHAR(20) DEFAULT 'GEO',
    description TEXT,
    user_id INTEGER NOT NULL,           -- 所属用户ID
    is_shared BOOLEAN DEFAULT 0,        -- 是否共享 (公开)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(name, sat_long, user_id)     -- 同一用户不能重复添加相同卫星
);

-- ============================================================================
-- Table: transponders
-- 存储转发器信息 (增加了用户ID和共享属性)
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
    user_id INTEGER NOT NULL,           -- 所属用户ID
    is_shared BOOLEAN DEFAULT 0,        -- 是否共享 (公开)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (satellite_id) REFERENCES satellite_positions(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(name, satellite_id, freq, user_id)
);

-- ============================================================================
-- Table: carriers (MODCOD configurations)
-- 存储载波/调制配置 (增加了用户ID和共享属性)
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
    user_id INTEGER NOT NULL,           -- 所属用户ID
    is_shared BOOLEAN DEFAULT 0,        -- 是否共享 (公开)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(modcod, user_id)             -- 同一用户不能重复添加相同MODCOD
);

-- ============================================================================
-- Table: ground_stations
-- 存储地面站位置信息 (增加了用户ID和共享属性)
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
    user_id INTEGER NOT NULL,           -- 所属用户ID
    is_shared BOOLEAN DEFAULT 0,        -- 是否共享 (公开)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(name, site_lat, site_long, user_id)
);

-- ============================================================================
-- Table: reception_complex
-- 存储复杂接收系统配置（详细硬件参数）(增加了用户ID和共享属性)
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
    user_id INTEGER NOT NULL,           -- 所属用户ID
    is_shared BOOLEAN DEFAULT 0,        -- 是否共享 (公开)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ground_station_id) REFERENCES ground_stations(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(name, ground_station_id, user_id)
);

-- ============================================================================
-- Table: reception_simple
-- 存储简化接收系统配置（直接使用G/T值）(增加了用户ID和共享属性)
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
    user_id INTEGER NOT NULL,           -- 所属用户ID
    is_shared BOOLEAN DEFAULT 0,        -- 是否共享 (公开)
    created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    FOREIGN KEY (ground_station_id) REFERENCES ground_stations(id),
    FOREIGN KEY (user_id) REFERENCES users(id),
    UNIQUE(name, ground_station_id, user_id)
);

-- ============================================================================
-- Table: link_calculations
-- 存储链路计算结果 (增加了用户ID和共享属性)
-- ============================================================================
CREATE TABLE link_calculations (
    id INTEGER PRIMARY KEY AUTOINCREMENT,
    name VARCHAR(100) NOT NULL,
    satellite_id INTEGER NOT NULL,
    transponder_id INTEGER NOT NULL,
    carrier_id INTEGER NOT NULL,
    ground_station_id INTEGER NOT NULL,
    reception_type VARCHAR(10) NOT NULL,  -- 'complex' or 'simple'
    reception_id INTEGER NOT NULL,

    user_id INTEGER NOT NULL,             -- 所属用户ID
    is_shared BOOLEAN DEFAULT 0,          -- 是否共享 (公开)

    -- Input parameters summary
    margin REAL DEFAULT 0,
    snr_relaxation REAL DEFAULT 0.1,

    -- Results
    elevation_angle REAL,                 -- 仰角 (度)
    azimuth_angle REAL,                   -- 方位角 (度)
    distance REAL,                        -- 距离 (km)

    -- Attenuation at 0.001%
    a_fs REAL,                            -- 自由空间损耗 (dB)
    a_g REAL,                             -- 气体衰减 (dB)
    a_c REAL,                             -- 云衰减 (dB)
    a_r REAL,                             -- 雨衰减 (dB)
    a_s REAL,                             -- 闪烁衰减 (dB)
    a_t REAL,                             -- 总大气衰减 (dB)
    a_tot REAL,                           -- 总损耗 (dB)

    -- Link quality metrics
    cn0 REAL,                             -- C/N0 (dB-Hz)
    snr REAL,                             -- SNR (dB)
    snr_threshold REAL,                   -- SNR门限 (dB)
    link_margin REAL,                     -- 链路余量 (dB)
    availability REAL,                    -- 可用性 (%)

    -- Figure of merit
    gt_value REAL,                        -- G/T (dB/K)

    -- Additional info
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    FOREIGN KEY (satellite_id) REFERENCES satellite_positions(id),
    FOREIGN KEY (transponder_id) REFERENCES transponders(id),
    FOREIGN KEY (carrier_id) REFERENCES carriers(id),
    FOREIGN KEY (ground_station_id) REFERENCES ground_stations(id),
    FOREIGN KEY (user_id) REFERENCES users(id)
);

-- ============================================================================
-- INDEXES for better query performance
-- ============================================================================

-- User indexes
CREATE INDEX idx_users_username ON users(username);
CREATE INDEX idx_users_email ON users(email);

-- Session indexes
CREATE INDEX idx_sessions_token ON user_sessions(session_token);
CREATE INDEX idx_sessions_expires ON user_sessions(expires_at);

-- Component indexes with user
CREATE INDEX idx_satellite_user ON satellite_positions(user_id);
CREATE INDEX idx_satellite_orbit ON satellite_positions(orbit_type);
CREATE INDEX idx_satellite_shared ON satellite_positions(is_shared);

CREATE INDEX idx_transponder_user ON transponders(user_id);
CREATE INDEX idx_transponder_sat ON transponders(satellite_id);
CREATE INDEX idx_transponder_freq ON transponders(freq);
CREATE INDEX idx_transponder_shared ON transponders(is_shared);

CREATE INDEX idx_carrier_user ON carriers(user_id);
CREATE INDEX idx_carrier_modulation ON carriers(modulation);
CREATE INDEX idx_carrier_shared ON carriers(is_shared);

CREATE INDEX idx_ground_station_user ON ground_stations(user_id);
CREATE INDEX idx_ground_station_location ON ground_stations(site_lat, site_long);
CREATE INDEX idx_ground_station_shared ON ground_stations(is_shared);

CREATE INDEX idx_reception_complex_user ON reception_complex(user_id);
CREATE INDEX idx_reception_complex_gs ON reception_complex(ground_station_id);
CREATE INDEX idx_reception_complex_shared ON reception_complex(is_shared);

CREATE INDEX idx_reception_simple_user ON reception_simple(user_id);
CREATE INDEX idx_reception_simple_gs ON reception_simple(ground_station_id);
CREATE INDEX idx_reception_simple_shared ON reception_simple(is_shared);

CREATE INDEX idx_link_calc_user ON link_calculations(user_id);
CREATE INDEX idx_link_calc_sat ON link_calculations(satellite_id);
CREATE INDEX idx_link_calc_gs ON link_calculations(ground_station_id);
CREATE INDEX idx_link_calc_shared ON link_calculations(is_shared);
CREATE INDEX idx_link_calc_date ON link_calculations(calculation_date);

-- ============================================================================
-- VIEWS for common queries
-- ============================================================================

-- View: Public satellite positions (shared by any user)
CREATE VIEW v_public_satellites AS
SELECT
    sp.id,
    sp.name,
    sp.sat_long,
    sp.sat_lat,
    sp.h_sat,
    sp.orbit_type,
    sp.description,
    u.username as owner,
    sp.created_at
FROM satellite_positions sp
JOIN users u ON sp.user_id = u.id
WHERE sp.is_shared = 1;

-- View: Public transponders (shared by any user)
CREATE VIEW v_public_transponders AS
SELECT
    t.id,
    t.name,
    t.freq,
    t.freq_band,
    t.eirp_max,
    t.b_transp,
    t.polarization,
    u.username as owner,
    sp.name as satellite_name
FROM transponders t
JOIN users u ON t.user_id = u.id
JOIN satellite_positions sp ON t.satellite_id = sp.id
WHERE t.is_shared = 1;

-- View: Public carriers (shared by any user)
CREATE VIEW v_public_carriers AS
SELECT
    c.id,
    c.name,
    c.modcod,
    c.modulation,
    c.fec,
    c.roll_off,
    c.b_util,
    c.standard,
    u.username as owner
FROM carriers c
JOIN users u ON c.user_id = u.id
WHERE c.is_shared = 1;

-- View: Public ground stations (shared by any user)
CREATE VIEW v_public_ground_stations AS
SELECT
    gs.id,
    gs.name,
    gs.site_name,
    gs.site_lat,
    gs.site_long,
    gs.country,
    gs.city,
    u.username as owner
FROM ground_stations gs
JOIN users u ON gs.user_id = u.id
WHERE gs.is_shared = 1;

-- View: User's components (with shared public components accessible)
CREATE VIEW v_user_accessible_satellites AS
SELECT DISTINCT
    sp.id,
    sp.name,
    sp.sat_long,
    sp.sat_lat,
    sp.h_sat,
    sp.orbit_type,
    sp.description,
    u.username as owner,
    sp.user_id
FROM satellite_positions sp
JOIN users u ON sp.user_id = u.id
WHERE sp.user_id = USER_ID OR sp.is_shared = 1;  -- Note: USER_ID is placeholder for actual user ID

-- View: All accessible link calculations for a user
CREATE VIEW v_user_accessible_calculations AS
SELECT
    lc.id,
    lc.name,
    lc.user_id as owner_id,
    u.username as owner,
    lc.is_shared,
    lc.elevation_angle,
    lc.distance,
    lc.cn0,
    lc.snr,
    lc.availability,
    lc.calculation_date
FROM link_calculations lc
JOIN users u ON lc.user_id = u.id
WHERE lc.user_id = USER_ID OR lc.is_shared = 1;  -- Note: USER_ID is placeholder for actual user ID

-- ============================================================================
-- Sample Data
-- ============================================================================

-- Sample admin user
INSERT INTO users (username, email, password_hash, salt, is_active)
SELECT 'admin', 'admin@satlink.com', '8c6976e5b5410415bde908bd4dee15dfb167a9c873fc4bb8a81f6f2ab448a918', 'adminsalt12345678', 1
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'admin');

INSERT INTO users (username, email, password_hash, salt, is_active)
SELECT 'user1', 'user1@example.com', '4e77d97e20d21828f55be60ee31a31550a34f1e959c1e0e4141047945f91788e', 'usersalt12345678', 1
WHERE NOT EXISTS (SELECT 1 FROM users WHERE username = 'user1');
"""
