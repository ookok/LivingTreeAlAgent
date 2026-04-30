"""
pytest 配置文件 - UI 自动化测试

提供：
- Mock 配置
- 测试夹具 (fixtures)
- 并行执行支持
"""

import sys
import os
import pytest
from unittest.mock import patch, MagicMock

# 添加项目路径
sys.path.insert(0, os.path.join(os.path.dirname(__file__), '..', '..', 'src'))


@pytest.fixture(scope="session")
def mock_network():
    """Mock 网络请求"""
    with patch('requests.get') as mock_get, \
         patch('requests.post') as mock_post, \
         patch('urllib.request.urlopen') as mock_urlopen:
        
        # 设置默认返回值
        mock_response = MagicMock()
        mock_response.status_code = 200
        mock_response.json.return_value = {"result": "success"}
        mock_response.text = "OK"
        
        mock_get.return_value = mock_response
        mock_post.return_value = mock_response
        mock_urlopen.return_value.__enter__.return_value.read.return_value = b'{"result": "success"}'
        
        yield {
            'get': mock_get,
            'post': mock_post,
            'urlopen': mock_urlopen
        }


@pytest.fixture(scope="session")
def mock_database():
    """Mock 数据库连接"""
    with patch('client.src.infrastructure.database.connect') as mock_connect:
        mock_db = MagicMock()
        mock_connect.return_value = mock_db
        
        yield mock_db


@pytest.fixture(scope="session")
def mock_ollama():
    """Mock Ollama 服务"""
    with patch('ollama.list') as mock_list, \
         patch('ollama.chat') as mock_chat, \
         patch('ollama.generate') as mock_generate:
        
        # 设置默认返回值
        mock_list.return_value = {
            "models": [
                {"name": "qwen3.6:latest", "size": 8000000000}
            ]
        }
        
        mock_chat.return_value = {
            "message": {"role": "assistant", "content": "这是测试响应"}
        }
        
        mock_generate.return_value = {
            "response": "这是测试生成结果"
        }
        
        yield {
            'list': mock_list,
            'chat': mock_chat,
            'generate': mock_generate
        }


@pytest.fixture(scope="session")
def mock_chroma():
    """Mock Chroma DB"""
    with patch('chromadb.Client') as mock_client:
        mock_db = MagicMock()
        mock_collection = MagicMock()
        
        mock_client.return_value = mock_db
        mock_db.get_or_create_collection.return_value = mock_collection
        mock_collection.add.return_value = None
        mock_collection.query.return_value = {
            "ids": ["test-id"],
            "documents": ["test document"],
            "distances": [0.1]
        }
        
        yield {
            'client': mock_client,
            'collection': mock_collection
        }


@pytest.fixture(scope="session")
def app_instance():
    """获取或创建 QApplication 实例"""
    from PyQt6.QtWidgets import QApplication
    
    app = QApplication.instance()
    if app is None:
        app = QApplication(sys.argv)
    
    yield app
    
    # 清理
    app.quit()


@pytest.fixture(scope="session")
def main_window(app_instance):
    """获取主窗口"""
    from page_objects import PageFactory
    from PyQt6.QtWidgets import QMainWindow
    import time
    
    # 等待主窗口出现
    start = time.time()
    main_window = None
    
    while time.time() - start < 30:
        main_window = PageFactory.get_main_window()
        if main_window.widget:
            break
        time.sleep(1)
    
    return main_window


@pytest.fixture(scope="function")
def sidebar(main_window):
    """获取侧边栏"""
    from page_objects import PageFactory
    return PageFactory.get_sidebar(main_window.widget if main_window else None)


@pytest.fixture(scope="function")
def chat_panel(main_window):
    """获取聊天面板"""
    from page_objects import PageFactory
    return PageFactory.get_chat_panel(main_window.widget if main_window else None)


# 并行执行配置
def pytest_configure(config):
    """配置 pytest"""
    # 添加自定义标记
    config.addinivalue_line("markers", "ui: UI 测试")
    config.addinivalue_line("markers", "integration: 集成测试")
    config.addinivalue_line("markers", "slow: 慢速测试")


def pytest_collection_modifyitems(items):
    """修改测试项"""
    for item in items:
        # 标记所有 UI 测试
        if "ui" in item.nodeid.lower():
            item.add_marker(pytest.mark.ui)