# SpaceBridge Development Roadmap

## Phase 1: Foundation (Q1 2025)

### Core Infrastructure
- [x] Project setup and configuration
- [x] Database schema design and implementation
- [x] PGVector integration
- [x] RESTful API server implementation with FastAPI
- [x] Authentication and authorization framework
- [x] Logging and monitoring setup

### Organization and Project Management
- [x] Organization CRUD operations
- [x] Project CRUD operations
- [x] Basic user management
- [x] Issue tracker credential management

### Initial Integration
- [x] Jira integration (basic functionality)
- [x] GitHub Issues integration (basic functionality)
- [x] GitLab Issues integration (basic functionality)

## Phase 2: Core Functionality (Q2 2025)

### REST API Development
- [x] Complete OpenAPI specification
- [x] Endpoint implementation for organizations, projects, and issues
- [x] JWT authentication integration
- [x] Request validation with Pydantic models
- [x] Comprehensive error handling
- [x] API versioning strategy

### Issue Management
- [x] Basic issue search (direct API queries)
- [x] Issue creation across platforms
- [x] Issue updating across platforms
- [x] Cross-platform issue linking

### Vector Search
- [x] Embedding generation for issues
- [x] Vector similarity search implementation
- [x] Hybrid search combining vector and metadata
- [x] Batch indexing mechanism

### MCP Server with Dynamic Tool Filtering
- [x] **Phase 1A: Default Tools with Dynamic Filtering** ([PRELOOP_ARCHITECTURE.md](PRELOOP_ARCHITECTURE.md))
    - [x] Implement `DynamicFastMCP` extending FastMCP for per-request tool filtering
    - [x] Register 6 default tools (get_issue, create_issue, update_issue, search, estimate_compliance, improve_compliance)
    - [x] Implement conditional tool visibility based on tracker presence
    - [x] Integrate StreamableHTTP transport with JWT authentication
    - [x] Use ContextVar for async-safe user context propagation
    - [x] Mount MCP server at `/mcp/v1` with lifespan management
- [x] **Phase 1B: External MCP Servers & Tool Proxying** ✅ COMPLETED
    - [x] Add support for user-configured external MCP servers (MCPServer model, CRUD operations)
    - [x] Implement MCP client pool for external server connections (MCPClientPool with connection pooling)
    - [x] Implement tool discovery and caching from external servers (scan endpoint, MCPTool model)
    - [x] Enable proxied tool execution (DynamicMCPServer with proxied tool support)
- [x] **Phase 2: Approval Workflow** ✅ COMPLETED
    - [x] Implement human-in-the-loop approval for tool execution (ApprovalService, ToolConfiguration)
    - [x] Database models for approval policies and requests (ApprovalPolicy, ApprovalRequest)
    - [x] Webhook integrations for notifications (Slack, Mattermost, custom webhooks)
    - [x] Public approval response endpoint
    - [x] Tool configuration management (API endpoints for tool configs and approval policies)
- [ ] **Phase 3: Tools UI** (Partially Complete - Backend Ready)
    - [x] API endpoints for tool management
    - [x] API endpoints for MCP server management
    - [x] API endpoints for approval management
    - [ ] Build UI components for tool management
    - [ ] MCP server management interface
    - [ ] Approval dashboard


### Event-Driven Agentic Flows

