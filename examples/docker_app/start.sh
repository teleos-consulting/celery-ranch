#!/bin/bash

# Check if docker or podman is installed
if command -v docker &> /dev/null; then
    CONTAINER_ENGINE="docker"
elif command -v podman &> /dev/null; then
    CONTAINER_ENGINE="podman"
else
    echo "Error: Neither docker nor podman is installed"
    exit 1
fi

# Check if docker-compose or podman-compose is installed
if [ "$CONTAINER_ENGINE" = "docker" ] && command -v docker-compose &> /dev/null; then
    COMPOSE_CMD="docker-compose"
elif [ "$CONTAINER_ENGINE" = "podman" ] && command -v podman-compose &> /dev/null; then
    COMPOSE_CMD="podman-compose"
else
    echo "Error: $CONTAINER_ENGINE-compose is not installed"
    exit 1
fi

# Parse command line arguments
ACTION="up"
if [ $# -gt 0 ]; then
    ACTION="$1"
fi

# Handle various commands
case "$ACTION" in
    "up")
        echo "Starting Ranch Demo with $CONTAINER_ENGINE..."
        if [ "$CONTAINER_ENGINE" = "docker" ]; then
            docker-compose up -d
        else
            podman-compose up -d
        fi
        echo "Services are starting. The web interface will be available at http://localhost:8000"
        echo "Celery Flower monitoring is available at http://localhost:5555"
        ;;
    "down")
        echo "Stopping Ranch Demo..."
        if [ "$CONTAINER_ENGINE" = "docker" ]; then
            docker-compose down
        else
            podman-compose down
        fi
        ;;
    "logs")
        echo "Showing logs..."
        if [ "$CONTAINER_ENGINE" = "docker" ]; then
            docker-compose logs -f
        else
            podman-compose logs -f
        fi
        ;;
    "rebuild")
        echo "Rebuilding and starting services..."
        if [ "$CONTAINER_ENGINE" = "docker" ]; then
            docker-compose down
            docker-compose build
            docker-compose up -d
        else
            podman-compose down
            podman-compose build
            podman-compose up -d
        fi
        ;;
    *)
        echo "Usage: $0 [up|down|logs|rebuild]"
        echo "  up:      Start the services (default)"
        echo "  down:    Stop the services"
        echo "  logs:    Show service logs"
        echo "  rebuild: Rebuild and restart services"
        exit 1
        ;;
esac