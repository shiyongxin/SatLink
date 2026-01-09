"""
Simplified Reception class for link budget analysis using G/T value

This module provides a simplified reception system class when the Figure of Merit (G/T)
is known, eliminating the need for detailed hardware parameters.
"""

import numpy as np
import pandas as pd
from scipy import constants as const
import sys


class SimpleReception:
    """
    Simplified reception system when G/T (Figure of Merit) is known

    Parameters
    ----------
    gt_value : float
        Figure of Merit G/T in dB/K
    depoint_loss : float, optional
        Estimated depointing loss in dB (default: 0)
    frequency : float, optional
        System frequency in GHz (optional, for compatibility)
    elevation : float, optional
        Elevation angle in degrees (optional, for compatibility)
    """

    def __init__(self, gt_value, depoint_loss=0, frequency=None, elevation=None):
        self.gt_value = gt_value  # G/T in dB/K
        self.depoint_loss = depoint_loss  # Depointing loss in dB
        self.freq = frequency
        self.e = elevation

        # Compatibility attributes (not used in simplified calculation)
        self.ant_size = None
        self.ant_eff = None
        self.coupling_loss = 0
        self.polarization_loss = 0
        self.lnb_gain = 0
        self.lnb_noise_temp = 0
        self.cable_loss = 0
        self.max_depoint = 0

        # Cached values
        self.gain = None
        self.t_ground = None
        self.t_sky = None
        self.t_ant = None
        self.total_noise_temp = None
        self.figure_of_merit = None
        self.angle_3db = None
        self.a_dep = None

    def set_parameters(self, freq, e):
        """Set frequency and elevation (for compatibility)"""
        self.freq = freq
        self.e = e

    def get_figure_of_merit(self):
        """Return the G/T value directly"""
        return self.gt_value

    def get_depoint_loss(self):
        """Return the depointing loss"""
        return self.depoint_loss

    def get_antenna_gain(self):
        """
        Estimate antenna gain from G/T if possible
        This is a rough estimation and may not be accurate
        """
        if self.gain is not None:
            return self.gain

        # Rough estimation: assume T_sys ≈ 100K for typical Ka/Ku band systems
        # G/T = G - 10*log10(T_sys)
        # G ≈ G/T + 10*log10(100) = G/T + 20
        self.gain = self.gt_value + 20
        return self.gain  # dBi

    def get_beamwidth(self):
        """Placeholder - not available without antenna size"""
        if self.angle_3db is not None:
            return self.angle_3db

        # Can't calculate without antenna size
        # Return a typical value for Ku/Ka band
        if self.freq:
            # Assume a typical antenna size that would give the estimated gain
            # Rough approximation
            wavelength = const.c / (self.freq * 1e9)
            gain_linear = 10 ** (self.get_antenna_gain() / 10)
            # G = η * (π*D/λ)², assume η = 0.6
            ant_size = np.sqrt(gain_linear / 0.6) * wavelength / np.pi
            self.angle_3db = 70 * wavelength / (ant_size * self.freq * 1e9)
            return self.angle_3db

        return None

    def get_ground_temp(self):
        """Placeholder - not typically needed when G/T is known"""
        if self.t_ground is not None:
            return self.t_ground

        if self.e is not None:
            if self.e < -10:
                self.t_ground = 290
            elif -10 <= self.e < 0:
                self.t_ground = 150
            elif 0 <= self.e < 10:
                self.t_ground = 50
            elif 10 <= self.e < 90:
                self.t_ground = 10

        return self.t_ground if self.t_ground is not None else 50

    def get_brightness_temp(self, printer=False):
        """Placeholder - not typically needed when G/T is known"""
        if self.t_sky is not None:
            return self.t_sky

        if self.freq is not None and self.e is not None:
            # This would require the ITU-R P.372 table
            # Return a typical value for Ku/Ka band
            if self.freq < 10:
                self.t_sky = 10 + self.e * 0.5
            else:
                self.t_sky = 20 + self.e * 0.3

        return self.t_sky if self.t_sky is not None else 15

    def get_antenna_noise_temp(self):
        """Placeholder - not typically needed when G/T is known"""
        if self.t_ant is not None:
            return self.t_ant

        self.t_ant = self.get_brightness_temp() + self.get_ground_temp()
        return self.t_ant

    @staticmethod
    def calculate_gt_from_hardware(ant_size, ant_eff, lnb_gain, lnb_temp,
                                   coupling_loss=0, cable_loss=0,
                                   polarization_loss=0, max_depoint=0,
                                   freq=14, elevation=45, rain_attenuation=0):
        """
        Calculate G/T from hardware parameters (helper function)

        Parameters
        ----------
        ant_size : float
            Antenna diameter in meters
        ant_eff : float
            Antenna efficiency (0-1)
        lnb_gain : float
            LNB gain in dB
        lnb_temp : float
            LNB noise temperature in K
        coupling_loss : float
            Coupling loss in dB
        cable_loss : float
            Cable loss in dB
        polarization_loss : float
            Polarization loss in dB
        max_depoint : float
            Maximum depointing angle in degrees
        freq : float
            Frequency in GHz
        elevation : float
            Elevation angle in degrees
        rain_attenuation : float
            Rain attenuation in dB (for system noise calculation)

        Returns
        -------
        float
            G/T in dB/K
        """
        # Calculate antenna gain
        gain = 10 * np.log10(ant_eff * (np.pi * ant_size * freq * 1e9 / const.c) ** 2)

        # Calculate beamwidth
        beamwidth = 70 * const.c / (freq * 1e9 * ant_size)

        # Calculate depointing loss
        depoint_loss = 12 * ((max_depoint / beamwidth) ** 2)

        # Calculate ground temperature
        if elevation < -10:
            t_ground = 290
        elif -10 <= elevation < 0:
            t_ground = 150
        elif 0 <= elevation < 10:
            t_ground = 50
        else:
            t_ground = 10

        # Estimate sky brightness temperature (simplified)
        if freq < 10:
            t_sky = 10 + elevation * 0.5
        else:
            t_sky = 20 + elevation * 0.3

        # Calculate antenna noise temperature under rain
        if rain_attenuation > 0:
            a_rain_linear = 10 ** (rain_attenuation / 10)
            tm = 275
            t_ant_rain = t_sky / a_rain_linear + tm * (1 - 1 / a_rain_linear) + t_ground
        else:
            t_ant_rain = t_sky + t_ground

        # Calculate system noise temperature
        total_loss = coupling_loss + cable_loss
        loss_linear = 10 ** (total_loss / 10)
        t_loss = 290 * (loss_linear - 1)

        t_sys = t_ant_rain + (lnb_temp + t_loss / (10 ** (lnb_gain / 10)))

        # Calculate G/T using simplified formula
        # G/T = G - 10*log10(T_sys)  (simplified, ignoring loss effects)
        # For more accurate calculation, use the ITU-R BO.790 methodology

        # Simplified approach: G/T ≈ G - 10*log10(T_sys)
        gt = gain - 10 * np.log10(t_sys)

        return gt

    def __repr__(self):
        return f"SimpleReception(G/T={self.gt_value} dB/K, depoint_loss={self.depoint_loss} dB)"


