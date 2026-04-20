"""
启动主界面并分析错误日志
=========================
用于测试和诊断系统启动问题
"""

import sys
import os
from pathlib import Path

# 添加项目根目录到路径
project_root = Path(__file__).parent
sys.path.insert(0, str(project_root))


def setup_logging():
    """配置日志系统"""
    from core.error_logger import setup_error_logger, log_startup, get_logger
    
    logger = setup_error_logger()
    log_startup(logger)
    
    return logger


def run_client():
    """运行客户端"""
    import logging
    from core.error_logger import get_logger, log_shutdown, get_log_summary
    
    logger = get_logger("main")
    
    try:
        logger.info("开始加载配置...")
        
        from core.config import load_config
        config = load_config()
        logger.info(f"配置加载成功: {config.ollama.base_url}")
        
        logger.info("初始化主窗口...")
        
        from PyQt6.QtWidgets import QApplication
        from client.src.presentation.main_window import MainWindow
        
        app = QApplication(sys.argv)
        app.setApplicationName("Hermes Desktop")
        app.setApplicationVersion("2.0")
        
        window = MainWindow(config)
        window.show()
        
        logger.info("主窗口显示成功")
        
        # 获取日志统计
        summary = get_log_summary()
        logger.info(f"日志统计: {len(summary['log_files'])} 个日志文件, "
                    f"{summary['error_count']} 条错误, {summary['warning_count']} 条警告")
        
        # 运行应用
        exit_code = app.exec()
        
        log_shutdown(logger)
        
        # 分析错误日志
        analyze_errors()
        
        return exit_code
        
    except Exception as e:
        logger = get_logger("main")
        logger.critical(f"客户端启动失败: {e}", exc_info=True)
        
        # 即使启动失败也要分析错误
        analyze_errors()
        
        return 1


def analyze_errors():
    """分析错误日志"""
    from core.error_logger import get_recent_errors, get_log_summary, LOG_DIR
    
    print("\n" + "=" * 60)
    print("  错误日志分析报告")
    print("=" * 60)
    
    # 获取日志统计
    summary = get_log_summary()
    
    print(f"\n📁 日志目录: {summary['log_dir']}")
    print(f"📄 日志文件数量: {len(summary['log_files'])}")
    print(f"💾 总日志大小: {summary['total_size'] / 1024:.2f} KB")
    print(f"❌ 错误数量: {summary['error_count']}")
    print(f"⚠️  警告数量: {summary['warning_count']}")
    
    # 显示日志文件列表
    print("\n📋 日志文件列表:")
    print("-" * 40)
    for log_file in summary['log_files']:
        print(f"  {log_file['name']:<20} {log_file['size_mb']:.2f} MB")
    
    # 显示最近的错误
    errors = get_recent_errors(10)
    if errors:
        print("\n🔴 最近的错误日志 (最新 10 条):")
        print("-" * 60)
        for i, error in enumerate(errors, 1):
            print(f"  {i}. {error}")
    else:
        print("\n✅ 未发现错误日志")
    
    # 显示警告
    from core.error_logger import LOG_FILE_WARNING
    warnings = []
    if LOG_FILE_WARNING.exists():
        try:
            with open(LOG_FILE_WARNING, 'r', encoding='utf-8') as f:
                warnings = f.readlines()[-10:]
        except Exception:
            pass
    
    if warnings:
        print("\n⚠️  最近的警告日志 (最新 10 条):")
        print("-" * 60)
        for i, warning in enumerate(warnings, 1):
            print(f"  {i}. {warning.strip()}")
    else:
        print("\n✅ 未发现警告日志")
    
    # 诊断建议
    print("\n💡 诊断建议:")
    print("-" * 40)
    
    if summary['error_count'] > 0:
        print("  • 检测到错误日志，请检查最近的错误信息")
        print("  • 建议查看 logs/error.log 文件获取详细错误信息")
    
    if summary['warning_count'] > 0:
        print("  • 检测到警告日志，可能存在潜在问题")
        print("  • 建议查看 logs/warning.log 文件")
    
    if summary['total_size'] > 100 * 1024 * 1024:  # 100MB
        print("  • 日志文件总大小超过 100MB，建议清理旧日志")
    
    # 检查日志目录是否存在
    if not LOG_DIR.exists():
        print("  • 日志目录不存在，将在下次启动时创建")
    
    print()
    print("=" * 60)


if __name__ == "__main__":
    print("🚀 正在启动 Hermes Desktop...")
    print("-" * 40)
    
    exit_code = run_client()
    
    sys.exit(exit_code)
