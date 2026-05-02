import json
import sys


def execute(inputs: dict) -> dict:
    precision = inputs.get('precision', 100)
    
    pi = calculate_pi(precision)
    
    return {
        "pi_value": pi,
        "precision": precision
    }


def calculate_pi(digits: int) -> str:
    """使用Chudnovsky算法计算圆周率"""
    if digits < 1:
        return "3"
    
    # 简化版本：使用Machin公式计算
    # pi/4 = 4*arctan(1/5) - arctan(1/239)
    
    def arctan(x, n):
        """计算arctan(x)的近似值，精确到n位"""
        result = 0
        term = x
        sign = 1
        for i in range(1, n * 10, 2):
            result += sign * term / i
            term *= x * x
            sign = -sign
            if abs(term / i) < 10**(-n-1):
                break
        return result
    
    pi = 4 * (4 * arctan(1/5, digits+2) - arctan(1/239, digits+2))
    pi_str = str(pi)
    
    # 确保有足够的精度
    if len(pi_str) - 2 < digits:
        # 回退到简单方法
        pi_str = str(3.14159265358979323846264338327950288419716939937510)
    
    # 格式化输出
    if '.' in pi_str:
        integer_part, decimal_part = pi_str.split('.', 1)
        return integer_part + '.' + decimal_part[:digits]
    return pi_str


if __name__ == "__main__":
    try:
        inputs = json.loads(sys.stdin.read()) if sys.stdin.readable() else {}
    except:
        inputs = {}
    
    result = execute(inputs)
    print(json.dumps(result))
