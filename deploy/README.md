# Deployment Guide

This repository uses **Google Cloud Build** for CI/CD, with three distinct deployment tiers.

## 1. Autopush (Development)
- **Trigger**: Push to `main` branch.
- **Config**: `deploy/autopush.yaml`
- **Output**:
  - **PyPI**: `datacommons-mcp` (TestPyPI) version `X.Y.Z.devN` (Sequential dev versions).
  - **Docker**: `gcr.io/$PROJECT_ID/datacommons-mcp-server:autopush` (Overwritten).
  - **Cloud Run**: `mcp-server-autopush` (Auto-updated).
- **Purpose**: Rapid testing of the latest code on the `main` branch.

## 2. Staging (Release Candidates)
- **Trigger**: Pushing a tag matching `v*` (specifically `rc` tags like `v1.1.3rc1`).
- **Config**: `deploy/staging.yaml`
- **Output**:
  - **PyPI**: `datacommons-mcp` (TestPyPI) version `X.Y.ZrcN`.
  - **Docker**: `gcr.io/$PROJECT_ID/datacommons-mcp-server:vX.Y.ZrcN`.
  - **Cloud Run**: `mcp-server-staging` (Pinned to this tag).
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
- **Trigger**: Pushing a final release tag (e.g., `v1.1.3`).
- **Config**: `deploy/release.yaml`
- **Output**:
  - **PyPI**: `datacommons-mcp` (**Official PyPI**) version `X.Y.Z`.
  - **Docker**: `gcr.io/$PROJECT_ID/datacommons-mcp-server:vX.Y.Z` and `:latest` (if configured).
  - **Cloud Run**: `mcp-server-prod`.
  - **GitHub**: Creates a Version Bump PR to update `version.py` on `main`.
- **Purpose**: Official public release.

### How to Create a Production Release
**Recommended**: Use the [GitHub Releases UI](https://github.com/datacommonsorg/agent-toolkit/releases/new).
1.  Draft a new release.
2.  Choose a tag (e.g., `v1.1.3`).
3.  Write release notes.
4.  Publish.

This will automatically trigger the `release.yaml` pipeline.
