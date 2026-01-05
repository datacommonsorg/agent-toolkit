# Deployment Guide

This repository uses **Google Cloud Build** for CI/CD, with three distinct deployment tiers.

## 1. Autopush (Development)
- **Trigger**: Push to `main` branch.
- **Config**: `deploy/autopush.yaml`
- **Output**:
  - **PyPI**: `datacommons-mcp` (TestPyPI) version `X.Y.Z.devN` (Sequential dev versions).
  - **Docker**: 
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:autopush-X.Y.Z.devN` - immutable
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:autopush` - latest autopush
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:latest` - latest overall
  - **Cloud Run**: `mcp-server-autopush` (Auto-updated).
- **Purpose**: Rapid testing of the latest code on the `main` branch.

## 2. Staging (Release Candidates)
- **Trigger**: Pushing a tag matching `v*` (specifically `rc` tags like `v1.1.3rc1`).
- **Config**: `deploy/staging.yaml`
- **Output**:
  - **PyPI**: `datacommons-mcp` (TestPyPI) version `X.Y.ZrcN`.
  - **Docker**: 
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:staging-vX.Y.ZrcN` - immutable
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:staging` - latest staging
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:latest` - latest overall
  - **Cloud Run**: `mcp-server-staging` (Pinned to such tag).
- **Purpose**: Verifying releases in a production-like environment before going live.

### How to Create a Staging Release
Run the helper script to automatically find the next available RC version and push the tag:
```bash
python3 scripts/create_staging_tag.py
```
Or manually:
```bash
git tag v1.1.3rc1
git push origin v1.1.3rc1
```

## 3. Production Release
- **Trigger**: Pushing a tag matching `v*` that is **NOT** an `rc` (e.g., `v1.1.3`).
- **Config**: `deploy/release.yaml`
- **Output**:
  - **PyPI**: `datacommons-mcp` (**Official PyPI**) version `X.Y.Z`.
  - **Docker**: 
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:production-vX.Y.Z` - immutable
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:production` - latest production
    - `gcr.io/$PROJECT_ID/datacommons-mcp-server:latest` - latest overall
  - **Cloud Run**: `mcp-server-prod` (Pinned to such tag).
  - **GitHub**: Creates a Version Bump PR to update `version.py` on `main`.
- **Purpose**: Official public release to PyPI and Production Cloud Run.

> [!NOTE]
> The `:latest` tag is pushed by **all** pipelines (Autopush, Staging, and Production). It always points to the single most recently built image, regardless of environment.

### Process Flow
1.  **Tag Push**: Triggers the release build.
2.  **Publication**: Pushes official package to PyPI and images to Artifact Registry.
3.  **Deployment**: Updates `mcp-server-prod` Cloud Run service.
4.  **Post-Release**:
    -   Automatically creates a **Version Bump PR** on `main`.
    -   This synchronizes `version.py` on the main branch to match the release tag, ensuring future dev versions build off this new baseline.

### How to Create a Production Release
**Prerequisite**: Ensure you have validated the changes in **Staging** (`vX.Y.ZrcN`) first.

**Method 1: GitHub UI (Recommended)**
1.  Go to [Draft a New Release](https://github.com/datacommonsorg/agent-toolkit/releases/new).
2.  **Choose a tag**: Create a new tag (e.g., `v1.1.3`).
    *   *Critical: Must strictly follow Semantic Versioning (No `rc`, no `dev`).*
3.  **Target**: `main`.
4.  **Release title**: `v1.1.3`.
5.  **Description**: Generate release notes using the "Generate release notes" button.
6.  Click **Publish release**.

**Method 2: Manual Git Tag**
```bash
git tag v1.1.3
git push origin v1.1.3
```
