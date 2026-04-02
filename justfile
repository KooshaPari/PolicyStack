# PolicyStack - TypeScript API
# Native task runner (just)

# Default recipe
default: help

# Help
help:
  @echo "PolicyStack - TypeScript API"
  @echo ""
  @just --list

# Install dependencies
install:
  npm install

# Quality checks
check: lint typecheck test
  @echo "All checks passed!"

# Lint
lint:
  npm run lint

# Type check
typecheck:
  npm run typecheck

# Run tests
test:
  npm run test

# Build
build:
  npm run build

# Development
dev:
  npm run dev

# Production
start:
  npm start

# Clean
clean:
  rm -rf dist node_modules/.cache

# Format
fmt:
  npm run format
