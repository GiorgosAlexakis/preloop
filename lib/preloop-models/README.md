# SpaceModels Library

SpaceModels is a SQLAlchemy-based ORM library that provides a comprehensive set of models and CRUD operations for SpaceBridge and related applications. This library aims to unify data models across the SpaceBridge ecosystem.

## Installation

1. Clone the repository:
```bash
git clone https://github.com/spacecode/spacemodels.git
cd spacemodels
```

2. Create a virtual environment (optional but recommended):
```bash
python -m venv .venv
source .venv/bin/activate  # On Windows: .venv\Scripts\activate
```

3. Install the package:
```bash
pip install -r requirements.txt
pip install -e .  # Install in development mode
```

4. Set up your database:
```bash
# For PostgreSQL (recommended for production)
export DATABASE_URL="postgresql+psycopg://user:password@localhost/spacemodels"

# For SQLite (development/testing)
export DATABASE_URL="sqlite:///./spacemodels.db"
```

## Usage

```python
from spacemodels.db.session import get_db_session
from spacemodels.crud import crud_account, crud_tracker

# Get database session
db = next(get_db_session())

# Create a new account
new_account = crud_account.create(
    db, 
    obj_in={
        "username": "johndoe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "hashed_password": "hashed_password_here"
    }
)

# Set up a GitHub tracker for the account
new_tracker = crud_tracker.create(
    db,
    obj_in={
        "name": "GitHub Issues",
        "tracker_type": "github",
        "account_id": new_account.id,
        "api_key": "github_token_here",
        "connection_details": {
            "repository": "owner/repo"
        }
    }
)

# Always close the session when done
db.close()
```

See [Usage Examples](docs/usage_examples.md) for more detailed examples.

## Core Models

### Base Model

All models should inherit from the `Base` class which provides:
- Automatic table name generation
- Created/updated timestamps
- Serialization methods
- UUID primary keys

### Account Model

```python
class Account(Base):
    """Account model for user authentication and authorization."""
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    
    # Account details
    username: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    email: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    full_name: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Authentication
    hashed_password: Mapped[str] = mapped_column(String(255), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    is_superuser: Mapped[bool] = mapped_column(default=False)
    
    # OAuth information
    oauth_provider: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    oauth_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    
    # Generic metadata field for extensibility
    metadata: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # Relationships
    trackers: Mapped[List["Tracker"]] = relationship(
        "Tracker", back_populates="account", cascade="all, delete-orphan"
    )
    organizations: Mapped[List["AccountOrganization"]] = relationship(
        "AccountOrganization", back_populates="account", cascade="all, delete-orphan"
    )
    
    # Many-to-many relationship helper
    organization_roles: Mapped[Dict[str, str]] = association_proxy(
        "organizations", "role", creator=lambda k, v: AccountOrganization(organization_id=k, role=v)
    )
```

### Tracker Model

