"""
零配置入口 - Zero Config Entry Point

一行命令启动完整的 P2P 分布式网络：

```bash
# 启动节点（零配置）
python -m core.relay_chain.event_ext.p2p_network.zero_config

# 指定节点ID
python -m core.relay_chain.event_ext.p2p_network.zero_config --node-id node-001

# 指定能力
python -m core.relay_chain.event_ext.p2p_network.zero_config --capabilities gpu,cpu
```

或者在代码中使用：

```python
from core.relay_chain.event_ext.p2p_network.zero_config import start_node

# 一行启动
node = start_node()
```

Web 界面：

```bash
python -m core.relay_chain.event_ext.p2p_network.zero_config --web
```
"""

import argparse
import logging
import sys
import time
import json
from typing import Optional

# 设置日志
logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)

logger = logging.getLogger(__name__)


def create_node(
    node_id: str = None,
    port: int = 0,
    capabilities: list = None,
    task_executor: callable = None,
) :
    """
    创建分布式节点

    Args:
        node_id: 节点ID
        port: TCP 端口
        capabilities: 节点能力列表
        task_executor: 任务执行函数

    Returns:
        DistributedNode 实例
    """
    from .distributed_node import DistributedNode

    # 创建节点
    node = DistributedNode(
        node_id=node_id,
        port=port,
        capabilities=capabilities,
    )

    # 设置任务执行器
    if task_executor:
        node.set_task_executor(task_executor)
    else:
        # 默认执行器
        node.set_task_executor(default_task_executor)

    return node


def start_node(
    node_id: str = None,
    port: int = 0,
    capabilities: list = None,
    task_executor: callable = None,
    block: bool = True,
) :
    """
    启动分布式节点（一行启动）

    Args:
        node_id: 节点ID
        port: TCP 端口
        capabilities: 节点能力列表
        task_executor: 任务执行函数
        block: 是否阻塞主线程

    Returns:
        DistributedNode 实例

    Example:
        ```python
        from core.relay_chain.event_ext.p2p_network.zero_config import start_node

        # 最简启动
        node = start_node()

        # 指定配置
        node = start_node(
            node_id="worker-001",
            capabilities=["gpu", "cpu"],
        )
        ```
    """
    node = create_node(
        node_id=node_id,
        port=port,
        capabilities=capabilities,
        task_executor=task_executor,
    )

    # 启动
    node.start()

    logger.info("=" * 60)
    logger.info("🎉 分布式节点已启动!")
    logger.info(f"   节点ID: {node.node_id}")
    logger.info(f"   能力: {capabilities or '无'}")
    logger.info(f"   模式: 零配置自发现")
    logger.info("=" * 60)

    if block:
        try:
            while True:
                time.sleep(10)
                _print_status(node)
        except KeyboardInterrupt:
            logger.info("\n正在停止节点...")
            node.stop()

    return node


def _print_status(node):
    """打印状态"""
    try:
        status = node.get_status()
        print("\n" + "=" * 60)
        print(f"节点状态: {status['node_id']}")
        print(f"  角色: {status['role']}")
        print(f"  协调者: {status['coordinator'] or '无'}")
        print(f"  连接数: {status['connections']}")
        print(f"  待分发任务: {status['task_distributor']['pending']}")
        print(f"  运行中任务: {status['task_distributor']['running']}")
        print("=" * 60)
    except:
        pass


def default_task_executor(task) -> dict:
    """
    默认任务执行器

    Args:
        task: Task 对象

    Returns:
        执行结果
    """
    import random

    logger.info(f"[执行器] 处理任务: {task.task_id}, 类型: {task.task_type}")

    # 模拟处理
    time.sleep(random.uniform(0.5, 2.0))

    return {
        "status": "completed",
        "task_id": task.task_id,
        "task_type": task.task_type,
        "result": f"处理完成: {task.task_data}",
        "executed_by": "default-executor",
    }


