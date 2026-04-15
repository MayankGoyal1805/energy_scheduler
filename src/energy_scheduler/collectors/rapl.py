from __future__ import annotations

import time
from dataclasses import dataclass
from pathlib import Path

from energy_scheduler.collectors.base import Collector
from energy_scheduler.models import CollectorReading


@dataclass(slots=True, frozen=True)
class RaplDomain:
    name: str
    path: Path
    max_energy_range_uj: int | None

    @property
    def energy_path(self) -> Path:
        return self.path / "energy_uj"


class RaplCollector(Collector):
    name = "rapl"

    def __init__(self, powercap_root: Path = Path("/sys/class/powercap")) -> None:
        self._powercap_root = powercap_root
        self._domains: list[RaplDomain] = []
        self._start_energy: dict[str, int] = {}
        self._started_at_s = 0.0
        self._unavailable_reason = ""
        self._skipped_domains: dict[str, str] = {}

    def start(self) -> None:
        discovered_domains = self._discover_domains()
        self._domains = []
        self._start_energy = {}
        self._unavailable_reason = ""
        self._skipped_domains = {}
        for domain in discovered_domains:
            try:
                self._start_energy[domain.name] = self._read_energy_uj(domain)
            except OSError as error:
                self._skipped_domains[domain.name] = (
                    f"cannot read {domain.energy_path}: {error.strerror or error}"
                )
                continue
            self._domains.append(domain)

        if not self._domains:
            if discovered_domains and self._skipped_domains:
                first_reason = next(iter(self._skipped_domains.values()))
                self._unavailable_reason = first_reason
            else:
                self._unavailable_reason = "no intel-rapl energy_uj files found under /sys/class/powercap"
        self._started_at_s = time.perf_counter()

    def stop(self) -> CollectorReading:
        elapsed_s = max(time.perf_counter() - self._started_at_s, 0.0)
        if not self._domains:
            reason = self._unavailable_reason
            if not reason:
                reason = "no intel-rapl energy_uj files found under /sys/class/powercap"
            return CollectorReading(
                collector_name=self.name,
                metrics={
                    "available": 0,
                    "reason": reason,
                },
            )

        metrics: dict[str, float | int | str] = {
            "available": 1,
            "domain_count": len(self._domains),
            "elapsed_s": elapsed_s,
        }
        if self._skipped_domains:
            metrics["available_partial"] = 1
            metrics["skipped_domain_count"] = len(self._skipped_domains)
            metrics["skipped_domains"] = "; ".join(
                f"{name}: {reason}" for name, reason in sorted(self._skipped_domains.items())
            )
        total_package_energy_uj = 0

        for domain in self._domains:
            start_uj = self._start_energy[domain.name]
            try:
                end_uj = self._read_energy_uj(domain)
            except OSError as error:
                self._skipped_domains[domain.name] = (
                    f"cannot read {domain.energy_path}: {error.strerror or error}"
                )
                continue
            delta_uj = self._energy_delta_uj(
                start_uj=start_uj,
                end_uj=end_uj,
                max_energy_range_uj=domain.max_energy_range_uj,
            )
            safe_name = self._safe_metric_name(domain.name)
            metrics[f"{safe_name}_energy_uj"] = delta_uj
            metrics[f"{safe_name}_energy_j"] = delta_uj / 1_000_000
            if elapsed_s > 0:
                metrics[f"{safe_name}_average_power_w"] = (delta_uj / 1_000_000) / elapsed_s
            if domain.name.startswith("package-"):
                total_package_energy_uj += delta_uj

        if self._skipped_domains:
            metrics["available_partial"] = 1
            metrics["skipped_domain_count"] = len(self._skipped_domains)
            metrics["skipped_domains"] = "; ".join(
                f"{name}: {reason}" for name, reason in sorted(self._skipped_domains.items())
            )

        if total_package_energy_uj:
            metrics["package_energy_uj"] = total_package_energy_uj
            metrics["package_energy_j"] = total_package_energy_uj / 1_000_000
            if elapsed_s > 0:
                metrics["package_average_power_w"] = (
                    total_package_energy_uj / 1_000_000
                ) / elapsed_s

        return CollectorReading(collector_name=self.name, metrics=metrics)

    def _discover_domains(self) -> list[RaplDomain]:
        if not self._powercap_root.exists():
            return []

        domains: list[RaplDomain] = []
        for energy_path in sorted(self._powercap_root.glob("intel-rapl*/**/energy_uj")):
            domain_path = energy_path.parent
            name = self._read_name(domain_path)
            max_energy_range_uj = self._read_optional_int(domain_path / "max_energy_range_uj")
            domains.append(
                RaplDomain(
                    name=name,
                    path=domain_path,
                    max_energy_range_uj=max_energy_range_uj,
                )
            )
        return domains

    def _read_name(self, domain_path: Path) -> str:
        name_path = domain_path / "name"
        if name_path.exists():
            name = name_path.read_text(encoding="utf-8").strip()
            if name:
                return name
        return domain_path.name

    def _read_energy_uj(self, domain: RaplDomain) -> int:
        return int(domain.energy_path.read_text(encoding="utf-8").strip())

    def _read_optional_int(self, path: Path) -> int | None:
        if not path.exists():
            return None
        text = path.read_text(encoding="utf-8").strip()
        if not text:
            return None
        return int(text)

    def _energy_delta_uj(
        self,
        *,
        start_uj: int,
        end_uj: int,
        max_energy_range_uj: int | None,
    ) -> int:
        if end_uj >= start_uj:
            return end_uj - start_uj
        if max_energy_range_uj is None:
            return 0
        return (max_energy_range_uj - start_uj) + end_uj

    def _safe_metric_name(self, name: str) -> str:
        return (
            name.lower()
            .replace(" ", "_")
            .replace("-", "_")
            .replace(":", "_")
        )
