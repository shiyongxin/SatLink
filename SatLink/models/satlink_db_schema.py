"""
SatLink Database Schema Design

This module defines the database schema for storing satellite link calculation components:
- SatellitePosition: 卫星位置信息
- Transponder: 转发器信息
- Carrier: 载波/调制信息
- Reception (Complex): 复杂接收系统（详细硬件参数）
- Reception (Simple): 简化接收系统（G/T值）
- GroundStation: 地面站位置
"""

# ============================================================================
# SQL SCHEMA DEFINITION
# ============================================================================

SQL_SCHEMA = """
-- ============================================================================
-- SatLink Database Schema
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
    sat_long REAL NOT NULL,           -- 卫星经度 (度)
    sat_lat REAL DEFAULT 0,           -- 卫星纬度 (度)，GEO为0
    h_sat REAL DEFAULT 35786,         -- 卫星高度 (km)
    orbit_type VARCHAR(20) DEFAULT 'GEO',  -- 轨道类型: GEO, MEO, LEO
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
    satellite_id INTEGER,              -- 关联卫星（可选）
    freq REAL NOT NULL,                -- 中心频率 (GHz)
    freq_band VARCHAR(10),             -- 频段: C, Ku, Ka, Q
    eirp_max REAL DEFAULT 0,           -- 最大EIRP (dBW)
    b_transp REAL DEFAULT 36,          -- 转发器带宽 (MHz)
    back_off REAL DEFAULT 0,           -- 输出回退 (dB)
    contorno REAL DEFAULT 0,           -- 轮廓因子 (dB)
    polarization VARCHAR(20),          -- 极化方式: Horizontal, Vertical, Circular
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
    modcod VARCHAR(50) NOT NULL,       -- 完整MODCOD: '8PSK 120/180'
    modulation VARCHAR(20) NOT NULL,   -- 调制方式: QPSK, 8PSK, 16APSK, 32APSK
    fec VARCHAR(20) NOT NULL,          -- FEC码率: 1/2, 2/3, 3/4, 5/6, 8/9
    roll_off REAL NOT NULL,            -- 滚降系数: 0.2, 0.25, 0.35
    b_util REAL DEFAULT 36,            -- 占用带宽 (MHz)
    snr_threshold REAL,                -- SNR门限 (dB) - 从MODCOD表获取
    spectral_efficiency REAL,          -- 频谱效率 (bps/Hz)
    standard VARCHAR(20),              -- 标准: DVB-S, DVB-S2, DVB-S2X
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
    site_name VARCHAR(100),            -- 站点名称
    site_lat REAL NOT NULL,            -- 纬度 (度)
    site_long REAL NOT NULL,           -- 经度 (度)
    altitude REAL DEFAULT 0,           -- 海拔高度 (m)
    country VARCHAR(50),
    region VARCHAR(50),
    city VARCHAR(50),
    climate_zone VARCHAR(20),          -- 气候区域 (用于ITU-R P.618雨衰减)
    itu_region VARCHAR(10),            -- ITU区域
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
    ground_station_id INTEGER,         -- 关联地面站
    ant_size REAL NOT NULL,            -- 天线直径 (m)
    ant_eff REAL NOT NULL,             -- 天线效率 (0-1)
    lnb_gain REAL NOT NULL,            -- LNB增益 (dB)
    lnb_temp REAL NOT NULL,            -- LNB噪声温度 (K)
    coupling_loss REAL DEFAULT 0,      -- 耦合损耗 (dB)
    cable_loss REAL DEFAULT 0,         -- 电缆损耗 (dB)
    polarization_loss REAL DEFAULT 3,  -- 极化损耗 (dB)
    max_depoint REAL DEFAULT 0,        -- 最大指向误差 (度)
    manufacturer VARCHAR(100),
    model VARCHAR(100),
    description TEXT,
    calculated_gt REAL,                -- 计算出的G/T值 (dB/K)
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
    ground_station_id INTEGER,         -- 关联地面站
    gt_value REAL NOT NULL,            -- G/T 值 (dB/K)
    depoint_loss REAL DEFAULT 0,       -- 指向损耗 (dB)
    frequency REAL,                    -- 参考频率 (GHz)
    measurement_method VARCHAR(50),    -- 测量方法: calculated, measured, specified
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
    reception_type VARCHAR(10) NOT NULL,  -- 'complex' or 'simple'
    reception_id INTEGER NOT NULL,

    -- Input parameters summary
    margin REAL DEFAULT 0,
    snr_relaxation REAL DEFAULT 0.1,

    -- Results
    elevation_angle REAL,               -- 仰角 (度)
    azimuth_angle REAL,                 -- 方位角 (度)
    distance REAL,                      -- 距离 (km)

    -- Attenuation at 0.001%
    a_fs REAL,                          -- 自由空间损耗 (dB)
    a_g REAL,                           -- 气体衰减 (dB)
    a_c REAL,                           -- 云衰减 (dB)
    a_r REAL,                           -- 雨衰减 (dB)
    a_s REAL,                           -- 闪烁衰减 (dB)
    a_t REAL,                           -- 总大气衰减 (dB)
    a_tot REAL,                         -- 总损耗 (dB)

    -- Link quality metrics
    cn0 REAL,                           -- C/N0 (dB-Hz)
    snr REAL,                           -- SNR (dB)
    snr_threshold REAL,                 -- SNR门限 (dB)
    link_margin REAL,                   -- 链路余量 (dB)
    availability REAL,                  -- 可用性 (%)

    -- Figure of merit
    gt_value REAL,                      -- G/T (dB/K)

    -- Additional info
    calculation_date TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
    notes TEXT,

    FOREIGN KEY (satellite_id) REFERENCES satellite_positions(id),
    FOREIGN KEY (transponder_id) REFERENCES transponders(id),
    FOREIGN KEY (carrier_id) REFERENCES carriers(id),
    FOREIGN KEY (ground_station_id) REFERENCES ground_stations(id)
);

-- ============================================================================
-- INDEXES for better query performance
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
-- VIEWS for common queries
-- ============================================================================

-- View: Satellite summary
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

-- View: Available carriers
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

-- View: Reception systems with ground stations
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

-- ============================================================================
-- Sample Data
-- ============================================================================

-- Sample satellite positions
INSERT INTO satellite_positions (name, sat_long, sat_lat, h_sat, orbit_type, description) VALUES
('StarOne C1', -70.0, 0, 35786, 'GEO', 'Brazilian GEO satellite at 70°W'),
('StarOne D1', -84.0, 0, 35786, 'GEO', 'Brazilian GEO satellite at 84°W'),
('Intelsat 21', -58.0, 0, 35786, 'GEO', 'Intelsat satellite at 58°W'),
('Telstar 14R', -63.0, 0, 35786, 'GEO', 'Telesat satellite at 63°W');

-- Sample transponders
INSERT INTO transponders (name, satellite_id, freq, freq_band, eirp_max, b_transp, back_off, contorno, polarization) VALUES
('Ku-Band TP1', 1, 14.25, 'Ku', 54, 36, 0, 0, 'Horizontal'),
('Ku-Band TP2', 1, 14.20, 'Ku', 52, 36, 0, 0, 'Vertical'),
('C-Band TP1', 1, 4.15, 'C', 40, 36, 0, 0, 'Horizontal');

-- Sample carriers (MODCODs)
INSERT INTO carriers (name, modcod, modulation, fec, roll_off, b_util, standard) VALUES
('8PSK 2/3', '8PSK 120/180', '8PSK', '2/3', 0.20, 9, 'DVB-S2'),
('QPSK 3/4', 'QPSK 3/4', 'QPSK', '3/4', 0.35, 9, 'DVB-S2'),
('16APSK 2/3', '16APSK 2/3', '16APSK', '2/3', 0.10, 18, 'DVB-S2');

-- Sample ground stations
INSERT INTO ground_stations (name, site_name, site_lat, site_long, country, city) VALUES
('Brasilia Station', 'Brasilia', -15.8, -47.9, 'Brazil', 'Brasilia'),
('Rio Station', 'Rio de Janeiro', -22.9, -43.2, 'Brazil', 'Rio de Janeiro'),
('Sao Paulo Station', 'Sao Paulo', -23.5, -46.6, 'Brazil', 'Sao Paulo'),
('Recife Station', 'Recife', -8.0, -34.9, 'Brazil', 'Recife');

-- Sample complex reception systems
INSERT INTO reception_complex (name, ground_station_id, ant_size, ant_eff, lnb_gain, lnb_temp,
                               coupling_loss, cable_loss, max_depoint) VALUES
('1.2m Ku System', 1, 1.2, 0.60, 55, 20, 0, 4, 0.1),
('1.8m Ku System', 2, 1.8, 0.65, 58, 15, 0, 4, 0.1),
('2.4m C System', 3, 2.4, 0.70, 60, 25, 0, 3, 0.1);

-- Sample simple reception systems
INSERT INTO reception_simple (name, ground_station_id, gt_value, depoint_loss, frequency) VALUES
('High-Gain Terminal', 1, 20.5, 0.5, 14.25),
('Standard Terminal', 2, 18.0, 0.5, 14.25),
('Low-Cost Terminal', 3, 15.5, 0.8, 14.25);
"""


