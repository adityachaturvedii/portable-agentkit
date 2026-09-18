"""Versioned, provider-neutral Phase 2 contracts. No policy from worker JSON."""

from dataclasses import asdict, dataclass, field
import math
from pathlib import Path
from typing import Any, Dict, List, Optional, Tuple


SCHEMA_VERSION = 1


@dataclass(frozen=True)
class Capability:
    state: str  # verified / unavailable / unknown
    evidence: str

    def __post_init__(self):
        if self.state not in ("verified", "unavailable", "unknown"):
            raise ValueError("invalid capability state")


@dataclass
class EngineCapabilities:
    engine: str
    executable: Optional[str]
    version: Optional[str]
    executable_sha256: Optional[str]
    features: Dict[str, Capability]
    authentication: Capability
    authentication_mode: str = "unknown"
    billing_mode: str = "unknown"
    paid_overflow: str = "unknown"
    provider_details: Dict[str, Any] = field(default_factory=dict)
    schema_version: int = SCHEMA_VERSION


@dataclass(frozen=True)
class ExecutionRequest:
    engine: str
    task_id: str
    prompt: str
    cwd: str
    timeout_seconds: float = 30.0
    max_output_bytes: int = 1048576
    model: Optional[str] = None
    mode: str = "model-only"
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if type(self.schema_version) is not int or self.schema_version != 1:
            raise ValueError("unsupported request schema version")
        if self.engine not in ("codex", "claude"):
            raise ValueError("unsupported engine")
        if not isinstance(self.task_id, str) or not self.task_id.strip() or len(self.task_id) > 128:
            raise ValueError("task_id must be a nonempty bounded string")
        if not isinstance(self.prompt, str) or not self.prompt.strip() or len(self.prompt.encode()) > 32768:
            raise ValueError("prompt must contain 1..32768 UTF-8 bytes")
        if type(self.timeout_seconds) not in (int, float) or not math.isfinite(self.timeout_seconds) or not 0.05 <= self.timeout_seconds <= 300:
            raise ValueError("timeout must be finite and between 0.05 and 300 seconds")
        if type(self.max_output_bytes) is not int or not 1024 <= self.max_output_bytes <= 4194304:
            raise ValueError("output bound must be 1 KiB..4 MiB")
        if self.mode not in ("model-only", "owned-code", "untrusted"):
            raise ValueError("unsupported execution mode")
        if not isinstance(self.cwd, str) or not Path(self.cwd).is_absolute():
            raise ValueError("cwd must be absolute")
        if self.model is not None and (not isinstance(self.model, str) or not self.model or self.model.startswith("-") or len(self.model) > 128):
            raise ValueError("invalid model identifier")

    @classmethod
    def from_dict(cls, value):
        if not isinstance(value, dict):
            raise ValueError("request must be an object")
        # Dataclass constructor rejects unknown fields, including billing/approval overrides.
        return cls(**value)


@dataclass(frozen=True)
class LivePolicy:
    """Trusted caller input, never deserialized from an ExecutionRequest.

    Default is blocked; the user can authorize subscription smoke tests.
    This is not an authenticated approval ledger (Phase 3).
    """
    subscription_smoke_authorized: bool = False
    evidence: str = "No trusted operator authorization supplied."


@dataclass(frozen=True)
class ExecutionBoundary:
    """Trusted, controller-created boundary for a disposable owned-code run."""
    workspace: str
    denied_read_paths: Tuple[str, ...]
    schema_version: int = SCHEMA_VERSION

    def __post_init__(self):
        if self.schema_version != SCHEMA_VERSION:
            raise ValueError("unsupported boundary schema version")
        paths = (self.workspace,) + tuple(self.denied_read_paths)
        if not self.denied_read_paths or any(not isinstance(p, str) or not Path(p).is_absolute() for p in paths):
            raise ValueError("boundary paths must be absolute and include denied paths")


@dataclass
class UsageObservation:
    input_tokens: Optional[int] = None
    output_tokens: Optional[int] = None
    cached_input_tokens: Optional[int] = None
    cache_creation_tokens: Optional[int] = None
    reasoning_tokens: Optional[int] = None
    estimated_cost_usd: Optional[float] = None
    billed_cost_usd: Optional[float] = None
    source: str = "unavailable"
    final: bool = False
    provider_details: Dict[str, Any] = field(default_factory=dict)


@dataclass
class CancellationStatus:
    requested: bool = False
    reason: Optional[str] = None
    term_sent: bool = False
    kill_sent: bool = False
    leader_reaped: bool = False
    process_group_gone: Optional[bool] = None
    scope: str = "POSIX process group; detached descendants and remote effects are not covered"


@dataclass
class ExecutionResult:
    engine: str
    task_id: str
    status: str
    error_class: Optional[str]
    exit_code: Optional[int]
    elapsed_seconds: float
    session_id: Optional[str] = None
    model: Optional[str] = None
    structured_output: Optional[Dict[str, Any]] = None
    final_text: Optional[str] = None
    usage: UsageObservation = field(default_factory=UsageObservation)
    cancellation: CancellationStatus = field(default_factory=CancellationStatus)
    artifacts: Dict[str, str] = field(default_factory=dict)
    provider_details: Dict[str, Any] = field(default_factory=dict)
    limitations: List[str] = field(default_factory=list)
    schema_version: int = SCHEMA_VERSION

    def to_dict(self):
        return asdict(self)
