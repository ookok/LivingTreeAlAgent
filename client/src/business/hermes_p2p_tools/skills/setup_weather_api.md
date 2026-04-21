# Skill: 天气API配置引导

> 当用户首次配置天气API或遇到相关问题时触发此引导

## 触发条件
- 用户点击"高级天气预测"功能
- 用户说"配置天气API"
- 系统检测到缺失 OpenWeatherMap API Key

## 引导流程

### 步骤1：检测当前状态
```python
# 调用工具检查配置
p2p_check_config(feature="weather_api")
```

### 步骤2：判断路径
- 如果已有Key → 验证Key有效性
- 如果无Key → 进入注册流程

### 步骤3A：验证已有Key
```
工具: p2p_validate_config(config_type="api_key", value="用户提供的Key")
```

### 步骤3B：注册新Key（最短路径）
1. 打开浏览器: https://openweathermap.org/api
2. 点击"Sign Up"注册（如已登录则跳过）
3. 复制API Key
4. 系统自动检测剪贴板
5. 自动填入配置

### 步骤4：验证配置
```
工具: p2p_check_key_health(provider="openweather")
```

## 预期结果
- 天气API配置完成
- 功能可用性提升到PRO级别

## 成功标准
- `p2p_check_config` 返回 `is_complete: true`
- 天气查询返回有效数据

## 失败处理
- 如果注册失败 → 提供备用方案（Open-Meteo）
- 如果Key无效 → 引导重新获取

## 进化记录
当此引导成功执行后，将经验追加到记忆：
> "用户通过OpenWeatherMap官网注册了API Key，复制粘贴方式比手动输入更高效"
