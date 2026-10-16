# Track: containers → Kubernetes

Every module is concept → hands-on in this project → check yourself. You run the commands; Claude explains them.
Tick a module once you can answer its questions without notes.

## Part 1: Docker basics

### [ ] 1. What a container is
- **Concept:** a normal process, isolated by the Linux kernel. *Namespaces* limit what it sees (files, network, other processes); *cgroups* limit what it uses (CPU, RAM). Unlike a VM there's no second OS, so it starts in milliseconds and stays small. On Windows, Docker runs a small Linux VM through WSL2.
- **Hands-on:** `docker run hello-world`, `docker run -it --rm python:3.12-slim python`, `docker ps`, `docker logs`, `docker exec`, `docker stop`, `docker rm`.
- **Check yourself:** container vs VM? What happens to files written inside a container when it's removed?

### [ ] 2. Images
- **Concept:** an image is a read-only template made of stacked **layers**; a container is a running instance of it, plus a thin writable layer. Images come from a **registry** (Docker Hub, GHCR). A **tag** (`pg17`) can move to a new image; a **digest** (`sha256:…`) never changes.
- **Hands-on:** `docker pull pgvector/pgvector:pg17`, `docker image ls`, `docker history`, `docker inspect`.
- **Check yourself:** why does pulling a second image that shares layers go faster? Why pin by digest in production?

### [ ] 3. Volumes, ports, networks
- **Concept:** containers are disposable, so data lives in **volumes** (our `pgdata`). A **port mapping** (`5432:5432`) exposes a container port on your machine. Containers on the same network reach each other by service name (`db:5432`).
- **Hands-on:** `docker compose up -d db`, `docker compose exec db psql -U pm`, remove the container and see the data survive, `docker volume ls`.
- **Check yourself:** why does the backend in Compose use `db` as the host but your laptop uses `localhost`?

### [ ] 4. Docker Compose
- **Concept:** one YAML file that runs several containers together, with healthchecks and start order.
- **Hands-on:** read our `docker-compose.yml`; add the backend as a second service; `depends_on: condition: service_healthy`.
- **Check yourself:** what does a healthcheck add over "container is running"?

## Part 2: Building images

### [ ] 5. Writing a Dockerfile
- **Concept:** a recipe for an image. **Multi-stage** builds compile in one stage and copy only the result into a slim final image. Ordering for **layer cache**: dependencies first, code last. `.dockerignore`, a **non-root** user, `HEALTHCHECK`.
- **Hands-on:** Dockerfile for the backend with uv; compare image sizes; break the cache on purpose and watch the rebuild time.
- **Check yourself:** why copy `uv.lock` before the code? Why not run as root?

### [ ] 6. Image security + registries
- **Concept:** images carry OS packages with CVEs. Scan them (Trivy), use small base images, never bake secrets into layers, push to a registry with immutable tags.
- **Hands-on:** `trivy image`, push to GHCR, inspect layers for leaked files.
- **Check yourself:** why is `ENV API_KEY=…` in a Dockerfile a leak even if you delete it in a later layer?

### [ ] 7. Containers in CI
- **Concept:** CI builds the image once, tests it, and promotes the same image to staging and prod ("build once, deploy many").
- **Hands-on:** GitHub Actions: Postgres service container for tests, `docker build` with cache, push on `main`.
- **Check yourself:** why not rebuild the image for production?

## Part 3: Running in production

### [ ] 8. Production-ready containers
- **Concept:** 12-factor apps: config from env, logs to stdout (we already do JSON), stateless processes, **graceful shutdown** on SIGTERM, CPU/memory limits, restart policies.
- **Hands-on:** send SIGTERM and watch `app.shutdown`; set memory limits and watch the OOM kill.
- **Check yourself:** what happens to in-flight requests when a container is stopped?

### [ ] 9. Scaling + parallel deployment
- **Concept:** **horizontal scaling** means more replicas behind a load balancer; this needs stateless apps. Workers scale in parallel safely because jobs are claimed with `SKIP LOCKED`. Deployment strategies:
  - **rolling:** replace replicas a few at a time
  - **blue-green:** switch all traffic to a new copy at once
  - **canary:** send a small % of traffic to the new version first

  **Zero-downtime migrations** use expand → migrate → contract.
- **Hands-on:** `docker compose up --scale worker=3` and watch jobs split across workers; a rolling update with no failed requests.
- **Check yourself:** why can't you rename a column in one deploy without downtime?

## Part 4: Kubernetes

### [ ] 10. Kubernetes fundamentals
- **Concept:** a system that keeps the running state matching the desired state you declare in YAML.

  | Object | What it is |
  |---|---|
  | Cluster, node | the machines |
  | Pod | one or more containers scheduled together |
  | Deployment, ReplicaSet | keeps N pods alive and handles updates |
  | Service | stable address for a set of pods |
  | Ingress | HTTP entry point from outside |
  | ConfigMap, Secret | configuration and credentials |
  | Probes | our `/health` = liveness, `/health/db` = readiness |
  | Requests, limits | CPU and memory per pod |
  | HPA | autoscaling |
- **Hands-on:** local cluster with **kind**; `kubectl apply` the backend + worker; kill a pod and watch it come back; scale to 3.
- **Check yourself:** what does k8s do when readiness fails vs when liveness fails?

### [ ] 11. Kubernetes in practice
- **Concept:** **Helm** packages manifests as charts, **namespaces** separate environments, a **Job** runs migrations before a rollout, **CronJob** runs scheduled work, **StatefulSet** runs databases (and why we still use managed Postgres).
- **Hands-on:** Helm chart for the app; `kubectl rollout status` / `rollout undo`; migration Job; HPA under a k6 load test.
- **Check yourself:** how do you roll back a bad release in under a minute?

### [ ] 12. GitOps + managed Kubernetes
- **Concept:** **GitOps** (Argo CD): the cluster syncs itself from a git repo. Managed k8s (EKS, GKE, AKS) vs simpler platforms (Cloud Run, Fly.io, ECS). When *not* to use k8s: cost and operational load at small scale.
- **Hands-on:** Argo CD on kind syncing our Helm chart; write the ADR "k8s or not for prod".
- **Check yourself:** for this app at 100 users, k8s or Cloud Run? Defend it with cost and effort numbers.
