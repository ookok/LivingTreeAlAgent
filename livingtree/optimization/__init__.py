"""LivingTree Optimization Package — LPO + Annealing + Ising + Discovery Machine."""

from livingtree.optimization.lpo_optimizer import (
    LPOOptimizer,
    SynapseLPO,
    ProviderLPO,
    TrajectoryLPO,
    DIVERGENCES,
    LPO_DIVERGENCE_GRADIENTS,
    get_lpo_optimizer,
    get_synapse_lpo,
    get_provider_lpo,
)
from livingtree.optimization.annealing_core import (
    AnnealingScheduler,
    EnergyLandscape,
    TunnelGate,
    ConvergenceCertificate,
    AnnealingState,
    ConvergenceReport,
    make_annealer,
    run_annealing,
)
from livingtree.optimization.ising_model import (
    IsingModel,
    IsingOptimizer,
    IsingConfig,
    IsingOptimizationResult,
    build_provider_ising,
    build_strategy_ising,
)
from livingtree.optimization.discovery_machine import (
    DiscoveryProblem,
    DiscoveryResult,
    NeuromorphicAutoencoder,
    DiscoveryMachine,
    get_discovery_machine,
)

__all__ = [
    "LPOOptimizer",
    "SynapseLPO",
    "ProviderLPO",
    "TrajectoryLPO",
    "DIVERGENCES",
    "LPO_DIVERGENCE_GRADIENTS",
    "get_lpo_optimizer",
    "get_synapse_lpo",
    "get_provider_lpo",
    "AnnealingScheduler",
    "EnergyLandscape",
    "TunnelGate",
    "ConvergenceCertificate",
    "AnnealingState",
    "ConvergenceReport",
    "make_annealer",
    "run_annealing",
    "IsingModel",
    "IsingOptimizer",
    "IsingConfig",
    "IsingOptimizationResult",
    "build_provider_ising",
    "build_strategy_ising",
    "DiscoveryProblem",
    "DiscoveryResult",
    "NeuromorphicAutoencoder",
    "DiscoveryMachine",
    "get_discovery_machine",
]
