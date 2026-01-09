"""
演示使用 G/T 进行简化链路预算计算

当已知接收站的 G/T 值时，可以跳过详细的硬件参数计算，
直接进行链路预算分析。
"""

import sys
import os
import numpy as np

sys.path.insert(0, os.path.dirname(os.path.abspath(__file__)))

from GrStat import GroundStation
from satellite_new import Satellite
from models.satellite_components import SatellitePosition, Transponder, Carrier, calculate_eirp
from models.simple_reception import SimpleReception

print("=" * 70)
print("简化链路预算演示 - 使用 G/T 值")
print("=" * 70)
print()

# ============================================================================
# 场景设置
# ============================================================================
print("场景设置:")
print("-" * 70)

# 卫星参数（从卫星运营商获取）
sat_long = -70  # 卫星经度
freq = 14       # 下行频率 GHz
eirp_max = 54   # 最大 EIRP dBW
b_transp = 36   # 转发器带宽 MHz
b_util = 9      # 占用带宽 MHz
modcod = '8PSK 120/180'
roll_off = 0.2

print(f"卫星: GEO @ {sat_long}°")
print(f"下行频率: {freq} GHz (Ku波段)")
print(f"最大 EIRP: {eirp_max} dBW")
print(f"调制: {modcod}")
print(f"占用带宽: {b_util} MHz")
print()

# 接收站位置
site_lat = -3.7   # 巴西位置
site_long = -45.9

print(f"地面站位置: {site_lat}°, {site_long}°")
print()

# ============================================================================
# 方法1: 使用详细硬件参数
# ============================================================================
print("\n" + "=" * 70)
print("方法1: 使用详细硬件参数计算")
print("=" * 70)
print()

from GrStat import Reception

# 详细的接收系统硬件参数
ant_size = 1.2      # 天线直径 m
ant_eff = 0.6       # 天线效率
lnb_gain = 55       # LNB 增益 dB
lnb_temp = 20       # LNB 噪声温度 K
coupling_loss = 0   # 耦合损耗 dB
cable_loss = 4      # 电缆损耗 dB
max_depoint = 0.1   # 最大指向误差 度

print("接收站硬件参数:")
print(f"  天线: {ant_size}m, 效率 {ant_eff}")
print(f"  LNB: 增益 {lnb_gain} dB, 噪声温度 {lnb_temp} K")
print(f"  损耗: 耦合 {coupling_loss} dB, 电缆 {cable_loss} dB")
print(f"  指向误差: {max_depoint} 度")
print()

# 创建组件对象
position = SatellitePosition(sat_long=sat_long, h_sat=35786)
transponder = Transponder(freq=freq, eirp_max=eirp_max, b_transp=b_transp)
carrier = Carrier(modcod=modcod, roll_off=roll_off, b_util=b_util)

# 创建地面站和接收系统
station = GroundStation(site_lat, site_long)
reception_detailed = Reception(
    ant_size=ant_size,
    ant_eff=ant_eff,
    coupling_loss=coupling_loss,
    polarization_loss=3,
    lnb_gain=lnb_gain,
    lnb_noise_temp=lnb_temp,
    cable_loss=cable_loss,
    max_depoint=max_depoint
)

# 创建卫星并关联
satellite_detailed = Satellite(position, transponder, carrier)
satellite_detailed.set_grstation(station)
satellite_detailed.set_reception(reception_detailed)

# 计算链路参数
elevation = satellite_detailed.get_elevation()
distance = satellite_detailed.get_distance()
gt_detailed = satellite_detailed.get_figure_of_merit()

print(f"几何参数:")
print(f"  仰角: {elevation:.2f}°")
print(f"  距离: {distance:.2f} km")
print()
print(f"计算结果:")
print(f"  天线增益: {reception_detailed.get_antenna_gain():.2f} dBi")
print(f"  3dB 波束宽度: {reception_detailed.get_beamwidth():.3f}°")
print(f"  指向损耗: {reception_detailed.get_depoint_loss():.3f} dB")
print(f"  G/T (品质因数): {gt_detailed:.2f} dB/K")
print()

# ============================================================================
# 方法2: 直接使用 G/T 值
# ============================================================================
print("\n" + "=" * 70)
print("方法2: 直接使用 G/T 值 (简化方法)")
print("=" * 70)
print()

