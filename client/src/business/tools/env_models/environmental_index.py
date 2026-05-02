import numpy as np
from typing import Dict, Any, List


class NemerowIndex:
    """内梅罗污染指数"""
    
    def calculate_single_factor(self, concentration: float, standard: float) -> float:
        """计算单因子污染指数"""
        if standard <= 0:
            return 0.0
        return concentration / standard
    
    def calculate_nemerow(self, concentrations: List[float], standards: List[float]) -> float:
        """计算内梅罗综合指数"""
        if len(concentrations) != len(standards):
            return 0.0
        
        factors = [self.calculate_single_factor(c, s) for c, s in zip(concentrations, standards)]
        
        if not factors:
            return 0.0
        
        avg_factor = np.mean(factors)
        max_factor = np.max(factors)
        
        return np.sqrt((avg_factor**2 + max_factor**2) / 2)
    
    def get_quality_level(self, index: float) -> str:
        """判断污染等级"""
        if index < 0.7:
            return '清洁'
        elif index < 1.0:
            return '尚清洁'
        elif index < 2.0:
            return '轻度污染'
        elif index < 3.0:
            return '中度污染'
        else:
            return '重度污染'
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        pollutants = inputs.get('pollutants', [
            {'name': 'COD', 'concentration': 25.0, 'standard': 30.0},
            {'name': 'NH3-N', 'concentration': 1.5, 'standard': 1.5},
            {'name': 'TP', 'concentration': 0.3, 'standard': 0.2},
            {'name': 'TN', 'concentration': 15.0, 'standard': 15.0}
        ])
        
        concentrations = [p['concentration'] for p in pollutants]
        standards = [p['standard'] for p in pollutants]
        
        single_factors = []
        for p in pollutants:
            factor = self.calculate_single_factor(p['concentration'], p['standard'])
            single_factors.append({
                'pollutant': p['name'],
                'factor': round(factor, 3),
                'concentration': p['concentration'],
                'standard': p['standard']
            })
        
        nemerow_index = self.calculate_nemerow(concentrations, standards)
        quality_level = self.get_quality_level(nemerow_index)
        
        return {
            'pollutants': single_factors,
            'nemerow_index': round(nemerow_index, 3),
            'quality_level': quality_level,
            'evaluation': f'内梅罗指数为{round(nemerow_index, 3)}，水质{quality_level}'
        }


class WaterQualityIndex:
    """水质综合指数"""
    
    def __init__(self):
        self.weights = {
            'pH': 0.10,
            'DO': 0.15,
            'COD': 0.15,
            'BOD5': 0.15,
            'NH3-N': 0.15,
            'TP': 0.10,
            'TN': 0.10,
            'SS': 0.10
        }
    
    def calculate_factor(self, concentration: float, standard: float, param: str) -> float:
        """计算单个指标的评分"""
        if standard <= 0:
            return 0.0
        
        ratio = concentration / standard
        
        if param == 'DO':
            # DO是越大越好
            if ratio <= 1.0:
                return 100 - 20 * ratio
            else:
                return 100 - 20 * ratio
        
        if param == 'pH':
            # pH需要特殊处理
            if 6.0 <= concentration <= 9.0:
                return 100 - 10 * abs(concentration - 7.5)
            else:
                return 0.0
        
        # 其他指标：越小越好
        if ratio <= 0.5:
            return 100
        elif ratio <= 1.0:
            return 100 - 20 * (ratio - 0.5) / 0.5
        elif ratio <= 2.0:
            return 60 - 40 * (ratio - 1.0)
        else:
            return 0.0
    
    def calculate_wqi(self, parameters: Dict[str, float], standards: Dict[str, float]) -> float:
        """计算水质综合指数"""
        total_score = 0.0
        total_weight = 0.0
        
        for param, weight in self.weights.items():
            if param in parameters and param in standards:
                score = self.calculate_factor(parameters[param], standards[param], param)
                total_score += score * weight
                total_weight += weight
        
        if total_weight == 0:
            return 0.0
        
        return total_score / total_weight
    
    def get_water_grade(self, wqi: float) -> str:
        """判断水质等级"""
        if wqi >= 90:
            return 'Ⅰ类'
        elif wqi >= 80:
            return 'Ⅱ类'
        elif wqi >= 70:
            return 'Ⅲ类'
        elif wqi >= 60:
            return 'Ⅳ类'
        elif wqi >= 50:
            return 'Ⅴ类'
        else:
            return '劣Ⅴ类'
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        parameters = inputs.get('parameters', {
            'pH': 7.5,
            'DO': 7.5,
            'COD': 20.0,
            'BOD5': 4.0,
            'NH3-N': 0.5,
            'TP': 0.1,
            'TN': 1.0,
            'SS': 20.0
        })
        
        standards = inputs.get('standards', {
            'pH': 7.0,
            'DO': 5.0,
            'COD': 20.0,
            'BOD5': 4.0,
            'NH3-N': 0.5,
            'TP': 0.2,
            'TN': 1.5,
            'SS': 30.0
        })
        
        individual_scores = []
        for param in self.weights.keys():
            if param in parameters and param in standards:
                score = self.calculate_factor(parameters[param], standards[param], param)
                individual_scores.append({
                    'parameter': param,
                    'concentration': parameters[param],
                    'standard': standards[param],
                    'score': round(score, 1),
                    'weight': self.weights[param]
                })
        
        wqi = self.calculate_wqi(parameters, standards)
        grade = self.get_water_grade(wqi)
        
        return {
            'individual_scores': individual_scores,
            'water_quality_index': round(wqi, 1),
            'water_grade': grade,
            'evaluation': f'水质综合指数为{round(wqi, 1)}，水质等级为{grade}'
        }


class NDVI:
    """归一化植被指数"""
    
    def calculate_ndvi(self, nir_reflectance: float, red_reflectance: float) -> float:
        """计算NDVI"""
        denominator = nir_reflectance + red_reflectance
        if denominator == 0:
            return 0.0
        return (nir_reflectance - red_reflectance) / denominator
    
    def get_vegetation_status(self, ndvi: float) -> str:
        """判断植被状态"""
        if ndvi < -0.1:
            return '水体/裸地'
        elif ndvi < 0.1:
            return '稀疏植被/裸土'
        elif ndvi < 0.25:
            return '低植被覆盖'
        elif ndvi < 0.4:
            return '中等植被覆盖'
        elif ndvi < 0.6:
            return '高植被覆盖'
        else:
            return '极高植被覆盖'
    
    def execute(self, inputs: Dict[str, Any]) -> Dict[str, Any]:
        """执行计算"""
        nir = inputs.get('nir_reflectance', 0.7)
        red = inputs.get('red_reflectance', 0.3)
        
        ndvi_value = self.calculate_ndvi(nir, red)
        status = self.get_vegetation_status(ndvi_value)
        
        return {
            'nir_reflectance': nir,
            'red_reflectance': red,
            'ndvi': round(ndvi_value, 4),
            'vegetation_status': status,
            'interpretation': {
                '-1.0 ~ -0.1': '水体、裸地、冰雪',
                '-0.1 ~ 0.1': '稀疏植被、裸土',
                '0.1 ~ 0.25': '草地、灌丛',
                '0.25 ~ 0.4': '农田、林地',
                '0.4 ~ 0.6': '茂密森林',
                '0.6 ~ 1.0': '高生物量植被'
            }
        }
