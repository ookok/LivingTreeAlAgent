import numpy as np
from typing import Dict, Any


class ThermalRadiationModel:
    """热辐射模型"""
    
    def calculate_point_source_radiation(self, Q: float, R: float, 
                                         emissivity: float = 0.9) -> float:
        """计算点源热辐射强度"""
        if R <= 0:
            return 0.0
        
        # 斯蒂芬-玻尔兹曼定律
        sigma = 5.67e-8  # W/m²·K⁴
        T_flame = 1200.0  # K
        
        # 简化计算：I = Q / (4πR²) * τ
        tau = 0.7  # 大气透射率
        I = (Q * tau) / (4 * np.pi * R**2)
        
        return max(I, 0.0)
    
    def calculate_pool_fire_radiation(self, pool_diameter: float, heat_release_rate: float,
                                      distance: float) -> float:
        """计算池火热辐射"""
        if distance <= 0:
            return 0.0
        
        # 池火半径
        r_pool = pool_diameter / 2
        
        # 视角因子
        F = r_pool**2 / (r_pool**2 + distance**2)
        
        # 热辐射强度
        tau = 0.7
        I = (heat_release_rate * tau * F) / (4 * np.pi * distance**2)
        
        return max(I, 0.0)
    
    def calculate_jet_fire_radiation(self, exit_diameter: float, exit_velocity: float,
                                      distance: float) -> float:
        """计算喷射火热辐射"""
        if distance <= 0:
            return 0.0
        
        # 估算火焰长度
        flame_length = 10 * exit_diameter * (exit_velocity / 10)**0.5
        
        # 简化计算
        Q = 1e6 * exit_diameter**2 * exit_velocity
        
        tau = 0.65
        I = (Q * tau) / (4 * np.pi * distance**2)
        
        return max(I, 0.0)
    
    def get_damage_criteria(self, radiation_intensity: float) -> str:
        """判断热辐射伤害等级"""
        if radiation_intensity >= 12.5:
            return '严重烧伤（10秒内）'
        elif radiation_intensity >= 4.0:
            return '二级烧伤（20秒内）'
        elif radiation_intensity >= 1.6:
            return '一级烧伤（60秒内）'
        elif radiation_intensity >= 0.5:
            return '皮肤感觉不适'
        else:
            return '无明显影响'
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        fire_type = inputs.get('fire_type', 'pool')
        distance = inputs.get('distance', 50.0)
        
        if fire_type == 'pool':
            pool_diameter = inputs.get('pool_diameter', 10.0)
            heat_release_rate = inputs.get('heat_release_rate', 10e6)
            I = self.calculate_pool_fire_radiation(pool_diameter, heat_release_rate, distance)
        
        elif fire_type == 'jet':
            exit_diameter = inputs.get('exit_diameter', 0.1)
            exit_velocity = inputs.get('exit_velocity', 50.0)
            I = self.calculate_jet_fire_radiation(exit_diameter, exit_velocity, distance)
        
        else:
            Q = inputs.get('heat_release_rate', 10e6)
            I = self.calculate_point_source_radiation(Q, distance)
        
        damage = self.get_damage_criteria(I)
        
        # 计算不同距离的辐射强度
        distances = [10, 25, 50, 100, 200]
        intensities = []
        for d in distances:
            if fire_type == 'pool':
                I_d = self.calculate_pool_fire_radiation(pool_diameter, heat_release_rate, d)
            elif fire_type == 'jet':
                I_d = self.calculate_jet_fire_radiation(exit_diameter, exit_velocity, d)
            else:
                I_d = self.calculate_point_source_radiation(Q, d)
            intensities.append(round(I_d, 2))
        
        return {
            'fire_type': fire_type,
            'target_distance_m': distance,
            'radiation_intensity_kw_m2': round(I / 1000, 3),
            'damage_criteria': damage,
            'radiation_at_distances': {
                'distances_m': distances,
                'intensities_kw_m2': [round(i / 1000, 3) for i in intensities]
            }
        }


class OverpressureModel:
    """爆炸超压模型"""
    
    def calculate_TNT_equivalent(self, mass: float, heat_of_combustion: float = 45e6) -> float:
        """计算TNT当量"""
        # 典型值：TNT热值 4.6e6 J/kg
        return mass * heat_of_combustion / 4.6e6
    
    def calculate_overpressure_TNT(self, W_TNT: float, R: float) -> float:
        """TNT当量法计算超压"""
        if R <= 0 or W_TNT <= 0:
            return 0.0
        
        # 比例距离
        Z = R / W_TNT**(1/3)
        
        # 经验公式
        if Z < 1.0:
            P = 1.0 / Z**3
        elif Z < 10:
            P = 0.9 / Z**1.5
        elif Z < 100:
            P = 0.04 / Z
        else:
            P = 0.001
        
        return P * 101325  # Pa
    
    def calculate_overpressure_TNO(self, W: float, R: float, 
                                   explosion_type: str = 'vce') -> float:
        """TNO多能法计算超压"""
        if R <= 0 or W <= 0:
            return 0.0
        
        Z = R / W**(1/3)
        
        # 蒸气云爆炸系数
        K = 1.0 if explosion_type == 'vce' else 0.5
        
        P = K * 0.1 / Z**1.5
        
        return P * 101325
    
    def get_overpressure_damage(self, overpressure: float) -> str:
        """判断超压伤害等级"""
        P_kPa = overpressure / 1000
        
        if P_kPa >= 200:
            return '建筑物完全摧毁'
        elif P_kPa >= 100:
            return '建筑物严重破坏'
        elif P_kPa >= 50:
            return '建筑物中等破坏'
        elif P_kPa >= 30:
            return '窗户玻璃破碎'
        elif P_kPa >= 15:
            return '轻微损坏'
        else:
            return '无明显影响'
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        mass = inputs.get('mass', 1000.0)
        distance = inputs.get('distance', 100.0)
        method = inputs.get('method', 'TNT')
        
        W_TNT = self.calculate_TNT_equivalent(mass)
        
        if method == 'TNT':
            P = self.calculate_overpressure_TNT(W_TNT, distance)
        else:
            P = self.calculate_overpressure_TNO(mass, distance)
        
        damage = self.get_overpressure_damage(P)
        
        distances = [50, 100, 200, 500, 1000]
        pressures = []
        for d in distances:
            if method == 'TNT':
                P_d = self.calculate_overpressure_TNT(W_TNT, d)
            else:
                P_d = self.calculate_overpressure_TNO(mass, d)
            pressures.append(round(P_d / 1000, 2))
        
        return {
            'mass_kg': mass,
            'TNT_equivalent_kg': round(W_TNT, 2),
            'target_distance_m': distance,
            'overpressure_kPa': round(P / 1000, 2),
            'damage_criteria': damage,
            'overpressure_at_distances': {
                'distances_m': distances,
                'pressures_kPa': pressures
            },
            'method': method
        }
