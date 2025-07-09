# Docker Setup for SpaceLit

This document provides comprehensive Docker support for SpaceLit with multiple environments and easy API switching.

## Quick Start

### Development (with live debugging)
```bash
npm run docker:dev
# OR
./docker-run.sh dev
```
- **Frontend**: http://localhost:5173 (Vite dev server with HMR)
- **Mock API**: http://localhost:8000

### Production (with real API)
```bash
npm run docker:prod
# OR  
./docker-run.sh prod
```
- **Frontend**: http://localhost:3000 (nginx)
- **Backend**: http://localhost:8000 (expects real API)

### Production (with mock API for testing)
```bash
npm run docker:mock
# OR
./docker-run.sh mock
```
- **Frontend**: http://localhost:3000 (nginx)
- **Mock API**: http://localhost:8000

## Available Commands

| Command | Description |
|---------|-------------|
| `./docker-run.sh dev` | Start development with HMR |
| `./docker-run.sh prod` | Start production with real API |
| `./docker-run.sh mock` | Start production with mock API |
| `./docker-run.sh build` | Build production Docker image |
| `./docker-run.sh test` | Run tests in container |
| `./docker-run.sh stop` | Stop all containers |
| `./docker-run.sh clean` | Clean up containers and images |
| `./docker-run.sh logs [service]` | Show container logs |

## Docker Environments

### 1. Development Environment
- **File**: `docker-compose.dev.yml`
- **Container**: Vite dev server with volume mounts
- **Features**: Hot module replacement, live debugging, mock API
- **Use case**: Local development with instant feedback

### 2. Production Environment  
- **File**: `docker-compose.yml`
- **Container**: Multi-stage build with nginx
- **Features**: Optimized static assets, API proxy, real backend
- **Use case**: Testing with actual backend services

### 3. Mock Testing Environment
- **File**: `docker-compose.mock.yml`  
- **Container**: Production build with mock API
- **Features**: Full production setup, mock backend responses
- **Use case**: Testing without external dependencies

## Environment Variables

Configure API routing with these environment variables:

| Variable | Description | Default |
|----------|-------------|---------|
| `API_URL` | Backend API URL | `http://localhost:8000` |
| `MOCK_API` | Use mock API responses | `false` |

### Example: Custom API URL
```bash
API_URL=https://your-api.example.com ./docker-run.sh prod
```

## Mock API Endpoints

The mock API provides realistic responses for testing:

- `POST /api/v1/auth/token/json` - Login
- `POST /api/v1/auth/register` - Registration  
- `POST /api/v1/auth/refresh` - Token refresh
- `GET /api/v1/auth/users/me` - User profile
- `GET /api/v1/trackers` - Issue trackers
- `GET /api/v1/auth/api-usage` - API usage stats
- `GET /api/v1/issue-duplicates/` - Duplicate issues
- `GET /api/v1/auth/api-keys` - API keys
- `GET /api/v1/llm-models` - LLM models

All endpoints include proper CORS headers and realistic JSON responses.

## Nginx Configuration

Production containers use nginx with:

- **Static file serving** with optimized caching
- **API proxying** to backend services
- **SPA routing** support (all routes serve index.html)
- **Security headers** (XSS protection, frame options, etc.)
- **Gzip compression** for better performance
- **Health check** endpoint at `/health`

## GitLab CI/CD

The pipeline is configured to:
1. **Test**: Run tests and format checks in Docker containers
2. **Build**: Build and push Docker images to GitLab registry
3. **Deploy**: Manual deployment to staging/production environments

### CI Pipeline Features
- **Docker-based**: All jobs run in containers for consistency
- **Multi-environment**: Separate dev and production image builds
- **Security scanning**: Trivy scans for vulnerabilities (main branch only)
- **Manual deployments**: Protected environments with manual approval

### Alternative CI Configuration
If you encounter issues with the main CI configuration, use the simpler version:
```bash
mv .gitlab-ci.yml .gitlab-ci.full.yml
mv .gitlab-ci.simple.yml .gitlab-ci.yml
```

## Troubleshooting

### GitLab CI Issues
- **Registry login fails**: Ensure GitLab Container Registry is enabled
- **Docker-in-Docker issues**: Check GitLab Runner has privileged mode enabled
- **Pipeline dependency errors**: Use the simple CI configuration as fallback

### Port Conflicts
If ports are already in use, modify the port mappings in docker-compose files:
```yaml
ports:
  - "3001:80"  # Change 3000 to 3001
```

### API Connection Issues
1. Verify backend is running: `curl http://localhost:8000/health`
2. Check nginx logs: `./docker-run.sh logs frontend`
3. Test with mock API: `./docker-run.sh mock`

### Build Issues
1. Clean Docker cache: `./docker-run.sh clean`
2. Rebuild from scratch: `./docker-run.sh build`
3. Check Node.js version: Requires Node 18+

### Development Volume Issues
If file changes aren't reflected:
1. Stop containers: `./docker-run.sh stop`
2. Clear volumes: `docker volume prune`
3. Restart: `./docker-run.sh dev`

## Production Deployment

For production deployment:

1. **Build the image**:
   ```bash
   docker build -t spacelit:v1.0.0 .
   ```

2. **Tag for registry**:
   ```bash
   docker tag spacelit:v1.0.0 your-registry.com/spacelit:v1.0.0
   ```

3. **Push to registry**:
   ```bash
   docker push your-registry.com/spacelit:v1.0.0
   ```

4. **Deploy with environment variables**:
   ```bash
   docker run -d \
     -p 80:80 \
     -e API_URL=https://your-api.example.com \
     -e MOCK_API=false \
     your-registry.com/spacelit:v1.0.0
   ```