```python
class TrackerType(enum.Enum):
    """Enum for tracker types."""
    GITHUB = "github"
    GITLAB = "gitlab"
    JIRA = "jira"


class Tracker(Base):
    """Tracker model - represents an integration with an issue tracking system."""
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    
    # Tracker details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    tracker_type: Mapped[str] = mapped_column(
        String(50), 
        nullable=False,
        comment="Possible values: github, gitlab, jira"
    )
    url: Mapped[Optional[str]] = mapped_column(
        String(1000), 
        nullable=True,
        comment="URL to the tracker (required for Jira, optional for others)"
    )
    api_key: Mapped[str] = mapped_column(
        String(1000), 
        nullable=False, 
        comment="Encrypted API key or token for authentication"
    )
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Additional connection details stored as JSON
    # Structure examples:
    # GitHub: {
    #     "repository": "owner/repo",
    #     "private_key_path": "/path/to/key.pem",  # For GitHub Apps
    #     "app_id": "12345",                       # For GitHub Apps
    #     "installation_id": "67890"               # For GitHub Apps
    # }
    # GitLab: {
    #     "project_id": "12345",
    #     "group_path": "my-group"
    # }
    # Jira: {
    #     "project_key": "PROJECT",
    #     "cloud_id": "cloud-id-for-jira-cloud",
    #     "use_oauth": true,
    #     "oauth_settings": {...}
    # }
    connection_details: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # Generic metadata field for extensibility
    metadata: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # Foreign keys
    account_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("account.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="trackers")
    organizations: Mapped[List["Organization"]] = relationship(
        "Organization", back_populates="tracker", cascade="all, delete-orphan"
    )
    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="tracker", cascade="all, delete-orphan"
    )
    
    # Validation status
    is_valid: Mapped[bool] = mapped_column(default=False)
    last_validation: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    validation_message: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    @validates("tracker_type")
    def validate_tracker_type(self, key, type_):
        """Validate that tracker_type is one of the allowed values."""
        if type_ not in [t.value for t in TrackerType]:
            raise ValueError(f"Invalid tracker type: {type_}. Must be one of: {', '.join([t.value for t in TrackerType])}")
        return type_
    
    @validates("url")
    def validate_url(self, key, url):
        """Validate URL is provided for Jira trackers."""
        if self.tracker_type == TrackerType.JIRA.value and not url:
            raise ValueError("URL is required for Jira trackers")
        return url
```

### Organization Model

```python
class Organization(Base):
    """Organization model - a top-level entity that can contain multiple projects."""
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    
    # Organization details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str] = mapped_column(
        String(100), unique=True, nullable=False, index=True
    )
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Organization settings stored as JSON
    settings: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True, default=dict)
    
    # Generic metadata field for extensibility
    metadata: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # Foreign keys
    tracker_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tracker.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relationships
    tracker: Mapped["Tracker"] = relationship("Tracker", back_populates="organizations")
    projects: Mapped[List["Project"]] = relationship(
        "Project", back_populates="organization", cascade="all, delete-orphan"
    )
    accounts: Mapped[List["AccountOrganization"]] = relationship(
        "AccountOrganization", back_populates="organization"
    )
```

### AccountOrganization Model (Join table)

```python
class AccountOrganization(Base):
    """Join table for accounts and organizations with roles."""
    
    # Composite primary key
    account_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("account.id", ondelete="CASCADE"), primary_key=True
    )
    organization_id: Mapped[str] = mapped_column(
        String(36), ForeignKey("organization.id", ondelete="CASCADE"), primary_key=True
    )
    
    # Role in the organization
    role: Mapped[str] = mapped_column(String(50), default="member")
    
    # Relationships
    account: Mapped["Account"] = relationship("Account", back_populates="organizations")
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="accounts"
    )
```

### Project Model

```python
class Project(Base):
    """Project model - belongs to an organization."""
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    
    # Project details
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    identifier: Mapped[str] = mapped_column(String(100), nullable=False, index=True)
    description: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Foreign keys
    organization_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("organization.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Project settings stored as JSON
    settings: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True, default=dict)
    
    # Project-specific tracker settings
    # For configuring project-specific keys, filters, etc.
    tracker_settings: Mapped[Optional[Dict]] = mapped_column(JSON, nullable=True, default=dict)
    
    # Generic metadata field for extensibility
    metadata: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # Relationships
    organization: Mapped["Organization"] = relationship(
        "Organization", back_populates="projects"
    )
    issues: Mapped[List["Issue"]] = relationship(
        "Issue", back_populates="project", cascade="all, delete-orphan"
    )
```

### Issue Model

