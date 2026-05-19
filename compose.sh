#!/bin/bash
set -e

echo "Starting Wolfram Alpha MCP Server..."

# Stop and remove existing containers
echo "Stopping existing containers..."
docker compose down

# Remove existing image to force rebuild
echo "Removing existing image..."
docker rmi -f mcp-worlfram-alpha-mcp-wolfram 2>/dev/null || true

# Build and start
echo "Building and starting service..."
docker compose up -d --build --remove-orphans

echo "Wolfram Alpha MCP Server is running!"
echo "MCP Endpoint: http://localhost:8019/wolfram/"
echo "Health Check: http://localhost:8019/health"
