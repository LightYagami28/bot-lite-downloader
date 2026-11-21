# Kubernetes manifests — bot-lite-downloader

Manifests in this directory deploy the bot (single replica) with its embedded
WebApp dashboard, backed by a PersistentVolumeClaim for the SQLite database.

## Contents

- `namespace.yaml` — dedicated namespace `bot-lite-downloader`
- `configmap.yaml` — non-sensitive configuration
- `secret.yaml` — **template** with placeholders; replace before applying
- `deployment.yaml` — Deployment with security context, resources, probes
- `service.yaml` — ClusterIP Service (port 8080)
- `pvc.yaml` — PersistentVolumeClaim for `/data` (SQLite)
- `ingress.yaml` — Ingress with TLS via cert-manager

## Prerequisites

- Kubernetes cluster with an Ingress controller (e.g. `ingress-nginx`)
- cert-manager installed with a `ClusterIssuer` named `letsencrypt-prod`
- A default StorageClass (or set `storageClassName` in `pvc.yaml`)
- Container image `bot-lite-downloader:latest` available to the cluster
  (build and push to your registry, then update `image:` in `deployment.yaml`)

## Deploy

1. Edit `configmap.yaml`:
   - set `WEBAPP_PUBLIC_URL` to your public HTTPS URL (must match the Ingress host)
2. Edit `secret.yaml` and replace all `REPLACE_ME` values.
3. Apply the manifests:

```bash
kubectl apply -f k8s/namespace.yaml
kubectl apply -f k8s/configmap.yaml
kubectl apply -f k8s/secret.yaml
kubectl apply -f k8s/pvc.yaml
kubectl apply -f k8s/deployment.yaml
kubectl apply -f k8s/service.yaml
kubectl apply -f k8s/ingress.yaml
```

Or apply the whole folder at once:

```bash
kubectl apply -f k8s/
```

4. Verify:

```bash
kubectl -n bot-lite-downloader get pods,svc,ingress,pvc
kubectl -n bot-lite-downloader logs deploy/bot-lite-downloader
```

## Notes

- The Deployment uses `strategy: Recreate` because the PVC is `ReadWriteOnce`.
- The WebApp dashboard is only enabled when `WEBAPP_PUBLIC_URL` is set (HTTPS).
- The bot runs as a non-root user; the image already owns `/data`.
- For Helm-based installs, package these manifests into a chart or use
  `helm create` and move the resources under `templates/`. No chart is shipped
  in this repository.