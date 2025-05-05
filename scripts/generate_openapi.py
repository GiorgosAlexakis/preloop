# scripts/generate_openapi.py
import yaml
import sys
from pathlib import Path

# Ensure the project root is in the Python path
# This allows importing spacebridge modules when running the script directly
project_root = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(project_root))

try:
    from spacebridge.api.app import create_app
except ImportError as e:
    print(f"Error importing FastAPI app factory: {e}", file=sys.stderr)
    print(
        "Ensure the script is run from the project root or the spacebridge package is installed.",
        file=sys.stderr,
    )
    sys.exit(1)


def generate_openapi_schema():
    """Generates the OpenAPI schema and writes it to docs/openapi.yaml."""
    print("Generating OpenAPI schema...")
    app = create_app()  # Create the app instance using the factory
    openapi_schema = app.openapi()

    output_path = project_root / "docs" / "openapi.yaml"
    print(f"Writing schema to {output_path}...")

    try:
        # Ensure the docs directory exists
        output_path.parent.mkdir(parents=True, exist_ok=True)

        with open(output_path, "w", encoding="utf-8") as f:
            yaml.dump(openapi_schema, f, sort_keys=False, allow_unicode=True)
        print("Successfully generated openapi.yaml")
    except IOError as e:
        print(f"Error writing OpenAPI schema to file: {e}", file=sys.stderr)
        sys.exit(1)
    except Exception as e:
        print(f"An unexpected error occurred: {e}", file=sys.stderr)
        sys.exit(1)


if __name__ == "__main__":
    generate_openapi_schema()
