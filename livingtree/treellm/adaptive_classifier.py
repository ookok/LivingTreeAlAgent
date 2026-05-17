"""DEPRECATED — re-exports from livingtree.treellm.classifier.

This file is kept for backward compatibility. All classifier logic has been
consolidated into treellm/classifier.py. Import from there directly in new code.
"""
from .classifier import AdaptiveClassifier, get_adaptive_classifier

__all__ = ["AdaptiveClassifier", "get_adaptive_classifier"]
