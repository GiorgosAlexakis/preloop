# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## Project Overview

SpaceLit is a modern web application frontend for SpaceBridge, built with:
- **Lit** (Web Components framework)
- **TypeScript** for type safety
- **Vaadin components** for UI (Vaadin router, forms, layouts)
- **Shoelace components** for additional UI elements
- **Vite** for build tooling and development server
- **Chart.js** for data visualization

The application is a single-page application (SPA) that provides an interface for managing issue trackers through the SpaceBridge API.

## Development Commands

```bash
# Install dependencies
npm install

# Start development server with HMR (http://localhost:5173)
npm run dev

# Build for production
npm run build

# Run tests
npm run test

# Format code
npm run format
npm run format:check

# Docker commands
npm run docker:dev    # Development with HMR
npm run docker:prod   # Production with real API
npm run docker:mock   # Production with mock API
npm run docker:build  # Build production image
npm run docker:test   # Run tests in container
```

## Architecture

### Application Structure
- **Entry point**: `src/main.ts` imports the main app component
- **Root component**: `src/components/lit-app.ts` - defines routing and app shell
- **Router**: Uses Vaadin Router for client-side routing, configured in `lit-app.ts:39-74`
- **API layer**: `src/api.ts` - handles authentication and API calls

### Component Architecture
- All components extend `LitElement` from the Lit framework
- Authenticated components should extend `AuthedElement` from `api.ts` for built-in auth handling
- Components use `@customElement` decorator for registration
- TypeScript decorators are enabled (`experimentalDecorators: true`)

### Authentication Flow
- JWT-based authentication with access/refresh tokens stored in localStorage
- `fetchWithAuth()` function in `api.ts:38-72` handles automatic token refresh
- Failed auth automatically redirects to `/login`
- `AuthedElement` base class provides `fetchData()` method for authenticated requests

### Routing Structure
```
/ - Landing page
/login - Login form
/register - Registration form  
/forgot-password - Password reset
/console - Authenticated app shell
  ├── / - Dashboard
  ├── /trackers - Issue tracker management
  ├── /issues - Issue management
  │   ├── /duplicates - Duplicate issue detection
  │   └── /assignments - Issue assignments
  ├── /api-usage - API usage statistics
  └── /settings - User settings
      ├── /profile - User profile
      ├── /security - Security settings
      ├── /api-keys - API key management
      └── /llm-models - LLM model configuration
```

### Development Server Configuration
- Vite dev server runs on port 5173
- API requests proxy to `http://127.0.0.1:8000` (backend)
- Static files proxy to same backend
- WebSocket support enabled for HMR

### Testing
- Uses Web Test Runner (`@web/test-runner`) with Playwright
- Test files: `src/**/*.test.{ts,js}`
- Testing utilities: `@open-wc/testing`, Chai, Sinon
- Test runner configured to run headed (browser visible) for debugging
- **Important**: Stub `window.fetch` (not ES module functions) for API testing
- Use `waitUntil()` for async DOM updates and `await new Promise(resolve => setTimeout(resolve, 100))` for API calls
- **Note**: Browser console errors during tests are expected for error handling tests - they indicate proper error flow, not test failures

### Code Style
- Prettier for formatting (configured in `lint-staged`)
- No ESLint configuration present
- TypeScript strict mode enabled
- Use `experimentalDecorators` for Lit decorators

### CI/CD
- GitLab CI configured in `.gitlab-ci.yml` with Docker-based pipeline
- Pipeline stages: test → build → deploy
- **Container-based testing**: Tests run in Docker containers for consistency
- **Format validation**: `npm run format:check` ensures code follows Prettier standards
- **Docker image builds**: Separate dev and production images pushed to GitLab registry
- **Security scanning**: Trivy scans for vulnerabilities in production images
- **Manual deployments**: Staging and production deployments with environment protection
- **Alternative config**: `.gitlab-ci.simple.yml` available for simpler setups without registry

### Docker Support
- **Production**: Multi-stage build with nginx serving static files (`Dockerfile`)
- **Development**: Vite dev server with HMR for live debugging (`Dockerfile.dev`)
- **API Flexibility**: Easy switching between real API and mock API for testing
- **Management Script**: `./docker-run.sh` provides simple commands for all Docker operations

#### Docker Quick Start
```bash
# Development with live debugging
npm run docker:dev     # or ./docker-run.sh dev

# Production with real API
npm run docker:prod    # or ./docker-run.sh prod  

# Production with mock API (testing)
npm run docker:mock    # or ./docker-run.sh mock
```

#### Docker Environments
- **Development** (`docker-compose.dev.yml`): Vite dev server on :5173, mock API on :8000
- **Production** (`docker-compose.yml`): Nginx on :3000, expects real API backend
- **Mock Testing** (`docker-compose.mock.yml`): Nginx on :3000, mock API on :8000
- **Environment Variables**: `API_URL` and `MOCK_API` control backend routing

## Key Files
- `src/components/lit-app.ts:39-74` - Route definitions
- `src/api.ts:38-72` - Authentication handling
- `src/api.ts:74-87` - AuthedElement base class
- `vite.config.ts:21-32` - Development proxy configuration