"""SafetyModels — Safety, Occupational Health, and Emergency Response computation.

Comprehensive safety engineering models per Chinese AQ/SH/GB/GBZ standards.
Three domains: Safety Engineering, Occupational Health, Emergency Response.

Standards: GB18218, GB50160, GB50016, AQ/T3046, AQ/T3049, AQ/T3054,
  IEC 61508/61511, GBZ 2.1, GBZ/T 189, GBZ/T 229, HJ 169, SH 3012
"""

from __future__ import annotations

import math
from dataclasses import dataclass, field
from typing import Any, Optional

from loguru import logger


# ═══ A. SAFETY ENGINEERING ═════════════════════════════════════════


@dataclass
class SafetyResult:
    risk_level: str = ""
    risk_score: float = 0.0
    sil_required: int = 0
    pfd_avg: float = 1.0
    recommendations: list[str] = field(default_factory=list)


class SafetyModels:
    """AQ/T 3049 HAZOP, IEC 61511 LOPA/SIL, FTA/ETA, consequence models."""

    # ── HAZOP ──────────────────────────────────────────────────────

    HAZOP_GUIDEWORDS = ["无/NO", "过多/MORE", "过少/LESS", "部分/PART",
                        "反向/REVERSE", "伴随/AS_WELL_AS", "其他/OTHER"]
    HAZOP_PARAMS = ["流量", "温度", "压力", "液位", "组成", "pH", "速度"]

    @staticmethod
    def hazop_risk(L: float, S: float, R: float) -> dict:
        """HAZOP risk level: D = L × S, then classified per AQ/T 3049.

        L=likelihood(1-5), S=severity(1-5), R=risk score.
        Returns {risk_level, recommendations}.
        """
        D = L * S
        recs = []
        if D >= 15:
            level = "重大风险"
            recs = ["立即停用", "重新设计SIF", "增加独立保护层", "实施ALARP分析"]
        elif D >= 10:
            level = "高风险"
            recs = ["增加SIL保护", "加强检测频率", "制定应急预案"]
        elif D >= 5:
            level = "中风险"
            recs = ["增加操作程序控制", "定期检测", "培训操作人员"]
        else:
            level = "低风险"
            recs = ["维持现有控制措施"]
        return {"risk_score": D, "risk_level": level, "recommendations": recs}

    @staticmethod
    def hazop_deviation(guideword: str, param: str,
                        consequence: str = "") -> dict:
        """Generate a HAZOP deviation and suggested safeguards."""
        safeguards = {
            ("过多", "流量"): ["流量控制阀", "限流孔板", "高流量联锁"],
            ("过少", "流量"): ["低流量报警", "备用泵自启", "流量监测"],
            ("过多", "温度"): ["温度高联锁", "冷却系统", "泄压装置"],
            ("过少", "温度"): ["伴热保温", "温度低报警", "防冻措施"],
            ("过多", "压力"): ["安全阀", "爆破片", "压力高联锁"],
            ("过少", "压力"): ["压力低报警", "真空破坏器"],
            ("过多", "液位"): ["高液位联锁", "溢流管", "液位监测"],
            ("过少", "液位"): ["低液位联锁", "补液系统"],
            ("反向", "流量"): ["止回阀", "单向阀"],
        }
        sg = safeguards.get((guideword, param), ["流程审查", "操作规程", "定期检测"])
        return {
            "deviation": f"{guideword} {param}",
            "consequence": consequence or f"{guideword} {param}可能导致工艺偏差",
            "safeguards": sg,
        }

    # ── LOPA / SIL ─────────────────────────────────────────────────

    @staticmethod
    def lopa_ipl(target_risk: float, initiating_event_freq: float,
                 ipl_pfds: list[float]) -> dict:
        """LOPA: mitigated event frequency = IEF × Π PFD_ipl.

        target_risk: acceptable frequency (e.g., 1e-5/yr)
        IEF: initiating event frequency (e.g., 0.1/yr)
        ipl_pfds: list of PFD for each independent protection layer
        """
        mitigated = initiating_event_freq
        for pfd in ipl_pfds:
            mitigated *= max(pfd, 1e-6)
        gap = target_risk / mitigated if mitigated > 0 else float('inf')
        return {
            "mitigated_frequency": mitigated,
            "target_risk": target_risk,
            "gap_ratio": round(gap, 2),
            "acceptable": mitigated <= target_risk,
            "ipl_count": len(ipl_pfds),
        }

    @staticmethod
    def sil_determination(rrf_required: float) -> dict:
        """SIL determination per IEC 61511: SIL = floor(log10(RRF)).

        RRF = 1/PFDavg. SIL1:10-100, SIL2:100-1000, SIL3:1000-10000, SIL4:>10000.
        """
        if rrf_required <= 0:
            return {"sil": 0, "pfd_avg": 1.0}
        sil = int(math.floor(math.log10(rrf_required)))
        sil = min(max(sil, 0), 4)
        sil_ranges = {1: (10, 100), 2: (100, 1000), 3: (1000, 10000), 4: (10000, 100000)}
        pfd_min, pfd_max = sil_ranges.get(sil, (0, 1))
        return {
            "sil": sil,
            "rrf_required": round(rrf_required, 0),
            "pfd_avg_range": f"{1/pfd_max:.1e} - {1/pfd_min:.1e}",
            "architecture_hint": {
                1: "1oo1", 2: "1oo2 or 2oo3",
                3: "2oo3 (redundant)", 4: "2oo4D (diverse)",
            }.get(sil, "1oo1"),
        }

    @staticmethod
    def pfd_1oo1(lambda_du: float, TI: float, MTTR: float = 8.0) -> float:
        """PFDavg for 1oo1 architecture: PFDavg ≈ λ_du × TI/2."""
        return lambda_du * TI / 2 / 8760

    @staticmethod
    def pfd_1oo2(lambda_du: float, TI: float, beta: float = 0.05,
                 MTTR: float = 8.0) -> float:
        """PFDavg for 1oo2 with common cause: (λ_du×TI)²/3 + β×λ_du×TI/2."""
        single = lambda_du * TI / 8760
        return (single ** 2) / 3 + beta * single / 2

    @staticmethod
    def pfd_2oo3(lambda_du: float, TI: float, beta: float = 0.02) -> float:
        """PFDavg for 2oo3 voting with CCF."""
        single = lambda_du * TI / 8760
        return (single ** 2) + beta * single / 2

    # ── FTA / ETA ──────────────────────────────────────────────────

    @staticmethod
    def ft_and_gate(probabilities: list[float]) -> float:
        """Fault Tree AND gate: P = Π p_i."""
        result = 1.0
        for p in probabilities:
            result *= max(0, min(1, p))
        return result

    @staticmethod
    def ft_or_gate(probabilities: list[float]) -> float:
        """Fault Tree OR gate (rare event approximation): P ≈ Σ p_i."""
        return min(1.0, sum(max(0, p) for p in probabilities))

    @staticmethod
    def et_barrier(initiating_freq: float,
                   barrier_probs: list[float],
                   consequence_severity: list[float] = None) -> dict:
        """Event Tree: calculate outcome frequencies.

        Branching: success of barrier i → next barrier; failure → consequence.
        Returns {outcome_frequencies, risk_values}.
        """
        outcomes = []
        current_freq = initiating_freq
        for i, pb in enumerate(barrier_probs):
            pf = 1 - pb  # Failure probability
            sev = consequence_severity[i] if consequence_severity and i < len(consequence_severity) else 1
            outcomes.append({
                "barrier": i + 1,
                "success_path_freq": current_freq * pb,
                "failure_path_freq": current_freq * pf,
                "consequence": current_freq * pf * sev,
            })
        return {"outcomes": outcomes, "total_consequence": sum(o["consequence"] for o in outcomes)}

    @staticmethod
    def bowtie_barrier_score(preventive: list[float],
                             mitigative: list[float]) -> dict:
        """Bowtie barrier effectiveness: preventive × mitigative."""
        prev_score = SafetyModels.ft_or_gate([1 - p for p in preventive])
        mit_score = SafetyModels.ft_or_gate([1 - p for p in mitigative])
        return {
            "preventive_effectiveness": round(1 - prev_score, 3),
            "mitigative_effectiveness": round(1 - mit_score, 3),
            "overall_risk_reduction": round((1 - prev_score) * (1 - mit_score), 3),
        }

    # ── Fire & Explosion Consequence ───────────────────────────────

    @staticmethod
    def pool_fire(mass_kg: float, pool_area_m2: float,
                  burning_rate: float = 0.05) -> dict:
        """Pool fire: burning rate, flame height, thermal flux.

        Burning rate m''= 0.001 kg/m²/s (gasoline), Hc=44 MJ/kg.
        Flame height Thomas: H/D = 42×(m''/(ρ_air×√(g×D)))^0.61.
        """
        D = math.sqrt(4 * pool_area_m2 / math.pi)
        m_dot = burning_rate * pool_area_m2
        Hc = 44e6  # J/kg for hydrocarbons
        Q = m_dot * Hc
        # Thomas correlation for flame height
        g = 9.81
        rho_air = 1.2
        m_dot_s = burning_rate
        H_D = 42 * (m_dot_s / (rho_air * math.sqrt(g * D))) ** 0.61 if D > 0 else 0
        H = H_D * D
        # Point source thermal flux at distance r
        eta = 0.3  # Radiative fraction
        r = max(D, 10)
        q = eta * Q / (4 * math.pi * r * r) / 1000  # kW/m²
        duration = mass_kg / max(m_dot, 0.001)  # seconds
        return {
            "flame_height_m": round(H, 1),
            "heat_release_MW": round(Q / 1e6, 1),
            "thermal_flux_kW_m2": round(q, 2),
            "burn_duration_s": round(duration, 0),
            "pool_diameter_m": round(D, 1),
        }

    @staticmethod
    def bleve(mass_kg: float, T_K: float,
              T_boil_K: float = 373) -> dict:
        """BLEVE: fireball diameter D=5.8×M^⅓, duration t=0.45×M^⅓.

        Thermal radiation at distance R: q=τ×F×Q/(4πR²).
        """
        D = 5.8 * mass_kg ** (1.0 / 3.0)
        t = 0.45 * mass_kg ** (1.0 / 3.0) if mass_kg < 100000 else 0.45 * 100000 ** (1.0/3.0)
        r = max(D, 50)
        Q = mass_kg * 2e6  # ~2 MJ/kg BLEVE energy
        tau = 0.7
        F = 1.0
        q = tau * F * Q / (4 * math.pi * r * r) / 1000 / t if t > 0 else 0  # kW/m²
        return {
            "fireball_diameter_m": round(D, 1),
            "duration_s": round(t, 1),
            "thermal_flux_kW_m2": round(q, 2),
        }

    @staticmethod
    def vce_tnt(mass_kg: float, efficiency: float = 0.04,
                Hc_J_kg: float = 44e6, TNT_energy: float = 4.184e6) -> dict:
        """VCE TNT equivalency: W_TNT = η × mass × Hc / E_TNT.

        Overpressure vs scaled distance Z = R / W_TNT^(1/3).
        """
        W_tnt = efficiency * mass_kg * Hc_J_kg / TNT_energy
        Z_vals = {0.5: 1.0, 1.0: 0.5, 2.0: 0.1, 5.0: 0.03, 10.0: 0.01, 20.0: 0.005}
        overpressure = {}
        for Z, P in Z_vals.items():
            R = Z * W_tnt ** (1.0/3.0) if W_tnt > 0 else 0
            overpressure[f"{Z}m/kg^⅓"] = {"distance_m": round(R, 1), "overpressure_bar": P}
        return {
            "tnt_equivalent_kg": round(W_tnt, 1),
            "overpressure_by_distance": overpressure,
        }

    @staticmethod
    def toxic_dispersion_slab(Q_kg_s: float, u: float, x: float,
                              stability: str = 'D') -> dict:
        """SLAB heavy gas / neutral buoyancy toxic dispersion (simplified).

        Uses Gaussian with Briggs transition for dense gas.
        """
        # Simplified — uses eia_models Gaussian for neutral buoyancy
        from .eia_models import AtmosphericModels
        C = AtmosphericModels.gaussian_plume(Q_kg_s * 1e6, u, x, 0, 0, stability, 0)
        LC50_defaults = {"氯气": 293, "氨气": 1390, "硫化氢": 444, "一氧化碳": 3760}
        return {
            "concentration_mg_m3": round(C, 2),
            "suggested_LC50_values": LC50_defaults,
        }

    # ── QRA / Risk ─────────────────────────────────────────────────

    @staticmethod
    def fn_curve(scenario_freqs: list[float],
                 scenario_fatalities: list[float]) -> dict:
        """Construct F-N curve from scenarios. Returns cumulative frequency."""
        if len(scenario_freqs) != len(scenario_fatalities):
            return {"error": "length mismatch"}
        pairs = sorted(zip(scenario_fatalities, scenario_freqs), reverse=True)
        cumulative = []
        running = 0.0
        for N, f in pairs:
            running += f
            cumulative.append({"fatalities_N": N, "cumulative_frequency": round(running, 8)})
        return {"fn_points": cumulative}

    @staticmethod
    def alarp_check(risk: float, acceptable: float = 1e-6,
                    tolerable: float = 1e-4) -> str:
        """ALARP region check: risk < acceptable → broadly acceptable,
        acceptable ≤ risk < tolerable → ALARP, risk ≥ tolerable → intolerable.
        """
        if risk < acceptable:
            return "broadly_acceptable"
        if risk < tolerable:
            return "alarp_region"
        return "intolerable"

    @staticmethod
    def major_hazard_identify(substances: dict[str, float]) -> dict:
        """GB18218 major hazard source identification.

        substances: {name: inventory_tons}. Compares against critical thresholds.
        """
        thresholds = {
            "液氨": 10, "液氯": 5, "甲醇": 500, "苯": 50, "甲苯": 500,
            "汽油": 200, "液化石油气": 50, "氢气": 5, "硫化氢": 5,
            "环氧乙烷": 10, "硝酸铵": 50, "丙烯腈": 50, "光气": 0.3,
        }
        results = {}
        for name, tons in substances.items():
            threshold = thresholds.get(name, 100)
            ratio = tons / threshold if threshold > 0 else 0
            grade = ""
            if ratio >= 1.0:
                grade = "一级重大危险源" if ratio >= 5 else ("二级" if ratio >= 2 else "三级") if ratio >= 1 else ""
            results[name] = {"ratio": round(ratio, 2), "threshold_tons": threshold, "grade": grade or "非重大危险源"}
        return results