# 从设备规格书中获取的 G/T 值
gt_value = gt_detailed  # 假设这是从规格书获取的
depoint_loss = 0.077    # 估计的指向损耗 dB

print(f"从设备规格书获取的参数:")
print(f"  G/T: {gt_value:.2f} dB/K")
print(f"  估计指向损耗: {depoint_loss:.3f} dB")
print()

# 创建简化的接收系统
reception_simple = SimpleReception(
    gt_value=gt_value,
    depoint_loss=depoint_loss
)

# 创建新的卫星对象用于简化计算
satellite_simple = Satellite(position, transponder, carrier)
satellite_simple.set_grstation(station)
satellite_simple.set_reception(reception_simple)

# ============================================================================
# 链路预算计算
# ============================================================================
print("\n" + "=" * 70)
print("链路预算计算 (p = 0.001% 的时间百分比)")
print("=" * 70)
print()

# 详细方法
a_fs, a_dep, a_g, a_c, a_r, a_s, a_t, a_tot = satellite_detailed.get_link_attenuation(p=0.001)
cn0_detailed = satellite_detailed.get_c_over_n0(0.001)
snr_detailed = satellite_detailed.get_snr(0.001)
snr_threshold = satellite_detailed.get_reception_threshold()
availability = satellite_detailed.get_availability(margin=0, relaxation=0.1)

print("链路损耗 (详细方法):")
print(f"  自由空间损耗: {a_fs:.2f} dB")
print(f"  气体衰减: {a_g:.3f} dB")
print(f"  云衰减: {a_c:.3f} dB")
print(f"  雨衰减: {a_r:.2f} dB")
print(f"  闪烁衰减: {a_s:.3f} dB")
print(f"  总大气衰减: {a_t:.2f} dB")
print(f"  指向损耗: {a_dep:.3f} dB")
print(f"  总损耗: {a_tot:.2f} dB")
print()

print("链路质量:")
print(f"  C/N0: {cn0_detailed:.2f} dB-Hz")
print(f"  SNR: {snr_detailed:.2f} dB")
print(f"  SNR 门限: {snr_threshold:.2f} dB")
print(f"  链路余量: {snr_detailed - snr_threshold:.2f} dB")
print(f"  可用性: {availability}%")
print()

# 简化方法
print("-" * 70)
print("验证: 使用简化 G/T 方法计算")
print("-" * 70)

cn0_simple = satellite_simple.get_c_over_n0(0.001)
snr_simple = satellite_simple.get_snr(0.001)

print("链路质量 (简化方法):")
print(f"  C/N0: {cn0_simple:.2f} dB-Hz")
print(f"  SNR: {snr_simple:.2f} dB")
print()

# 比较
print("\n" + "=" * 70)
print("两种方法的结果比较")
print("=" * 70)
print()
print(f"{'参数':<20} {'详细方法':<15} {'简化方法':<15} {'差异':<10}")
print("-" * 70)
print(f"{'G/T':<20} {gt_detailed:<15.2f} {gt_value:<15.2f} {0:<10.2f}")
print(f"{'C/N0':<20} {cn0_detailed:<15.2f} {cn0_simple:<15.2f} {cn0_simple-cn0_detailed:<10.2f}")
print(f"{'SNR':<20} {snr_detailed:<15.2f} {snr_simple:<15.2f} {snr_simple-snr_detailed:<10.2f}")
print()

# ============================================================================
# 总结
# ============================================================================
print("\n" + "=" * 70)
print("总结")
print("=" * 70)
print()
print("当已知接收站的 G/T 值时，可以:")
print("  1. 跳过详细的硬件参数计算")
print("  2. 直接进行链路预算分析")
print("  3. 获得与详细方法相同的结果")
print()
print("简化的链路预算公式:")
print("  C/N0 = EIRP - L_total + G/T + 228.6")
print("  SNR = C/N0 - 10*log10(B)")
print()
print("其中:")
print("  EIRP: 有效全向辐射功率 (dBW)")
print("  L_total: 总路径损耗 (dB)")
print("  G/T: 品质因数 (dB/K)")
print("  B: 噪声带宽 (Hz)")
print("  228.6 = 10*log10(k_B), k_B 是玻尔兹曼常数")
print()
