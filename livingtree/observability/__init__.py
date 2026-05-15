"""Observability layer — Structured logging, distributed tracing, and metrics.

Exports: get_logger, RequestTracer, MetricsCollector, setup_observability
"""

from .logger import get_logger, LogContext, setup_logging
from .tracer import RequestTracer, TraceSpan, trace_span, GenerationSpan, calculate_cost, DistilledEvidence, EvidenceLayer
from .metrics import MetricsCollector, MetricGauge, MetricCounter, MetricHistogram
from .setup import setup_observability, get_observability
from .agent_eval import EvalCase, EvaluationDataset, DatasetResult, ComparisonReport, EvalResult, AgentEval, get_eval
from .activity_feed import ActivityFeed, ActivityEvent, get_activity_feed
from ..treellm.debug_pro import ErrorReplay, OperationRecorder, get_error_replay
from ..core.system_health import TrustScorer, TrustProfile, get_trust_scorer
from ..treellm.confidence_calibrator import CalibrationEntry, CalibrationTracker, get_calibration_tracker, AttributionEntry
from ..knowledge.hallucination_guard import ClaimChecker, Claim, VerificationResult, CLAIM_CHECKER, get_claim_checker
from ..treellm.daemon_doctor import Sentinel, SentinelAlert, SentinelCheck, get_sentinel
from .change_manifest import ChangeManifest, ChangeEntry, VerificationStatus, CHANGE_MANIFEST, get_manifest
from .harness_registry import HarnessRegistry, FileAnnulus, HARNESS_REGISTRY, get_harness
from .audit_log import AuditLog, AuditEvent, AUDIT_LOG, get_audit_log

__all__ = [
    "get_logger",
    "LogContext",
    "setup_logging",
    "RequestTracer",
    "TraceSpan",
    "trace_span",
    "MetricsCollector",
    "MetricGauge",
    "MetricCounter",
    "MetricHistogram",
    "setup_observability",
    "get_observability",
    "EvalCase",
    "EvaluationDataset",
    "DatasetResult",
    "ComparisonReport",
    "EvalResult",
    "GenerationSpan",
    "calculate_cost",
    "DistilledEvidence",
    "EvidenceLayer",
    "ClaimChecker",
    "Claim",
    "VerificationResult",
    "CLAIM_CHECKER",
    "get_claim_checker",
    "Sentinel",
    "SentinelAlert",
    "SentinelCheck",
    "get_sentinel",
    "CalibrationEntry",
    "CalibrationTracker",
    "get_calibration_tracker",
    "AttributionEntry",
    "AgentEval",
    "get_eval",
    "ActivityFeed",
    "ActivityEvent",
    "get_activity_feed",
    "ErrorReplay",
    "OperationRecorder",
    "get_error_replay",
    "TrustScorer",
    "TrustProfile",
    "get_trust_scorer",
    "ChangeManifest",
    "ChangeEntry",
    "VerificationStatus",
    "CHANGE_MANIFEST",
    "get_manifest",
    "HarnessRegistry",
    "FileAnnulus",
    "HARNESS_REGISTRY",
    "get_harness",
    "AuditLog",
    "AuditEvent",
    "AUDIT_LOG",
    "get_audit_log",
]
