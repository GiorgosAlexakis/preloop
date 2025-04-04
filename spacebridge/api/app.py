"""FastAPI application for SpaceBridge.

This FastAPI application provides HTTP endpoints for authentication and management
of issue tracking systems.
"""

import logging
import os
import json
from datetime import datetime
from pathlib import Path

from fastapi import Depends, FastAPI, Request
from fastapi.middleware.cors import CORSMiddleware
from fastapi.openapi.docs import get_redoc_html, get_swagger_ui_html
from fastapi.openapi.utils import get_openapi
from fastapi.responses import HTMLResponse
from fastapi.staticfiles import StaticFiles
from fastapi.templating import Jinja2Templates
from starlette.middleware.base import BaseHTTPMiddleware
from fastapi.encoders import jsonable_encoder

from spacebridge import __version__
from spacebridge.api.auth import auth_router, get_current_active_user
from spacebridge.api.endpoints import (
    comments,
    health,
    issues,
    organizations,
    projects,
    trackers,
)
from spacemodels.db.session import get_db_session
from spacemodels.db.setup import setup_database
from spacemodels.models.api_usage import ApiUsage

logger = logging.getLogger(__name__)


class ApiUsageMiddleware(BaseHTTPMiddleware):
    """Middleware to track API usage."""

    async def dispatch(self, request: Request, call_next):
        """Process a request and track API usage.

        Args:
            request: The request to process.
            call_next: The next middleware to call.

        Returns:
            The response from the next middleware.
        """
        # Skip tracking for non-api routes
        path = request.url.path
        if not path.startswith("/api/v1") or path.startswith("/api/v1/health"):
            return await call_next(request)

        start_time = datetime.utcnow()
        response = await call_next(request)
        duration = (datetime.utcnow() - start_time).total_seconds()

        # Extract tracking information
        method = request.method
        status_code = response.status_code
        user = None
        action_type = None

        # Determine the action type based on the path and method
        if "/issues" in path:
            if method == "POST":
                action_type = "create_issue"
            elif method == "PUT" or method == "PATCH":
                action_type = "update_issue"
            elif method == "DELETE":
                action_type = "delete_issue"

        # Get username from auth token if available
        auth_header = request.headers.get("Authorization")
        if auth_header and auth_header.startswith("Bearer "):
            from spacebridge.api.auth.jwt import decode_token

            try:
                token = auth_header.replace("Bearer ", "")
                token_data = decode_token(token)
                user = getattr(token_data, "sub", None)
            except Exception:
                # Ignore errors in token decoding
                pass

        # Log usage in database
        if user and status_code < 500:  # Only log successful API calls
            try:
                session_generator = get_db_session()
                session = next(session_generator)

                try:
                    # Create usage entry
                    usage_entry = ApiUsage(
                        username=user,
                        endpoint=path,
                        method=method,
                        status_code=status_code,
                        duration=duration,
                        action_type=action_type,
                        timestamp=start_time,
                    )

                    session.add(usage_entry)
                    session.commit()
                finally:
                    session.close()
                    try:
                        # Clean up the generator
                        next(session_generator, None)
                    except StopIteration:
                        pass
            except Exception as e:
                # Don't let tracking issues affect the response
                logger.error(f"Error logging API usage: {str(e)}")

        return response