```python
class Issue(Base):
    """Issue model - represents a task, bug, or feature in a project."""
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    
    # Issue details
    title: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[Optional[str]] = mapped_column(String(5000), nullable=True)
    status: Mapped[str] = mapped_column(String(50), nullable=False, default="open")
    priority: Mapped[Optional[str]] = mapped_column(String(50), nullable=True)
    issue_type: Mapped[str] = mapped_column(String(50), nullable=False, default="task")
    
    # External issue identifiers
    external_id: Mapped[Optional[str]] = mapped_column(String(255), nullable=True)
    external_url: Mapped[Optional[str]] = mapped_column(String(1000), nullable=True)
    
    # Foreign keys
    project_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("project.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    tracker_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("tracker.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # Relationships
    project: Mapped["Project"] = relationship("Project", back_populates="issues")
    tracker: Mapped["Tracker"] = relationship("Tracker", back_populates="issues")
    embeddings: Mapped[List["IssueEmbedding"]] = relationship(
        "IssueEmbedding", back_populates="issue", cascade="all, delete-orphan"
    )
    
    # Metadata stored as JSON (for custom fields, labels, etc.)
    metadata: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # Timestamps for issue-specific events
    last_updated_external: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)
    last_synced: Mapped[Optional[datetime]] = mapped_column(DateTime, nullable=True)


class EmbeddingModel(Base):
    """Model to track different embedding models used in the system."""
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    
    # Embedding model details
    name: Mapped[str] = mapped_column(String(255), nullable=False, unique=True)
    provider: Mapped[str] = mapped_column(String(100), nullable=False)  # 'openai', 'google', etc.
    version: Mapped[str] = mapped_column(String(100), nullable=False)
    dimensions: Mapped[int] = mapped_column(Integer, nullable=False)
    is_active: Mapped[bool] = mapped_column(default=True)
    
    # Additional embedding model properties
    metadata: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # Relationships
    embeddings: Mapped[List["IssueEmbedding"]] = relationship(
        "IssueEmbedding", back_populates="embedding_model"
    )
    
    __table_args__ = (
        # Enforce unique composite key for provider+version
        UniqueConstraint('provider', 'version', name='uix_provider_version'),
    )


class IssueEmbedding(Base):
    """Model to store embeddings for issues.
    
    This flexible design supports embeddings of different dimensions.
    """
    
    # Primary key
    id: Mapped[str] = mapped_column(String(36), primary_key=True, index=True)  # UUID
    
    # Foreign keys
    issue_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("issue.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    embedding_model_id: Mapped[str] = mapped_column(
        String(36),
        ForeignKey("embeddingmodel.id", ondelete="CASCADE"),
        nullable=False,
        index=True,
    )
    
    # The actual embedding vector (PostgreSQL vector type)
    # We define it as a JSON field here to accommodate SQLAlchemy's type system,
    # but at the database level, use an appropriate vector type with JSONB fallback
    # For PostgreSQL, use the pgvector extension's vector type
    embedding: Mapped[Dict] = mapped_column(
        JSON,  # Will be mapped to vector type in PostgreSQL with pgvector
        nullable=False,
        comment="Embedding vector, stored as JSON array in SQLite, vector in PostgreSQL"
    )
    
    # Metadata about how this embedding was created
    metadata: Mapped[Dict] = mapped_column(JSON, nullable=True, default=dict)
    
    # When this embedding was created
    created_at: Mapped[datetime] = mapped_column(
        DateTime, server_default=func.now(), nullable=False
    )
    
    # Relationships
    issue: Mapped["Issue"] = relationship("Issue", back_populates="embeddings")
    embedding_model: Mapped["EmbeddingModel"] = relationship(
        "EmbeddingModel", back_populates="embeddings"
    )
    
    __table_args__ = (
        # Enforce one embedding per issue per model
        UniqueConstraint('issue_id', 'embedding_model_id', name='uix_issue_embedding_model'),
    )
```

## CRUD Operations

The library should implement the following CRUD operations for each model:

### Base CRUD Methods

