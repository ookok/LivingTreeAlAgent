"""
CoolProp物性计算工具 - 符合工具管理层规范
提供 execute(inputs) -> outputs 函数
"""
import sys

def execute(inputs: dict) -> dict:
    """执行物性计算"""
    try:
        import CoolProp
        
        substance = inputs.get('substance', 'water')
        temperature = inputs.get('temperature', 25)
        pressure = inputs.get('pressure', 101325)
        
        if isinstance(temperature, str):
            temperature = float(temperature)
        if isinstance(pressure, str):
            pressure = float(pressure)
        
        T = temperature + 273.15
        p = pressure
        
        props = {}
        try:
            props['density'] = CoolProp.CoolProp.PropsSI('D', 'T', T, 'P', p, substance)
            props['enthalpy'] = CoolProp.CoolProp.PropsSI('H', 'T', T, 'P', p, substance)
            props['entropy'] = CoolProp.CoolProp.PropsSI('S', 'T', T, 'P', p, substance)
            props['specific_heat'] = CoolProp.CoolProp.PropsSI('CPMASS', 'T', T, 'P', p, substance)
            props['thermal_conductivity'] = CoolProp.CoolProp.PropsSI('L', 'T', T, 'P', p, substance)
            props['viscosity'] = CoolProp.CoolProp.PropsSI('V', 'T', T, 'P', p, substance)
            props['phase'] = CoolProp.CoolProp.PropsSI('Phase', 'T', T, 'P', p, substance)
            props['critical_temperature'] = CoolProp.CoolProp.PropsSI('Tcrit', substance)
            props['critical_pressure'] = CoolProp.CoolProp.PropsSI('Pcrit', substance)
            props['molar_mass'] = CoolProp.CoolProp.PropsSI('M', substance)
            
            props['success'] = True
            props['unit_info'] = {
                'density': 'kg/m3',
                'enthalpy': 'J/kg',
                'entropy': 'J/kg/K',
                'specific_heat': 'J/kg/K',
                'thermal_conductivity': 'W/m/K',
                'viscosity': 'Pa*s',
                'temperature': 'K',
                'pressure': 'Pa'
            }
            
        except Exception as e:
            props['error'] = str(e)
            props['success'] = False
        
        return props
        
    except ImportError:
        return {'success': False, 'error': 'CoolProp not installed'}
    except Exception as e:
        return {'success': False, 'error': str(e)}

if __name__ == '__main__':
    import json
    if len(sys.argv) > 1:
        inputs = json.loads(sys.argv[1])
    else:
        inputs = {'substance': 'water', 'temperature': 25}
    result = execute(inputs)
    print(json.dumps(result, indent=2))