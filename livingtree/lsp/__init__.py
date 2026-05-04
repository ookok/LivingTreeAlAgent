"""livingtree.lsp — Language Server Protocol integration for inline diagnostics."""
from .lsp_manager import LSPManager, LSPDiagnostic, LSPCheckResult

__all__ = ["LSPManager", "LSPDiagnostic", "LSPCheckResult"]
