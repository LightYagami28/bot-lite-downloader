# Kubernetes manifests — bot-lite-downloader

Manifests in this directory deploy the bot (single replica) with its embedded
WebApp dashboard, backed by a PersistentVolumeClaim for the SQLite database.

## Contents

- `namespace.yaml` — dedicated namespace `bot-lite-downloader`
- `configmap.yaml` — non-sensitive configuration
- secrets — created outside git from the local `.env` file (see below)
- `deployment.yaml` — Deployment with security context, resources, probes
- `service.yaml` — ClusterIP Service (port 8080)
- `pvc.yaml` — PersistentVolumeClaim for `/data` (SQLite)
- `ingress.yaml` — Ingress with TLS via cert-manager

## Prerequisites

- Kubernetes cluster with an Ingress controller (e.g. `ingress-nginx`)
- cert-manager installed with a `ClusterIssuer` named `letsencrypt-prod`
- A default StorageClass (or set `storageClassName` in `pvc.yaml`)
- Container image pinned by digest in `deployment.yaml`
  (`ghcr.io/lightyagami28/bot-lite-downloader@sha256:...`). CI publishes one
  immutable digest per commit; to upgrade, take the digest printed by the Docker
  Scout workflow for the new commit and update `deployment.yaml`.

## Deploy

1. Edit `configmap.yaml`:
   - set `WEBAPP_PUBLIC_URL` to your public HTTPS URL (must match the Ingress host)
2. Create the Secret from the local `.env` file (never commit it):

```bash
kubectl -n bot-lite-downloader create secret generic bot-lite-downloader-secrets \
  --from-env-file=.env
```

   Alternatively let a secret manager (for example External Secrets Operator)
   provision the same `bot-lite-downloader-secrets` Secret. The required keys are
   `API_ID`, `API_HASH`, `BOT_TOKEN` and `SUDO_USERS`. No secret values or
   placeholders are stored in this repository.
3. Apply the manifests:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

Or apply the whole folder at once:

```bash
kubectl apply -f k8s/
```

1. Verify:

```bash
kubectl -n bot-lite-downloader get pods,svc,ingress,pvc
kubectl -n bot-lite-downloader logs deploy/bot-lite-downloader
```

## Notes

- The Deployment uses `strategy: Recreate` because the PVC is `ReadWriteOnce`.
- The WebApp dashboard is only enabled when `WEBAPP_PUBLIC_URL` is set (HTTPS).
- The bot runs as a non-root user with a read-only root filesystem; an
  `emptyDir` is mounted at `/tmp` for download staging (the app uses `tempfile`).
- The Pod does not mount a service account token: the bot needs no Kubernetes
  API access.
- Credentials are mounted as read-only files under `/etc/botlite-secrets` and read
  by the application directly; they are not injected as environment variables.
- For Helm-based installs, package these manifests into a chart or use
  `helm create` and move the resources under `templates/`. No chart is shipped
  in this repository.
