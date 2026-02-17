# Helm Repository Setup Guide

Host a Helm chart repository at `charts.preloop.ai` so users can install Preloop with:

```bash
helm repo add preloop https://charts.preloop.ai
helm repo update
helm install preloop preloop/preloop
```

## Option A: GitHub Pages (recommended)

1. **Create repo**: `preloop/helm-charts` on GitHub
2. **Push chart assets**:
   ```bash
   # After running scripts/release.sh
   cp helm-releases/preloop-*.tgz helm-releases/index.yaml /path/to/helm-charts-repo/
   cd /path/to/helm-charts-repo
   git add . && git commit -m "release: preloop 0.8.0" && git push
   ```
3. **Enable GitHub Pages**: Settings > Pages > Branch: `main`, folder: `/ (root)`
4. **Configure DNS**: Add CNAME record `charts.preloop.ai` → `preloop.github.io`
5. **Add CNAME file**: Create a `CNAME` file in the repo root containing `charts.preloop.ai`

## Option B: S3 + CloudFront

1. **Create S3 bucket**: `charts.preloop.ai`
2. **Upload chart assets**:
   ```bash
   aws s3 sync helm-releases/ s3://charts.preloop.ai/ --acl public-read
   ```
3. **Create CloudFront distribution** pointing to the S3 bucket
4. **Configure DNS**: CNAME `charts.preloop.ai` → CloudFront distribution domain
5. **SSL**: Use ACM certificate for `charts.preloop.ai`

## Option C: Nginx on Existing Kubernetes Cluster

1. **Create namespace and deployment**:
   ```yaml
   # Deploy a simple nginx serving the chart files
   apiVersion: apps/v1
   kind: Deployment
   metadata:
     name: helm-repo
     namespace: helm-repo
   spec:
     replicas: 1
     selector:
       matchLabels:
         app: helm-repo
     template:
       spec:
         containers:
           - name: nginx
             image: nginx:alpine
             ports:
               - containerPort: 80
             volumeMounts:
               - name: charts
                 mountPath: /usr/share/nginx/html
         volumes:
           - name: charts
             configMap:
               name: helm-charts
   ```
2. **Create Ingress** with `charts.preloop.ai` hostname + TLS via cert-manager
3. **Upload charts** as ConfigMap or use a PVC with an init container

## CI/CD Automation

Add to `.github/workflows/release.yml`:

```yaml
publish-helm:
  needs: [build-docker]
  runs-on: ubuntu-latest
  steps:
    - uses: actions/checkout@v4
    - name: Package and publish
      run: |
        helm package helm/preloop --destination helm-releases/
        helm repo index helm-releases/ --url https://charts.preloop.ai
    - name: Push to helm-charts repo
      uses: peaceiris/actions-gh-pages@v4
      with:
        deploy_key: ${{ secrets.HELM_CHARTS_DEPLOY_KEY }}
        external_repository: preloop/helm-charts
        publish_dir: ./helm-releases
```
