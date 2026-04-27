# Security Review: Custom Component System

## Executive Summary

The current custom component runtime is **not strongly isolated**. It uses a subprocess plus restricted builtins, which is better than in-process execution, but it is not a security boundary against malicious Python code.

If your requirement is:

> custom components can access **only** what is explicitly handed to them

then the current design does not fully satisfy that requirement. A containerized sandbox with OS-level isolation, seccomp/capability restrictions, and strict I/O contracts is required.

---

## Scope Reviewed

- `pipeline/components/sandbox.py`
- `pipeline/components/sandbox_bootstrap.py`
- `pipeline/components/custom_store.py`
- `pipeline/components/__init__.py`
- `ai/tools/components.py`

---

## Current Architecture (as implemented)

1. Custom component code is persisted as JSON files at:
   - `custom_components/<component_id>.json`
   - Structure: `{ "manifest": {...}, "code": "..." }`
2. Registry loads built-ins and custom components from disk (`pipeline/components/__init__.py`).
3. Runtime executes custom code by launching:
   - `python sandbox_bootstrap.py` as a subprocess
   - payload over stdin (`inputs`, `config`, `code`)
4. `sandbox_bootstrap.py` runs `exec(code, globals_dict)` with restricted builtins and exposes only `pipeline.input/config/output/log`.

---

## Findings (Security Perspective)

### 1) Python `exec` with restricted builtins is not a hard sandbox (High)

Even with blocked `import` and reduced builtins, CPython object graph/introspection tricks can often recover powerful primitives in "restricted exec" environments. Historically, this model is brittle against adversarial code.

**Impact:** malicious component code may escape intended restrictions (file/network/process access), depending on runtime hardening.

**Status:** unresolved by current design; requires OS/container isolation.

---

### 2) Subprocess isolation lacks OS-level confinement (High)

`sandbox.py` starts the bootstrap with plain `subprocess.run(...)` under the host Python interpreter.

No hard boundary exists for:
- filesystem namespace
- network namespace
- Linux capabilities
- seccomp syscall filtering
- memory/process quotas beyond timeout

**Impact:** if code escapes language restrictions, host access is possible.

---

### 3) Environment reduction is partial hardening only (Medium)

Current runtime removes parent env except `PYTHONSAFEPATH` and limits API surface. This reduces accidental leakage but is not sufficient to enforce zero access.

**Impact:** improves hygiene, not strong isolation.

---

### 4) Good improvements already made (Positive)

Recently fixed/hardened:
- `qual_component_run_debug`: `json.loads(config_json)` bug fixed.
- custom component file writes are now atomic (temp + rename).
- malformed custom files are skipped with warning logs instead of breaking load flow.

These are reliability and operational improvements, but they do not materially change sandbox security guarantees.

---

## Threat Model and Desired Security Properties

### Threat model

Assume component code can be:
- user-authored but buggy
- intentionally malicious
- supply-chain contaminated

### Required properties

1. **No ambient authority**: component receives only explicit `inputs` + `config`.
2. **No host FS access**: no reads/writes outside isolated scratch.
3. **No network egress/ingress** by default.
4. **No host process/privilege escalation**.
5. **Resource control**: CPU/memory/time/process caps.
6. **Auditable execution**: image hash, policy, input/output metadata, logs.

---

## Target Architecture: Containerized Component Runtime

## Recommendation

Run each custom component in a **short-lived container** (or microVM) with strict policy.

### If the backend itself is already running in Docker

This is an important deployment detail. "Containerizing components" from inside a container has different security implications:

1. **Do not mount the host Docker socket (`/var/run/docker.sock`) into the backend container** unless absolutely required.
   - Any process with socket access is effectively root-equivalent on the host.
   - This can fully break isolation goals.

2. Preferred execution patterns:
   - **Best (orchestrated):** backend submits component-run jobs to a dedicated sandbox worker service (Kubernetes Job/Pod, Nomad task, etc.).
   - **Good (single host):** dedicated runner daemon outside backend process boundary with a strict API; backend calls runner over localhost/private network.
   - **Avoid for prod:** Docker-in-Docker privileged setup from backend container.

3. Isolation must be applied at the **component-runner boundary**, not just "backend is in a container."
   - Backend container isolation does not prevent custom code from attacking sibling workloads if the backend can spawn privileged children or access host runtime controls.

4. Recommended trust split:
   - **Backend API container:** no capability to create raw containers directly.
   - **Sandbox runner service:** minimal API (`run_component(payload, policy)`), enforces policy and resource limits, no broad host access.

5. Network model:
   - backend -> runner over authenticated internal channel.
   - runner launches ephemeral sandbox with `network=none` by default (or explicit allowlist).

---

## Deployment Reference (Backend-in-Container)

### Option A (recommended): Runner sidecar/service

- Backend container remains unprivileged.
- Separate runner service handles sandbox execution.
- Runner can use:
  - rootless container runtime,
  - seccomp/AppArmor profiles,
  - strict cgroups and tmpfs.