# ═══ B. OCCUPATIONAL HEALTH ════════════════════════════════════════


class OccupationalHealthModels:
    """GBZ 2.1, GBZ/T 189, GBZ/T 229 occupational health."""

    # ── Chemical Exposure ──────────────────────────────────────────

    @staticmethod
    def twa_8h(concentrations: list[float], durations_h: list[float]) -> float:
        """PC-TWA: 8-hour time-weighted average = Σ(Ci×Ti)/8."""
        if len(concentrations) != len(durations_h):
            return 0.0
        total = sum(c * t for c, t in zip(concentrations, durations_h))
        return total / 8.0

    @staticmethod
    def stel_15min(C: float, limit: float) -> dict:
        """PC-STEL: 15-min short-term exposure check."""
        ratio = C / limit if limit > 0 else 0
        return {"concentration": C, "stel_limit": limit,
                "ratio": round(ratio, 2),
                "exceeded": ratio > 1.0,
                "max_exceed_per_day": 4 if ratio > 1 else 0}

    @staticmethod
    def mixed_exposure_hazard_index(exposures: dict[str, float],
                                    limits: dict[str, float]) -> dict:
        """Mixed exposure assessment: HI = Σ (Ei / OELi).

        HI > 1 indicates potential over-exposure per GBZ 2.1.
        """
        hi = sum(exposures.get(k, 0) / max(limits.get(k, 1), 0.001) for k in exposures)
        return {"hazard_index": round(hi, 3),
                "overexposure": hi > 1.0,
                "components": {k: round(exposures[k] / max(limits.get(k, 1), 0.001), 3) for k in exposures}}

    # ── Physical Hazards ───────────────────────────────────────────

    @staticmethod
    def noise_lex_8h(LAeq: list[float], durations_h: list[float]) -> float:
        """Lex,8h daily noise exposure: 80 + 10×log(Σ10^(0.1×(LAeq_i-80))×Ti/8)."""
        total = sum(10 ** (0.1 * L) * t / 8 for L, t in zip(LAeq, durations_h))
        return 80 + 10 * math.log10(total) if total > 0 else 0

    @staticmethod
    def noise_action_level(Lex_8h: float) -> dict:
        """GBZ/T 189.8 action levels: 80dB(警示), 85dB(行动), 90dB(限值)."""
        return {
            "Lex_8h": round(Lex_8h, 1),
            "warning": Lex_8h >= 80,
            "action_required": Lex_8h >= 85,
            "limit_exceeded": Lex_8h >= 90,
        }

    @staticmethod
    def wbgt_outdoor(Tnwb: float, Tg: float, Ta: float) -> float:
        """WBGT (outdoor with solar load): WBGT = 0.7×Tnwb + 0.2×Tg + 0.1×Ta.

        GBZ/T 189.7: Tnwb=自然湿球, Tg=黑球, Ta=干球温度.
        """
        return 0.7 * Tnwb + 0.2 * Tg + 0.1 * Ta

    @staticmethod
    def wbgt_indoor(Tnwb: float, Tg: float) -> float:
        """WBGT (indoor/outdoor no solar): WBGT = 0.7×Tnwb + 0.3×Tg."""
        return 0.7 * Tnwb + 0.3 * Tg

    @staticmethod
    def wbgt_work_rest_regime(WBGT: float, workload: str = "moderate") -> dict:
        """Work-rest ratio per WBGT (GBZ/T 189.7).

        Workload: light(<200W), moderate(200-350W), heavy(350-500W).
        """
        limits = {
            "light": [(30, "100%工作"), (31.5, "75%工作,25%休息"),
                     (33, "50%工作,50%休息"), (34, "25%工作,75%休息"), (99, "停止工作")],
            "moderate": [(27, "100%工作"), (29, "75%工作,25%休息"),
                        (31, "50%工作,50%休息"), (32.5, "25%工作,75%休息"), (99, "停止工作")],
            "heavy": [(25, "100%工作"), (26.5, "75%工作,25%休息"),
                     (28.5, "50%工作,50%休息"), (30, "25%工作,75%休息"), (99, "停止工作")],
        }
        for threshold, recommendation in limits.get(workload, limits["moderate"]):
            if WBGT < threshold:
                return {"wbgt": round(WBGT, 1), "workload": workload,
                        "recommendation": recommendation, "regime_ok": threshold < 99}
        return {"wbgt": round(WBGT, 1), "workload": workload, "recommendation": "停止工作", "regime_ok": False}

    @staticmethod
    def ventilation_dilution(G_mg_s: float, C_limit_mg_m3: float,
                             K: float = 5.0) -> float:
        """Dilution ventilation: Q = G × K / (C_limit - C_bg) (m³/s)."""
        return G_mg_s * K / max(C_limit_mg_m3, 0.001) / 1000  # m³/s

    @staticmethod
    def ppe_adequacy(required_apf: int, provided_apf: int) -> dict:
        """PPE Assigned Protection Factor check per GB/T 11651."""
        return {"required_apf": required_apf, "provided_apf": provided_apf,
                "adequate": provided_apf >= required_apf,
                "multiplier": round(provided_apf / max(required_apf, 1), 1)}

    @staticmethod
    def dust_hazard_classification(concentration_mg_m3: float,
                                   MAC_mg_m3: float,
                                   free_silica_pct: float = 0) -> dict:
        """Dust hazard per GBZ 2.1 / GBZ 188."""
        ratio = concentration_mg_m3 / max(MAC_mg_m3, 0.001)
        # Silica adjustment
        if free_silica_pct > 50:
            ratio *= 2.0
        elif free_silica_pct > 10:
            ratio *= 1.5
        level = "轻微" if ratio <= 0.5 else ("中度" if ratio <= 1 else ("高度" if ratio <= 5 else "极度"))
        return {"ratio": round(ratio, 2), "hazard_level": level,
                "medical_surveillance": "required" if ratio > 0.5 else "optional"}

    @staticmethod
    def occupational_hazard_grading(hazard_index: float) -> dict:
        """GBZ/T 229 occupational hazard classification.

        Class 0: HI<0.5 (轻微),  Class 1: 0.5≤HI<1,  Class 2: 1≤HI<3,  Class 3: HI≥3.
        """
        if hazard_index < 0.5:
            grade, desc = 0, "轻微危害 (常规管理)"
        elif hazard_index < 1.0:
            grade, desc = 1, "一般危害 (加强监测)"
        elif hazard_index < 3.0:
            grade, desc = 2, "较重危害 (工程控制+个体防护)"
        else:
            grade, desc = 3, "严重危害 (专项治理)"
        return {"grade": grade, "description": desc,
                "ppe_level": {0: "基本", 1: "加强", 2: "全面", 3: "最高"}[grade]}

    @staticmethod
    def cmr_classification(substance: str) -> dict:
        """GBZ 2.1 CMR (Carcinogen/Mutagen/Reprotoxic) lookup."""
        CMR_DB = {
            "苯": {"carcinogen": "G1", "comment": "确认人类致癌物"},
            "甲醛": {"carcinogen": "G1", "comment": "确认人类致癌物"},
            "石棉": {"carcinogen": "G1", "comment": "确认人类致癌物"},
            "氯乙烯": {"carcinogen": "G1", "comment": "确认人类致癌物"},
            "苯并[a]芘": {"carcinogen": "G1", "comment": "确认人类致癌物"},
            "丙烯腈": {"carcinogen": "G2A", "comment": "可能人类致癌物"},
            "二氯甲烷": {"carcinogen": "G2B", "comment": "可疑人类致癌物"},
            "铅": {"reprotoxic": True, "comment": "生殖毒性"},
            "汞": {"reprotoxic": True, "comment": "生殖毒性"},
        }
        return CMR_DB.get(substance, {"carcinogen": "未分类", "comment": "无CMR分类数据"})


