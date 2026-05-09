"""TreeLLM — Lightweight multi-provider LLM routing.

Usage:
    from livingtree.treellm import TreeLLM, create_deepseek_provider, create_longcat_provider

    llm = TreeLLM()
    llm.add_provider(create_deepsek_provider("sk-xxx"))
    llm.add_provider(create_longcat_provider("ak-xxx"))

    result = await llm.chat([{"role": "user", "content": "Hello"}])
    async for token in llm.stream([...]):
        print(token, end="")
"""

from .core import TreeLLM, RouterStats
from .providers import (
    Provider, ProviderResult,
    DeepSeekProvider, LongCatProvider, NvidiaProvider, OpenAILikeProvider,
    create_deepseek_provider, create_longcat_provider, create_nvidia_provider,
)
from .classifier import TinyClassifier
from .prompt_versioning import PromptVersionManager, PromptTemplate, PROMPT_VERSION_MANAGER
from .embedding_scorer import EmbeddingScorer, ModelProfile, get_embedding_scorer
from .foresight_gate import ForesightGate, ForesightDecision, get_foresight_gate
from .onto_prompt_builder import OntoPromptBuilder, get_onto_prompt_builder
from .holistic_election import HolisticElection, ProviderScore, PROVIDER_CAPABILITIES, get_election
from .route_learner import RouteLearner, LearnedProfile, RoutingWeight, get_route_learner

from .providers import (
    create_modelscope_provider, create_bailing_provider,
    create_stepfun_provider, create_internlm_provider,
    create_sensetime_provider,
)

__all__ = [
    "TreeLLM", "RouterStats",
    "Provider", "ProviderResult",
    "DeepSeekProvider", "LongCatProvider", "NvidiaProvider", "OpenAILikeProvider",
    "create_deepseek_provider", "create_longcat_provider", "create_nvidia_provider",
    "TinyClassifier",
    "PromptVersionManager", "PromptTemplate", "PROMPT_VERSION_MANAGER",
    "EmbeddingScorer", "ModelProfile", "get_embedding_scorer",
    "ForesightGate", "ForesightDecision", "get_foresight_gate",
    "OntoPromptBuilder", "get_onto_prompt_builder",
    "HolisticElection", "ProviderScore", "PROVIDER_CAPABILITIES", "get_election",
    "RouteLearner", "LearnedProfile", "RoutingWeight", "get_route_learner",
    "create_modelscope_provider", "create_bailing_provider",
    "create_stepfun_provider", "create_internlm_provider",
    "create_sensetime_provider",
]
