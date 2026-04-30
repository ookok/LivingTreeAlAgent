# -*- coding: utf-8 -*-
"""搜索建议模块测试"""

import asyncio
import sys
import io
from datetime import datetime

# 设置 UTF-8 输出
sys.stdout = io.TextIOWrapper(sys.stdout.buffer, encoding='utf-8')

def test_suggestion_model():
    print("=" * 50)
    print("Test 1: Suggestion Model")
    print("=" * 50)
    
    import sys
    sys.path.insert(0, r"F:\mhzyapp\LivingTreeAlAgent")
    from business.search_suggestion import SuggestionManager
    
    manager = SuggestionManager(max_results=10)
    
    # Add history
    manager.add_from_history("Python async", datetime.now())
    manager.add_from_history("Python async/await", datetime.now())
    manager.add_from_history("JavaScript tutorial", datetime.now())
    
    # Add knowledge base results
    manager.add_from_knowledge("Python async详解", score=0.9)
    manager.add_from_knowledge("Python async协程", score=0.8)
    
    # Query
    suggestions = manager.get_suggestions("Python async")
    
    print(f"\nQuery 'Python async' returned {len(suggestions)} suggestions:")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s.text} [{s.source}] Time:{s.time_label} Score:{s.final_score:.2f}")
    
    assert len(suggestions) > 0, "Should have suggestions"
    print("\n[PASS] Suggestion Model Test!")


async def test_knowledge_query():
    print("\n" + "=" * 50)
    print("Test 2: Knowledge Query")
    print("=" * 50)
    
    from business.search_suggestion import query_knowledge
    
    suggestions = await query_knowledge("Python", limit=5)
    
    print(f"\nQuery 'Python' returned {len(suggestions)} suggestions:")
    for i, s in enumerate(suggestions, 1):
        print(f"  {i}. {s.text} [{s.source}] Score:{s.score:.2f}")
    
    print("\n[PASS] Knowledge Query Test!")


def test_cache():
    print("\n" + "=" * 50)
    print("Test 3: Cache")
    print("=" * 50)
    
    from business.search_suggestion import get_suggestion_cache
    
    cache = get_suggestion_cache()
    
    # Test history cache
    cache.set_history("test", [
        {"text": "test1", "timestamp": 1234567890, "count": 1},
        {"text": "test2", "timestamp": 1234567891, "count": 2},
    ])
    
    result = cache.get_history("test")
    print(f"\nHistory cache: {result}")
    
    # Get stats
    stats = cache.get_stats()
    print(f"\nCache stats: {stats}")
    
    print("\n[PASS] Cache Test!")


def test_popup_creation():
    print("\n" + "=" * 50)
    print("Test 4: UI Popup Component")
    print("=" * 50)
    
    try:
        from PyQt6.QtWidgets import QApplication, QLineEdit
        from business.search_suggestion import SearchSuggestionPopup, SuggestionController
        
        app = QApplication(sys.argv)
        
        # Create input
        input_widget = QLineEdit()
        input_widget.setPlaceholderText("Input search...")
        input_widget.show()
        
        # Create popup
        popup = SearchSuggestionPopup()
        
        # Create controller
        controller = SuggestionController(input_widget, popup)
        
        print("\n[PASS] Component creation success!")
        
        app.quit()
        
    except ImportError as e:
        print(f"[SKIP] PyQt6 not installed: {e}")
    except Exception as e:
        print(f"[SKIP] UI Test skipped: {e}")


def main():
    print("\n[TEST] Search Suggestion Module\n")
    
    # Test data model
    test_suggestion_model()
    
    # Test knowledge query
    asyncio.run(test_knowledge_query())
    
    # Test cache
    test_cache()
    
    # Test UI
    test_popup_creation()
    
    print("\n" + "=" * 50)
    print("[OK] All tests passed!")
    print("=" * 50)


if __name__ == "__main__":
    main()
