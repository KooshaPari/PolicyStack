FROM node:20-slim AS docs-builder

WORKDIR /app/docs
COPY docs/package.json ./
RUN npm install
COPY docs/ ./
RUN npm run docs:build

FROM rust:1-slim AS rust-builder

WORKDIR /app/wrappers/rust
COPY wrappers/rust/Cargo.toml wrappers/rust/Cargo.lock ./
COPY wrappers/rust/src ./src
RUN cargo build --release

FROM python:3.12-slim

WORKDIR /app

COPY pyproject.toml README.md ./
COPY cli/ ./cli/
COPY policy_lib.py validate_governance.py resolve.py ./
COPY schemas/ ./schemas/
COPY contracts/ ./contracts/
COPY policies/ ./policies/
COPY scripts/ ./scripts/
COPY --from=docs-builder /app/docs/.vitepress/dist ./static_docs
COPY --from=rust-builder /app/wrappers/rust/target/release/policy-wrapper-rust /usr/local/bin/policy-wrapper-rust

RUN pip install --no-cache-dir . ./cli && \
    groupadd -g 1000 appgroup && \
    useradd -u 1000 -g appgroup -s /bin/sh -m appuser && \
    chown -R appuser:appgroup /app

USER appuser
EXPOSE 8000

HEALTHCHECK --interval=30s --timeout=10s --start-period=15s --retries=3 \
    CMD python -c "import urllib.request; urllib.request.urlopen('http://localhost:8000')" || exit 1

CMD ["python", "-m", "http.server", "8000", "--directory", "static_docs"]
