# Workflow Platform Truth Table

This table shows which architectures are built for each step in each workflow, based on the triggering event.

| Workflow | Job | Step | Event | amd64 | arm64 |
|---|---|---|---|---|---|
| `codeql.yml` | `analyze` | `Checkout repository` | (called) | N/A | N/A |
| `codeql.yml` | `analyze` | `Initialize CodeQL` | (called) | N/A | N/A |
| `codeql.yml` | `analyze` | `N/A` | (called) | N/A | N/A |
| `codeql.yml` | `analyze` | `Perform CodeQL Analysis` | (called) | N/A | N/A |
| `build.yml` | `prepare_build_vars` | `Set Image Tag` | (called) | ✅ | ❌ |
| `build.yml` | `determine_platforms` | `Process platform list and overrides` | (called) | ✅ | ❌ |
| `build.yml` | `build_images` | `Checkout code` | (called) | ✅ | ❌ |
| `build.yml` | `build_images` | `Set up QEMU` | (called) | ✅ | ❌ |
| `build.yml` | `build_images` | `Set up Docker buildx` | (called) | ✅ | ❌ |
| `build.yml` | `build_images` | `Sanitize platform for tag` | (called) | ✅ | ❌ |
| `build.yml` | `build_images` | `Build and cache candidate image - ${{ matrix.daemon.name }}` | (called) | ✅ | ❌ |
| `build.yml` | `build_images` | `Build and cache tester image - ${{ matrix.daemon.name }}` | (called) | ✅ | ❌ |
| `publish.yml` | `publish_images` | `Checkout code` | (called) | ✅ | ❌ |
| `publish.yml` | `publish_images` | `Set up QEMU` | (called) | ✅ | ❌ |
| `publish.yml` | `publish_images` | `Set up Docker Buildx` | (called) | ✅ | ❌ |
| `publish.yml` | `publish_images` | `Log in to GitHub Container Registry` | (called) | ✅ | ❌ |
| `publish.yml` | `publish_images` | `Generate image metadata for ${{ matrix.daemon.image_name }}` | (called) | ✅ | ❌ |
| `publish.yml` | `publish_images` | `Build and push ${{ matrix.daemon.name }} image` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Checkout code` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Set up QEMU` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Set up Docker buildx` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Sanitize platform for tag` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Load scale-daemon image from cache` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Load printer-daemon image from cache` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Install Docker's Compose` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Prepare .env file for Compose` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Pull eclipse-mosquitto image` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Run integration test with Compose` | (called) | ✅ | ❌ |
| `integration-test.yml` | `integration_test` | `Compose tear down` | (called) | ✅ | ❌ |
| `unit-test.yml` | `unit_test_images` | `Checkout code` | (called) | ✅ | ❌ |
| `unit-test.yml` | `unit_test_images` | `Set up QEMU` | (called) | ✅ | ❌ |
| `unit-test.yml` | `unit_test_images` | `Set up Docker buildx` | (called) | ✅ | ❌ |
| `unit-test.yml` | `unit_test_images` | `Sanitize platform for tag` | (called) | ✅ | ❌ |
| `unit-test.yml` | `unit_test_images` | `Load tester image from cache - ${{ matrix.daemon.name }}` | (called) | ✅ | ❌ |
| `unit-test.yml` | `unit_test_images` | `Run unit tests - ${{ matrix.daemon.name }}` | (called) | ✅ | ❌ |