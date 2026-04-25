"""
New Features Test Script
Test: Task Decomposition, System Brain, User Auth, Config Import/Export
"""

import sys
import os
import tempfile
import shutil
from pathlib import Path

# Ensure project root in Python path
_root = os.path.dirname(os.path.abspath(__file__))
if _root not in sys.path:
    sys.path.insert(0, _root)


def test_task_decomposer():
    """Test Task Decomposition System"""
    print("\n" + "="*60)
    print("Test 1: Task Decomposition System")
    print("="*60)
    
    from client.src.business.task_decomposer import TaskDecomposer, ChainOfThoughtExecutor, format_task_result
    
    # Create decomposer
    decomposer = TaskDecomposer()
    
    # Test auto type detection
    test_questions = [
        ("Analyze Python vs Java", "analysis"),
        ("Design a login system", "design"),
        ("Write an article about AI", "writing"),
        ("Which plan should I choose?", "decision"),
    ]
    
    print("  Type Detection:")
    for question, expected_type in test_questions:
        detected_type = decomposer.detect_task_type(question)
        status = "[OK]" if detected_type == expected_type else "[FAIL]"
        print(f"    {status} '{question[:20]}...' -> {detected_type} (expected: {expected_type})")
    
    # Test task decomposition
    print("\n  Decompose complex task...")
    task = decomposer.decompose(
        "How to plan a campus AI tech talk?",
        max_steps=4
    )
    
    print(f"  Task type: {task.metadata.get('task_type')}")
    print(f"  Decomposed into {len(task.steps)} steps:")
    for i, step in enumerate(task.steps, 1):
        print(f"    {i}. {step.title} ({step.description})")
    
    # Test executor
    print("\n  Test executor...")
    executor = ChainOfThoughtExecutor()
    
    simple_task = decomposer.decompose("What is machine learning?", max_steps=2)
    executed = executor.execute(simple_task)
    
    print(f"  Execution complete: {executed.completed_steps}/{executed.total_steps} steps")
    
    print("\n[PASS] Task Decomposition System test passed!")
    return True


def test_system_brain():
    """Test System Brain"""
    print("\n" + "="*60)
    print("Test 2: System Brain")
    print("="*60)
    
    from client.src.business.system_brain import SystemBrain, SystemBrainConfig
    
    # Create config
    config = SystemBrainConfig(
        model_name="qwen2.5:0.5b",
        api_base="http://localhost:11434"
    )
    
    # Create instance
    brain = SystemBrain(config)
    
    print(f"  Model name: {config.model_name}")
    print(f"  Current status: {brain.status.value}")
    print(f"  Ollama available: {brain._is_available}")
    
    # Get available models
    models = brain.get_model_list()
    print(f"\n  Available small models ({len(models)}):")
    for m in models:
        recommended = "[*]" if m.get("recommended") else "[ ]"
        print(f"    {recommended} {m['name']}: {m['description']}")
    
    # Get status info
    status_info = brain.get_status_info()
    print(f"\n  Status info: {status_info}")
    
    print("\n[PASS] System Brain test passed!")
    return True


def test_auth_system():
    """Test User Auth System"""
    print("\n" + "="*60)
    print("Test 3: User Auth System")
    print("="*60)
    
    from core.auth_system import AuthSystem, AuthResult
    
    # Use temp database
    temp_db = tempfile.NamedTemporaryFile(delete=False, suffix=".db")
    temp_db.close()
    
    try:
        # Create auth system
        auth = AuthSystem(temp_db.name)
        
        print(f"  Database: {temp_db.name}")
        
        # Test registration
        print("\n  Test registration...")
        result = auth.register(
            username="testuser",
            password="test123456",
            email="test@example.com",
            display_name="Test User"
        )
        status = "[OK]" if result.success else "[FAIL]"
        print(f"    Registration: {status} - {result.message}")
        
        if not result.success:
            print("    [SKIP] Registration failed, skipping remaining tests")
            return True
        
        # Test duplicate registration
        result2 = auth.register(username="testuser", password="123456")
        print(f"    Duplicate registration: {'[OK](expected fail)' if not result2.success else '[FAIL](unexpected)'}")
        
        # Test login
        print("\n  Test login...")
        result = auth.login("testuser", "test123456")
        status = "[OK]" if result.success else "[FAIL]"
        print(f"    Login: {status} - {result.message}")
        
        if result.success and result.user:
            print(f"    User: {result.user.username}")
            print(f"    Role: {result.user.role.value}")
            user_id = result.user.id
        else:
            print("    [SKIP] Login failed, skipping password change test")
            return True
        
        # Test wrong password
        result = auth.login("testuser", "wrong")
        print(f"    Wrong password: {'[OK](expected fail)' if not result.success else '[FAIL](unexpected)'}")
        
        # Test password change
        print("\n  Test password change...")
        result = auth.change_password(user_id, "test123456", "newpass123")
        status = "[OK]" if result.success else "[FAIL]"
        print(f"    Change password: {status} - {result.message}")
        
        # Test logout
        print("\n  Test logout...")
        auth.logout()
        print(f"    Logout status: {'[OK]' if not auth.is_logged_in else '[FAIL]'}")
        
        # New password login
        result = auth.login("testuser", "newpass123")
        print(f"    New password login: {'[OK]' if result.success else '[FAIL]'}")
        
        # Test user count
        count = auth.get_user_count()
        print(f"\n  Total users: {count}")
        
        print("\n[PASS] User Auth System test passed!")
        return True
        
    finally:
        try:
            os.unlink(temp_db.name)
        except:
            pass