#### Epic 1: Enhanced Event Ingestion & Webhook Coverage
- [x] **Task 1.1: Implement Configurable Event Subscriptions (GitHub & GitLab)** ([Issue #55](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/55))
    *   *Description:* Update `Tracker` model and client logic to allow user-configurable event subscriptions for GitHub and GitLab, enhancing flexibility beyond current hardcoded subscriptions.
- [x] **Task 1.2: Implement Jira Webhook Registration & Full Event Handling** ([Issue #56](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/56))
    *   *Description:* Develop comprehensive webhook registration, validation, and event processing for Jira, covering key events like `jira:issue_created`, `jira:issue_updated`, etc.
- [x] **Task 1.3: NATS Integration for Internal Event Bus** ([Issue #57](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/57))
    *   *Description:* Set up NATS. Modify webhook ingestion points (GitHub, GitLab, new Jira) to publish standardized events to NATS, decoupling event producers and consumers.
- [x] **Task 1.4: Update `SpaceModels` for Event Configuration** ([Issue #58](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/58))
    *   *Description:* Enhance `SpaceModels` (e.g., `Tracker` model) to store and manage the new configurable event subscriptions.

#### Epic 2: Core Flow Infrastructure & Database Models
- [x] **Task 2.1: Implement `Flows` Database Model in `SpaceModels`** ([Issue #59](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/59))
    *   *Description:* Create the `Flows` SQLAlchemy model, Pydantic schema, and CRUD operations as detailed in `ARCHITECTURE.md`.
- [x] **Task 2.2: Implement `AIModel` Database Model in `SpaceModels`** ([Issue #60](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/60))
    *   *Description:* Create the `AIModel` SQLAlchemy model, Pydantic schema (including initial unencrypted API key storage), and CRUD operations.
- [x] **Task 2.3: Implement `FlowExecutions` Database Model in `SpaceModels`** ([Issue #61](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/61))
    *   *Description:* Create the `FlowExecutions` SQLAlchemy model, Pydantic schema, and CRUD operations for logging Flow runs and outcomes.

#### Epic 3: Flow Definition & Management (API & UI)
- [x] **Task 3.1: Develop Flow Definition & Management APIs** ([Issue #62](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/62))
    *   *Description:* Create REST API endpoints in SpaceBridge for CRUD operations on `Flows` and `AIModels`.
- [x] **Task 3.2: Build UI Components for Flow & AIModel Management** ([Issue #63](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/63))
    *   *Description:* Develop user interface elements for creating, viewing, editing, deleting, enabling/disabling `Flows`, and managing `AIModels`.
- [x] **Task 3.3: Implement Flow Presets System** ([Issue #64](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/64))
    *   *Description:* Design and implement a system for defining, managing, and allowing users to utilize or clone pre-defined Flow templates.

#### Epic 4: Flow Execution Engine Development
- [x] **Task 4.1: Develop Flow Trigger Service** ([Issue #65](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/65)) ✅
    *   *Description:* Create the service that subscribes to the NATS event bus, matches incoming events against active `Flow` definitions, and initiates their execution.
    *   *Status:* Implemented in `spacebridge/services/flow_orchestrator.py` with webhook integration
- [x] **Task 4.2: Develop Flow Execution Orchestrator** ([Issue #66](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/66)) ✅
    *   *Description:* Build the orchestrator to manage Flow lifecycles: retrieve definitions, resolve dynamic prompts, handle API key decryption, and manage agent sessions via the Agent Execution Infrastructure.
    *   *Status:* `FlowOrchestrator` class handles full lifecycle management with NATS integration
- [x] **Task 4.3: Agent Execution Infrastructure & OpenHands Integration** ([Issue #67](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/67)) ✅
    *   *Description:* Build the Agent Execution Infrastructure abstraction layer for running agents in isolated containers. Integrate OpenHands as the first agent implementation. Support for additional agents (Claude Code, Aider) can be added later by creating container images.
    *   *Status:* Container-based execution with Docker/K8s support, OpenHands integration complete
- [x] **Task 4.4: Implement Dynamic Prompt Construction & Context Resolution** ([Issue #68](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/68)) ✅
    *   *Description:* Develop logic within the Flow Execution Orchestrator to parse `prompt_template` placeholders and dynamically fetch/inject required context data from `SpaceModels` or other services.
    *   *Status:* Prompt resolver system implemented with variable substitution
- [x] **Task 4.5: Enable MCP Tool Interaction from Agents** ([Issue #69](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/69)) ✅
    *   *Description:* Configure agents to directly call allowed MCP tools on specified MCP servers, adhering to `allowed_mcp_servers` and `allowed_mcp_tools` in the `Flow` definition. Initial implementation for OpenHands, extensible to other agent types.
    *   *Status:* MCP tool integration complete with temporary API keys for agent sessions
- [x] **Task 4.6: Implement Comprehensive Flow Execution Logging** ([Issue #70](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/70)) ✅
    *   *Description:* Ensure detailed logging of Flow executions into the `FlowExecutions` table, and integrate with centralized logging for agent operational logs (container logs, process output, etc.).
    *   *Status:* Real-time execution monitoring via NATS with WebSocket streaming to UI

#### Epic 5: Security & Initial Content
- [ ] **Task 5.1: Secure `AIModel` API Keys (Initial Implementation)** ([Issue #71](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/71))
    *   *Description:* Implement robust encrypted storage for API keys within the `AIModel` table. Ensure secure decryption by the Flow Execution Orchestrator. Track future OpenBAO integration as a separate issue.
- [ ] **Task 5.2: Create and Deploy Initial Flow Presets** ([Issue #72](https://gitlab.spacecode.ai/spacecode/spacebridge/-/issues/72))
    *   *Description:* Define, implement, and make available a set of useful initial Flow presets to demonstrate capabilities and provide value to users.

## Phase 3: Advanced Features (Q3 2025)

### Enhanced Issue Management
- [x] Intelligent duplicate detection
- [ ] Assignee suggestion
- [ ] Issue effort estimation
- [ ] Issue prioritization
- [ ] Health check analysis

### Synchronization and Consistency
- [ ] Cross-tracker issue synchronization
- [ ] Conflict resolution mechanisms
- [ ] Real-time updates via webhooks
- [ ] Background synchronization jobs

### Performance Optimization
- [ ] Query optimization
- [ ] Caching layer implementation
- [ ] Bulk operations for efficiency
- [ ] Rate limit optimization strategies

### Explore: Issue Tracker Visualization
- [ ] **Frontend:** Implement a new 'Explore' route and view component within the SpaceBridge dashboard.
- [ ] **Backend API:** Develop an API endpoint to serve raw embeddings for issues (and later, comments, MRs).
- [ ] **Frontend Dimensionality Reduction:** Integrate modular JavaScript libraries (e.g., UMAP-JS, tSNE-JS, scikit-learn.js for PCA) for client-side dimensionality reduction of fetched embeddings.
- [ ] **Frontend Caching:** Implement browser-side caching (e.g., IndexedDB or localStorage) for storing and retrieving computed dimensionality reduction results to optimize performance.
- [ ] **Frontend Visualization:** Utilize `deck.gl` to implement a 2D/3D scatter plot visualization layer for the client-side reduced embedding data within the 'Explore' view.
- [ ] **Interactive Navigation:** Configure `deck.gl` controllers for zoom, pan, and data point inspection (e.g., displaying issue details on hover/click).
- [ ] **Data Scope:** Initially support visualization of issue embeddings; design data pipelines and API for future inclusion of comment and MR embeddings.

## Phase 4: Enterprise Readiness (Q4 2025)

### Enterprise Features
- [ ] Advanced access control
- [ ] Audit logging
- [ ] Custom field mappings
- [ ] Workflow integration
- [ ] SLA monitoring and reporting

### Scalability
- [ ] Horizontal scaling optimizations
- [ ] Database sharding strategy
- [ ] Vector store optimization for large datasets
- [ ] Performance benchmarking and tuning

### Integration Expansion
- [ ] Azure DevOps integration
- [ ] Linear integration
- [ ] Custom tracker adapter framework

## Phase 5: Advanced Intelligence (Q1-Q2 2026)

### AI-Powered Features
- [ ] Contextual issue summaries
- [ ] Issue clustering and categorization
- [ ] Anomaly detection in issue patterns
- [ ] Predictive analytics for issue resolution
- [ ] Natural language understanding for complex queries

### Developer Experience
- [ ] SDK for custom API integrations
- [ ] Interactive documentation
- [ ] Integration testing framework
- [ ] Developer portal

### Community and Ecosystem
- [ ] API client libraries in multiple languages
- [ ] Integration marketplace
- [ ] Contributing guidelines and governance
- [ ] Community engagement program

## Ongoing Activities

### Documentation
- [x] API documentation
- [x] User guides
- [ ] Integration guides
- [x] Architecture documentation updates

### Quality Assurance
- [x] Automated test suite expansion
- [x] Unit test coverage measurement
- [-] Integration and functional tests
- [-] Production smoke tests
- [ ] Performance testing
- [ ] Security audits
- [ ] Compliance verification

### DevOps
- [ ] CI/CD pipeline optimization
- [ ] Infrastructure as code improvements
- [ ] Observability enhancements
- [ ] Disaster recovery testing
