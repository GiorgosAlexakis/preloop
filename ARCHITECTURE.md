# SpaceBridge Architecture

## System Overview

SpaceBridge is designed as a modular, scalable RESTful API server that provides a unified interface for issue tracking across multiple platforms. The architecture emphasizes flexibility, performance, and ease of integration.

## High-Level Architecture

```mermaid
graph LR
    subgraph "External Systems"
        MCP_Clients["MCP Clients (e.g., Claude Code)"]
        Issue_Trackers["Issue Trackers (Jira, GitHub, GitLab, etc.)"]
    end

    subgraph "SpaceBridge Ecosystem"
        direction LR
        subgraph "SpaceBridge Main Repository"
            direction TB
            API["SpaceBridge REST API"]
            subgraph "Submodules"
                direction LR
                SpaceModels["SpaceModels (./SpaceModels)"]
                SpaceSync["SpaceSync (./spacesync)"]
            end
            DB["PostgreSQL + PGVector"]

            API --> SpaceModels
            SpaceModels --> DB
            SpaceSync --> SpaceModels
            SpaceSync --> Issue_Trackers
            API --> Issue_Trackers # Direct interaction for some operations
        end

        subgraph "SpaceBridge-MCP (Separate Repo)"
            MCP_Server["SpaceBridge-MCP Server"]
        end

        MCP_Clients --> MCP_Server
        MCP_Server --> API
    end

    style SpaceBridge_Ecosystem fill:#f9f,stroke:#333,stroke-width:2px
    style SpaceBridge_Main_Repository fill:#ccf,stroke:#333,stroke-width:1px
    style Submodules fill:#eef,stroke:#666,stroke-width:1px,stroke-dasharray: 5 5
    style SpaceBridge_MCP fill:#cfc,stroke:#333,stroke-width:1px
```

**Key Components:**

*   **SpaceBridge REST API (Main Repository):** The core FastAPI application providing the HTTP interface.
*   **SpaceModels (Submodule):** Handles database interactions, defining SQLAlchemy models, Pydantic schemas, and CRUD operations. Manages the PostgreSQL database connection and PGVector operations.
*   **SpaceSync (Submodule):** A service responsible for polling external issue trackers, processing data, generating embeddings, and storing/updating information in the database via `SpaceModels`.
*   **PostgreSQL + PGVector:** The database storing metadata and vector embeddings.
*   **SpaceBridge-MCP (Separate Repository):** An MCP server acting as a bridge for MCP clients, translating MCP requests into calls to the SpaceBridge REST API.
*   **External Systems:** Issue trackers and MCP clients interacting with the SpaceBridge ecosystem.

## Frontend Architecture (V2)

A new, modern frontend is being developed in the `SpaceLit` directory, aiming to replace the existing static HTML/JavaScript interface.

```mermaid
graph TD
    subgraph "Browser"
        direction LR
        WebApp["Lit Web Application"]
        MWC["Material Web Components"]
        WebApp -- Uses --> MWC
    end

    subgraph "Build & Dev Tools"
        direction LR
        Vite["Vite"]
        TypeScript["TypeScript"]
        WTR["Web Test Runner"]
    end

    subgraph "Backend"
        SpaceBridgeAPI["SpaceBridge REST API"]
    end

    WebApp -- Bundled by --> Vite
    TypeScript -- Transpiled by --> Vite
    WebApp -- Makes API Calls to --> SpaceBridgeAPI
    WTR -- Runs Tests on --> WebApp

    style WebApp fill:#aef,stroke:#333,stroke-width:2px
```

### Technology Stack

