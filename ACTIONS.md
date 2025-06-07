# GitHub Actions Workflow Execution Truth Table

This table shows which steps execute on which platforms for different trigger events.

## Legend
- ✅ = Step executes on this platform
- ❌ = Step does not execute on this platform
- Event types:
  - `push_master`: Push to master branch
  - `pull_request`: Pull request events
  - `merge_group`: Merge group events
  - `release`: Release published
  - `workflow_dispatch_*`: Manual workflow dispatch with different platform selections

| Workflow File | Workflow Name | Job | Step | Event | amd64 | arm64 | Condition |
|---|---|---|---|---|---|---|---|
| `build.yml` | Build Images | `determine_platforms` | Process platform list and overrides | `merge_group, ... (+6 more)` | ✅ | ❌ |  |
| `build.yml` | Build Images | `prepare_build_vars` | Set Image Tag | `merge_group, ... (+6 more)` | ✅ | ❌ |  |
| `build.yml` | Build Images | `build_images` | Checkout code | `merge_group, push_master` | ✅ | ✅ |  |
| `build.yml` | Build Images | `build_images` | Set up QEMU | `merge_group, push_master` | ✅ | ✅ |  |
| `build.yml` | Build Images | `build_images` | Set up Docker buildx | `merge_group, push_master` | ✅ | ✅ |  |
| `build.yml` | Build Images | `build_images` | Sanitize platform for tag | `merge_group, push_master` | ✅ | ✅ |  |
| `build.yml` | Build Images | `build_images` | Build and cache candidate image - ${{ matrix.daemon.name }} | `merge_group, push_master` | ✅ | ✅ |  |
| `build.yml` | Build Images | `build_images` | Build and cache tester image - ${{ matrix.daemon.name }} | `merge_group, ... (+3 more)` | ✅ | ✅ | github.event_name != 'release' |
| `build.yml → unit-test.yml` | Unit Test Images (called) | `unit_test_images` | Checkout code | `merge_group, ... (+3 more)` | ✅ | ✅ |  |
| `build.yml → unit-test.yml` | Unit Test Images (called) | `unit_test_images` | Set up QEMU | `merge_group, ... (+3 more)` | ✅ | ✅ |  |
| `build.yml → unit-test.yml` | Unit Test Images (called) | `unit_test_images` | Set up Docker buildx | `merge_group, ... (+3 more)` | ✅ | ✅ |  |
| `build.yml → unit-test.yml` | Unit Test Images (called) | `unit_test_images` | Sanitize platform for tag | `merge_group, ... (+3 more)` | ✅ | ✅ |  |
| `build.yml → unit-test.yml` | Unit Test Images (called) | `unit_test_images` | Load tester image from cache - ${{ matrix.daemon.name }} | `merge_group, ... (+3 more)` | ✅ | ✅ |  |
| `build.yml → unit-test.yml` | Unit Test Images (called) | `unit_test_images` | Run unit tests - ${{ matrix.daemon.name }} | `merge_group, ... (+3 more)` | ✅ | ✅ |  |
| `build.yml → publish.yml` | Publish images (called) | `publish_images` | Checkout code | `release` | ✅ | ❌ |  |
| `build.yml → publish.yml` | Publish images (called) | `publish_images` | Set up QEMU | `release` | ✅ | ❌ |  |
| `build.yml → publish.yml` | Publish images (called) | `publish_images` | Set up Docker Buildx | `release` | ✅ | ❌ |  |
| `build.yml → publish.yml` | Publish images (called) | `publish_images` | Log in to GitHub Container Registry | `release` | ✅ | ❌ |  |
| `build.yml → publish.yml` | Publish images (called) | `publish_images` | Generate image metadata for ${{ matrix.daemon.image_name }} | `release` | ✅ | ❌ |  |
| `build.yml → publish.yml` | Publish images (called) | `publish_images` | Build and push ${{ matrix.daemon.name }} image | `release` | ✅ | ❌ |  |
| `codeql.yml` | CodeQL Advanced | `analyze` | Checkout repository | `pull_request, push_master` | ✅ | ❌ |  |
| `codeql.yml` | CodeQL Advanced | `analyze` | Initialize CodeQL | `pull_request, push_master` | ✅ | ❌ |  |
| `codeql.yml` | CodeQL Advanced | `analyze` | Unnamed step | `pull_request, push_master` | ✅ | ❌ | matrix.build-mode == 'manual' |
| `codeql.yml` | CodeQL Advanced | `analyze` | Perform CodeQL Analysis | `pull_request, push_master` | ✅ | ❌ |  |