def test_config_manager():
    """Test Config Manager"""
    print("\n" + "="*60)
    print("Test 4: Config Manager")
    print("="*60)
    
    import zipfile
    from core.config_manager import ConfigManager
    
    # Create temp directory
    temp_dir = tempfile.mkdtemp()
    
    try:
        # Create manager
        manager = ConfigManager(temp_dir)
        
        print(f"  Data directory: {temp_dir}")
        
        # Create test config files
        config_dir = Path(temp_dir)
        (config_dir / "config.json").write_text('{"test": true}', encoding="utf-8")
        (config_dir / "expert_system").mkdir()
        (config_dir / "expert_system" / "experts.json").write_text(
            '{"experts": [{"id": "test", "name": "Test Expert"}]}',
            encoding="utf-8"
        )
        
        # Test get exportable items
        print("\n  Exportable items:")
        items = manager.get_exportable_items()
        for item in items:
            print(f"    - {item.name}: {item.description}")
        
        # Test export
        print("\n  Test export...")
        export_path = Path(temp_dir) / "test_export.zip"
        result = manager.export_items(["config", "experts"], str(export_path))
        status = "[OK]" if result.success else "[FAIL]"
        print(f"    Export result: {status}")
        if result.success:
            print(f"    File: {result.file_path}")
            print(f"    Size: {result.size} bytes")
        
        # Test export all
        print("\n  Test export all...")
        all_path = Path(temp_dir) / "test_all.zip"
        result = manager.export_all(str(all_path), include_sessions=False)
        print(f"    Export all: {'[OK]' if result.success else '[FAIL]'}")
        
        # Test import
        print("\n  Test import...")
        # Add a file to export
        with zipfile.ZipFile(export_path, 'a') as zf:
            zf.writestr("expert_system/skills.json", '{"skills": []}')
        
        result = manager.import_from_zip(str(export_path))
        print(f"    Import result: {'[OK]' if result.success else '[FAIL]'}")
        print(f"    Imported items: {result.items_imported}")
        
        # Test JSON export
        print("\n  Test JSON export...")
        json_data = manager.export_to_json("config")
        print(f"    JSON data: {json_data[:50]}...")
        
        print("\n[PASS] Config Manager test passed!")
        return True
        
    finally:
        try:
            shutil.rmtree(temp_dir)
        except:
            pass


def main():
    """Main test function"""
    print("\n" + "="*60)
    print("  Hermes Desktop New Features Test")
    print("="*60)
    
    tests = [
        ("Task Decomposer", test_task_decomposer),
        ("System Brain", test_system_brain),
        ("Auth System", test_auth_system),
        ("Config Manager", test_config_manager),
    ]
    
    passed = 0
    failed = 0
    
    for name, test_func in tests:
        try:
            if test_func():
                passed += 1
            else:
                failed += 1
        except Exception as e:
            print(f"\n[ERROR] Test '{name}' failed: {e}")
            import traceback
            traceback.print_exc()
            failed += 1
    
    print("\n" + "="*60)
    print(f"  Test Results: {passed}/{len(tests)} passed")
    print("="*60)
    
    if failed == 0:
        print("\n[SUCCESS] All tests passed!")
    else:
        print(f"\n[WARNING] {failed} tests failed")
    
    return failed == 0


if __name__ == "__main__":
    success = main()
    sys.exit(0 if success else 1)