# ============================================================================
# ORM MODEL DEFINITIONS (SQLAlchemy)
# ============================================================================

ORM_MODELS = """
from sqlalchemy import create_engine, Column, Integer, String, Float, Text, DateTime, ForeignKey, UniqueConstraint
from sqlalchemy.ext.declarative import declarative_base
from sqlalchemy.orm import relationship, sessionmaker
from datetime import datetime

Base = declarative_base()


class SatellitePosition(Base):
    \"\"\"卫星位置信息表\"\"\"
    __tablename__ = 'satellite_positions'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    sat_long = Column(Float, nullable=False)  # 卫星经度 (度)
    sat_lat = Column(Float, default=0)  # 卫星纬度 (度)
    h_sat = Column(Float, default=35786)  # 卫星高度 (km)
    orbit_type = Column(String(20), default='GEO')  # 轨道类型
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    transponders = relationship('Transponder', back_populates='satellite')

    def __repr__(self):
        return f'<SatellitePosition(name={self.name}, long={self.sat_long}°, orbit={self.orbit_type})>'


class Transponder(Base):
    \"\"\"转发器信息表\"\"\"
    __tablename__ = 'transponders'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    satellite_id = Column(Integer, ForeignKey('satellite_positions.id'))
    freq = Column(Float, nullable=False)  # 中心频率 (GHz)
    freq_band = Column(String(10))  # 频段: C, Ku, Ka, Q
    eirp_max = Column(Float, default=0)  # 最大EIRP (dBW)
    b_transp = Column(Float, default=36)  # 转发器带宽 (MHz)
    back_off = Column(Float, default=0)  # 输出回退 (dB)
    contorno = Column(Float, default=0)  # 轮廓因子 (dB)
    polarization = Column(String(20))  # 极化方式
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    satellite = relationship('SatellitePosition', back_populates='transponders')

    def __repr__(self):
        return f'<Transponder(name={self.name}, freq={self.freq}GHz, band={self.freq_band})>'


class Carrier(Base):
    \"\"\"载波/调制配置表\"\"\"
    __tablename__ = 'carriers'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    modcod = Column(String(50), nullable=False, unique=True)  # 完整MODCOD
    modulation = Column(String(20), nullable=False)  # 调制方式
    fec = Column(String(20), nullable=False)  # FEC码率
    roll_off = Column(Float, nullable=False)  # 滚降系数
    b_util = Column(Float, default=36)  # 占用带宽 (MHz)
    snr_threshold = Column(Float)  # SNR门限 (dB)
    spectral_efficiency = Column(Float)  # 频谱效率 (bps/Hz)
    standard = Column(String(20))  # 标准: DVB-S, DVB-S2, DVB-S2X
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    def __repr__(self):
        return f'<Carrier(modcod={self.modcod}, mod={self.modulation}, fec={self.fec})>'


class GroundStation(Base):
    \"\"\"地面站位置信息表\"\"\"
    __tablename__ = 'ground_stations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    site_name = Column(String(100))  # 站点名称
    site_lat = Column(Float, nullable=False)  # 纬度 (度)
    site_long = Column(Float, nullable=False)  # 经度 (度)
    altitude = Column(Float, default=0)  # 海拔高度 (m)
    country = Column(String(50))
    region = Column(String(50))
    city = Column(String(50))
    climate_zone = Column(String(20))  # 气候区域
    itu_region = Column(String(10))  # ITU区域
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    complex_receptions = relationship('ReceptionComplex', back_populates='ground_station')
    simple_receptions = relationship('ReceptionSimple', back_populates='ground_station')

    def __repr__(self):
        return f'<GroundStation(name={self.name}, lat={self.site_lat}°, long={self.site_long}°)>'


class ReceptionComplex(Base):
    \"\"\"复杂接收系统配置表（详细硬件参数）\"\"\"
    __tablename__ = 'reception_complex'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    ground_station_id = Column(Integer, ForeignKey('ground_stations.id'))
    ant_size = Column(Float, nullable=False)  # 天线直径 (m)
    ant_eff = Column(Float, nullable=False)  # 天线效率
    lnb_gain = Column(Float, nullable=False)  # LNB增益 (dB)
    lnb_temp = Column(Float, nullable=False)  # LNB噪声温度 (K)
    coupling_loss = Column(Float, default=0)  # 耦合损耗 (dB)
    cable_loss = Column(Float, default=0)  # 电缆损耗 (dB)
    polarization_loss = Column(Float, default=3)  # 极化损耗 (dB)
    max_depoint = Column(Float, default=0)  # 最大指向误差 (度)
    manufacturer = Column(String(100))
    model = Column(String(100))
    description = Column(Text)
    calculated_gt = Column(Float)  # 计算出的G/T值 (dB/K)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    ground_station = relationship('GroundStation', back_populates='complex_receptions')

    def __repr__(self):
        return f'<ReceptionComplex(name={self.name}, ant={self.ant_size}m, gt={self.calculated_gt})>'


class ReceptionSimple(Base):
    \"\"\"简化接收系统配置表（直接使用G/T值）\"\"\"
    __tablename__ = 'reception_simple'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    ground_station_id = Column(Integer, ForeignKey('ground_stations.id'))
    gt_value = Column(Float, nullable=False)  # G/T值 (dB/K)
    depoint_loss = Column(Float, default=0)  # 指向损耗 (dB)
    frequency = Column(Float)  # 参考频率 (GHz)
    measurement_method = Column(String(50))  # 测量方法
    manufacturer = Column(String(100))
    model = Column(String(100))
    description = Column(Text)
    created_at = Column(DateTime, default=datetime.utcnow)
    updated_at = Column(DateTime, default=datetime.utcnow, onupdate=datetime.utcnow)

    # Relationships
    ground_station = relationship('GroundStation', back_populates='simple_receptions')

    def __repr__(self):
        return f'<ReceptionSimple(name={self.name}, gt={self.gt_value})>'


class LinkCalculation(Base):
    \"\"\"链路计算结果表\"\"\"
    __tablename__ = 'link_calculations'

    id = Column(Integer, primary_key=True, autoincrement=True)
    name = Column(String(100), nullable=False)
    satellite_id = Column(Integer, ForeignKey('satellite_positions.id'), nullable=False)
    transponder_id = Column(Integer, ForeignKey('transponders.id'), nullable=False)
    carrier_id = Column(Integer, ForeignKey('carriers.id'), nullable=False)
    ground_station_id = Column(Integer, ForeignKey('ground_stations.id'), nullable=False)
    reception_type = Column(String(10), nullable=False)  # 'complex' or 'simple'
    reception_id = Column(Integer, nullable=False)

    # Input parameters
    margin = Column(Float, default=0)
    snr_relaxation = Column(Float, default=0.1)

    # Results
    elevation_angle = Column(Float)  # 仰角 (度)
    azimuth_angle = Column(Float)  # 方位角 (度)
    distance = Column(Float)  # 距离 (km)

    # Attenuation at 0.001%
    a_fs = Column(Float)  # 自由空间损耗
    a_g = Column(Float)  # 气体衰减
    a_c = Column(Float)  # 云衰减
    a_r = Column(Float)  # 雨衰减
    a_s = Column(Float)  # 闪烁衰减
    a_t = Column(Float)  # 总大气衰减
    a_tot = Column(Float)  # 总损耗

    # Link quality
    cn0 = Column(Float)  # C/N0 (dB-Hz)
    snr = Column(Float)  # SNR (dB)
    snr_threshold = Column(Float)  # SNR门限
    link_margin = Column(Float)  # 链路余量
    availability = Column(Float)  # 可用性 (%)
    gt_value = Column(Float)  # G/T

    calculation_date = Column(DateTime, default=datetime.utcnow)
    notes = Column(Text)

    def __repr__(self):
        return f'<LinkCalculation(name={self.name}, availability={self.availability}%)>'
"""
