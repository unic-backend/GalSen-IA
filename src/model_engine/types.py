"""
Modèle de données pour le moteur de modèles GalSen IA.
"""

from enum import Enum
from dataclasses import dataclass, field
from typing import Dict, Any, Optional, List
import time


class ModelType(Enum):
    """Types de modèles pris en charge."""
    OPENAI_GPT4 = "openai_gpt4"
    OPENAI_GPT35 = "openai_gpt35"
    ANTHROPIC_CLAUDE3_OPUS = "anthropic_claude3_opus"
    ANTHROPIC_CLAUDE3_SONNET = "anthropic_claude3_sonnet"
    ANTHROPIC_CLAUDE3_HAIKU = "anthropic_claude3_haiku"
    GOOGLE_GEMINI_PRO = "google_gemini_pro"
    GOOGLE_GEMINI_ULTRA = "google_gemini_ultra"
    MISTRAL_LARGE = "mistral_large"
    MISTRAL_MEDIUM = "mistral_medium"
    DEEPSEEK_CHAT = "deepseek_chat"
    QWEN_PLUS = "qwen_plus"
    LLAMA2_70B = "llama2_70b"
    LLAMA2_13B = "llama2_13b"
    LOCAL_OLLAMA = "local_ollama"
    LOCAL_VLLM = "local_vllm"
    FUTURE_PROVIDER = "future_provider"


class ModelPriority(Enum):
    """Priorités des modèles."""
    LOW = 0
    MEDIUM = 1
    HIGH = 2
    CRITICAL = 3


class ModelStatus(Enum):
    """Statuts des modèles."""
    ACTIVE = "active"
    INACTIVE = "inactive"
    MAINTENANCE = "maintenance"
    DEPRECATED = "deprecated"
    ERROR = "error"


@dataclass
class ModelItem:
    """Représente un modèle enregistré dans le moteur."""
    model_id: str
    model_type: ModelType
    provider: str
    name: str
    version: str
    priority: ModelPriority = ModelPriority.MEDIUM
    status: ModelStatus = ModelStatus.ACTIVE
    context_window: int = 4096
    max_output_tokens: int = 2048
    supported_features: List[str] = field(default_factory=list)
    metadata: Dict[str, Any] = field(default_factory=dict)
    created_at: float = field(default_factory=time.time)
    updated_at: float = field(default_factory=time.time)
    usage_count: int = 0
    total_tokens_used: int = 0
    total_cost: float = 0.0
    avg_latency: float = 0.0
    error_rate: float = 0.0

    def to_dict(self) -> Dict[str, Any]:
        """Convertit l'élément en dictionnaire."""
        return {
            "model_id": self.model_id,
            "model_type": self.model_type.value,
            "provider": self.provider,
            "name": self.name,
            "version": self.version,
            "priority": self.priority.value,
            "status": self.status.value,
            "context_window": self.context_window,
            "max_output_tokens": self.max_output_tokens,
            "supported_features": self.supported_features,
            "metadata": self.metadata,
            "created_at": self.created_at,
            "updated_at": self.updated_at,
            "usage_count": self.usage_count,
            "total_tokens_used": self.total_tokens_used,
            "total_cost": self.total_cost,
            "avg_latency": self.avg_latency,
            "error_rate": self.error_rate
        }

    @classmethod
    def from_dict(cls, data: Dict[str, Any]) -> 'ModelItem':
        """Crée un élément à partir d'un dictionnaire."""
        return cls(
            model_id=data["model_id"],
            model_type=ModelType(data["model_type"]),
            provider=data["provider"],
            name=data["name"],
            version=data["version"],
            priority=ModelPriority(data.get("priority", ModelPriority.MEDIUM.value)),
            status=ModelStatus(data.get("status", ModelStatus.ACTIVE.value)),
            context_window=data.get("context_window", 4096),
            max_output_tokens=data.get("max_output_tokens", 2048),
            supported_features=data.get("supported_features", []),
            metadata=data.get("metadata", {}),
            created_at=data.get("created_at", time.time()),
            updated_at=data.get("updated_at", time.time()),
            usage_count=data.get("usage_count", 0),
            total_tokens_used=data.get("total_tokens_used", 0),
            total_cost=data.get("total_cost", 0.0),
            avg_latency=data.get("avg_latency", 0.0),
            error_rate=data.get("error_rate", 0.0)
        )