class SimpleTaskExecutor:
    """
    简单任务执行器

    支持：
    1. 计算任务
    2. 数据处理任务
    3. 自定义任务
    """

    @staticmethod
    def execute(task) -> dict:
        """执行任务"""
        task_type = task.task_type
        task_data = task.task_data

        if task_type == "compute":
            return SimpleTaskExecutor._compute(task_data)
        elif task_type == "data_process":
            return SimpleTaskExecutor._data_process(task_data)
        elif task_type == "custom":
            return SimpleTaskExecutor._custom(task_data)
        else:
            return {
                "status": "completed",
                "task_id": task.task_id,
                "result": f"未知任务类型: {task_type}",
            }

    @staticmethod
    def _compute(data: dict) -> dict:
        """计算任务"""
        a = data.get("a", 0)
        b = data.get("b", 0)
        operation = data.get("operation", "add")

        if operation == "add":
            result = a + b
        elif operation == "sub":
            result = a - b
        elif operation == "mul":
            result = a * b
        elif operation == "div":
            result = a / b if b != 0 else 0
        else:
            result = 0

        return {
            "status": "completed",
            "operation": operation,
            "a": a,
            "b": b,
            "result": result,
        }

    @staticmethod
    def _data_process(data: dict) -> dict:
        """数据处理任务"""
        records = data.get("records", [])
        operation = data.get("operation", "count")

        if operation == "count":
            result = len(records)
        elif operation == "sum":
            result = sum(records)
        elif operation == "avg":
            result = sum(records) / len(records) if records else 0
        else:
            result = records

        return {
            "status": "completed",
            "operation": operation,
            "input_count": len(records),
            "result": result,
        }

    @staticmethod
    def _custom(data: dict) -> dict:
        """自定义任务"""
        return {
            "status": "completed",
            "data": data,
            "message": "自定义任务处理完成",
        }


def run_web_dashboard(node=None, port=8080):
    """
    运行 Web 监控面板

    Args:
        node: 分布式节点，不指定则创建新节点
        port: Web 服务端口
    """
    try:
        from flask import Flask, jsonify, render_template
        import threading

        app = Flask(__name__)

        if node is None:
            node = create_node()

        @app.route("/")
        def index():
            return render_template("dashboard.html")

        @app.route("/api/status")
        def api_status():
            return jsonify(node.get_status())

        @app.route("/api/peers")
        def api_peers():
            return jsonify(node.get_peers())

        @app.route("/api/tasks")
        def api_tasks():
            return jsonify({
                "pending": node.task_distributor.get_pending_tasks(),
                "running": node.task_distributor.get_running_tasks(),
            })

        @app.route("/api/submit_task", methods=["POST"])
        def api_submit_task():
            from flask import request
            data = request.json

            task_id = node.submit_task(
                task_type=data.get("task_type", "compute"),
                task_data=data.get("task_data", {}),
                requirements=data.get("requirements"),
                priority=data.get("priority", 5),
            )

            return jsonify({"task_id": task_id})

        # 启动节点
        node.start()

        # 启动 Web 服务
        logger.info(f"🌐 Web 监控面板启动: http://localhost:{port}")
        app.run(host="0.0.0.0", port=port, debug=False, threaded=True)

    except ImportError:
        logger.error("需要 Flask: pip install flask")
        sys.exit(1)


def main():
    """命令行入口"""
    parser = argparse.ArgumentParser(
        description="零配置 P2P 分布式节点",
        formatter_class=argparse.RawDescriptionHelpFormatter,
        epilog="""
示例:
  # 零配置启动
  python zero_config.py

  # 指定节点ID和能力
  python zero_config.py --node-id worker-001 --capabilities gpu,cpu

  # 启动 Web 监控面板
  python zero_config.py --web

  # 不阻塞（后台运行）
  python zero_config.py --daemon
        """
    )

    parser.add_argument(
        "--node-id",
        type=str,
        default=None,
        help="节点ID（不指定则自动生成）"
    )
    parser.add_argument(
        "--port",
        type=int,
        default=0,
        help="TCP 端口（0 表示自动选择）"
    )
    parser.add_argument(
        "--capabilities",
        type=str,
        default="",
        help="节点能力，逗号分隔（如 gpu,cpu）"
    )
    parser.add_argument(
        "--web",
        action="store_true",
        help="启动 Web 监控面板"
    )
    parser.add_argument(
        "--web-port",
        type=int,
        default=8080,
        help="Web 服务端口"
    )
    parser.add_argument(
        "--daemon",
        action="store_true",
        help="后台运行"
    )
    parser.add_argument(
        "--verbose",
        action="store_true",
        help="详细输出"
    )

    args = parser.parse_args()

    # 设置日志级别
    if args.verbose:
        logging.getLogger().setLevel(logging.DEBUG)

    # 解析能力
    capabilities = None
    if args.capabilities:
        capabilities = [c.strip() for c in args.capabilities.split(",")]

    # 创建节点
    node = create_node(
        node_id=args.node_id,
        port=args.port,
        capabilities=capabilities,
        task_executor=SimpleTaskExecutor.execute,
    )

    if args.web:
        # Web 模式
        run_web_dashboard(node, args.web_port)
    else:
        # 控制台模式
        if args.daemon:
            import threading
            thread = threading.Thread(target=node.start, daemon=True)
            thread.start()
            logger.info(f"节点在后台运行: {node.node_id}")
            try:
                while True:
                    time.sleep(10)
                    _print_status(node)
            except KeyboardInterrupt:
                pass
        else:
            start_node(block=True)


if __name__ == "__main__":
    main()
