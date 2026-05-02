import numpy as np
from typing import Tuple, Dict, Any
from dataclasses import dataclass


@dataclass
class SourceParameter:
    emission_rate: float  # kg/s
    stack_height: float  # m
    stack_diameter: float  # m
    exit_velocity: float  # m/s
    exit_temperature: float  # K
    ambient_temperature: float  # K


@dataclass
class Meteorology:
    wind_speed: float  # m/s
    wind_direction: float  # degrees from north
    stability_class: str  # 'A' to 'F'
    mixing_height: float = 1000.0  # m


class GaussianPlumeModel:
    """高斯烟羽扩散模型"""
    
    def __init__(self):
        self.sigma_y_coeff = {
            'A': (0.22, 0.0001, 0.0001),
            'B': (0.16, 0.0001, 0.0001),
            'C': (0.11, 0.0001, 0.0001),
            'D': (0.08, 0.0001, 0.0001),
            'E': (0.06, 0.0001, 0.0001),
            'F': (0.04, 0.0001, 0.0001),
        }
        self.sigma_z_coeff = {
            'A': (0.20, 0.0001, 0.0001),
            'B': (0.12, 0.0001, 0.0001),
            'C': (0.08, 0.0001, 0.0001),
            'D': (0.06, 0.0001, 0.0001),
            'E': (0.03, 0.0001, 0.0001),
            'F': (0.016, 0.0001, 0.0001),
        }

    def calculate_plume_rise(self, source: SourceParameter, met: Meteorology) -> float:
        """计算烟气抬升高度"""
        delta_T = source.exit_temperature - source.ambient_temperature
        if delta_T <= 0:
            return 0.0
        
        F = 0.25 * np.pi * source.stack_diameter**2 * source.exit_velocity * delta_T / source.ambient_temperature
        x = 100.0  # reference distance
        
        if F < 55:
            delta_h = 2.4 * F**(1/3) * x**(2/3) / (met.wind_speed * x**(1/3))
        else:
            delta_h = 1.4 * F**(1/3) * x**(2/3) / (met.wind_speed * x**(1/3))
        
        return min(delta_h, 200.0)

    def get_sigma(self, x: float, stability_class: str) -> Tuple[float, float]:
        """获取扩散参数"""
        x = max(x, 10.0)
        
        if stability_class not in self.sigma_y_coeff:
            stability_class = 'D'
        
        a_y, b_y, c_y = self.sigma_y_coeff[stability_class]
        a_z, b_z, c_z = self.sigma_z_coeff[stability_class]
        
        sigma_y = a_y * x**(0.9) if x < 1000 else a_y * x**0.85
        sigma_z = a_z * x**(0.9) if x < 1000 else a_z * x**0.8
        
        return sigma_y, sigma_z

    def calculate_concentration(
        self,
        x: float, y: float, z: float,
        source: SourceParameter,
        met: Meteorology
    ) -> float:
        """计算单点浓度 (mg/m³)"""
        if met.wind_speed <= 0.1:
            return 0.0
        
        delta_h = self.calculate_plume_rise(source, met)
        effective_height = source.stack_height + delta_h
        
        sigma_y, sigma_z = self.get_sigma(x, met.stability_class)
        
        wind_rad = np.deg2rad(met.wind_direction)
        x_prime = x * np.cos(wind_rad) + y * np.sin(wind_rad)
        y_prime = -x * np.sin(wind_rad) + y * np.cos(wind_rad)
        
        if x_prime < 0:
            return 0.0
        
        C = (source.emission_rate * 1e6 / (2 * np.pi * met.wind_speed * sigma_y * sigma_z)) * \
            np.exp(-y_prime**2 / (2 * sigma_y**2)) * \
            (np.exp(-(z - effective_height)**2 / (2 * sigma_z**2)) + 
             np.exp(-(z + effective_height)**2 / (2 * sigma_z**2)))
        
        return max(C, 0.0)

    def calculate_grid(
        self,
        x_points: np.ndarray,
        y_points: np.ndarray,
        z: float,
        source: SourceParameter,
        met: Meteorology
    ) -> np.ndarray:
        """计算网格浓度"""
        X, Y = np.meshgrid(x_points, y_points)
        concentration = np.zeros_like(X)
        
        for i in range(X.shape[0]):
            for j in range(X.shape[1]):
                concentration[i, j] = self.calculate_concentration(
                    X[i, j], Y[i, j], z, source, met
                )
        
        return concentration

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        source = SourceParameter(
            emission_rate=inputs.get('emission_rate', 0.1),
            stack_height=inputs.get('stack_height', 20.0),
            stack_diameter=inputs.get('stack_diameter', 1.0),
            exit_velocity=inputs.get('exit_velocity', 10.0),
            exit_temperature=inputs.get('exit_temperature', 423.0),
            ambient_temperature=inputs.get('ambient_temperature', 293.0)
        )
        
        met = Meteorology(
            wind_speed=inputs.get('wind_speed', 3.0),
            wind_direction=inputs.get('wind_direction', 180.0),
            stability_class=inputs.get('stability_class', 'D'),
            mixing_height=inputs.get('mixing_height', 1000.0)
        )
        
        x_points = np.linspace(0, 2000, 100)
        y_points = np.linspace(-500, 500, 50)
        
        concentration = self.calculate_grid(x_points, y_points, 10.0, source, met)
        
        max_concentration = float(np.max(concentration))
        max_x, max_y = np.unravel_index(np.argmax(concentration), concentration.shape)
        max_distance = float(x_points[max_y])
        
        return {
            'max_concentration': round(max_concentration, 6),
            'max_distance': round(max_distance, 2),
            'concentration_shape': concentration.shape,
            'x_range': [float(np.min(x_points)), float(np.max(x_points))],
            'y_range': [float(np.min(y_points)), float(np.max(y_points))],
            'source_info': {
                'emission_rate': source.emission_rate,
                'stack_height': source.stack_height,
                'effective_height': float(source.stack_height + self.calculate_plume_rise(source, met))
            },
            'meteorology': {
                'wind_speed': met.wind_speed,
                'wind_direction': met.wind_direction,
                'stability_class': met.stability_class
            }
        }