```python
class CRUDBase[T]:
    """Base class for CRUD operations on models."""
    
    def __init__(self, model: Type[T]):
        self.model = model
    
    def get(self, db: Session, id: str) -> Optional[T]:
        """Get entity by ID."""
        return db.query(self.model).filter(self.model.id == id).first()
    
    def get_multi(
        self, db: Session, *, skip: int = 0, limit: int = 100, **filters
    ) -> List[T]:
        """Get multiple entities with optional filtering."""
        query = db.query(self.model)
        for key, value in filters.items():
            if hasattr(self.model, key):
                query = query.filter(getattr(self.model, key) == value)
        return query.offset(skip).limit(limit).all()
    
    def create(self, db: Session, *, obj_in: Dict[str, Any]) -> T:
        """Create new entity."""
        if 'id' not in obj_in:
            obj_in['id'] = str(uuid.uuid4())
        obj = self.model(**obj_in)
        db.add(obj)
        db.commit()
        db.refresh(obj)
        return obj
    
    def update(
        self, db: Session, *, db_obj: T, obj_in: Union[Dict[str, Any], BaseModel]
    ) -> T:
        """Update entity."""
        if isinstance(obj_in, dict):
            update_data = obj_in
        else:
            update_data = obj_in.dict(exclude_unset=True)
        
        for field in update_data:
            if hasattr(db_obj, field):
                setattr(db_obj, field, update_data[field])
        
        db.add(db_obj)
        db.commit()
        db.refresh(db_obj)
        return db_obj
    
    def delete(self, db: Session, *, id: str) -> Optional[T]:
        """Delete entity."""
        obj = db.query(self.model).get(id)
        if obj:
            db.delete(obj)
            db.commit()
        return obj
```

### Model-Specific CRUD Extensions

Each model should have its own CRUD class extending the base with model-specific operations:

