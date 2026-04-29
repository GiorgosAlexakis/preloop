import requests


def test():
    # Make a dummy request to backend
    response = requests.get("http://localhost:8000/api/v1/flows/executions?limit=1")
    print(response.json())


if __name__ == "__main__":
    test()
