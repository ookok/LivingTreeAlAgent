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

_LAZY_REEXPORTS: dict[str, tuple[str, str]] = {
    # name → (module, attr)
    "IsingModel": ("livingtree.treellm.holistic_election", "IsingModel"),
    "IsingOptimizer": ("livingtree.treellm.holistic_election", "IsingOptimizer"),
    "IsingConfig": ("livingtree.treellm.holistic_election", "IsingConfig"),
    "IsingOptimizationResult": ("livingtree.treellm.holistic_election", "IsingOptimizationResult"),
    "build_provider_ising": ("livingtree.treellm.holistic_election", "build_provider_ising"),
    "build_strategy_ising": ("livingtree.treellm.holistic_election", "build_strategy_ising"),
    "get_ising_optimizer": ("livingtree.treellm.holistic_election", "get_ising_optimizer"),
    "DiscoveryProblem": ("livingtree.treellm.strategic_orchestrator", "DiscoveryProblem"),
    "DiscoveryResult": ("livingtree.treellm.strategic_orchestrator", "DiscoveryResult"),
    "NeuromorphicAutoencoder": ("livingtree.treellm.strategic_orchestrator", "NeuromorphicAutoencoder"),
    "DiscoveryMachine": ("livingtree.treellm.strategic_orchestrator", "DiscoveryMachine"),
    "get_discovery_machine": ("livingtree.treellm.strategic_orchestrator", "get_discovery_machine"),
}

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
    *list(_LAZY_REEXPORTS.keys()),
]

_deprecated_modules: dict[str, str] = {
    "ising_model": "livingtree.treellm.holistic_election",
    "discovery_machine": "livingtree.treellm.strategic_orchestrator",
}


def __getattr__(name: str):
    if name in _LAZY_REEXPORTS:
        import importlib
        mod_name, attr_name = _LAZY_REEXPORTS[name]
        module = importlib.import_module(mod_name)
        val = getattr(module, attr_name)
        globals()[name] = val
        return val
    if name in _deprecated_modules:
        raise ImportError(
            f"Module 'livingtree.optimization.{name}' has been merged into "
            f"'{_deprecated_modules[name]}'. Update your import to the new location."
        )
    raise AttributeError(f"module {__name__!r} has no attribute {name!r}")