```python
class CRUDAccount(CRUDBase[Account]):
    """CRUD operations for Account model."""
    
    def get_by_email(self, db: Session, *, email: str) -> Optional[Account]:
        """Get account by email."""
        return db.query(Account).filter(Account.email == email).first()
    
    def get_by_username(self, db: Session, *, username: str) -> Optional[Account]:
        """Get account by username."""
        return db.query(Account).filter(Account.username == username).first()
    
    def create_with_organization(
        self, db: Session, *, obj_in: Dict[str, Any], organization_id: str, role: str = "owner"
    ) -> Account:
        """Create account and link to organization."""
        account = self.create(db, obj_in=obj_in)
        db_obj = AccountOrganization(
            account_id=account.id,
            organization_id=organization_id,
            role=role
        )
        db.add(db_obj)
        db.commit()
        return account
    
    def get_active(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Account]:
        """Get active accounts."""
        return (
            db.query(Account)
            .filter(Account.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def deactivate(self, db: Session, *, id: str) -> Optional[Account]:
        """Deactivate an account."""
        account = self.get(db, id=id)
        if account:
            account.is_active = False
            db.add(account)
            db.commit()
            db.refresh(account)
        return account


class CRUDTracker(CRUDBase[Tracker]):
    """CRUD operations for Tracker model."""
    
    def validate_connection(self, db: Session, *, tracker_id: str) -> bool:
        """Validate tracker connection and update status."""
        tracker = self.get(db, id=tracker_id)
        if not tracker:
            return False
        
        # Logic to test connection based on tracker_type
        is_valid = False
        message = "Connection failed"
        
        try:
            # Connection validation logic here
            is_valid = True
            message = "Connection successful"
        except Exception as e:
            message = str(e)
        
        # Update tracker validation status
        tracker.is_valid = is_valid
        tracker.last_validation = datetime.utcnow()
        tracker.validation_message = message
        
        db.add(tracker)
        db.commit()
        db.refresh(tracker)
        
        return is_valid
    
    def get_for_account(
        self, db: Session, *, account_id: str, tracker_type: Optional[str] = None
    ) -> List[Tracker]:
        """Get trackers for an account, optionally filtered by type."""
        query = db.query(Tracker).filter(Tracker.account_id == account_id)
        if tracker_type:
            query = query.filter(Tracker.tracker_type == tracker_type)
        return query.all()
    
    def get_active(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Tracker]:
        """Get active trackers."""
        return (
            db.query(Tracker)
            .filter(Tracker.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def deactivate(self, db: Session, *, id: str) -> Optional[Tracker]:
        """Deactivate a tracker."""
        tracker = self.get(db, id=id)
        if tracker:
            tracker.is_active = False
            db.add(tracker)
            db.commit()
            db.refresh(tracker)
        return tracker


class CRUDOrganization(CRUDBase[Organization]):
    """CRUD operations for Organization model."""
    
    def get_by_identifier(self, db: Session, *, identifier: str) -> Optional[Organization]:
        """Get organization by unique identifier."""
        return db.query(Organization).filter(Organization.identifier == identifier).first()
    
    def get_for_account(self, db: Session, *, account_id: str) -> List[Organization]:
        """Get organizations for an account."""
        return (
            db.query(Organization)
            .join(AccountOrganization)
            .filter(AccountOrganization.account_id == account_id)
            .all()
        )
    
    def get_for_tracker(
        self, db: Session, *, tracker_id: str, skip: int = 0, limit: int = 100
    ) -> List[Organization]:
        """Get organizations for a tracker."""
        return (
            db.query(Organization)
            .filter(Organization.tracker_id == tracker_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_active(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Organization]:
        """Get active organizations."""
        return (
            db.query(Organization)
            .filter(Organization.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def deactivate(self, db: Session, *, id: str) -> Optional[Organization]:
        """Deactivate an organization."""
        organization = self.get(db, id=id)
        if organization:
            organization.is_active = False
            db.add(organization)
            db.commit()
            db.refresh(organization)
        return organization


class CRUDProject(CRUDBase[Project]):
    """CRUD operations for Project model."""
    
    def get_by_identifier(
        self, db: Session, *, organization_id: str, identifier: str
    ) -> Optional[Project]:
        """Get project by organization ID and project identifier."""
        return (
            db.query(Project)
            .filter(
                Project.organization_id == organization_id,
                Project.identifier == identifier
            )
            .first()
        )
    
    def get_for_organization(
        self, db: Session, *, organization_id: str, skip: int = 0, limit: int = 100
    ) -> List[Project]:
        """Get projects for an organization."""
        return (
            db.query(Project)
            .filter(Project.organization_id == organization_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def get_active(self, db: Session, *, skip: int = 0, limit: int = 100) -> List[Project]:
        """Get active projects."""
        return (
            db.query(Project)
            .filter(Project.is_active == True)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def deactivate(self, db: Session, *, id: str) -> Optional[Project]:
        """Deactivate a project."""
        project = self.get(db, id=id)
        if project:
            project.is_active = False
            db.add(project)
            db.commit()
            db.refresh(project)
        return project


class CRUDIssue(CRUDBase[Issue]):
    """CRUD operations for Issue model."""
    
    def create_with_external(
        self, db: Session, *, obj_in: Dict[str, Any], sync_to_tracker: bool = True
    ) -> Issue:
        """Create issue, optionally syncing with external tracker."""
        issue = self.create(db, obj_in=obj_in)
        
        if sync_to_tracker and issue.tracker_id:
            # Logic to sync issue to external tracker
            # Update external_id and external_url after sync
            pass
        
        return issue
    
    def get_for_project(
        self, db: Session, *, project_id: str, status: Optional[str] = None, 
        issue_type: Optional[str] = None, skip: int = 0, limit: int = 100
    ) -> List[Issue]:
        """Get issues for a project with optional filters."""
        query = db.query(Issue).filter(Issue.project_id == project_id)
        
        if status:
            query = query.filter(Issue.status == status)
        if issue_type:
            query = query.filter(Issue.issue_type == issue_type)
            
        return query.order_by(Issue.created_at.desc()).offset(skip).limit(limit).all()
    
    def get_for_tracker(
        self, db: Session, *, tracker_id: str, skip: int = 0, limit: int = 100
    ) -> List[Issue]:
        """Get issues for a tracker."""
        return (
            db.query(Issue)
            .filter(Issue.tracker_id == tracker_id)
            .order_by(Issue.created_at.desc())
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def sync_from_external(
        self, db: Session, *, tracker_id: str, external_id: str
    ) -> Optional[Issue]:
        """Sync issue from external tracker by ID."""
        # Logic to fetch issue details from external tracker
        # and update or create local issue
        pass
    
    def create_embeddings(
        self, db: Session, *, issue_id: str, force_update: bool = False
    ) -> Dict[str, Any]:
        """Create embeddings for an issue using all active embedding models."""
        issue = self.get(db, id=issue_id)
        if not issue:
            raise ValueError(f"Issue with ID {issue_id} not found")
            
        # Get active embedding models
        embedding_models = (
            db.query(EmbeddingModel)
            .filter(EmbeddingModel.is_active == True)
            .all()
        )
        
        results = {}
        for model in embedding_models:
            # Check if embedding already exists
            existing = (
                db.query(IssueEmbedding)
                .filter(
                    IssueEmbedding.issue_id == issue_id,
                    IssueEmbedding.embedding_model_id == model.id
                )
                .first()
            )
            
            if existing and not force_update:
                results[model.name] = "already_exists"
                continue
                
            # Generate text to embed (typically title + description)
            text_to_embed = f"{issue.title}: {issue.description or ''}"
            
            # In a real implementation, this would call the respective API
            # Here we're just creating a placeholder vector
            embedding_vector = [0.0] * model.dimensions  # Placeholder
            
            # Create or update embedding
            if existing:
                existing.embedding = embedding_vector
                existing.metadata = {
                    "updated_at": datetime.utcnow().isoformat(),
                    "text_processed": text_to_embed[:100] + "..." if len(text_to_embed) > 100 else text_to_embed
                }
                db.add(existing)
                results[model.name] = "updated"
            else:
                new_embedding = IssueEmbedding(
                    id=str(uuid.uuid4()),
                    issue_id=issue_id,
                    embedding_model_id=model.id,
                    embedding=embedding_vector,
                    metadata={
                        "text_processed": text_to_embed[:100] + "..." if len(text_to_embed) > 100 else text_to_embed
                    }
                )
                db.add(new_embedding)
                results[model.name] = "created"
                
        db.commit()
        return results


class CRUDEmbeddingModel(CRUDBase[EmbeddingModel]):
    """CRUD operations for EmbeddingModel model."""
    
    def get_by_name(self, db: Session, *, name: str) -> Optional[EmbeddingModel]:
        """Get embedding model by name."""
        return db.query(EmbeddingModel).filter(EmbeddingModel.name == name).first()
    
    def get_by_provider_version(
        self, db: Session, *, provider: str, version: str
    ) -> Optional[EmbeddingModel]:
        """Get embedding model by provider and version."""
        return (
            db.query(EmbeddingModel)
            .filter(
                EmbeddingModel.provider == provider,
                EmbeddingModel.version == version
            )
            .first()
        )
    
    def get_active(self, db: Session) -> List[EmbeddingModel]:
        """Get all active embedding models."""
        return db.query(EmbeddingModel).filter(EmbeddingModel.is_active == True).all()


class CRUDIssueEmbedding(CRUDBase[IssueEmbedding]):
    """CRUD operations for IssueEmbedding model."""
    
    def get_for_issue(
        self, db: Session, *, issue_id: str
    ) -> Dict[str, IssueEmbedding]:
        """Get all embeddings for an issue, keyed by model name."""
        embeddings = (
            db.query(IssueEmbedding, EmbeddingModel)
            .join(EmbeddingModel)
            .filter(IssueEmbedding.issue_id == issue_id)
            .all()
        )
        
        return {model.name: embedding for embedding, model in embeddings}
    
    def get_for_model(
        self, db: Session, *, model_id: str, skip: int = 0, limit: int = 100
    ) -> List[IssueEmbedding]:
        """Get embeddings for a specific model."""
        return (
            db.query(IssueEmbedding)
            .filter(IssueEmbedding.embedding_model_id == model_id)
            .offset(skip)
            .limit(limit)
            .all()
        )
    
    def similarity_search(
        self, db: Session, *, model_id: str, query_vector: List[float], limit: int = 10
    ) -> List[Tuple[Issue, float]]:
        """
        Search for similar issues based on vector similarity.
        
        Note: This is a placeholder for the actual implementation that would 
        use either PostgreSQL with pgvector or an external vector database.
        
        Returns a list of (issue, similarity_score) tuples.
        """
        # This would actually use a database-specific vector similarity search
        # For PostgreSQL + pgvector, it would use:
        # SELECT i.*, 1 - (e.embedding <=> :query_vector) as similarity
        # FROM issue i
        # JOIN issue_embedding e ON i.id = e.issue_id
        # WHERE e.embedding_model_id = :model_id
        # ORDER BY similarity DESC
        # LIMIT :limit
        
        # Placeholder implementation
        embeddings = (
            db.query(IssueEmbedding, Issue)
            .join(Issue)
            .filter(IssueEmbedding.embedding_model_id == model_id)
            .limit(limit)
            .all()
        )
        
        # Simulate similarity scores (random values between 0.5 and 1.0)
        import random
        results = [(issue, random.uniform(0.5, 1.0)) for embedding, issue in embeddings]
        
        # Sort by similarity (highest first)
        results.sort(key=lambda x: x[1], reverse=True)
        
        return results
```