### Option B: Kubernetes-native jobs/pods

- Backend creates a CR/job request (not direct Docker socket access).
- Admission policy enforces:
  - non-root
  - no privilege escalation
  - dropped caps
  - read-only root FS
  - no hostPath mounts
  - `networkPolicy` deny egress by default

### Option C (interim): In-container subprocess sandbox (current)

- Keep current subprocess mode only as fallback/dev.
- Mark as **not strong isolation** in production.
- Gate with explicit env flag and warning logs.

### Runtime options

- **Strongest**: Firecracker/Kata microVM per run
- **Practical**: rootless OCI container (containerd/Docker) + seccomp + AppArmor + read-only FS + no network
- **Defense-in-depth**: gVisor runtime (`runsc`) for syscall mediation

### Container policy baseline

1. `--network=none`
2. `--read-only`
3. `--pids-limit=64` (or lower)
4. memory/cpu limits (example: `--memory=256m --cpus=0.5`)
5. `--cap-drop=ALL`
6. non-root user (`runAsNonRoot`, uid != 0)
7. `no-new-privileges`
8. hardened seccomp profile (deny risky syscalls)
9. AppArmor/SELinux profile
10. mount only:
    - one tmpfs workdir (`/work`, size-limited)
    - no host bind mounts by default

### Data handoff model (explicit only)

Replace ambient access with explicit contract:

- Parent process passes one JSON payload via stdin:
  - `{inputs, config, code, limits, run_id}`
- Component returns one JSON result via stdout:
  - `{ok, outputs, logs}`
- Enforce max sizes:
  - max payload bytes
  - max logs lines/bytes
  - max output bytes
- Reject non-JSON-serializable outputs.

No file or network channels are available unless explicitly enabled by policy.

---

## Policy Model (Per Component)

Add an explicit execution policy in manifest (or adjacent policy registry):

- `network_access`: `none` (default), `allowlist` (future)
- `filesystem_access`: `none` (default), `scratch_only`
- `max_memory_mb`, `max_cpu_ms`, `timeout_seconds`
- `max_output_bytes`, `max_log_lines`
- `handles_sensitive_data`

**Default should be deny-all**.

### Data-residency guardrail: custom components cannot be terminal sinks

To prevent custom code from being the final data resting point in the graph, enforce:

- Any terminal node (node with no outgoing edges) **must not** be a custom component.
- Terminal nodes should be approved built-in sinks (e.g., `box`, `grid`) or an explicitly allowlisted audited sink type.

Implementation status in backend validation:

- Pipeline save/create validation now rejects graphs where a terminal node resolves to a custom component id.
- Validation also resolves legacy `type="stage"` nodes by node id when that id matches a known component type, preventing bypass via legacy shape.

---

## Control Plane & Persistence Considerations

Current file persistence (`custom_components/*.json`) is acceptable for development/small deployments, with caveats:

1. Add integrity metadata:
   - code hash (sha256)
   - created/updated by + timestamp
2. Optional signature verification for production (trusted publisher model).
3. Lock down directory permissions:
   - writable only by service account
   - non-world-readable if sensitive configs are present
4. Keep atomic writes (already implemented).

---

## Migration Plan

### Phase 1 (Immediate hardening)

- Keep current API/manifest shape.
- Introduce `container_sandbox_runner.py` behind feature flag:
  - `CUSTOM_COMPONENT_RUNTIME=container|subprocess`
- Implement deny-all container profile (`network=none`, read-only, caps dropped).
- Add resource quotas and I/O size limits.

### Phase 2 (Policy-aware runtime)

- Extend manifest/policy schema with runtime controls.
- Enforce policy at run time with explicit allowlists.
- Add run audit records (policy used, image digest, duration, resource usage, exit code).

### Phase 3 (Production-grade isolation)

- Move to gVisor or microVM runtime for stronger tenant isolation.
- Add signed component bundles and admission checks.
- Add continuous sandbox escape testing (red-team test corpus).

---

## Validation / Security Test Checklist

1. Attempt file read (`/etc/passwd`, project files) -> must fail.
2. Attempt file write outside scratch -> must fail.
3. Attempt outbound DNS/TCP/HTTP -> must fail.
4. Attempt `import os`, `subprocess`, `socket` escapes -> fail/blocked.
5. Attempt fork bomb / heavy memory allocation -> killed by limits.
6. Attempt oversized stdout/log payload -> truncated/rejected safely.
7. Verify only explicit inputs/config appear in container.
8. Verify no host env secrets visible in container.

---

## Bottom Line

- **Today:** reasonably structured component model, but **not a strong security sandbox**.
- **Needed for your requirement:** containerized (or microVM) execution with deny-all defaults and explicit policy-driven grants.
- **Recommended next step:** implement container runner behind a feature flag, then switch default runtime after validation.

