# RAASA Agent — Production Container Image
#
# Multi-stage build to minimize final image size.
# Stage 1 installs dependencies; Stage 2 copies only the runtime artifacts.
#
# Build:
#   docker build -t raasa/agent:1.0.0 -f raasa/k8s/Dockerfile .
#
# Test locally:
#   docker run --rm raasa/agent:1.0.0 python -m pytest tests/ -v

# ── Stage 1: Build dependencies ───────────────────────────────────────────────
FROM python:3.12-slim AS builder

WORKDIR /build

# Install build tools and dependencies
COPY requirements.txt .
RUN pip install --upgrade pip \
 && pip install --no-cache-dir --prefix=/install -r requirements.txt


# ── Stage 2: Minimal runtime image ───────────────────────────────────────────
FROM python:3.12-slim AS runtime

LABEL maintainer="RAASA Research Team"
LABEL description="Risk-Adaptive Autonomous Security Agent — DaemonSet Agent"
LABEL version="1.0.0"

# Non-root user for security (matches securityContext.runAsUser: 1000 in DaemonSet)
# Install iproute2 for `tc`, util-linux for `nsenter`, and bpftool for LSM map updates.
RUN apt-get update && apt-get install -y --no-install-recommends iproute2 util-linux bpftool \
 && rm -rf /var/lib/apt/lists/* \
 && groupadd -g 1000 raasa && useradd -u 1000 -g raasa -s /bin/sh -m raasa

WORKDIR /app

# Copy installed packages from builder
COPY --from=builder /install /usr/local

# Copy application code
COPY raasa/ ./raasa/
COPY tests/  ./tests/

# Pre-create directories the agent will write to
RUN mkdir -p raasa/logs raasa/models \
 && chown -R raasa:raasa /app

USER raasa

# Health check: verify the RAASA module is importable
HEALTHCHECK --interval=30s --timeout=5s --start-period=10s --retries=3 \
    CMD python -c "import raasa.core.app" || exit 1

# Default entrypoint: run the adaptive controller indefinitely
# Override via DaemonSet args[] for mode/scenario selection
ENTRYPOINT ["python", "-m", "raasa.core.app"]
CMD ["--mode", "raasa", "--config", "/etc/raasa/config.yaml"]