class GaussianPuffModel:
    """高斯烟团扩散模型（瞬时泄漏）"""
    
    def calculate_concentration(
        self,
        x: float, y: float, z: float, t: float,
        release_mass: float,
        release_height: float,
        wind_speed: float,
        wind_direction: float,
        stability_class: str
    ) -> float:
        """计算瞬时泄漏浓度"""
        if wind_speed <= 0.1 or t <= 0:
            return 0.0
        
        sigma_y = 0.15 * (wind_speed * t)**0.9
        sigma_z = 0.10 * (wind_speed * t)**0.9
        
        wind_rad = np.deg2rad(wind_direction)
        x_prime = x - wind_speed * t * np.cos(wind_rad)
        y_prime = y - wind_speed * t * np.sin(wind_rad)
        
        C = (release_mass * 1e6 / (8 * (np.pi * t)**1.5 * sigma_y * sigma_z * wind_speed)) * \
            np.exp(-x_prime**2 / (4 * sigma_y**2 * t)) * \
            np.exp(-y_prime**2 / (4 * sigma_y**2 * t)) * \
            (np.exp(-(z - release_height)**2 / (4 * sigma_z**2 * t)) + 
             np.exp(-(z + release_height)**2 / (4 * sigma_z**2 * t)))
        
        return max(C, 0.0)

    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        release_mass = inputs.get('release_mass', 100.0)
        release_height = inputs.get('release_height', 0.0)
        wind_speed = inputs.get('wind_speed', 3.0)
        wind_direction = inputs.get('wind_direction', 180.0)
        stability_class = inputs.get('stability_class', 'D')
        
        times = [60, 180, 300, 600]
        max_concentrations = []
        
        for t in times:
            x_points = np.linspace(0, 3000, 100)
            y_points = np.linspace(-500, 500, 50)
            X, Y = np.meshgrid(x_points, y_points)
            conc = np.zeros_like(X)
            
            for i in range(X.shape[0]):
                for j in range(X.shape[1]):
                    conc[i, j] = self.calculate_concentration(
                        X[i, j], Y[i, j], 1.5, t,
                        release_mass, release_height,
                        wind_speed, wind_direction, stability_class
                    )
            
            max_concentrations.append(float(np.max(conc)))
        
        return {
            'release_mass': release_mass,
            'release_height': release_height,
            'max_concentrations': [round(c, 6) for c in max_concentrations],
            'times_seconds': times,
            'wind_speed': wind_speed,
            'wind_direction': wind_direction
        }
