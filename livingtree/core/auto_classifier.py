"""DEPRECATED — re-exports from livingtree.treellm.classifier.

This file is kept for backward compatibility. All classifier logic has been
consolidated into treellm/classifier.py. Import from there directly in new code.
"""
from ..treellm.classifier import AutoClassifier, get_auto_classifier, ClassificationResult

__all__ = ["AutoClassifier", "get_auto_classifier", "ClassificationResult"]
