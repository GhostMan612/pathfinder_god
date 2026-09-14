# ============================================================
# As Above, So Below. As Within, So Without.
# The Future Dictates the Past and the Past is Always Present.
# ============================================================

# ─── Builder Stage ───
FROM ghcr.io/cirruslabs/flutter:3.12.2 AS builder

WORKDIR /app

# Copy pubspec files
COPY pubspec.yaml pubspec.lock ./

# Get dependencies
RUN flutter pub get

# Copy source code
COPY lib/ ./lib/
COPY assets/ ./assets/

# Build APK
RUN flutter build apk --release

# ─── Runtime Stage ───
FROM ubuntu:24.04 AS runtime

# Install runtime dependencies
RUN apt-get update && apt-get install -y --no-install-recommends \
    ca-certificates \
    && rm -rf /var/lib/apt/lists/*

# Create non-root user
RUN groupadd -r pathfinder && useradd -r -g pathfinder pathfinder

WORKDIR /app

# Copy built APK
COPY --from=builder /app/build/app/outputs/flutter-apk/app-release.apk /app/pathfinder-god.apk

# Create non-root user
RUN groupadd -r pathfinder && useradd -r -g pathfinder pathfinder
USER pathfinder

# Expose port (for web build if needed)
EXPOSE 8080

# Health check
HEALTHCHECK --interval=30s --timeout=10s --start-period=10s --retries=3 \
    CMD curl -f http://localhost:8080/health || exit 1

# Run a simple HTTP server to serve the APK (for download)
CMD ["python3", "-m", "http.server", "8080"]