def create_app() -> FastAPI:
    """Create and configure the FastAPI application.

    Returns:
        FastAPI: The configured FastAPI application.
    """
    # Initialize FastAPI app
    app = FastAPI(
        title="SpaceBridge API",
        description="REST API for SpaceBridge issue tracking management",
        version=__version__,
        docs_url=None,  # Disable the automatic docs at /docs
        redoc_url=None,  # Disable the automatic redoc at /redoc
        openapi_url="/api/v1/openapi.json",
    )

    # Override the default JSON encoder to handle datetime objects
    class CustomJSONEncoder(json.JSONEncoder):
        def default(self, obj):
            if isinstance(obj, datetime):
                return obj.isoformat()
            return super().default(obj)

    # Replace the default jsonable_encoder function with our custom one
    def custom_jsonable_encoder(obj, *args, **kwargs):
        # First let FastAPI's encoder prepare the object
        encoded = jsonable_encoder(obj, *args, **kwargs)
        # Then manually process any datetime objects that might have been missed
        if isinstance(encoded, dict):
            for key, value in encoded.items():
                if isinstance(value, datetime):
                    encoded[key] = value.isoformat()
        elif isinstance(encoded, list):
            for i, item in enumerate(encoded):
                if isinstance(item, datetime):
                    encoded[i] = item.isoformat()
                elif isinstance(item, dict):
                    for key, value in item.items():
                        if isinstance(value, datetime):
                            item[key] = value.isoformat()
        return encoded

    # Patch FastAPI's jsonable_encoder
    import fastapi.encoders

    original_jsonable_encoder = fastapi.encoders.jsonable_encoder
    fastapi.encoders.jsonable_encoder = custom_jsonable_encoder

    # Configure CORS
    app.add_middleware(
        CORSMiddleware,
        allow_origins=["*"],  # This should be more restrictive in production
        allow_credentials=True,
        allow_methods=["*"],
        allow_headers=["*"],
    )

    # Add API usage tracking
    app.add_middleware(ApiUsageMiddleware)

    # Create static files directory with absolute path
    base_dir = Path(
        os.path.dirname(os.path.dirname(os.path.dirname(os.path.abspath(__file__))))
    )
    static_dir = base_dir / "static"
    static_css_dir = static_dir / "css"
    static_js_dir = static_dir / "js"

    os.makedirs(static_dir, exist_ok=True)
    os.makedirs(static_css_dir, exist_ok=True)
    os.makedirs(static_js_dir, exist_ok=True)

    logger.info(f"Static files directory: {static_dir}")

    # Mount static files
    app.mount("/static", StaticFiles(directory=str(static_dir)), name="static")

    # Add custom docs routes
    @app.get("/docs", include_in_schema=False)
    async def custom_swagger_ui_html():
        return get_swagger_ui_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - Swagger UI",
            oauth2_redirect_url=app.swagger_ui_oauth2_redirect_url,
            swagger_js_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui-bundle.js",
            swagger_css_url="https://cdn.jsdelivr.net/npm/swagger-ui-dist@5.9.0/swagger-ui.css",
        )

    @app.get("/redoc", include_in_schema=False)
    async def custom_redoc_html():
        return get_redoc_html(
            openapi_url=app.openapi_url,
            title=f"{app.title} - ReDoc",
            redoc_js_url="https://cdn.jsdelivr.net/npm/redoc@2.0.0/bundles/redoc.standalone.js",
        )

    # Add custom OpenAPI schema
    def custom_openapi():
        if app.openapi_schema:
            return app.openapi_schema

        openapi_schema = get_openapi(
            title=app.title,
            version=app.version,
            description=app.description,
            routes=app.routes,
        )

        # Add security schemes and requirements
        openapi_schema["components"]["securitySchemes"] = {
            "bearerAuth": {
                "type": "http",
                "scheme": "bearer",
                "bearerFormat": "JWT",
                "description": "JWT token for authentication",
            }
        }

        # Apply security to all endpoints except auth endpoints, landing page, and health checks
        excluded_prefixes = [
            "/api/v1/auth",
            "/",
            "/static",
            "/register",
            "/verify-email",
            "/forgot-password",
            "/reset-password",
            "/api/v1/health",
        ]
        for path in openapi_schema["paths"]:
            if not any(path.startswith(prefix) for prefix in excluded_prefixes):
                for method in openapi_schema["paths"][path]:
                    if method.lower() != "options":  # Skip OPTIONS method
                        openapi_schema["paths"][path][method]["security"] = [
                            {"bearerAuth": []}
                        ]

        app.openapi_schema = openapi_schema
        return app.openapi_schema

    app.openapi = custom_openapi

    # Add routers
    app.include_router(health.router, prefix="/api/v1", tags=["Health"])
    app.include_router(auth_router, prefix="/api/v1/auth", tags=["Authentication"])
    app.include_router(
        organizations.router,
        prefix="/api/v1",
        tags=["Organizations"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        projects.router,
        prefix="/api/v1",
        tags=["Projects"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        issues.router,
        prefix="/api/v1",
        tags=["Issues"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        comments.router,
        prefix="/api/v1",
        tags=["Comments"],
        dependencies=[Depends(get_current_active_user)],
    )
    app.include_router(
        trackers.router,
        prefix="/api/v1",
        tags=["Trackers"],
        dependencies=[Depends(get_current_active_user)],
    )

    # Create HTML landing page template

    # Create templates directory with absolute path
    templates_dir = base_dir / "templates"
    templates_dir.mkdir(exist_ok=True)

    # Print the templates directory path for debugging
    logger.info(f"Templates directory: {templates_dir}")

    # Create landing page template
    landing_page_path = templates_dir / "landing.html"
    if not landing_page_path.exists():
        landing_page_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>SpaceBridge - Connect Your Issue Trackers</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            line-height: 1.6;
            color: #333;
            background-color: #f8f9fa;
        }
        .hero {
            background-color: #4a86e8;
            color: white;
            padding: 80px 0;
            margin-bottom: 40px;
        }
        .feature-box {
            background: white;
            border-radius: 8px;
            padding: 25px;
            box-shadow: 0 2px 15px rgba(0,0,0,0.1);
            margin-bottom: 30px;
            transition: transform 0.3s ease;
        }
        .feature-box:hover {
            transform: translateY(-5px);
        }
        .feature-icon {
            font-size: 40px;
            margin-bottom: 15px;
            color: #4a86e8;
        }
        .cta-section {
            background-color: #f0f4f8;
            padding: 60px 0;
            margin: 40px 0;
        }
        .btn-primary {
            background-color: #4a86e8;
            border-color: #4a86e8;
            padding: 10px 20px;
            font-weight: 600;
        }
        .btn-primary:hover {
            background-color: #3a76d8;
            border-color: #3a76d8;
        }
        .footer {
            background-color: #343a40;
            color: #f8f9fa;
            padding: 30px 0;
            margin-top: 40px;
        }
        .footer a {
            color: #adb5bd;
        }
        .footer a:hover {
            color: #f8f9fa;
            text-decoration: none;
        }
    </style>
</head>
<body>
    <nav class="navbar navbar-expand-lg navbar-dark bg-dark">
        <div class="container">
            <a class="navbar-brand" href="/">SpaceBridge</a>
            <button class="navbar-toggler" type="button" data-bs-toggle="collapse" data-bs-target="#navbarNav">
                <span class="navbar-toggler-icon"></span>
            </button>
            <div class="collapse navbar-collapse" id="navbarNav">
                <ul class="navbar-nav ms-auto">
                    <li class="nav-item">
                        <a class="nav-link" href="#features">Features</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/docs">API Docs</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link" href="/login">Login</a>
                    </li>
                    <li class="nav-item">
                        <a class="nav-link btn btn-outline-light ms-2" href="/register">Sign Up</a>
                    </li>
                </ul>
            </div>
        </div>
    </nav>

    <section class="hero">
        <div class="container text-center">
            <h1 class="display-4 fw-bold mb-4">Connect All Your Issue Trackers in One Place</h1>
            <p class="lead mb-5">SpaceBridge centralizes your GitHub, GitLab, and Jira issues for seamless management with AI tools</p>
            <a href="/register" class="btn btn-light btn-lg">Get Started for Free</a>
        </div>
    </section>

    <section class="container py-5" id="features">
        <h2 class="text-center mb-5">Why Use SpaceBridge?</h2>
        <div class="row">
            <div class="col-md-4">
                <div class="feature-box text-center">
                    <div class="feature-icon">⚡</div>
                    <h3>Unified Interface</h3>
                    <p>Search and manage issues across multiple trackers from a single dashboard</p>
                </div>
            </div>
            <div class="col-md-4">
                <div class="feature-box text-center">
                    <div class="feature-icon">🔌</div>
                    <h3>Easy Integration</h3>
                    <p>Connect GitHub, GitLab, and Jira repositories with just a few clicks</p>
                </div>
            </div>
            <div class="col-md-4">
                <div class="feature-box text-center">
                    <div class="feature-icon">🔍</div>
                    <h3>Powerful Search</h3>
                    <p>Find issues across all your trackers with semantic search capabilities</p>
                </div>
            </div>
        </div>
        <div class="row mt-4">
            <div class="col-md-4">
                <div class="feature-box text-center">
                    <div class="feature-icon">🤖</div>
                    <h3>AI-Powered</h3>
                    <p>Use AI tools to analyze and organize your issues more efficiently</p>
                </div>
            </div>
            <div class="col-md-4">
                <div class="feature-box text-center">
                    <div class="feature-icon">📊</div>
                    <h3>Analytics</h3>
                    <p>Get insights into your issue tracking workflow and team performance</p>
                </div>
            </div>
            <div class="col-md-4">
                <div class="feature-box text-center">
                    <div class="feature-icon">🔐</div>
                    <h3>Secure Access</h3>
                    <p>Your data is protected with robust authentication and encryption</p>
                </div>
            </div>
        </div>
    </section>

    <section class="cta-section">
        <div class="container text-center">
            <h2 class="mb-4">Ready to streamline your issue management?</h2>
            <p class="lead mb-4">Create your free account and start connecting your trackers today.</p>
            <a href="/register" class="btn btn-primary btn-lg">Sign Up Now</a>
        </div>
    </section>

    <footer class="footer">
        <div class="container">
            <div class="row">
                <div class="col-md-4">
                    <h5>SpaceBridge</h5>
                    <p>Connecting issue trackers for efficient management and collaboration.</p>
                </div>
                <div class="col-md-4">
                    <h5>Links</h5>
                    <ul class="list-unstyled">
                        <li><a href="/docs">API Documentation</a></li>
                        <li><a href="/register">Register</a></li>
                        <li><a href="/login">Login</a></li>
                    </ul>
                </div>
                <div class="col-md-4">
                    <h5>Contact</h5>
                    <ul class="list-unstyled">
                        <li><a href="mailto:support@spacebridge.example.com">support@spacebridge.example.com</a></li>
                    </ul>
                </div>
            </div>
            <hr>
            <div class="text-center">
                <p>&copy; 2025 SpaceBridge. All rights reserved.</p>
            </div>
        </div>
    </footer>

    <script src="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/js/bootstrap.bundle.min.js"></script>
</body>
</html>
"""
        with open(landing_page_path, "w") as f:
            f.write(landing_page_html)

    # Create login page template
    login_page_path = templates_dir / "login.html"
    if not login_page_path.exists():
        login_page_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Login - SpaceBridge</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .login-container {
            max-width: 450px;
            margin: 40px auto;
            padding: 30px;
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .login-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .login-header h1 {
            color: #4a86e8;
            font-weight: bold;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-control {
            padding: 12px;
            border-radius: 5px;
        }
        .btn-primary {
            background-color: #4a86e8;
            border-color: #4a86e8;
            padding: 12px;
            font-weight: 600;
            width: 100%;
            margin-top: 10px;
        }
        .btn-primary:hover {
            background-color: #3a76d8;
            border-color: #3a76d8;
        }
        .login-footer {
            text-align: center;
            margin-top: 20px;
        }
        .login-footer a {
            color: #4a86e8;
            text-decoration: none;
        }
        .login-footer a:hover {
            text-decoration: underline;
        }
        .alert {
            margin-bottom: 20px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="login-container">
            <div class="login-header">
                <h1>SpaceBridge</h1>
                <p>Sign in to your account</p>
            </div>

            <div id="errorAlert" class="alert alert-danger d-none" role="alert">
                Incorrect username or password
            </div>

            <form id="loginForm">
                <div class="form-group">
                    <label for="username" class="form-label">Username</label>
                    <input type="text" class="form-control" id="username" name="username" placeholder="Enter your username" required>
                </div>

                <div class="form-group">
                    <label for="password" class="form-label">Password</label>
                    <input type="password" class="form-control" id="password" name="password" placeholder="Enter your password" required>
                </div>

                <div class="form-group d-flex justify-content-between align-items-center">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="remember">
                        <label class="form-check-label" for="remember">Remember me</label>
                    </div>
                    <a href="/forgot-password" class="small">Forgot password?</a>
                </div>

                <button type="submit" class="btn btn-primary">Sign In</button>
            </form>

            <div class="login-footer">
                <p>Don't have an account? <a href="/register">Register</a></p>
            </div>
        </div>
    </div>

    <script>
        // Handle login form submission
        document.getElementById('loginForm').addEventListener('submit', async function(event) {
            event.preventDefault();

            const username = document.getElementById('username').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/v1/auth/token/json', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: username,
                        password: password
                    })
                });

                if (response.ok) {
                    const data = await response.json();

                    // Save tokens to localStorage
                    localStorage.setItem('accessToken', data.access_token);
                    localStorage.setItem('refreshToken', data.refresh_token);
                    localStorage.setItem('tokenExpires', Date.now() + (data.expires_in * 1000));

                    // Redirect to dashboard
                    window.location.href = '/dashboard';
                } else {
                    // Show error message
                    document.getElementById('errorAlert').classList.remove('d-none');
                }
            } catch (error) {
                console.error('Login error:', error);
                document.getElementById('errorAlert').classList.remove('d-none');
            }
        });
    </script>
</body>
</html>
"""
        with open(login_page_path, "w") as f:
            f.write(login_page_html)

    # Create register page template
    register_page_path = templates_dir / "register.html"
    if not register_page_path.exists():
        register_page_html = """<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>Register - SpaceBridge</title>
    <link href="https://cdn.jsdelivr.net/npm/bootstrap@5.3.0/dist/css/bootstrap.min.css" rel="stylesheet">
    <style>
        body {
            background-color: #f8f9fa;
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
        }
        .register-container {
            max-width: 500px;
            margin: 40px auto;
            padding: 30px;
            background-color: #ffffff;
            border-radius: 10px;
            box-shadow: 0 0 20px rgba(0,0,0,0.1);
        }
        .register-header {
            text-align: center;
            margin-bottom: 30px;
        }
        .register-header h1 {
            color: #4a86e8;
            font-weight: bold;
        }
        .form-group {
            margin-bottom: 20px;
        }
        .form-control {
            padding: 12px;
            border-radius: 5px;
        }
        .btn-primary {
            background-color: #4a86e8;
            border-color: #4a86e8;
            padding: 12px;
            font-weight: 600;
            width: 100%;
            margin-top: 10px;
        }
        .btn-primary:hover {
            background-color: #3a76d8;
            border-color: #3a76d8;
        }
        .register-footer {
            text-align: center;
            margin-top: 20px;
        }
        .register-footer a {
            color: #4a86e8;
            text-decoration: none;
        }
        .register-footer a:hover {
            text-decoration: underline;
        }
        .alert {
            margin-bottom: 20px;
        }
        .password-requirements {
            font-size: 14px;
            color: #6c757d;
            margin-top: 5px;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="register-container">
            <div class="register-header">
                <h1>SpaceBridge</h1>
                <p>Create your account</p>
            </div>

            <div id="errorAlert" class="alert alert-danger d-none" role="alert">
                Registration failed. Please check your information.
            </div>

            <div id="successAlert" class="alert alert-success d-none" role="alert">
                Registration successful! Please check your email to verify your account.
            </div>

            <form id="registerForm">
                <div class="form-group">
                    <label for="username" class="form-label">Username</label>
                    <input type="text" class="form-control" id="username" name="username" placeholder="Choose a username" required minlength="3" maxlength="50">
                    <div class="form-text">Username must be alphanumeric and between 3-50 characters.</div>
                </div>

                <div class="form-group">
                    <label for="email" class="form-label">Email</label>
                    <input type="email" class="form-control" id="email" name="email" placeholder="Enter your email" required>
                </div>

                <div class="form-group">
                    <label for="fullName" class="form-label">Full Name (Optional)</label>
                    <input type="text" class="form-control" id="fullName" name="fullName" placeholder="Enter your full name">
                </div>

                <div class="form-group">
                    <label for="password" class="form-label">Password</label>
                    <input type="password" class="form-control" id="password" name="password" placeholder="Create a password" required minlength="8">
                    <div class="password-requirements">
                        Password must be at least 8 characters long.
                    </div>
                </div>

                <div class="form-group">
                    <label for="confirmPassword" class="form-label">Confirm Password</label>
                    <input type="password" class="form-control" id="confirmPassword" name="confirmPassword" placeholder="Confirm your password" required>
                </div>

                <div class="form-group">
                    <div class="form-check">
                        <input class="form-check-input" type="checkbox" id="agree" required>
                        <label class="form-check-label" for="agree">
                            I agree to the <a href="/terms" target="_blank">Terms of Service</a> and <a href="/privacy" target="_blank">Privacy Policy</a>
                        </label>
                    </div>
                </div>

                <button type="submit" class="btn btn-primary">Create Account</button>
            </form>

            <div class="register-footer">
                <p>Already have an account? <a href="/login">Sign In</a></p>
            </div>
        </div>
    </div>

    <script>
        // Password confirmation validation
        document.getElementById('confirmPassword').addEventListener('input', function() {
            const password = document.getElementById('password').value;
            const confirmPassword = this.value;

            if (password !== confirmPassword) {
                this.setCustomValidity('Passwords do not match');
            } else {
                this.setCustomValidity('');
            }
        });

        // Handle registration form submission
        document.getElementById('registerForm').addEventListener('submit', async function(event) {
            event.preventDefault();

            const username = document.getElementById('username').value;
            const email = document.getElementById('email').value;
            const fullName = document.getElementById('fullName').value;
            const password = document.getElementById('password').value;

            try {
                const response = await fetch('/api/v1/auth/register', {
                    method: 'POST',
                    headers: {
                        'Content-Type': 'application/json'
                    },
                    body: JSON.stringify({
                        username: username,
                        email: email,
                        full_name: fullName || null,
                        password: password
                    })
                });

                if (response.ok) {
                    // Show success message
                    document.getElementById('successAlert').classList.remove('d-none');
                    document.getElementById('errorAlert').classList.add('d-none');

                    // Reset form
                    document.getElementById('registerForm').reset();

                    // Redirect to login after 3 seconds
                    setTimeout(() => {
                        window.location.href = '/login';
                    }, 3000);
                } else {
                    // Show error message
                    const errorData = await response.json();
                    const errorAlert = document.getElementById('errorAlert');
                    errorAlert.textContent = errorData.detail || 'Registration failed. Please check your information.';
                    errorAlert.classList.remove('d-none');
                    document.getElementById('successAlert').classList.add('d-none');
                }
            } catch (error) {
                console.error('Registration error:', error);
                const errorAlert = document.getElementById('errorAlert');
                errorAlert.textContent = 'Registration failed. Please try again later.';
                errorAlert.classList.remove('d-none');
                document.getElementById('successAlert').classList.add('d-none');
            }
        });
    </script>
</body>
</html>
"""
        with open(register_page_path, "w") as f:
            f.write(register_page_html)

    # Create a basic templates system
    templates = Jinja2Templates(directory=str(templates_dir))
    logger.info(f"Jinja2Templates directory: {templates_dir}")

    # Add route for landing page
    @app.get("/", response_class=HTMLResponse, tags=["Pages"])
    async def landing_page(request: Request):
        """Landing page route."""
        try:
            return templates.TemplateResponse("landing.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering landing page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for login page
    @app.get("/login", response_class=HTMLResponse, tags=["Pages"])
    async def login_page(request: Request):
        """Login page route."""
        try:
            return templates.TemplateResponse("login.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering login page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for forgot-password page
    @app.get("/forgot-password", response_class=HTMLResponse, tags=["Pages"])
    async def forgot_password_page(request: Request):
        """Forgot password page route."""
        try:
            return templates.TemplateResponse(
                "forgot-password.html", {"request": request}
            )
        except Exception as e:
            logger.error(f"Error rendering forgot password page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for reset-password page
    @app.get("/reset-password", response_class=HTMLResponse, tags=["Pages"])
    async def reset_password_page(request: Request):
        """Reset password page route."""
        try:
            return templates.TemplateResponse(
                "reset-password.html", {"request": request}
            )
        except Exception as e:
            logger.error(f"Error rendering reset password page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for verify-email page
    @app.get("/verify-email", response_class=HTMLResponse, tags=["Pages"])
    async def verify_email_page(request: Request):
        """Email verification page route."""
        try:
            return templates.TemplateResponse("verify-email.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering email verification page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for register page
    @app.get("/register", response_class=HTMLResponse, tags=["Pages"])
    async def register_page(request: Request):
        """Register page route."""
        try:
            return templates.TemplateResponse("register.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering register page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for dashboard page
    @app.get("/dashboard", response_class=HTMLResponse, tags=["Pages"])
    async def dashboard_page(request: Request):
        """Dashboard page route."""
        try:
            return templates.TemplateResponse("dashboard.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering dashboard page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for trackers page
    @app.get("/trackers", response_class=HTMLResponse, tags=["Pages"])
    async def trackers_page(request: Request):
        """Trackers management page route."""
        try:
            return templates.TemplateResponse("trackers.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering trackers page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for privacy policy page
    @app.get("/privacy", response_class=HTMLResponse, tags=["Pages"])
    async def privacy_page(request: Request):
        """Privacy policy page route."""
        try:
            return templates.TemplateResponse("privacy.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering privacy policy page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Add route for terms of service page
    @app.get("/terms", response_class=HTMLResponse, tags=["Pages"])
    async def terms_page(request: Request):
        """Terms of service page route."""
        try:
            return templates.TemplateResponse("terms.html", {"request": request})
        except Exception as e:
            logger.error(f"Error rendering terms of service page: {str(e)}")
            return HTMLResponse(content=f"<h1>Error rendering template: {str(e)}</h1>")

    # Initialize the database on startup
    @app.on_event("startup")
    def startup_db_client():
        """Initialize database tables on startup."""
        try:
            # Get the database URL from environment
            database_url = os.getenv(
                "DATABASE_URL",
                "postgresql+psycopg://postgres:postgres@localhost/spacebridge",
            )
            # Set up the database
            setup_database(database_url)
            logger.info("Database schema initialized successfully")

            # Initialize test data if needed
            if os.getenv("INIT_TEST_DATA", "false").lower() == "true":
                import asyncio

                from spacebridge.init_test_data import create_test_data

                asyncio.run(create_test_data())
                logger.info("Test data initialized successfully")
        except Exception as e:
            logger.error(f"Error initializing database: {e}")

    logger.info(f"SpaceBridge API {__version__} initialized")
    return app