def estimate_depointing_loss(ant_size, freq, max_depoint_error):
    """
    Estimate depointing loss from antenna parameters

    Parameters
    ----------
    ant_size : float
        Antenna diameter in meters
    freq : float
        Frequency in GHz
    max_depoint_error : float
        Maximum pointing error in degrees

    Returns
    -------
    float
        Depointing loss in dB
    """
    beamwidth = 70 * const.c / (freq * 1e9 * ant_size)
    depoint_loss = 12 * ((max_depoint_error / beamwidth) ** 2)
    return depoint_loss


# Example usage and verification
if __name__ == "__main__":
    print("SimpleReception Class - G/T Based Link Budget")
    print("=" * 60)

    # Example 1: Direct G/T value
    print("\nExample 1: Using direct G/T value")
    reception1 = SimpleReception(gt_value=20.0, depoint_loss=0.5)
    print(f"Reception: {reception1}")
    print(f"G/T: {reception1.get_figure_of_merit()} dB/K")
    print(f"Depoint Loss: {reception1.get_depoint_loss()} dB")

    # Example 2: Calculate G/T from hardware parameters
    print("\nExample 2: Calculating G/T from hardware parameters")
    gt_calculated = SimpleReception.calculate_gt_from_hardware(
        ant_size=1.2,
        ant_eff=0.6,
        lnb_gain=55,
        lnb_temp=20,
        coupling_loss=0,
        cable_loss=4,
        max_depoint=0.1,
        freq=14,
        elevation=45
    )
    print(f"Calculated G/T: {gt_calculated:.2f} dB/K")

    # Example 3: Estimate depointing loss
    print("\nExample 3: Estimating depointing loss")
    dep_loss = estimate_depointing_loss(
        ant_size=1.2,
        freq=14,
        max_depoint_error=0.1
    )
    print(f"Estimated depointing loss: {dep_loss:.3f} dB")
