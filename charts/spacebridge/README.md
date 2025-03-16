# SpaceBridge Helm Chart

This Helm chart deploys SpaceBridge, a Model Context Protocol (MCP) server that serves as a unified interface between Spacecode's infrastructure and multiple issue tracking systems.

## Prerequisites

- Kubernetes 1.19+
- Helm 3.2.0+
- PV provisioner support in the underlying infrastructure (if persistence is enabled)
- PostgreSQL with PGVector extension (either deployed as part of this chart or externally)

## Installing the Chart

To install the chart with the release name `spacebridge`:

```bash
# Add the SpaceCode Helm repository (if available)
# helm repo add spacecode https://charts.spacecode.ai
# helm repo update

# Install the chart from local path
helm install spacebridge ./charts/spacebridge
```

The command deploys SpaceBridge on the Kubernetes cluster in the default configuration. The [Parameters](#parameters) section lists the parameters that can be configured during installation.

## Uninstalling the Chart

To uninstall/delete the `spacebridge` deployment:

```bash
helm uninstall spacebridge
```

## Parameters

### Common parameters

| Name                | Description                                                                                         | Value           |
|---------------------|-----------------------------------------------------------------------------------------------------|-----------------|
| `replicaCount`      | Number of replicas                                                                                 | `1`             |
| `image.repository`  | SpaceBridge image repository                                                                       | `gitlab.spacecode.ai:5000/spacecode/spacebridge` |
| `image.tag`         | SpaceBridge image tag                                                                              | `latest`        |
| `image.pullPolicy`  | SpaceBridge image pull policy                                                                      | `IfNotPresent`  |
| `imagePullSecrets`  | Secret names for pulling images                                                                    | `[]`            |
| `nameOverride`      | String to partially override the name template                                                     | `""`            |
| `fullnameOverride`  | String to fully override the name template                                                         | `""`            |

### Service parameters

| Name                       | Description                                              | Value       |
|----------------------------|----------------------------------------------------------|-------------|
| `service.type`             | Service type                                             | `ClusterIP` |
| `service.port`             | Service port                                             | `8000`      |

### Ingress parameters

| Name                       | Description                                              | Value       |
|----------------------------|----------------------------------------------------------|-------------|
| `ingress.enabled`          | Enable ingress record generation                         | `false`     |
| `ingress.className`        | IngressClass that will be used                           | `""`        |
| `ingress.annotations`      | Annotations for the ingress record                        | `{}`        |
| `ingress.hosts`            | Hosts configuration for the ingress record               | See values.yaml |
| `ingress.tls`              | TLS configuration for the ingress record                 | `[]`        |

### Database parameters

| Name                               | Description                                           | Value       |
|------------------------------------|-------------------------------------------------------|-------------|
| `database.enabled`                 | Deploy PostgreSQL instance                            | `true`      |
| `database.external`                | Use external PostgreSQL instance                      | `false`     |
| `database.externalDatabase.host`   | External PostgreSQL host                             | `""`        |
| `database.externalDatabase.port`   | External PostgreSQL port                             | `5432`      |
| `database.externalDatabase.user`   | External PostgreSQL user                             | `""`        |
| `database.externalDatabase.password` | External PostgreSQL password                       | `""`        |
| `database.externalDatabase.database` | External PostgreSQL database                       | `""`        |
| `database.postgresql.auth.username` | PostgreSQL username                                 | `postgres`  |
| `database.postgresql.auth.password` | PostgreSQL password                                 | `postgres`  |
| `database.postgresql.auth.database` | PostgreSQL database                                 | `spacebridge` |
| `database.postgresql.service.port`  | PostgreSQL service port                             | `5432`      |
| `database.postgresql.persistence.enabled` | Enable PostgreSQL persistence                | `true`      |
| `database.postgresql.persistence.size`   | PostgreSQL persistence size                    | `1Gi`       |
| `database.postgresql.pgvector.enabled`   | Enable PGVector extension                      | `true`      |

### Environment parameters

| Name                           | Description                                           | Value       |
|--------------------------------|-------------------------------------------------------|-------------|
| `environment.host`             | Server host                                           | `0.0.0.0`   |
| `environment.port`             | Server port                                           | `8000`      |
| `environment.debug`            | Enable debug mode                                     | `false`     |
| `environment.jwtSecret`        | JWT secret key                                        | `change-this-in-production` |
| `environment.jwtAlgorithm`     | JWT algorithm                                         | `HS256`     |
| `environment.jwtExpireMinutes` | JWT expiration time in minutes                        | `60`        |
| `environment.logLevel`         | Log level                                             | `INFO`      |
| `environment.logFormat`        | Log format                                            | `json`      |

### Resource management parameters

| Name                           | Description                                           | Value       |
|--------------------------------|-------------------------------------------------------|-------------|
| `resources.limits.cpu`         | CPU resource limits                                   | `500m`      |
| `resources.limits.memory`      | Memory resource limits                                | `512Mi`     |
| `resources.requests.cpu`       | CPU resource requests                                 | `100m`      |
| `resources.requests.memory`    | Memory resource requests                              | `128Mi`     |

### Other parameters

| Name                           | Description                                           | Value       |
|--------------------------------|-------------------------------------------------------|-------------|
| `serviceAccount.create`        | Create a service account                              | `true`      |
| `serviceAccount.annotations`   | Annotations for the service account                   | `{}`        |
| `serviceAccount.name`          | The name of the service account                       | `""`        |
| `podAnnotations`               | Annotations for pods                                  | `{}`        |
| `podSecurityContext`           | Pod security context                                  | `{}`        |
| `securityContext`              | Container security context                            | `{}`        |
| `nodeSelector`                 | Node selector                                         | `{}`        |
| `tolerations`                  | Tolerations                                           | `[]`        |
| `affinity`                     | Affinity settings                                     | `{}`        |
| `autoscaling.enabled`          | Enable autoscaling                                    | `false`     |
| `autoscaling.minReplicas`      | Minimum number of replicas                            | `1`         |
| `autoscaling.maxReplicas`      | Maximum number of replicas                            | `5`         |
| `autoscaling.targetCPUUtilizationPercentage` | Target CPU utilization percentage      | `80`        |

## Configuration

### PostgreSQL with PGVector

This chart deploys PostgreSQL with the PGVector extension by default, which is required for vector search capabilities in SpaceBridge. If you prefer to use an external PostgreSQL instance, ensure that it has the PGVector extension installed.

### Using an external PostgreSQL database

To use an external PostgreSQL database, set `database.enabled=false` and configure the external database parameters:

```yaml
database:
  enabled: false
  external: true
  externalDatabase:
    host: my-postgresql.example.com
    port: 5432
    user: postgres
    password: my-password
    database: spacebridge
```

### JWT Authentication

SpaceBridge uses JWT for authentication. By default, it uses a placeholder JWT secret. For production deployments, you should set a proper JWT secret:

```yaml
environment:
  jwtSecret: your-secure-jwt-secret
```

### Ingress Configuration

To enable ingress, set `ingress.enabled=true` and configure the ingress hosts:

```yaml
ingress:
  enabled: true
  className: nginx
  annotations:
    kubernetes.io/ingress.class: nginx
    cert-manager.io/cluster-issuer: letsencrypt-prod
  hosts:
    - host: spacebridge.example.com
      paths:
        - path: /
          pathType: Prefix
  tls:
    - secretName: spacebridge-tls
      hosts:
        - spacebridge.example.com
```

### Scaling the deployment

For production environments, you may want to enable autoscaling:

```yaml
autoscaling:
  enabled: true
  minReplicas: 2
  maxReplicas: 10
  targetCPUUtilizationPercentage: 80
```

## Upgrading the Chart

### To 1.0.0

No special actions are required when upgrading from previous versions.