## Database Session Management

```python
def get_engine(database_url: Optional[str] = None):
    """Create SQLAlchemy engine with fallback for testing."""
    url = database_url or os.getenv(
        "DATABASE_URL", "postgresql+psycopg://postgres:postgres@localhost/spacemodels"
    )
    
    try:
        engine = create_engine(url)
        # Test the connection
        with engine.connect() as conn:
            conn.execute(text("SELECT 1"))
        logger.info(f"Connected to database using {url}")
        return engine
    except (ImportError, SQLAlchemyError) as e:
        logger.warning(
            f"Database connection failed: {e}. Using SQLite in memory for testing purposes."
        )
        return create_engine("sqlite:///:memory:")


def get_session_factory(engine=None):
    """Get session factory for database."""
    engine = engine or get_engine()
    return sessionmaker(autocommit=False, autoflush=False, bind=engine)


def get_db_session() -> Generator[Session, None, None]:
    """Get a database session."""
    SessionLocal = get_session_factory()
    db = SessionLocal()
    try:
        yield db
    finally:
        db.close()
```

## Usage Example

```python
# Create a new account with a tracker
from spacemodels.crud import crud_account, crud_tracker
from spacemodels.db.session import get_db_session

db = next(get_db_session())
new_account = crud_account.create(
    db, 
    obj_in={
        "username": "johndoe",
        "email": "john@example.com",
        "full_name": "John Doe",
        "hashed_password": "hashed_password_here",
        "is_active": True,
        "metadata": {
            "timezone": "America/New_York",
            "preferences": {
                "notifications": {
                    "email": True,
                    "in_app": True
                }
            }
        }
    }
)

# Set up a GitHub tracker for the account
new_tracker = crud_tracker.create(
    db,
    obj_in={
        "name": "GitHub Issues",
        "tracker_type": "github",
        "account_id": new_account.id,
        "is_active": True,
        "url": "https://api.github.com",
        "api_key": "encrypted_github_token_here",
        "connection_details": {
            "repository": "owner/repo"
        },
        "metadata": {
            "app_integration_type": "personal_access_token",
            "rate_limit_remaining": 5000
        }
    }
)

# Create an organization linked to the tracker
from spacemodels.crud import crud_organization

new_org = crud_organization.create(
    db, 
    obj_in={
        "name": "Example Organization",
        "identifier": "example-org",
        "description": "This is an example organization",
        "is_active": True,
        "tracker_id": new_tracker.id,
        "metadata": {
            "industry": "Technology",
            "size": "Medium",
            "location": "San Francisco, CA"
        }
    }
)

# Link the account to the organization with a role
from spacemodels.models.account import AccountOrganization

db_obj = AccountOrganization(
    account_id=new_account.id,
    organization_id=new_org.id,
    role="owner"
)
db.add(db_obj)
db.commit()

# Create a project in the organization
from spacemodels.crud import crud_project

new_project = crud_project.create(
    db,
    obj_in={
        "name": "Example Project",
        "identifier": "example-project",
        "organization_id": new_org.id,
        "description": "This is an example project",
        "is_active": True,
        "tracker_settings": {
            "project_key": "EXP",  # For JIRA
            "labels": ["spacebridge"]  # For GitHub/GitLab
        },
        "metadata": {
            "team": "Backend",
            "stage": "Development",
            "custom_fields": {
                "target_release": "v1.0",
                "customer_facing": True
            }
        }
    }
)

# Create an issue
from spacemodels.crud import crud_issue

new_issue = crud_issue.create(
    db,
    obj_in={
        "title": "Example Issue",
        "description": "This is an example issue",
        "status": "open",
        "issue_type": "bug",
        "priority": "high",
        "project_id": new_project.id,
        "tracker_id": new_tracker.id,
        "metadata": {
            "labels": ["backend", "critical", "customer-reported"],
            "custom_fields": {
                "story_points": 5,
                "reporter_name": "Jane Smith",
                "expected_behavior": "The API should return a 200 status code"
            }
        }
    }
)

# Set up embedding models
from spacemodels.crud import crud_embedding_model

openai_model = crud_embedding_model.create(
    db,
    obj_in={
        "name": "text-embedding-3-large",
        "provider": "openai",
        "version": "v1",
        "dimensions": 3072,
        "is_active": True,
        "metadata": {
            "context_length": 8191,
            "api_version": "2023-05-15"
        }
    }
)

gemini_model = crud_embedding_model.create(
    db,
    obj_in={
        "name": "gemini-embedding-exp-03-07",
        "provider": "google",
        "version": "exp-03-07",
        "dimensions": 3072,
        "is_active": True,
        "metadata": {
            "context_length": 32768,
            "api_version": "v1"
        }
    }
)

# Create embeddings for the issue
from spacemodels.crud import crud_issue_embedding

# Create an embedding vector (normally this would come from the API)
# This is a simple placeholder with 3072 dimensions, initialized with random values
import numpy as np
sample_embedding = np.random.rand(3072).tolist()

openai_embedding = crud_issue_embedding.create(
    db,
    obj_in={
        "issue_id": new_issue.id,
        "embedding_model_id": openai_model.id,
        "embedding": sample_embedding,
        "metadata": {
            "text_processed": "Example Issue: This is an example issue",
            "token_count": 8,
            "processing_time_ms": 152
        }
    }
)

# For demonstration, create another embedding with the same sample data
# In a real system, this would be the result of calling the Gemini API
gemini_embedding = crud_issue_embedding.create(
    db,
    obj_in={
        "issue_id": new_issue.id,
        "embedding_model_id": gemini_model.id,
        "embedding": sample_embedding,
        "metadata": {
            "text_processed": "Example Issue: This is an example issue",
            "token_count": 10,
            "processing_time_ms": 98
        }
    }
)
```