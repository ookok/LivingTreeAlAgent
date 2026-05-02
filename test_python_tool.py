import sys
sys.path.insert(0, "client/src")

# 测试导入gaussian_plume模块
try:
    from business.tools import gaussian_plume
    print('导入成功')
    
    # 测试execute函数
    result = gaussian_plume.execute({
        'emission_rate': 0.1,
        'stack_height': 20.0,
        'wind_speed': 3.0,
        'wind_direction': 180.0,
        'stability_class': 'D'
    })
    print('执行成功:', result)
except Exception as e:
    print('错误:', e)
    import traceback
    traceback.print_exc()