"""质量认证系统 - 统一调度器"""

from typing import Dict, Any
from .cert import (
    QualityCertificationSystem, QualityReport, QualityMetrics,
    TrustProfile, CertificationBadge, ReviewChain,
    CertLevel, TrustLevel,
    create_quality_certification_system
)


class QualitySystem:
    """质量系统"""
    
    def __init__(self):
        self.system = create_quality_certification_system()
    
    def certify_document(self, document: Dict, creator_id: str = "system", review_result: Any = None) -> QualityReport:
        return self.system.certify(document, creator_id, review_result)
    
    def get_certification(self, document_id: str) -> QualityReport:
        return self.system.get_certification(document_id)
    
    def get_trust(self, user_id: str) -> TrustProfile:
        return self.system.get_trust_profile(user_id)
    
    def verify_traceability(self, document_id: str) -> bool:
        return self.system.verify_chain(document_id)
    
    def get_stats(self) -> Dict:
        return self.system.get_statistics()


def create_quality_system() -> QualitySystem:
    return QualitySystem()
