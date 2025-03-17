from mcp.client import MCPClient


def test_connection():
    # Create the client
    client = MCPClient("http://localhost:8000")

    try:
        # Test a tracker connection
        connection = client.invoke(
            "test_connection", {"organization": "spacecode", "project": "astrobot"}
        )
        print("Connection result:", connection)
    except Exception as e:
        print(f"Error: {e}")


if __name__ == "__main__":
    test_connection()
