#!/bin/bash

# SpaceLit Docker Management Script
# Usage: ./docker-run.sh [command] [options]

set -e

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
cd "$SCRIPT_DIR"

# Colors for output
RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
NC='\033[0m' # No Color

print_usage() {
    echo -e "${BLUE}SpaceLit Docker Management${NC}"
    echo ""
    echo -e "${YELLOW}Usage:${NC} ./docker-run.sh [command] [options]"
    echo ""
    echo -e "${YELLOW}Commands:${NC}"
    echo "  dev         Start development environment (Vite + Mock API)"
    echo "  prod        Start production environment (Nginx + Real API)"
    echo "  mock        Start production build with mock API"
    echo "  build       Build production Docker image"
    echo "  test        Run tests in container"
    echo "  stop        Stop all containers"
    echo "  clean       Clean up containers and images"
    echo "  logs        Show container logs"
    echo ""
    echo -e "${YELLOW}Examples:${NC}"
    echo "  ./docker-run.sh dev           # Start development with HMR"
    echo "  ./docker-run.sh prod          # Start production with real API"
    echo "  ./docker-run.sh mock          # Start production with mock API"
    echo "  ./docker-run.sh logs frontend # Show frontend logs"
}

run_dev() {
    echo -e "${GREEN}Starting development environment...${NC}"
    echo -e "${BLUE}Frontend:${NC} http://localhost:5173 (with HMR)"
    echo -e "${BLUE}Mock API:${NC} http://localhost:8000"
    docker-compose -f docker-compose.dev.yml up --build
}

run_prod() {
    echo -e "${GREEN}Starting production environment...${NC}"
    echo -e "${BLUE}Frontend:${NC} http://localhost:3000"
    echo -e "${BLUE}Backend:${NC} http://localhost:8000"
    echo -e "${YELLOW}Note:${NC} Make sure your real API backend is running"
    docker-compose up --build
}

run_mock() {
    echo -e "${GREEN}Starting production environment with mock API...${NC}"
    echo -e "${BLUE}Frontend:${NC} http://localhost:3000"
    echo -e "${BLUE}Mock API:${NC} http://localhost:8000"
    docker-compose -f docker-compose.mock.yml up --build
}

build_image() {
    echo -e "${GREEN}Building production Docker image...${NC}"
    docker build -t spacelit:latest .
    echo -e "${GREEN}Image built successfully: spacelit:latest${NC}"
}

run_tests() {
    echo -e "${GREEN}Running tests in container...${NC}"
    docker build -f Dockerfile.dev -t spacelit:test .
    docker run --rm spacelit:test npm test
}

stop_containers() {
    echo -e "${YELLOW}Stopping all containers...${NC}"
    docker-compose down 2>/dev/null || true
    docker-compose -f docker-compose.dev.yml down 2>/dev/null || true
    docker-compose -f docker-compose.mock.yml down 2>/dev/null || true
}

clean_up() {
    echo -e "${YELLOW}Cleaning up containers and images...${NC}"
    stop_containers
    docker system prune -f
    docker image rm spacelit:latest spacelit:test 2>/dev/null || true
    echo -e "${GREEN}Cleanup complete${NC}"
}

show_logs() {
    local service=${1:-""}
    if [ -z "$service" ]; then
        echo -e "${YELLOW}Available services:${NC}"
        docker-compose ps --services 2>/dev/null || echo "No running services"
        return
    fi

    echo -e "${GREEN}Showing logs for: $service${NC}"
    docker-compose logs -f "$service" 2>/dev/null || \
    docker-compose -f docker-compose.dev.yml logs -f "$service" 2>/dev/null || \
    docker-compose -f docker-compose.mock.yml logs -f "$service" 2>/dev/null || \
    echo -e "${RED}Service not found: $service${NC}"
}

# Main command handler
case "${1:-help}" in
    "dev")
        run_dev
        ;;
    "prod")
        run_prod
        ;;
    "mock")
        run_mock
        ;;
    "build")
        build_image
        ;;
    "test")
        run_tests
        ;;
    "stop")
        stop_containers
        ;;
    "clean")
        clean_up
        ;;
    "logs")
        show_logs "$2"
        ;;
    "help"|*)
        print_usage
        ;;
esac
