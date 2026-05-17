"""DEPRECATED — re-exports from livingtree.treellm.classifier.

This file is kept for backward compatibility. All classifier logic has been
consolidated into treellm/classifier.py. Import from there directly in new code.
"""
from .classifier import QueryClassifier, get_query_classifier

__all__ = ["QueryClassifier", "get_query_classifier"]
