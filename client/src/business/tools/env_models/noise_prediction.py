import numpy as np
from typing import Dict, Any, List
from dataclasses import dataclass


@dataclass
class PointSource:
    name: str
    x: float  # m
    y: float  # m
    sound_power_level: float  # dB(A)
    frequency: float = 1000.0  # Hz


class BarrierAttenuation:
    """屏障衰减计算"""
    
    @staticmethod
    def calculate_barrier_attenuation(source_height: float, receiver_height: float,
                                      barrier_height: float, distance: float) -> float:
        """计算屏障衰减"""
        if barrier_height <= max(source_height, receiver_height):
            return 0.0
        
        # 菲涅尔数
        delta = (barrier_height - source_height) + (barrier_height - receiver_height)
        lambda_wave = 343 / 1000  # 波长 (m) at 1000 Hz
        
        N = 2 * delta * distance / (lambda_wave * (source_height + receiver_height))
        
        if N < 0:
            return 0.0
        elif N < 1:
            return 5 * N
        else:
            return 20 * np.log10(2 * N + 1) + 5
    
    @staticmethod
    def calculate_ground_attenuation(distance: float, frequency: float = 1000.0) -> float:
        """计算地面衰减"""
        if distance < 10:
            return 0.0
        
        # 简化地面衰减公式
        return min(0.01 * distance * (frequency / 1000), 10.0)


class NoiseModel:
    """工业噪声预测模型"""
    
    def calculate_point_source_attenuation(self, distance: float, reference_distance: float = 1.0) -> float:
        """点声源衰减"""
        if distance <= 0:
            return 0.0
        
        return 20 * np.log10(distance / reference_distance) + 8
    
    def calculate_line_source_attenuation(self, distance: float, source_length: float,
                                          reference_distance: float = 1.0) -> float:
        """线声源衰减"""
        if distance <= 0:
            return 0.0
        
        if distance > source_length:
            return 20 * np.log10(distance / reference_distance) + 8
        else:
            return 10 * np.log10(distance / reference_distance) + 8
    
    def calculate_octave_band_attenuation(self, distance: float, frequency: float) -> float:
        """倍频带衰减"""
        if distance <= 0:
            return 0.0
        
        # 考虑空气吸收
        absorption_coeff = {
            125: 0.01, 250: 0.01, 500: 0.02,
            1000: 0.04, 2000: 0.10, 4000: 0.22,
            8000: 0.50
        }
        
        alpha = absorption_coeff.get(int(frequency), 0.04)
        air_absorption = alpha * distance / 100
        
        return self.calculate_point_source_attenuation(distance) + air_absorption
    
    def calculate_combined_level(self, levels: List[float]) -> float:
        """计算多个声源的合成声级"""
        if not levels:
            return 0.0
        
        sum_powers = sum(10**(L / 10) for L in levels)
        return 10 * np.log10(sum_powers)
    
    def calculate_room_reverberation(self, volume: float, surface_area: float,
                                     absorption_coefficient: float) -> float:
        """计算混响时间"""
        if surface_area <= 0 or absorption_coefficient <= 0:
            return 0.0
        
        return 0.161 * volume / (surface_area * absorption_coefficient)
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        sources = inputs.get('sources', [
            {'name': '泵', 'x': 0, 'y': 0, 'sound_power_level': 95},
            {'name': '风机', 'x': 10, 'y': 0, 'sound_power_level': 100}
        ])
        
        receiver_x = inputs.get('receiver_x', 50.0)
        receiver_y = inputs.get('receiver_y', 0.0)
        
        barrier_height = inputs.get('barrier_height', 0.0)
        source_height = inputs.get('source_height', 1.5)
        receiver_height = inputs.get('receiver_height', 1.5)
        
        total_levels = []
        
        for source in sources:
            dx = receiver_x - source['x']
            dy = receiver_y - source['y']
            distance = np.sqrt(dx**2 + dy**2)
            
            if distance < 1.0:
                distance = 1.0
            
            attenuation = self.calculate_point_source_attenuation(distance)
            
            if barrier_height > 0:
                barrier_atten = BarrierAttenuation.calculate_barrier_attenuation(
                    source_height, receiver_height, barrier_height, distance
                )
                attenuation += barrier_atten
            
            ground_atten = BarrierAttenuation.calculate_ground_attenuation(distance)
            attenuation += ground_atten
            
            received_level = source['sound_power_level'] - attenuation
            total_levels.append(received_level)
        
        combined_level = self.calculate_combined_level(total_levels)
        
        return {
            'sources': sources,
            'receiver_position': {'x': receiver_x, 'y': receiver_y},
            'individual_levels_dba': [round(L, 1) for L in total_levels],
            'combined_level_dba': round(combined_level, 1),
            'barrier_attenuation_db': round(barrier_atten if barrier_height > 0 else 0, 1),
            'ground_attenuation_db': round(ground_atten, 1)
        }
