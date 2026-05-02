import numpy as np
from typing import Dict, Any


class SLABModel:
    """简化版SLAB重质气体扩散模型"""
    
    def __init__(self):
        pass
    
    def calculate_density(self, temperature: float, molecular_weight: float) -> float:
        """计算气体密度 (kg/m³)"""
        R = 8.314  # J/(mol·K)
        return (molecular_weight * 1e-3 * 101325) / (R * temperature)
    
    def calculate_spreading(self, release_rate: float, source_density: float, 
                           ambient_density: float, wind_speed: float) -> float:
        """计算横向扩散速度"""
        g = 9.81
        delta_rho = source_density - ambient_density
        
        if delta_rho <= 0:
            return wind_speed * 0.1
        
        buoyancy_flux = g * release_rate * delta_rho / ambient_density
        return (buoyancy_flux / wind_speed)**(1/3)
    
    def calculate_concentration(self, x: float, y: float, release_rate: float, 
                               wind_speed: float, stability_class: str) -> float:
        """计算浓度"""
        if x <= 0:
            return 0.0
        
        sigma_y = {
            'A': 0.15, 'B': 0.12, 'C': 0.10,
            'D': 0.08, 'E': 0.06, 'F': 0.04
        }.get(stability_class, 0.08)
        
        sigma_z = sigma_y.get(stability_class, 0.08) * 0.5
        
        C = (release_rate * 1e6) / (2 * np.pi * wind_speed * sigma_y * sigma_z * x) * \
            np.exp(-y**2 / (2 * (sigma_y * x)**2))
        
        return max(C, 0.0)
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        release_rate = inputs.get('release_rate', 1.0)
        temperature = inputs.get('temperature', 283.0)
        molecular_weight = inputs.get('molecular_weight', 71.0)  # Cl2
        ambient_temp = inputs.get('ambient_temp', 293.0)
        ambient_pressure = inputs.get('ambient_pressure', 101325.0)
        wind_speed = inputs.get('wind_speed', 2.0)
        stability_class = inputs.get('stability_class', 'D')
        
        source_density = self.calculate_density(temperature, molecular_weight)
        ambient_density = self.calculate_density(ambient_temp, 29.0)
        
        distances = [100, 500, 1000, 2000]
        concentrations = []
        
        for x in distances:
            C = self.calculate_concentration(x, 0, release_rate, wind_speed, stability_class)
            concentrations.append(round(C, 6))
        
        return {
            'source_density': round(source_density, 3),
            'ambient_density': round(ambient_density, 3),
            'is_heavy_gas': source_density > ambient_density,
            'distances_m': distances,
            'concentrations_mg_m3': concentrations,
            'release_rate': release_rate,
            'wind_speed': wind_speed
        }


class HeavyGasDispersion:
    """重质气体扩散计算"""
    
    def calculate_impact_radius(self, release_mass: float, molecular_weight: float,
                                wind_speed: float, threshold_concentration: float) -> float:
        """计算影响半径"""
        if wind_speed <= 0.1:
            return 0.0
        
        # 简化公式：基于质量和风速的经验公式
        radius = (release_mass / (wind_speed * threshold_concentration))**(1/3) * 10
        
        return min(radius, 5000.0)
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        release_mass = inputs.get('release_mass', 1000.0)
        molecular_weight = inputs.get('molecular_weight', 71.0)
        wind_speed = inputs.get('wind_speed', 2.0)
        
        thresholds = {
            'TLV': 0.5,      # 阈限值 (mg/m³)
            'IDLH': 300.0,    # 立即危及生命健康值
            'LC50': 1500.0    # 半数致死浓度
        }
        
        radii = {}
        for name, threshold in thresholds.items():
            radii[name] = round(self.calculate_impact_radius(
                release_mass, molecular_weight, wind_speed, threshold
            ), 2)
        
        return {
            'release_mass': release_mass,
            'molecular_weight': molecular_weight,
            'wind_speed': wind_speed,
            'impact_radii_m': radii,
            'thresholds_mg_m3': thresholds
        }
