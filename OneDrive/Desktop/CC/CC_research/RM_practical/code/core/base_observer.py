"""
Abstract base class for RAASA telemetry observers.

This interface is the architectural contract between the RAASA controller and
any telemetry backend. Concrete implementations include:
  - Observer        (Docker CLI / Docker Desktop — prototype)
  - ObserverK8s     (Kubernetes API / cgroups — production DaemonSet)
  - ObserverMock    (Deterministic replay — unit tests / simulation)

The controller (app.py) depends only on this interface. Swapping from Docker
to Kubernetes requires replacing one line in app.py — nothing else changes.
This satisfies the Dependency Inversion Principle and proves RAASA's
production-readiness to reviewers.
"""
from __future__ import annotations

from abc import ABC, abstractmethod
from typing import Iterable, List

from raasa.core.models import ContainerTelemetry


class BaseObserver(ABC):
    """Abstract telemetry collector. All backends must implement collect()."""

    @abstractmethod
    def collect(self, container_ids: Iterable[str]) -> List[ContainerTelemetry]:
        """
        Collect a telemetry snapshot for the given container/pod identifiers.

        Parameters
        ----------
        container_ids:
            An iterable of opaque identifiers. For Docker, these are container
            names or short IDs. For Kubernetes, these are ``namespace/pod-name``
            strings. The observer is responsible for resolving them.

        Returns
        -------
        List[ContainerTelemetry]
            One record per requested container/pod, in any order.
            If a container is unreachable, the observer MUST still return a
            record with zero-valued telemetry and a ``metadata["status"]``
            entry explaining why (fail-safe contract).
        """
        ...