*   **Framework:** [Lit](https://lit.dev/) - A simple library for building fast, lightweight web components. It provides reactive state, scoped styles, and a declarative templating system.
*   **Build Tool:** [Vite](https://vitejs.dev/) - A modern frontend build tool that provides an extremely fast development experience with features like Hot Module Replacement (HMR) and optimized production builds.
*   **Language:** [TypeScript](https://www.typescriptlang.org/) - A statically typed superset of JavaScript that enhances code quality and maintainability.
*   **UI Components:** [Material Web Components (MWC)](https://github.com/material-components/material-web) - A set of high-quality, standards-based web components that implement the Material v3 design system.
*   **Testing:** [Web Test Runner](https://modern-web.dev/docs/test-runner/overview/) - A tool for testing web applications in a real browser, ensuring that components behave as expected in a live environment.

### Structure

The `SpaceLit` application is structured around a component-based architecture.

*   **`src/components/`**: This directory contains all the custom Lit components that make up the application. Each component is typically defined in its own file (e.g., `tracker-list.ts`) and may have a corresponding test file (e.g., `tracker-list.test.ts`).
*   **`src/api.ts`**: A dedicated module for handling communication with the SpaceBridge REST API. It encapsulates fetch logic, authentication, and data transformation.
*   **`index.html`**: The main entry point for the application.
*   **`vite.config.ts`**: Configuration for the Vite build tool.
*   **`package.json`**: Defines project metadata, dependencies, and scripts for development, building, and testing.

## Core Components

### SpaceBridge API Server (Main Repository)
*   **Framework:** FastAPI-based RESTful API server.
*   **Authentication:** JWT authentication and authorization.
*   **Validation:** Request validation using Pydantic models (defined in `SpaceModels`).
*   **Documentation:** Automatic API documentation with Swagger/ReDoc.
*   **Features:** Rate limiting, error handling, monitoring integration.
*   **Interaction:** Communicates with `SpaceModels` for database operations and directly with Issue Tracker APIs for certain actions (e.g., creating/updating issues in real-time).

### SpaceModels (Submodule `./SpaceModels`)
*   **Purpose:** Data modeling and database interaction layer.
*   **Technology:** SQLAlchemy for ORM, Pydantic for data validation/schemas.
*   **Database:** Defines schema for PostgreSQL, including tables for organizations, projects, issues, embeddings, etc.
*   **Vector Store:** Integrates with PGVector for storing and querying issue embeddings.
*   **Operations:** Provides CRUD (Create, Read, Update, Delete) functions for all database entities.
*   **Migrations:** Uses Alembic for database schema evolution.

### SpaceSync (Submodule `./spacesync`)
*   **Purpose:** Data synchronization and embedding generation service.
*   **Functionality:**
    *   Polls configured issue trackers (Jira, GitHub, GitLab) periodically.
    *   Fetches new or updated issues, projects, and other relevant data.
    *   Processes fetched data and generates vector embeddings for issues.
    *   Uses `SpaceModels` to store/update data and embeddings in the PostgreSQL database.
*   **Execution:** Runs as a separate process, often invoked via CLI commands (e.g., `spacesync scan all`).

### SpaceBridge-MCP (Separate Repository)
*   **Purpose:** Provides an MCP interface for clients like Claude Code.
*   **Transport:** Uses stdio transport for communication.
*   **Functionality:**
    *   Registers MCP tools (e.g., `search_issues`, `create_issue`).
    *   Receives MCP requests and translates them into HTTP calls to the SpaceBridge REST API.
    *   Handles parameter validation and transformation between MCP and REST API formats.
    *   Returns results from the API back to the MCP client.

### Issue Tracker Clients (within SpaceBridge & SpaceSync)
*   **Location:** Implementations reside within both the main SpaceBridge API (for direct actions) and SpaceSync (for polling). Shared logic might be abstracted.
*   **Structure:** Abstract base classes define common interfaces (`get_issue`, `create_issue`, etc.).
*   **Implementations:** Concrete classes for each supported tracker (Jira, GitHub, GitLab).
*   **Features:** Handles authentication, API specifics, rate limiting, and error mapping for each tracker.

### Database (PostgreSQL + PGVector)
*   **Role:** Central data store for metadata and vector embeddings.
*   **Managed by:** `SpaceModels` submodule.
*   **Key Features:** Relational data storage, efficient vector similarity search via PGVector.

## Data Flow

### REST API Flow (e.g., Searching Issues)
1.  **Client Request:** An HTTP client sends a `GET /api/v1/issues/search` request to the SpaceBridge API server.
2.  **API Server:**
    *   Authenticates the request (JWT).
    *   Validates query parameters (using Pydantic models from `SpaceModels`).
    *   Calls the appropriate service function.
3.  **Service Layer (API):**
    *   Generates an embedding for the search query.
    *   Calls a function in `SpaceModels` to perform a vector similarity search in the PostgreSQL/PGVector database, potentially with metadata filters.
4.  **SpaceModels:**
    *   Constructs and executes the SQL query against the database.
    *   Retrieves matching issue data.
5.  **API Server:** Formats the results and returns the HTTP response to the client.

### Data Synchronization Flow (SpaceSync)
1.  **Trigger:** `spacesync scan all` command is executed.
2.  **SpaceSync Service:**
    *   Retrieves tracker configurations using `SpaceModels`.
    *   For each configured tracker:
        *   Uses the appropriate Issue Tracker Client to poll the external API (e.g., Jira API) for new/updated issues since the last scan.
        *   Processes the fetched issues.
        *   Generates vector embeddings for new/updated issue text.
        *   Calls functions in `SpaceModels` to insert or update issue data and embeddings in the database.
3.  **SpaceModels:** Interacts with the PostgreSQL database to persist changes.

### MCP Flow (via SpaceBridge-MCP)
1.  **MCP Client Request:** Claude Code sends a `search_issues` tool request via stdio.
2.  **SpaceBridge-MCP Server:**
    *   Parses the MCP request.
    *   Validates parameters.
    *   Constructs an equivalent HTTP request (e.g., `GET /api/v1/issues/search`).
    *   Sends the HTTP request to the SpaceBridge API server.
3.  **SpaceBridge API Server:** Processes the request as described in the "REST API Flow".
4.  **SpaceBridge-MCP Server:**
    *   Receives the HTTP response.
    *   Formats the result into an MCP response.
    *   Sends the MCP response back to Claude Code via stdio.

## Database Schema (Managed by SpaceModels)

The detailed schema is defined using SQLAlchemy models within the `SpaceModels` submodule. Key tables include:

*   **Organizations:** Stores organization metadata, settings, and potentially user associations.
*   **Projects:** Contains project details, tracker configurations (type, API URL, credentials), and links to organizations.
*   **Trackers:** Holds specific tracker instance details and encrypted credentials.
*   **Issues:** Stores core issue data (ID, title, description, status, labels, etc.) synchronized from trackers.
*   **Issue Embeddings:** Contains vector embeddings (using PGVector `vector` type) linked to issues, used for similarity search.
*   **Other Metadata:** Tables for comments, users, API keys, etc., as needed.

Schema migrations are managed using Alembic within `SpaceModels`.

## Integration with Existing Spacecode Infrastructure

- [ ] Authentication integration with Spacecode SSO
- [ ] Permission synchronization with central user management
- [ ] Event publishing to message bus for cross-service coordination
- [ ] Integration with Spacecode logging and monitoring systems

## Technical Decisions

### REST API Implementation
SpaceBridge implements a RESTful HTTP API using FastAPI, which provides:
- High performance with Starlette and Pydantic
- Automatic OpenAPI documentation generation
- Type annotation-based parameter validation
- Native async/await support
- Dependency injection system
- Middleware for authentication, logging, etc.

### SpaceBridge-MCP Implementation
The companion SpaceBridge-MCP project will implement an MCP server using:
- Official MCP SDK for stdio transport
- HTTP client for communicating with SpaceBridge REST API
- Function-based tool registration with decorators
- Type annotation-based parameter validation

### Language and Framework
Python is chosen as the primary language due to its strong ecosystem for machine learning and data processing, which is essential for similarity search and embedding generation. FastAPI is used for the REST API due to its performance, type safety, and automatic OpenAPI documentation generation.

### Database
PostgreSQL with the PGVector extension is used. The `SpaceModels` submodule encapsulates all database interaction logic, providing a clean separation from the API and synchronization services. This allows for centralized data management and schema evolution.

### Authentication
A JWT-based authentication system is implemented for the REST API, with integration points for existing Spacecode authentication services. This allows for flexible identity management while maintaining security.

### Deployment
The system is designed to be containerized using Docker, enabling easy deployment in various environments including Kubernetes clusters. Stateless components enable horizontal scaling under load.

## Security Considerations

- [ ] All API requests authenticated and authorized
- [ ] Issue tracker credentials encrypted at rest
- [ ] Sensitive data masked in logs
- [ ] Rate limiting to prevent abuse
- [ ] Input validation for all parameters
- [ ] Regular security audits and dependency updates

## Performance Considerations

- [ ] Connection pooling for database and external APIs
- [ ] Caching frequently accessed data
- [ ] Asynchronous processing for long-running operations
- [ ] Pagination for large result sets
- [ ] Efficient vector similarity algorithms
- [ ] Background indexing of issue embeddings

## Event-Driven Agentic Flows

This section details the architecture for the "Event-Driven Agentic Flows" (Flows) feature, enabling automated workflows triggered by various events and executed by AI agents.

### 1. Overview and Goals

The "Flows" feature allows users to define automated workflows that are initiated by events from integrated systems (e.g., GitHub, GitLab, Jira) or other sources (e.g., incidents, OpenTelemetry data). Each Flow leverages a configurable AI model and a dynamic prompt to perform tasks, potentially utilizing specified MCP (Meta-Cognitive Prompting) servers and tools.

**Key Goals:**

*   **Event-Driven Automation:** Trigger workflows based on specific events (e.g., commit to main, new issue, PR merged, incident triggered).
*   **Dynamic Prompting:** Allow prompts to be constructed dynamically, incorporating project-specific context (e.g., documentation summaries, code component maps).
*   **Configurable AI Models:** Enable users to select and configure different AI models for different Flows, managing API keys securely.
*   **Controlled Tool Usage:** Provide a mechanism to specify which MCP servers and tools an AI agent can use during a Flow's execution.
*   **Extensibility:** Design for easy addition of new event sources, AI models, and agent capabilities.
*   **User Experience:** Allow users to define Flows from presets, customize existing ones, or create them from scratch.

### 2. Key Components & Their Roles

```mermaid
graph TD
    subgraph "External Event Sources"
        direction LR
        Trackers["Issue Trackers (GitHub, GitLab, Jira)"]
        OtherSources["Other Sources (Incidents, OTel, etc.)"]
    end

    subgraph "SpaceBridge Core"
        direction TB
        WebhookEndpoint["Webhook Endpoint (/api/v1/private/webhooks/...)"]
        TaskQueue["Internal Task Queue (NATS)"]
        APIExt["SpaceBridge API (Flow/AIModel CRUD, Logs)"]
        SpaceModelsDB["SpaceModels (PostgreSQL - Flows, AIModels, Executions)"]
    end

    subgraph "Flows Subsystem"
        direction TB
        FlowTriggerService["Flow Trigger Service (part of Worker)"]
        FlowExecOrchestrator["Flow Execution Orchestrator"]
        OpenHandsInfra["OpenHands Execution Infrastructure (Docker/Kubernetes)"]
        subgraph "OpenHands Agent Session (Container)"
            OpenHandsAgent["OpenHands Agent"]
            AIModelClient["AIModel Client (via AIModel)"]
            MCPClient["MCP Client (for allowed tools)"]
        end
    end

    subgraph "External Services"
        AIModelAPIs["AI Model APIs (OpenAI, Anthropic, etc.)"]
        MCPServers["MCP Servers"]
    end

    Trackers -- Webhook Event --> WebhookEndpoint
    WebhookEndpoint -- Publishes Task --> TaskQueue
    TaskQueue -- Delivers Task --> FlowTriggerService
    FlowTriggerService -- Reads Flow Defs --> SpaceModelsDB
    FlowTriggerService -- Initiates Execution --> FlowExecOrchestrator
    FlowExecOrchestrator -- Reads Flow/AIModel --> SpaceModelsDB
    FlowExecOrchestrator -- Resolves Prompt Data --> SpaceModelsDB
    FlowExecOrchestrator -- Manages --> OpenHandsInfra
    OpenHandsInfra -- Runs --> OpenHandsAgent
    OpenHandsAgent -- Uses --> AIModelClient
    AIModelClient -- Calls --> AIModelAPIs
    OpenHandsAgent -- Uses --> MCPClient
    MCPClient -- Calls --> MCPServers
    FlowExecOrchestrator -- Writes Logs --> SpaceModelsDB
    APIExt -- Manages --> SpaceModelsDB
    APIExt -- Serves Logs --> UserClient["User Client (UI/CLI)"]

    style "SpaceBridge Core" fill:#ccf,stroke:#333,stroke-width:1px
    style "Flows Subsystem" fill:#cfc,stroke:#333,stroke-width:1px
    style "OpenHands Agent Session (Container)" fill:#eef,stroke:#666,stroke-width:1px,stroke-dasharray: 5 5
```

*   **Flow Definition (`Flows`):**
    *   Stored in the `SpaceModels` database.
    *   Details the triggering event, prompt template, selected `AIModel` ID, OpenHands agent configuration (e.g., specific agent type, parameters), and a list of allowed MCP servers and specific tools.
    *   Presets are implemented as special, non-editable (or cloneable) records in this table.
*   **AI Model (`AIModel`):**
    *   Stored in `SpaceModels`.
    *   Reusable definitions for AI models, including their identifiers (e.g., `openai/gpt-4`), API endpoints, and credentials.
    *   For initial implementation, API keys will be stored unencrypted directly in the database. A future enhancement will integrate a secrets management solution like OpenBAO.
    *   Models are linked to an `Account`.
*   **Event Ingestion:**
    *   Primarily through the existing webhook endpoint (e.g., `/api/v1/private/webhooks/{tracker_type}/{org_identifier}`) for tracker events.
    *   This endpoint validates incoming webhooks and then publishes a `process_webhook_event` task to the **Internal Task Queue (NATS)**.
*   **Internal Task Queue (NATS):**
    *   NATS is used as a simple, reliable task queue. It decouples the API from the background processing of events and flows.
    *   The `TaskPublisher` service is used to enqueue tasks.
    *   Workers consume tasks from the `spacesync.tasks` subject.
*   **Flow Trigger Service:**
    *   This logic is part of the NATS worker. When a `process_webhook_event` task is received, the worker acts as the trigger service.
    *   It matches the incoming event data against the `trigger_event_source` and `trigger_event_type` defined in active `Flows`.
    *   Upon a match, it initiates a Flow execution by invoking the Flow Execution Orchestrator.
*   **Flow Execution Orchestrator:**
    *   Responsible for managing the lifecycle of a single Flow execution.
    *   Retrieves the `Flow` definition and its associated `AIModel` (including the encrypted API key) from the database.
    *   **Dynamic Prompt Resolution:** Parses the `prompt_template` and resolves any placeholders (e.g., `{{project_docs_summary}}`, `{{relevant_code_files}}`) by querying `SpaceModels` or other SpaceBridge services for the necessary context data.
    *   Decrypts the API key and prepares the complete execution context for OpenHands, including the fully resolved prompt, AI model details (model name, API endpoint, decrypted API key), and the specific list of allowed MCP servers/tools.
    *   Initiates and manages an OpenHands agent session, potentially by requesting a new container from the OpenHands Execution Infrastructure.
    *   Monitors the execution and records results/logs.
*   **OpenHands Execution Infrastructure:**
    *   Manages the runtime environment for OpenHands agents.
    *   As per OpenHands capabilities, this will involve spinning up a new container (e.g., via Docker socket on localhost or as a Kubernetes job) for each Flow execution. This ensures isolation and scalability.
    *   The Flow Execution Orchestrator will interact with this infrastructure to start, monitor, and terminate agent sessions.
*   **OpenHands Agent (running in a container):**
    *   The core agentic execution environment provided by the OpenHands library.
    *   Receives the resolved prompt, AI model configuration , and allowed MCP toolset from the Flow Execution Orchestrator.
    *   Manages the interaction with the configured AI model.
    *   **Direct MCP Calls:** The AI model, operating within the OpenHands agent, will directly call the allowed MCP tools on the specified MCP servers. OpenHands will need to be configured or provided with the necessary network access and potentially authentication details (if any) for these MCP servers.
*   **Flow Execution Log (`FlowExecutions`):**
    *   A database table in `SpaceModels` to record the history and outcome of each Flow run.
    *   Includes details like the triggering event, start/end times, status (pending, running, succeeded, failed), the resolved input prompt, a summary of actions taken by the agent, logs of MCP tool usage, and a reference to more detailed logs from the OpenHands session (e.g., container logs or a session ID).
*   **SpaceBridge API Extensions:**
    *   New API endpoints will be added to the `SpaceBridge API` for:
        *   CRUD (Create, Read, Update, Delete) operations on `Flows` and `AIModels`.
        *   Listing and retrieving `FlowExecution` history and logs.
        *   Managing Flow presets (e.g., listing, cloning).

### 3. Database Schema Considerations (Conceptual)

The following Pydantic schemas and corresponding SQLAlchemy models will be defined within `SpaceModels`:

*   **`Flow` Table/Schema:**
    *   `id`: Primary Key (e.g., UUID)
    *   `name`: String (User-defined name for the Flow)
    *   `description`: Text (Optional description)
    *   `trigger_event_source`: String (e.g., 'github', 'jira', 'gitlab', 'custom_event', 'scheduled')
    *   `trigger_event_type`: String (e.g., 'commit_to_main', 'new_issue_created', 'incident_triggered', 'daily_scan')
    *   `trigger_config`: JSON (Optional, for more complex trigger conditions, e.g., specific branch for commits, specific labels for issues)
    *   `prompt_template`: Text (The prompt template with placeholders like `{{placeholder_name}}`)
    *   `ai_model_id`: Foreign Key to `AIModel.id`
    *   `openhands_agent_config`: JSON (Configuration for the OpenHands agent, e.g., `{"agent_type": "CodeActAgent", "max_iterations": 10}`)
    *   `allowed_mcp_servers`: JSON Array of strings (e.g., `["spacebridge-mcp", "code_analysis_mcp"]`)
    *   `allowed_mcp_tools`: JSON Array of objects (e.g., `[{"server_name": "spacebridge-mcp", "tool_name": "search_issues"}, {"server_name": "code_analysis_mcp", "tool_name": "lint_file"}]`)
    *   `is_preset`: Boolean (Indicates if this is a system-defined preset)
    *   `is_enabled`: Boolean (Allows users to enable/disable Flows)
    *   `created_by_user_id`: Foreign Key to `Users.id` (if user management exists)
    *   `organization_id`: Foreign Key to `Organizations.id`
    *   `created_at`: Timestamp
    *   `updated_at`: Timestamp

*   **`AIModel` Table/Schema:**
    *   `id`: Primary Key (UUID)
    *   `name`: String (User-defined name for this model configuration)
    *   `description`: Text (Optional description)
    *   `provider_name`: String (e.g., 'openai', 'anthropic')
    *   `model_identifier`: String (Standardized identifier, e.g., 'gpt-4-turbo')
    *   `api_endpoint`: String (URL for the model's API, if not standard)
    *   `api_key`: String (Stores the API key, unencrypted for now)
    *   `account_id`: Foreign Key to `Account.id`
    *   `is_default`: Boolean (Indicates if this is the default model for the account)
    *   `model_parameters`: JSON (Optional, for model-specific parameters like temperature, max_tokens)
    *   `meta_data`: JSON (Optional, for custom fields, labels, etc.)
    *   `created_at`: Timestamp
    *   `updated_at`: Timestamp

*   **`FlowExecution` Table/Schema:**
    *   `id`: Primary Key (e.g., UUID)
    *   `flow_id`: Foreign Key to `Flows.id`
    *   `trigger_event_id`: String (Optional, an identifier for the specific event that triggered this execution, if available from the event source)
    *   `trigger_event_details`: JSON (A snapshot of the payload of the triggering event)
    *   `status`: String (e.g., 'PENDING', 'INITIALIZING', 'RUNNING', 'COMPLETING', 'SUCCEEDED', 'FAILED', 'CANCELLED', 'TIMED_OUT')
    *   `start_time`: Timestamp
    *   `end_time`: Timestamp (Nullable)
    *   `resolved_input_prompt`: Text (The full prompt after placeholder resolution)
    *   `model_output_summary`: Text (Optional, a concise summary of the AI model's final output or key findings)
    *   `actions_taken_summary`: JSON Array (A structured log of significant actions performed by the agent, e.g., files created, MCP tools called with parameters)
    *   `mcp_usage_logs`: JSON Array of objects (Detailed log of each MCP tool call: `{"server_name", "tool_name", "arguments", "timestamp", "status", "result_summary"}`)
    *   `openhands_session_reference`: String (e.g., OpenHands session ID, Kubernetes job ID, Docker container ID, or path to detailed logs)
    *   `error_message`: Text (If status is 'FAILED', stores the error message or stack trace)
    *   `created_at`: Timestamp
    *   `updated_at`: Timestamp

### 4. Data Flow Diagrams

*(Mermaid diagrams will be used here as shown in the "Key Components" section and expanded as needed for specific flows.)*

**a. Event Ingestion & Flow Triggering:**

```mermaid
sequenceDiagram
    participant ExtSrc as External Event Source (e.g., GitHub)
    participant WebhookEP as SpaceBridge Webhook Endpoint
    participant TaskQueue as Internal Task Queue (NATS)
    participant Worker as SpaceSync Worker (Flow Trigger)
    participant FlowsDB as Flows Database (SpaceModels)
    participant FlowExecOrch as Flow Execution Orchestrator

    ExtSrc->>+WebhookEP: Sends Webhook (e.g., push event)
    WebhookEP->>+TaskQueue: Publishes `process_webhook_event` Task
    TaskQueue-->>-Worker: Delivers Task
    Worker->>+FlowsDB: Queries for matching Flow definitions
    FlowsDB-->>-Worker: Returns matching Flow(s)
    alt If match found
        Worker->>+FlowExecOrch: Initiates Flow Execution (with Flow ID, Event Data)
        FlowExecOrch-->>-Worker: Acknowledges (e.g., Execution ID)
    end
```

**b. Flow Execution (Simplified):**

```mermaid
sequenceDiagram
    participant FlowExecOrch as Flow Execution Orchestrator
    participant ModelsDB as SpaceModels (Flows, AIModels, Context Data)
    participant OpenHandsInfra as OpenHands Execution Infrastructure
    participant OHAgent as OpenHands Agent (in Container)
    participant AIModel_API as AI Model API
    participant MCP_Srv as Allowed MCP Server(s)

    FlowExecOrch->>+ModelsDB: Get Flow & AIModel details (incl. encrypted API key)
    ModelsDB-->>-FlowExecOrch: Return details
    Note over FlowExecOrch: Decrypts API key
    FlowExecOrch->>+ModelsDB: Get data for dynamic prompt placeholders
    ModelsDB-->>-FlowExecOrch: Return context data
    Note over FlowExecOrch: Resolves prompt, prepares OpenHands context (decrypted API key, allowed MCPs)
    FlowExecOrch->>+OpenHandsInfra: Request OpenHands Agent session (with context)
    OpenHandsInfra->>+OHAgent: Starts Agent in new container
    OHAgent->>+AIModel_API: Interacts with AI model (sends prompt, receives responses)
    AIModel_API-->>-OHAgent: AI model responses
    alt If AI model decides to use an MCP tool
        OHAgent->>+MCP_Srv: Calls allowed MCP tool directly
        MCP_Srv-->>-OHAgent: Tool result
    end
    OHAgent-->>-OpenHandsInfra: Execution logs/status
    OpenHandsInfra-->>-FlowExecOrch: Execution logs/status/results
    FlowExecOrch->>+ModelsDB: Store execution results in FlowExecutions table
```

### 5. Interaction with Existing Components

*   **`SpaceModels`:**
    *   Will house the new SQLAlchemy models and Pydantic schemas for `Flows`, `AIModels`, and `FlowExecutions`.
    *   CRUD operations for these new entities will be added to `SpaceModels`.
    *   Will be queried by the Flow Execution Orchestrator to resolve dynamic prompt content.
*   **`SpaceSync` / Webhook Infrastructure:**
    *   The existing webhook ingestion mechanism within the main `SpaceBridge API` will publish a `process_webhook_event` task to the NATS task queue.
    *   The `SpaceSync` worker, upon receiving this task, will be responsible for triggering the appropriate Agentic Flows.
*   **`SpaceBridge API`:**
    *   Will be extended with new RESTful API endpoints for:
        *   Managing `Flows` (CRUD, enable/disable, list presets).
        *   Managing `AIModels` (CRUD, share).
        *   Retrieving `FlowExecution` history, status, and logs (including links or content from OpenHands logs).
*   **`SpaceBridge-MCP` (and other MCP Servers):**
    *   MCP servers are *consumers* in this context. The OpenHands agents, as configured per Flow, will directly call tools on these MCP servers.
    *   The `Flow` definition will specify which MCP servers and which specific tools on those servers the agent is permitted to use.

### 6. OpenHands Integration - Key Aspects

*   **Flow to OpenHands Configuration:** The `Flow.openhands_agent_config` field will store JSON specifying the OpenHands agent type (e.g., `CodeActAgent`, `PlannerAgent`) and any necessary parameters for that agent. The Flow Execution Orchestrator translates this, along with the resolved prompt and AI model details, into the arguments needed to start an OpenHands session.
*   **Dynamic Prompts:** The Flow Execution Orchestrator resolves placeholders in `Flow.prompt_template` *before* passing the final prompt to OpenHands.
*   **AI Model Selection & API Key Management:**
    *   `Flow.ai_model_id` links to a `AIModel` record.
    *   `AIModel.api_key_encrypted` stores the encrypted API key in the database (for initial implementation).
    *   The Flow Execution Orchestrator is responsible for retrieving this encrypted key, decrypting it, and passing the plaintext API key securely to the OpenHands agent session, ideally as an environment variable or secure input specific to that containerized session. (Future: Retrieve from OpenBAO via a reference).
*   **MCP Tool Discovery & Invocation:**
    *   The `Flow.allowed_mcp_servers` and `Flow.allowed_mcp_tools` define the explicit allowlist.
    *   The OpenHands agent environment will need to be configured such that it can make network calls to these allowed MCP servers.
    *   If MCPs require authentication, mechanisms for securely providing necessary tokens/keys to the OpenHands agent for *only* the allowed MCPs will be needed. This might involve the Flow Execution Orchestrator injecting temporary credentials or connection details into the OpenHands session.
    *   OpenHands' own tool/action definition capabilities will be used to represent the allowed MCP tools to the AI model.

### 7. Security Considerations

*   **API Key Security:**
    *   **Initial Implementation:** AI model API keys (`AIModel.api_key`) will be stored unencrypted in the database.
    *   **Future Enhancement (OpenBAO Integration):** An issue should be tracked to migrate to storing API keys in OpenBAO (or a similar dedicated secrets management system). The database would then store only a reference to the secret in OpenBAO.
    *   The Flow Execution Orchestrator needs appropriate permissions to decrypt these keys (initial phase) or retrieve them from the vault (future phase) at runtime and inject them securely into the OpenHands agent's environment.
    *   Least privilege access for the orchestrator to decryption keys or the secrets vault.
*   **MCP Access Control:**
    *   The `allowed_mcp_servers` and `allowed_mcp_tools` in the `Flow` definition act as a strict allowlist.
    *   The OpenHands agent environment must be configured (e.g., network policies if running in Kubernetes, or wrapper logic around tool calls) to prevent calls to unlisted MCPs or tools.
    *   Consider if MCPs themselves have authentication/authorization; if so, the Flow execution might need to propagate user/Flow identity or use pre-configured service accounts.
*   **Input Validation & Sanitization:**
    *   Validate all inputs for Flow definitions, especially prompt templates and configurations.
    *   Sanitize any data from events or dynamic context before it's incorporated into prompts to prevent injection attacks against the AI model or downstream tools.
*   **Resource Limits for Agents:**
    *   OpenHands agents (especially if running in containers) should have resource limits (CPU, memory, execution time) to prevent abuse or runaway processes.
*   **Logging and Auditing:**
    *   Comprehensive logging of Flow executions, including which MCP tools were called with what parameters (sensitive data redacted).
    *   Audit trails for changes to `Flows` and `AIModels`.
*   **Permissions:**
    *   Role-based access control (RBAC) for managing `Flows` and `AIModels` via the SpaceBridge API. Users should only be able to create/edit/view Flows and AIModels within their authorized scope (e.g., organization).

### 8. Scalability and Extensibility

*   **Task Queue (NATS):** NATS is chosen for its high performance, lightweight nature, and scalability, allowing the system to handle a high volume of incoming tasks.
*   **Flow Trigger Service:** Can be scaled horizontally if event processing becomes a bottleneck. It should be stateless.
*   **Flow Execution Orchestrator:** Can also be scaled, though individual orchestration tasks might be stateful for the duration of a Flow.
*   **OpenHands Execution Infrastructure:**
    *   Leveraging containers (Docker or Kubernetes jobs) for OpenHands agents is key to scalability. Each Flow execution runs in an isolated container.
    *   The system can be configured to run these containers on a Docker host (via socket) or a Kubernetes cluster, allowing for dynamic scaling of agent execution capacity based on demand.
    *   The orchestrator will manage the lifecycle of these containerized jobs.
*   **Database:** `SpaceModels` (PostgreSQL) should be monitored for performance. Read replicas can be used for read-heavy operations like fetching Flow definitions or execution logs.
*   **Extensibility:**
    *   **New Event Sources:** Add new parsers/adapters to publish `process_webhook_event` tasks. The Flow Trigger Service can then match these new event types.
    *   **New AI Models:** Add new `AIModel` records. The Flow Execution Orchestrator and OpenHands need to be compatible with the new model's API.
    *   **New MCP Tools/Servers:** Update the allowlist options. OpenHands agents need to be able to make calls to these new tools.
    *   **New Agent Capabilities:** As OpenHands evolves or new agent frameworks emerge, the Flow Execution Orchestrator can be adapted to integrate with them.

### 9. Preset Use Case Examples

*   **Commit to `main` -> Doc/Test Check:** When a commit lands in the `main` branch, evaluate if documentation or tests require updates. If so, check if these updates have been applied. If not, open an issue detailing what needs to be done, and/or open a Pull Request with suggested changes.
*   **New Issue Created -> Triage & Label:** Analyze new issue content, suggest priority, labels, and potentially assign to a default team/person based on keywords or project area.
*   **PR Merged -> Release Notes Draft:** Summarize changes in the Pull Request (commit messages, linked issues) and draft a section for the project's release notes.
*   **Downtime Incident (e.g., from PagerDuty/Opsgenie webhook) -> Initial Investigation:** When an incident is triggered, check the deployed version, deployment time, and relevant telemetry data. Attempt to determine the potential cause and suggest or perform initial remediation actions (e.g., rollback, restart service, scale resources) or escalate to a human with a summary.
*   **New User Feedback (e.g., via a dedicated form or email integration) -> Summarize & Categorize:** Parse incoming user feedback, summarize key points, categorize it (e.g., bug report, feature request, question), and create a corresponding issue in the appropriate tracker.
*   **Scheduled Code Quality Scan (e.g., triggered by an internal cron-like event) -> Analyze & Report:** Trigger a static analysis tool (or use an MCP tool that does this), have the agent review the results, summarize critical issues, and create tasks for them in the issue tracker.
