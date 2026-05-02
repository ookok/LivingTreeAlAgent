import numpy as np
from typing import Dict, Any


class ProbitModel:
    """Probit概率模型"""
    
    def __init__(self):
        self.toxic_parameters = {
            'chlorine': {'a': -15.7, 'b': 1.52, 'n': 1.0, 'threshold': 0.5},
            'ammonia': {'a': -9.82, 'b': 0.71, 'n': 1.0, 'threshold': 25.0},
            'hydrogen_sulfide': {'a': -6.93, 'b': 0.70, 'n': 1.0, 'threshold': 0.01},
            'carbon_monoxide': {'a': -5.89, 'b': 0.52, 'n': 1.0, 'threshold': 50.0},
            'phosgene': {'a': -14.7, 'b': 1.0, 'n': 1.0, 'threshold': 0.1},
            'hydrogen_cyanide': {'a': -7.36, 'b': 0.85, 'n': 1.0, 'threshold': 10.0},
        }
    
    def _erf(self, x):
        """误差函数近似"""
        t = 1.0 / (1.0 + 0.3275911 * abs(x))
        y = 1.0 - t * np.exp(-x * x) * (1.061405429 * t - 1.453152027)
        y = y * t + 1.421413741
        y = y * t - 0.284496736
        y = y * t + 0.254829592
        return np.sign(x) * y
    
    def _norm_cdf(self, x):
        """标准正态分布累积分布函数"""
        return 0.5 * (1.0 + self._erf(x / np.sqrt(2.0)))
    
    def _norm_ppf(self, p):
        """标准正态分布分位数函数（简化版）"""
        if p <= 0.001:
            return -3.09
        elif p <= 0.023:
            return -2.0
        elif p <= 0.159:
            return -1.0
        elif p <= 0.5:
            return -np.sqrt(2) * self._erf_inv(1 - 2 * p)
        elif p <= 0.841:
            return 1.0
        elif p <= 0.977:
            return 2.0
        elif p <= 0.999:
            return 3.09
        else:
            return 5.0
    
    def _erf_inv(self, x):
        """误差函数逆（近似）"""
        if x >= 1.0:
            return 10.0
        elif x <= 0.0:
            return -10.0
        
        a = 0.147
        return np.sign(x) * np.sqrt(
            np.sqrt((2 / (np.pi * a) + np.log(1 - x * x) / 2)**2 - np.log(1 - x * x) / a) -
            (2 / (np.pi * a) + np.log(1 - x * x) / 2)
        )
    
    def calculate_probit(self, concentration: float, exposure_time: float, 
                        toxic_type: str) -> float:
        """计算Probit值"""
        params = self.toxic_parameters.get(toxic_type, self.toxic_parameters['chlorine'])
        
        C = concentration  # mg/m³
        t = exposure_time  # minutes
        
        Y = params['a'] + params['b'] * np.log(C**params['n'] * t)
        
        return Y
    
    def probit_to_probability(self, Y: float) -> float:
        """将Probit值转换为概率"""
        return self._norm_cdf((Y - 5) / np.sqrt(2))
    
    def calculate_mortality_probability(self, concentration: float, exposure_time: float,
                                       toxic_type: str) -> float:
        """计算死亡概率"""
        Y = self.calculate_probit(concentration, exposure_time, toxic_type)
        return self.probit_to_probability(Y)
    
    def calculate_impact_radius(self, release_mass: float, wind_speed: float,
                                toxic_type: str, target_probability: float = 0.5,
                                exposure_time: float = 5.0) -> float:
        """计算影响半径"""
        params = self.toxic_parameters.get(toxic_type, self.toxic_parameters['chlorine'])
        
        target_Y = self._norm_ppf(target_probability) * np.sqrt(2) + 5
        C_target = np.exp((target_Y - params['a']) / params['b']) / exposure_time
        
        radius = (release_mass / (wind_speed * C_target))**(1/3) * 20
        
        return min(radius, 5000.0)
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        toxic_type = inputs.get('toxic_type', 'chlorine')
        release_mass = inputs.get('release_mass', 1000.0)
        wind_speed = inputs.get('wind_speed', 2.0)
        exposure_time = inputs.get('exposure_time', 5.0)
        
        distances = [100, 250, 500, 1000, 2000]
        probabilities = []
        
        for distance in distances:
            C = release_mass / (wind_speed * distance**2) * 1000
            prob = self.calculate_mortality_probability(C, exposure_time, toxic_type)
            probabilities.append(round(prob * 100, 2))
        
        radii = {}
        for prob_level in [0.01, 0.10, 0.50, 0.90]:
            radius = self.calculate_impact_radius(release_mass, wind_speed, toxic_type, prob_level, exposure_time)
            radii[f'{int(prob_level * 100)}%'] = round(radius, 2)
        
        return {
            'toxic_type': toxic_type,
            'release_mass_kg': release_mass,
            'wind_speed_ms': wind_speed,
            'exposure_time_min': exposure_time,
            'mortality_probabilities': {
                'distances_m': distances,
                'probabilities_percent': probabilities
            },
            'impact_radii_m': radii
        }


class ToxicConsequence:
    """有毒物质后果计算"""
    
    def __init__(self):
        self.probit_model = ProbitModel()
    
    def calculate_consequence(self, release_mass: float, wind_speed: float,
                              wind_direction: float, toxic_type: str) -> Dict[str, Any]:
        """计算事故后果"""
        result = self.probit_model.execute({
            'toxic_type': toxic_type,
            'release_mass': release_mass,
            'wind_speed': wind_speed,
            'exposure_time': 5.0
        })
        
        return result
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        return self.calculate_consequence(
            inputs.get('release_mass', 1000.0),
            inputs.get('wind_speed', 2.0),
            inputs.get('wind_direction', 180.0),
            inputs.get('toxic_type', 'chlorine')
        )
