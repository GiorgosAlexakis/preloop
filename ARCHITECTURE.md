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
