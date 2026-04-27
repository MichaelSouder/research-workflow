"""
Component base: RunContext and execution contract.
Every pipeline component (built-in or custom) implements run(inputs, config, context) -> dict.
"""

from dataclasses import dataclass, field
from logging import Logger
from typing import Any

# Port types for manifest (documentation / optional validation)
PORT_TYPE_RECORDS = "records"
PORT_TYPE_FILE_PATH = "file_path"
PORT_TYPE_BLOB = "blob"
PORT_TYPE_ANY = "any"

DEFAULT_PORT_ID = "default"


@dataclass
class InputPort:
    """Declared input port for a component."""

    id: str
    label: str | None = None
    type: str = PORT_TYPE_ANY
    required: bool = True


@dataclass
class OutputPort:
    """Declared output port for a component."""

    id: str
    label: str | None = None
    type: str = PORT_TYPE_ANY


@dataclass
class ComponentManifest:
    """Metadata for a pipeline component."""

    id: str
    label: str
    description: str = ""
    category: str = "processing"  # sources | processing | sinks | integration | custom
    inputs: list[InputPort] = field(default_factory=list)
    outputs: list[OutputPort] = field(default_factory=list)
    config_keys: list[str] = field(default_factory=list)
    source: str = "builtin"  # builtin | custom
    version: str | None = None
    handles_sensitive_data: bool = False
    """If True, this component's inputs/outputs may contain PII or sensitive data. When the data proxy is enabled (MCP), such data is masked for AI users; the real app always uses unmasked data."""


@dataclass
class RunContext:
    """Context provided to every component at run time."""

    run_id: str | None = None
    study_id: str | None = None
    logger: Logger | None = None
    workspace_path: str | None = None
    export_dir: str | None = None
    extra: dict[str, Any] = field(default_factory=dict)

    def log(self, message: str, level: str = "info") -> None:
        if self.logger is None:
            return
        if level == "debug":
            self.logger.debug(message)
        elif level == "warning":
            self.logger.warning(message)
        elif level == "error":
            self.logger.error(message)
        else:
            self.logger.info(message)


# Execution contract (for documentation):
# Every component implements: run(inputs: dict, config: dict, context: RunContext) -> dict
# Returns: map from output port id to value (JSON-serializable for custom components).
