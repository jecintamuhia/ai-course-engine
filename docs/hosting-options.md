# Hosting Options and Resource Estimates

Status: decision support only. No provider has been selected and no resource
has been provisioned. Cost figures must be confirmed by the owner before any
purchase.

A separate, non-production staging plan using Render, Vercel, Neon and Upstash
is in [`render-staging-deployment.md`](render-staging-deployment.md). It is a
proposal only and has not been provisioned.

The application is a standard Docker Compose workload:

- FastAPI API
- one ingestion worker
- one content worker
- PostgreSQL
- Redis
- Caddy for TLS and reverse proxying
- local persistent storage for uploaded documents

The application code is provider-neutral. OCI-specific instructions exist, but
nothing in the application requires an OCI SDK, OCI networking, or an OCI
managed service.

## 1. Minimum host requirements

| Requirement | Minimum | Preferred |
| --- | --- | --- |
| Operating system | Linux with Docker Engine and Compose v2 | Ubuntu LTS ARM64 or x86_64 |
| CPU | 2 vCPU | 2 vCPU |
| RAM | 4 GB | 12 GB |
| Persistent disk | 50 GB | 100 GB or more, plus off-host backups |
| Public network | inbound `80` and `443`; outbound HTTPS | fixed public IPv4 |
| Access | SSH for the deployment user | key-only SSH |
| TLS | Caddy with an authorized ACME email | automatic certificate renewal |
| Backups | separate off-host copy of database and storage archives | scheduled copy plus restore test |
| Database | PostgreSQL 17 | managed or self-hosted |
| Cache/queue | Redis 8 | self-hosted |

Do not publish PostgreSQL or Redis ports to the internet.

## 2. Planning estimates

These are sizing estimates, not measured production requirements. Measure the
host after ingestion and content-generation workloads are known.

| Component | CPU estimate | RAM estimate | Notes |
| --- | --- | --- | --- |
| Caddy | low | 64-128 MB | TLS, headers, access logs |
| API | 0.25-1 vCPU | 512 MB-1 GB | concurrent authoring/learner traffic |
| Ingestion worker | 0.25-1 vCPU | 256 MB-1 GB | PDF extraction and AI calls; monitor spikes |
| Content worker | 0.25-1 vCPU | 256 MB-1 GB | long AI calls; monitor spikes |
| PostgreSQL | 0.5-1 vCPU | 512 MB-2 GB | grows with documents, chunks, and learner records |
| Redis | low | 128-512 MB | queues and transient state |
| **Total** | **2 vCPU** | **4-8 GB practical; 12 GB preferred** | leave headroom for build and backup jobs |

Disk planning:

- container images: roughly 2-4 GB initially
- PostgreSQL data: depends on document chunks and learner activity
- uploaded documents: current local staging set is small, but plan for growth
- backups: keep at least two recent copies and copy them off the host
- Docker build cache can grow; prune only with an approved maintenance window

LLM inference is external. The host does not need GPU capacity. Egress to the
AI provider and Moodle must be allowed; inbound access is limited to `80`/`443`.

## 3. Options

### 3.1 Oracle Cloud Always Free

Potential fit:

- one `VM.Standard.A1.Flex`, up to 2 OCPU / 12 GB RAM
- Ubuntu ARM64
- 200 GB total block storage allowance
- 10 TB monthly egress
- no paid load balancer or NAT gateway

Constraints:

- A1 capacity is not guaranteed in every region or tenancy.
- The tenancy, MFA, and resource limits are unconfirmed.
- Only one VM should be assumed; do not design around multi-node failover.
- The free block-storage allowance must also cover boot and backup needs.
- Off-host backups are still required.

This is the preferred target **only if** capacity and ownership are confirmed.
The repository already includes OCI-oriented Compose and deployment guidance.

### 3.2 Alternative Docker VM

Any Linux VM with Docker, a persistent disk, public `80`/`443`, and outbound
HTTPS can run the same Compose stack. Examples include a small VPS or an
existing approved host. This option requires:

- owner approval of provider and monthly cost
- root/sudo access for Docker and Caddy
- a static public address and DNS approval
- a backup destination outside the VM

Do not select a provider or buy a plan merely because it appears in this
document. Obtain a current quote.

### 3.3 HostAfrica/cPanel

HostAfrica/cPanel manages DNS for `skillupactionafrica.co.ke`. Do not assume the
cPanel hosting account can run this Docker stack. Shared cPanel hosting commonly
does not provide root access, long-running Docker containers, arbitrary
inbound ports, or persistent process supervision. Use cPanel for DNS unless the
provider explicitly confirms a suitable container/VPS product.

### 3.4 Railway fallback

The Railway configuration remains in the repository:

- `backend/railway.toml`
- `backend/railway.content-worker.toml`

Current status: project creation was blocked by the free-plan resource limit.
Railway is a fallback only. Paid use requires owner approval. The API and
worker configuration should be re-checked before use because Railway limits,
volumes, and pricing can change.

### 3.5 Managed PostgreSQL and Redis

Optional. If a provider supplies managed PostgreSQL/Redis:

- set `DATABASE_URL` and `REDIS_URL`
- keep the application upload storage on a persistent disk
- confirm the managed service allows the required connections and backups
- verify restore procedures and egress costs
- do not assume managed backups satisfy the application's retention policy

The current Compose stack is simpler and cheaper for a single small deployment.

## 4. Comparison

| Criterion | OCI Always Free | Alternative Docker VM | Railway fallback |
| --- | --- | --- | --- |
| Cost predictability | free allowance, capacity risk | depends on quote | plan limits/pricing |
| Operational control | high | high | lower |
| Docker/Compose | yes | yes | provider-specific |
| Persistent local uploads | yes | yes | volume behavior must be checked |
| TLS | Caddy/ACME | Caddy/ACME | provider-managed |
| Multi-node resilience | no | no | provider-dependent |
| Current readiness | prepared, not provisioned | portable, not provisioned | blocked by plan limit |

## 5. Cost controls

- Do not create paid load balancers, NAT gateways, extra block volumes, or
  larger shapes without approval.
- Set an AI provider spend limit and monitor usage.
- Keep only necessary container images and prune old build cache on a schedule.
- Copy backups off the VM; do not rely on the same disk.
- Watch egress if documents or media are served directly.
- Revisit sizing after measuring real ingestion and learner traffic.

## 6. Portability checklist

Before moving to any host:

1. Confirm Linux, Docker Engine, and Compose v2.
2. Confirm inbound `80`/`443` and outbound HTTPS to AI/Moodle.
3. Prepare a persistent directory for `deploy/oci/data`.
4. Run `python3 validate_env.py`.
5. Run `docker compose ... config >/dev/null`.
6. Build or pull the API image for the host architecture.
7. Run migrations and verify readiness.
8. Take and restore a disposable backup before importing real data.
9. Register DNS only after owner approval.
10. Never copy production secrets into chat, tickets, source control, or logs.

## 7. Decision required

The owner must choose one of:

1. OCI Always Free, subject to capacity confirmation.
2. An approved alternative Docker VM with a confirmed quote.
3. Defer production hosting and continue local/staging validation.

No option is approved by this document.