# ═══ C. EMERGENCY RESPONSE ═════════════════════════════════════════


class EmergencyModels:
    """HJ 169, GB 50160, SH 3012 emergency response models."""

    @staticmethod
    def fire_water_demand(area_m2: float, fire_risk: str = "medium") -> dict:
        """Fire water flow per GB 50160/GB50974.

        Flow rates: low=15L/s, medium=30L/s, high=60L/s, extreme=100L/s.
        Duration: 2-6h.
        """
        rates = {"low": (15, 2), "medium": (30, 3), "high": (60, 4), "extreme": (100, 6)}
        flow, duration = rates.get(fire_risk, (30, 3))
        total_volume = flow * duration * 3600 / 1000  # m³
        return {"flow_L_s": flow, "duration_h": duration,
                "total_water_m3": round(total_volume, 1),
                "foam_concentrate_L": round(flow * duration * 60 * 0.03, 0) if fire_risk in ("high", "extreme") else 0}

    @staticmethod
    def emergency_pool_capacity(V1: float, V2: float, V3: float = 0,
                                V4: float = 0, V5: float = 0) -> float:
        """Emergency pool per GB 50160 / SH 3012:
        V = V1(最大消防用水) + V2(雨水) - V3(可转输) + V4(泄漏物料) + V5(生产废水)

        All volumes in m³.
        """
        return max(0, V1 + V2 - V3 + V4 + V5)

    @staticmethod
    def evacuation_time(population: int, exit_width_m: float,
                        flow_rate: float = 1.3) -> dict:
        """SFPE hydraulic evacuation: t = P / (W × Fs) + t_pre.

        flow_rate=1.3 persons/s/m (NFPA 130), t_pre=60-300s per occupancy.
        """
        if exit_width_m <= 0 or flow_rate <= 0:
            return {"error": "invalid parameters"}
        travel_time = population / (exit_width_m * flow_rate)
        t_pre = 120 if population > 50 else 60
        t_total = t_pre + travel_time
        return {"total_time_s": round(t_total, 0), "pre_movement_s": t_pre,
                "travel_time_s": round(travel_time, 0),
                "acceptable": t_total < 600}

    @staticmethod
    def domino_escalation(thermal_kw_m2: float, duration_s: float,
                          overpressure_bar: float) -> dict:
        """Domino effect escalation thresholds per AQ/T 3046.

        Thermal: >37.5 kW/m² → equipment damage, >12.5 kW/m² → domino possible.
        Overpressure: >0.3 bar → heavy damage, >0.1 bar → moderate, >0.03 bar → minor.
        """
        thermal_risk = ("severe" if thermal_kw_m2 > 37.5 else
                        "moderate" if thermal_kw_m2 > 12.5 else "low")
        overpressure_risk = ("severe" if overpressure_bar > 0.3 else
                            "moderate" if overpressure_bar > 0.1 else
                            "minor" if overpressure_bar > 0.03 else "none")
        return {
            "thermal_escalation_risk": thermal_risk,
            "overpressure_escalation_risk": overpressure_risk,
            "domino_possible": thermal_risk in ("severe", "moderate") or
                              overpressure_risk in ("severe", "moderate"),
        }

    @staticmethod
    def worst_case_scenario(substances: dict[str, dict]) -> dict:
        """HJ 169-2018 worst-case scenario selection.

        substances: {name: {inventory_tons, threshold_tons, toxicity, flammability}}.
        Selects the scenario with maximum consequences.
        """
        scored = []
        for name, props in substances.items():
            ratio = props.get("inventory_tons", 0) / max(props.get("threshold_tons", 1), 0.01)
            tox = props.get("toxicity", 1)
            flam = props.get("flammability", 1)
            score = ratio * (tox * 0.6 + flam * 0.4)
            scored.append((name, score, ratio))
        scored.sort(key=lambda x: -x[1])
        if not scored:
            return {"worst_case": "none"}
        worst = scored[0]
        return {
            "worst_case_substance": worst[0],
            "worst_case_score": round(worst[1], 2),
            "alternative_cases": [s[0] for s in scored[1:4]],
            "scenarios": [
                {"type": "泄漏扩散", "substance": s[0],
                 "requires_emergency_pool": s[2] > 1}
                for s in scored[:3]
            ],
        }

    @staticmethod
    def emergency_response_time(distance_km: float,
                                speed_kmh: float = 40) -> float:
        """Response time estimate: t = distance / speed + preparation."""
        return distance_km / speed_kmh * 60 + 3  # minutes

    @staticmethod
    def plan_effectiveness_score(has_procedures: bool = False,
                                 has_resources: bool = False,
                                 has_drills: bool = False,
                                 has_communication: bool = False,
                                 has_review: bool = False) -> dict:
        """Emergency plan effectiveness scoring."""
        score = sum([has_procedures, has_resources, has_drills,
                     has_communication, has_review]) / 5.0
        return {
            "score": round(score, 2),
            "level": "adequate" if score >= 0.8 else "needs_improvement" if score >= 0.6 else "insufficient",
            "gaps": [
                area for area, has in [
                    ("procedures", has_procedures), ("resources", has_resources),
                    ("drills", has_drills), ("communication", has_communication),
                    ("review", has_review),
                ] if not has
            ],
        }

    @staticmethod
    def natech_coupling(N_hazard: int, N_tech: int,
                        coupling_score: float) -> str:
        """NaTech (Natural-hazard triggered technological accident) coupling.

        coupling_score: 0-1 strength of natural→technological coupling.
        """
        if N_hazard == 0:
            return "no_natech_risk"
        risk = N_hazard * N_tech * coupling_score
        if risk > 20:
            return "critical"
        if risk > 5:
            return "high"
        if risk > 1:
            return "moderate"
        return "low"


