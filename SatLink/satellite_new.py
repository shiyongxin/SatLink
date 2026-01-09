"""
Refactored Satellite class using component-based design

This module provides a Satellite class that uses the component classes
(SatellitePosition, Transponder, Carrier) for better organization.
"""

import sys
import warnings
import numpy as np
import pandas as pd
import itur
from GrStat import GroundStation, Reception
from models.FsAtt import FreeSpaceAtt as FsAtt
import astropy.units as u
from models.util import truncate
from models.satellite_components import SatellitePosition, Transponder, Carrier, calculate_eirp


class Satellite:
    """
    Satellite link calculation class with component-based design

    This class calculates parameters related to the satellite link to the ground station.
    It uses component objects for position, transponder, and carrier information.

    Parameters
    ----------
    position : SatellitePosition
        Satellite position information
    transponder : Transponder
        Transponder information
    carrier : Carrier
        Carrier/modulation information

    Or you can pass individual parameters for backward compatibility:
    sat_long, freq, eirp_max=0, h_sat=35786, b_transp=36, b_util=36,
    back_off=0, contorno=0, modulation='', roll_off=None, fec=''
    """

    def __init__(self, *args, **kwargs):
        # Check if using component-based initialization or backward compatibility
        if len(args) >= 3 and all(isinstance(arg, (SatellitePosition, Transponder, Carrier)) for arg in args[:3]):
            # Component-based initialization
            self.position = args[0]  # SatellitePosition
            self.transponder = args[1]  # Transponder
            self.carrier = args[2]  # Carrier

            # Set attributes from components for backward compatibility
            self.sat_long = self.position.sat_long_rad
            self.freq = self.transponder.freq
            self.eirp_max = self.transponder.eirp_max
            self.h_sat = self.position.h_sat
            self.b_transp = self.transponder.b_transp
            self.b_util = self.carrier.b_util
            self.back_off = self.transponder.back_off
            self.contorno = self.transponder.contorno
            self.modulation = self.carrier.modulation
            self.fec = self.carrier.fec
            self.roll_off = self.carrier.roll_off

        else:
            # Backward compatibility - individual parameters
            sat_long = kwargs.get('sat_long', args[0] if args else 0)
            sat_lat = kwargs.get('sat_lat', 0)
            h_sat = kwargs.get('h_sat', 35786)
            freq = kwargs.get('freq', args[1] if len(args) > 1 else 0)
            eirp_max = kwargs.get('eirp_max', args[2] if len(args) > 2 else 0)
            b_transp = kwargs.get('b_transp', 36)
            b_util = kwargs.get('b_util', 36)
            back_off = kwargs.get('back_off', 0)
            contorno = kwargs.get('contorno', 0)
            modulation = kwargs.get('modulation', '')
            roll_off = kwargs.get('roll_off', None)
            fec = kwargs.get('fec', '')
            modcod = kwargs.get('modcod', '')

            # Create component objects
            self.position = SatellitePosition(sat_long, sat_lat, h_sat)
            self.transponder = Transponder(freq, eirp_max, b_transp, back_off, contorno)
            self.carrier = Carrier(modulation, roll_off, fec, b_util, modcod)

            # Set attributes for backward compatibility
            self.sat_long = self.position.sat_long_rad
            self.freq = self.transponder.freq
            self.eirp_max = self.transponder.eirp_max
            self.h_sat = self.position.h_sat
            self.b_transp = self.transponder.b_transp
            self.b_util = self.carrier.b_util
            self.back_off = self.transponder.back_off
            self.contorno = self.transponder.contorno
            self.modulation = self.carrier.modulation
            self.fec = self.carrier.fec
            self.roll_off = self.carrier.roll_off

        # Calculate effective EIRP
        self.eirp = calculate_eirp(self.transponder, self.carrier)

        # not initialized parameters that will be calculated in the atmospheric attenuation function
        self.a_g = None  # gaseous attenuation
        self.a_c = None  # cloud attenuation
        self.a_r = None  # rain attenuation
        self.a_s = None  # scintillation or tropospheric attenuation
        self.a_t = None  # total atmospheric attenuation
        self.a_fs = None  # free space attenuation
        self.a_x = None  # cross-polar attenuation
        self.a_co = None  # co-polar attenuation
        self.a_tot = None  # total attenuation (atmospheric + free space)
        self.p = None  # exceed percentage - reference for attenuation calculations

        # other parameters calculated in this class
        self.cross_pol_discrimination = None  # attenuation due to depolarization effect
        self.power_flux_density = None  # power flux density at earth station (W/m^2)
        self.antenna_noise_rain = None  # antenna noise under rain conditions
        self.total_noise_temp = None  # system's noise temperature (K)
        self.figure_of_merit = None  # figure of merit - G/T
        self.c_over_n0 = None  # calculated C/N
        self.snr = None  # calculated SNR
        self.snr_threshold = None  # SNR threshold
        self.availability = None  # availability for a specific SNR threshold
        self.symbol_rate = None  # symbol rate based on bandwidth and roll off factor
        self.bitrate = None  # bitrate based on bandwidth and info rate efficiency

        # ground station and reception objects
        self.grstation = None  # ground station object
        self.reception = None  # reception object

    def set_grstation(self, grstation: GroundStation):
        """Associate a ground station to this satellite"""
        self.grstation = grstation

    def set_reception(self, reception: Reception):
        """Set the link's reception system"""
        reception.set_parameters(self.freq, self.get_elevation())
        self.reception = reception

    def get_elevation(self):
        """Returns the elevation angle between satellite and ground station in degrees"""
        if self.grstation is None:
            sys.exit(
                'Need to associate a ground station to a satellite first. Try satellite.set_grstation(GroundStation)!!!')

        site_lat = np.radians(self.grstation.site_lat)
        site_long = np.radians(self.grstation.site_long)
        E = np.arctan((np.cos(self.sat_long - site_long) * np.cos(site_lat) - 0.15116) /
                      (np.sqrt(1 - (np.cos(self.sat_long - site_long) ** 2) * (np.cos(site_lat) ** 2))))

        return np.degrees(E)

    def get_azimuth(self):
        """Returns the azimuth angle between satellite and ground station in degrees"""
        if self.grstation is None:
            sys.exit(
                'Need to associate a ground station to a satellite first. Try satellite.set_reception(reception)!!!')

        site_lat = np.radians(self.grstation.site_lat)
        site_long = np.radians(self.grstation.site_long)
        azimuth = np.pi + np.arctan2(np.tan(self.sat_long - site_long), np.sin(site_lat))

        return np.degrees(azimuth)

    def get_distance(self):
        """Returns the distance (km) between satellite and ground station"""
        if self.grstation is None:
            sys.exit(
                'Need to associate a ground station to a satellite first. Try satellite.set_reception(reception)!!!')

        e = np.radians(self.get_elevation())
        earth_rad = self.grstation.get_earth_radius()
        dist = np.sqrt(((earth_rad + self.h_sat) ** 2) - ((earth_rad * np.cos(e)) ** 2)) - earth_rad * np.sin(e)
        return dist

    def get_reception_threshold(self):
        """Returns the SNR threshold for the current modulation scheme"""
        if self.modulation == '' or self.fec == '':
            sys.exit(
                'You need to create a satellite class with a technology, modulation and FEC to use this function!!!')
        elif self.snr_threshold is not None:
            return self.snr_threshold

        # Use carrier object's method
        self.snr_threshold = self.carrier.get_snr_threshold()
        return self.snr_threshold

    def get_symbol_rate(self):
        """Returns the symbol rate in baud"""
        if self.symbol_rate is not None:
            return self.symbol_rate

        self.symbol_rate = self.carrier.get_symbol_rate()
        return self.symbol_rate

    def get_bitrate(self):
        """Returns the bitrate in bps"""
        if self.bitrate is not None:
            return self.bitrate

        self.bitrate = self.carrier.get_bitrate()
        return self.bitrate

    def get_link_attenuation(self, p=0.001, method='approx'):
        """
        Calculate link attenuation components

        Returns
        -------
        tuple
            (a_fs, a_dep, a_g, a_c, a_r, a_s, a_t, a_tot)
            Free space, depointing, gaseous, cloud, rain, scintillation,
            total atmospheric, and total attenuation
        """
        if self.grstation is None:
            sys.exit(
                'Need to associate a ground station to a satellite first. Try satellite.set_reception(reception)!!!')
        if self.reception is None:
            sys.exit('Need to associate a reception to a satellite first. Try satellite.set_reception(reception)!!!')
        if self.p is None:
            self.p = 0.001
            p = 0.001
        if self.a_tot is not None and p == self.p:
            return self.a_fs, self.reception.get_depoint_loss(), self.a_g, self.a_c, self.a_r, self.a_s, self.a_t, self.a_tot
        else:
            freq = self.freq * u.GHz
            e = self.get_elevation()
            # Handle SimpleReception case where ant_size might be None
            if self.reception.ant_size is not None:
                diam = self.reception.ant_size * u.m
            else:
                # Use a default antenna diameter for atmospheric attenuation calculation
                # This value doesn't significantly affect rain attenuation for typical antennas
                diam = 1.0 * u.m
            a_fs = FsAtt(self.get_distance(), self.freq)
            a_g, a_c, a_r, a_s, a_t = itur.atmospheric_attenuation_slant_path(
                self.grstation.site_lat, self.grstation.site_long, freq, e, p, diam,
                return_contributions=True, mode=method)
            a_tot = a_fs + self.reception.get_depoint_loss() + a_t.value

            self.a_g = a_g
            self.a_c = a_c
            self.a_r = a_r
            self.a_s = a_s
            self.a_t = a_t
            self.a_fs = a_fs
            self.a_tot = a_tot
            self.p = p

            # erasing the dependent variables that will use link attenuation for different p value
            self.power_flux_density = None
            self.antenna_noise_rain = None
            self.total_noise_temp = None
            self.figure_of_merit = None
            self.c_over_n0 = None
            self.snr = None
            self.cross_pol_discrimination = None

        return a_fs, self.reception.get_depoint_loss(), a_g, a_c, a_r, a_s, a_t, a_tot

    def get_total_attenuation(self, p=None):
        """Calculate total attenuation including cross-polarization"""
        self.a_fs = FsAtt(self.get_distance(), self.freq)
        xpd = self.get_cross_pol_discrimination()
        self.a_x = 10 * np.log10(1 + 10 ** (0.1 * xpd))
        self.a_co = 10 * np.log10(1 + 10 ** (0.1 * xpd))

        self.a_tot = self.a_fs + self.a_x + self.reception.get_depoint_loss() + self.a_t
        return self.a_tot, self.a_t, self.reception.get_depoint_loss(),

    def get_cross_pol_discrimination(self, p=None):
        """Calculate cross-polarization discrimination"""
        if self.cross_pol_discrimination is not None and p == self.p:
            return self.cross_pol_discrimination

        if p is not None:
            _, _, _, _, a_r, _, _, _ = self.get_link_attenuation(p)
        else:
            _, _, _, _, a_r, _, _, _ = self.get_link_attenuation(self.p)

        a_r = a_r.value
        if self.freq < 8:  # frequency in GHz
            f = 10  # dummy frequency for XPD calculations below 8 GHz
            if self.freq < 4:
                warnings.warn('XPD calculations are suited for frequencies above 4 GHz')
        else:
            f = self.freq
            if self.freq > 35:
                warnings.warn('XPD calculations are suited for frequencies below 35 GHz')

        cf = 20 * np.log10(f)

        if 8 <= f <= 20:
            v = 12.8 * (f ** 0.19)
        else:
            v = 22.6

        ca = v * np.log10(a_r)

        tau = 45  # TODO: Make this configurable
        c_tau = -10 * np.log10(1 - 0.484 * (1 + np.cos(4 * np.radians(tau))))
        c_teta = -40 * np.log10(np.cos(np.radians(self.get_elevation())))

        sigma = np.interp(self.p, [0.001, 0.01, 0.1, 1], [15, 10, 5, 0])
        c_sigma = 0.0052 * sigma

        xpd_rain = cf - ca + c_tau + c_teta + c_sigma
        c_ice = xpd_rain * (0.3 + 0.1 * np.log10(self.p)) / 2
        xpd = xpd_rain - c_ice

        tau2 = tau

        if self.freq < 8:
            xpd = (xpd_rain - 20 * np.log((self.freq * (1 + 0.484 * np.cos(4 * np.radians(tau2)))) ** 0.5) /
                   (f * (1 - 0.484 * (1 + np.cos(4 * np.radians(tau)))) ** 0.5))

        self.a_x = 10 * np.log10(1 + 10 ** (0.1 * xpd))
        self.a_co = 10 * np.log10(1 + 10 ** (-0.1 * xpd))

        self.cross_pol_discrimination = xpd
        return self.cross_pol_discrimination, self.a_co, self.a_x

    def get_power_flux_density(self, p=None):
        """Calculate power flux density at earth station (dBW/m^2)"""
        if self.grstation is None:
            sys.exit('Need to associate a grd. station to a satellite first. Try Satellite.set_grstation(Station)!!!')
        elif self.reception is None:
            sys.exit('Need to associate a reception to a satellite first. Try Satellite.set_reception(Reception)!!!')
        elif self.power_flux_density is not None and p == self.p:
            return self.power_flux_density

        if p is not None:
            _, _, _, _, _, _, a_t, _ = self.get_link_attenuation(p)
        else:
            _, _, _, _, _, _, a_t, _ = self.get_link_attenuation(self.p)

        a_t = a_t.value
        phi = (10 ** ((self.eirp - a_t) / 10)) / (4 * np.pi * ((self.get_distance() * 1000) ** 2))

        self.power_flux_density = 10 * np.log10(phi)

        return self.power_flux_density

    def get_antenna_noise_rain(self, p=None):
        """Calculate antenna noise temperature under rain conditions (K)"""
        if self.reception is None:
            sys.exit('Need to associate a reception to a satellite first. Try satellite.set_reception(reception)!!!')
        elif self.antenna_noise_rain is not None and self.p == p:
            return self.antenna_noise_rain

        if p is not None:
            _, _, _, _, _, _, a_t, _ = self.get_link_attenuation(p)
        else:
            _, _, _, _, _, _, a_t, _ = self.get_link_attenuation(self.p)
        Tm = 275
        a_t = 10 ** (a_t.value / 10)
        self.antenna_noise_rain = (self.reception.get_brightness_temp() / a_t +
                                   (Tm * (1 - 1 / a_t)) +
                                   self.reception.get_ground_temp())
        return self.antenna_noise_rain

    def get_total_noise_temp(self, p=None):
        """Calculate system noise temperature (K)"""
        if self.freq is None or self.reception.e is None:
            sys.exit('Need to associate a reception to a satellite first. Try satellite.set_reception(reception)!!!')
        elif self.total_noise_temp is not None and p == self.p:
            return self.total_noise_temp
        if p is not None:
            _, _, _, _, _, _, a_t, _ = self.get_link_attenuation(p)

        total_loss = self.reception.coupling_loss + self.reception.cable_loss
        loss = 10 ** (total_loss / 10)
        t_loss = 290 * (loss - 1)
        self.total_noise_temp = (self.get_antenna_noise_rain() +
                                 (self.reception.lnb_noise_temp +
                                  t_loss / (10 ** (self.reception.lnb_gain / 10))))

        return self.total_noise_temp

    def get_figure_of_merit(self, p=None):
        """Calculate figure of merit G/T (dB/K) - ITU-R BO.790"""
        if self.figure_of_merit is not None:
            return self.figure_of_merit
        elif self.figure_of_merit is not None and p == self.p:
            return self.figure_of_merit
        if p is not None:
            _, _, _, _, _, _, _, _ = self.get_link_attenuation(p)

        alfa = 10 ** ((self.reception.coupling_loss + self.reception.cable_loss) / 10)
        beta = 10 ** (self.reception.get_depoint_loss() / 10)
        gt = 10 ** (self.reception.get_antenna_gain() / 10)
        ta = self.get_antenna_noise_rain()
        t0 = 290
        n = self.get_total_noise_temp() / t0 + 1

        self.figure_of_merit = 10 * np.log10((alfa * beta * gt) / (alfa * ta + (1 - alfa) * t0 + (n - 1) * t0))

        return self.figure_of_merit

    def get_c_over_n0(self, p=None):
        """Calculate C/N0 ratio (dB-Hz)"""
        if self.reception is None:
            sys.exit('Need to associate a reception to a satellite first. Try satellite.set_reception(reception)!!!')
        if self.eirp_max == 0:
            sys.exit('Please set the satellite\'s E.I.R.P before running this!!!')
        if self.c_over_n0 is not None and self.p == p:
            return self.c_over_n0

        if p is not None:
            _, _, _, _, _, _, _, a_tot = self.get_link_attenuation(p)
        else:
            _, _, _, _, _, _, _, a_tot = self.get_link_attenuation(self.p)

        figure_of_merit = self.get_figure_of_merit()
        self.c_over_n0 = self.eirp - a_tot + figure_of_merit + 228.6

        self.snr = None  # erasing the dependent variables that will use C/N0 for different p value
        return self.c_over_n0

    def get_snr(self, p=None):
        """Calculate SNR (dB)"""
        if p == self.p and self.snr is not None:
            return self.snr
        if p is not None:
            _, _, _, _, _, _, _, _ = self.get_link_attenuation(p)
        else:
            _, _, _, _, _, _, _, _ = self.get_link_attenuation(self.p)

        self.snr = self.get_c_over_n0(p) - 10 * np.log10(self.b_util * (10 ** 6))

        return self.snr

    def get_availability(self, margin=0, relaxation=0.1):
        """
        Calculate availability percentage using iterative search

        This is a simple iterative method for convex optimization problems.
        For recommended methodology, see ITU-R BO.1696.
        """
        target = self.get_reception_threshold() + margin
        p = 0.0012
        speed = 0.000005
        speed_old = 0
        delta_old = 1000000000
        p_old = 10000000
        delta = self.get_snr(0.001) - target

        if delta >= 0:
            return 99.999

        for i in range(1, 5000):
            delta = abs(self.get_snr(p) - target)
            if delta < relaxation:
                self.availability = 100 - p
                return truncate(self.availability, 3)

            if delta_old < delta:
                if (abs(p_old - p) < 0.001) and (speed_old * speed < 1):
                    self.availability = 100 - p
                    return truncate(self.availability, 3)

                speed_old = speed
                speed = -1 * speed / 10
                p_old = p
                p += speed
            else:
                speed_old = speed
                speed = speed * 1.5
                p_old = p
                p += speed

            if p < 0.001:
                p_old = 100
                p = 0.001 + np.random.choice(np.arange(0.001, 0.002, 0.000005))
                speed_old = 1
                speed = 0.000005
                delta = abs(self.get_snr(p) - target)
            if p > 50:
                p_old = 100
                p = 50 - np.random.choice(np.arange(0.01, 2, 0.01))
                speed_old = 1
                speed = 0.000005

            delta_old = delta

        sys.exit(
            'Can\'t reach the required SNR. You can change the modulation settings or the required snr relaxation!!!')

    def get_wm_availability(self):
        """Get worst month availability - ITU-R P.841-4"""
        if self.availability is not None:
            self.wm_availability = 100 - (2.84 * (100 - self.availability) ** 0.87)
            return self.wm_availability
