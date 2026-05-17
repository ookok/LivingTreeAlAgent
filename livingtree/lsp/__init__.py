"""livingtree.lsp — Language Server Protocol integration for inline diagnostics."""
# DEPRECATED — candidate for removal. No active references found.

from .lsp_manager import LSPManager, LSPDiagnostic, LSPCheckResult

__all__ = ["LSPManager", "LSPDiagnostic", "LSPCheckResult"]