# ═══ SafetyEngine Facade ═══════════════════════════════════════════


class SafetyEngine:
    """Unified safety, occupational health, and emergency response computation."""

    _instance: Optional["SafetyEngine"] = None

    @classmethod
    def instance(cls) -> "SafetyEngine":
        if cls._instance is None:
            cls._instance = SafetyEngine()
        return cls._instance

    def __init__(self):
        self.safety = SafetyModels()
        self.oh = OccupationalHealthModels()
        self.emergency = EmergencyModels()

    def stats(self) -> dict:
        return {
            "safety": {"hazop": 2, "lopa_sil": 5, "fta_eta": 4,
                      "consequence": 4, "qra": 3, "major_hazard": 1},
            "occupational_health": {"exposure": 3, "physical": 6, "grading": 2, "cmr": 1},
            "emergency": {"resource": 2, "evacuation": 1, "domino": 1,
                         "worst_case": 1, "effectiveness": 1, "natech": 1},
            "total": 38,
        }


_safety: Optional[SafetyEngine] = None


def get_safety_engine() -> SafetyEngine:
    global _safety
    if _safety is None:
        _safety = SafetyEngine()
    return _safety


__all__ = [
    "SafetyEngine", "SafetyModels", "OccupationalHealthModels",
    "EmergencyModels", "get_safety_engine",
]
