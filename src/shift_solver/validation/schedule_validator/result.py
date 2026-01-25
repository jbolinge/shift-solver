"""ValidationResult dataclass for schedule validation."""

from dataclasses import dataclass, field
from typing import Any


@dataclass
class ValidationResult:
    """Result of schedule validation."""

    is_valid: bool
    violations: list[dict[str, Any]]
    warnings: list[dict[str, Any]] = field(default_factory=list)
    statistics: dict[str, Any] = field(default_factory=dict)

    def add_violation(
        self, violation_type: str, message: str, severity: str = "error", **details: Any
    ) -> None:
        """Add a violation to the result."""
        self.violations.append(
            {
                "type": violation_type,
                "message": message,
                "severity": severity,
                **details,
            }
        )
        if severity == "error":
            self.is_valid = False

    def add_warning(self, violation_type: str, message: str, **details: Any) -> None:
        """Add a warning to the result."""
        self.warnings.append(
            {
                "type": violation_type,
                "message": message,
                "severity": "warning",
                **details,
            }
        )
