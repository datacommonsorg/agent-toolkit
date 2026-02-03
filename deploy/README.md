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
git tag vX.Y.Z.rcN
git push upstream vX.Y.Z.rcN
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
- **Purpose**: Official public release to PyPI and Production Cloud Run.

> [!NOTE]
> The `:latest` tag is pushed by **production** pipeline only. It always points to the single most recently built image deployed to prod.

### Production Release Process
The process to release to production is a 2-step workflow: **Prepare** (Version Bump) -> **Release** (Tag & Deploy).

#### Step 1: Version Bump (Prepare)
Run this script to calculate the next version, update `pyproject.toml`, and create a PR.

```bash
python3 scripts/create_release_pr.py
# Follow the interactive prompt (Major/Minor/Patch)
```

1.  This triggers a Cloud Build job (`deploy/bump_version.yaml`).
2.  A Pull Request will be created (e.g., `chore: bump version to 1.1.4`).
3.  **Review and Merge** this PR into `main`.

#### Step 2: Deploy (Release)
Once the version bump is merged, create the official release to trigger deployment.

**Using GitHub UI (Recommended)**
1.  Go to [Draft a New Release](https://github.com/datacommonsorg/agent-toolkit/releases/new).
2.  **Choose a tag**: Create a new tag matching your bumped version (e.g., `v1.1.4`).
    *   *Critical: Must match the version you just merged into `pyproject.toml`.*
3.  **Target**: `main`.
4.  **Release title**: `v1.1.4`.
5.  **Description**: Generate release notes.
6.  Click **Publish release**.

**Or Manual Git Tag**
```bash
git checkout main
git pull
git tag v1.1.4
git push origin v1.1.4
```
