# Release Process

This document describes how to release new versions of `pinboard-tools` to PyPI.

## Prerequisites

- You must be a maintainer with write access to the repository
- PyPI trusted publishing must be configured (see below)
- All tests must be passing on the main branch

## Release Methods

### Method 1: Automated Release (Recommended)

Use the GitHub Actions workflow to automatically bump version and create a release:

1. Go to the [Actions tab](../../actions) in the repository
2. Click on "Create Release" workflow
3. Click "Run workflow"
4. Select:
   - **Version bump type**: `patch`, `minor`, or `major`
   - **Pre-release**: Check if this is a pre-release version
5. Click "Run workflow"

The workflow will:

- Bump the version in `pyproject.toml` and `pinboard_tools/__init__.py`
- Commit the version change
- Create a GitHub release with auto-generated release notes
- Trigger the PyPI publish workflow
- Upload signed artifacts to the GitHub release

### Method 2: Manual Release

If you prefer to control the version bump manually:

1. **Update version locally**:

   ```bash
   # Install bump-my-version if needed
   pip install bump-my-version
   
   # Check current version
   bump-my-version show current_version
   
   # Bump version (choose one)
   bump-my-version bump patch  # 0.1.1 -> 0.1.2
   bump-my-version bump minor  # 0.1.1 -> 0.2.0
   bump-my-version bump major  # 0.1.1 -> 1.0.0
   ```

2. **Commit and push**:

   ```bash
   git add pyproject.toml pinboard_tools/__init__.py
   git commit -m "chore: bump version to $(bump-my-version show current_version)"
   git push origin main
   ```

3. **Create GitHub release**:
   - Go to [Releases](../../releases)
   - Click "Draft a new release"
   - Click "Choose a tag" and create new tag: `v0.1.2` (match your version)
   - Set release title: `v0.1.2`
   - Auto-generate release notes or write your own
   - Check "Set as a pre-release" if applicable
   - Click "Publish release"

The release publication will trigger the PyPI publish workflow automatically.

## Version Numbering

We follow [Semantic Versioning](https://semver.org/):

- **MAJOR** (1.0.0): Incompatible API changes
- **MINOR** (0.1.0): New functionality, backwards compatible
- **PATCH** (0.0.1): Bug fixes, backwards compatible

## Pre-releases

For testing releases before making them public:

1. Use the automated workflow with "Pre-release" checked, or
2. Manually create a release and check "Set as a pre-release"

Pre-releases are visible on PyPI but won't be installed by default.

## PyPI Trusted Publishing Setup

This project uses PyPI's trusted publishing feature, which is more secure than API tokens.

To configure (already done for this project):

1. Log in to [PyPI.org](https://pypi.org)
2. Go to your project's settings
3. Add a new trusted publisher:
   - **Owner**: `kevinmcmahon`
   - **Repository**: `pinboard-tools`
   - **Workflow**: `publish.yml`
   - **Environment**: `pypi`

## Troubleshooting

### Tests failing in CI

The publish workflow won't run if tests fail. Check the test workflow results and fix any issues.

### Version already exists on PyPI

Each version can only be published once. Bump to a new version and try again.

### Trusted publishing not working

Ensure the PyPI trusted publisher configuration matches exactly:

- Repository owner and name
- Workflow filename (`publish.yml`)
- Environment name (`pypi`)

## Local Testing

Before releasing, test the package build locally:

```bash
# Build the package
uv build

# Check the build
uv run --with twine twine check dist/*

# Test installation in a new environment
cd /tmp
python -m venv test-env
source test-env/bin/activate
pip install /path/to/pinboard-tools/dist/pinboard_tools-0.1.2-py3-none-any.whl
python -c "import pinboard_tools; print(pinboard_tools.__version__)"
```

## Release Checklist

Before releasing:

- [ ] All tests pass locally: `make test`
- [ ] Code is formatted: `make format`
- [ ] Type checking passes: `make typecheck`
- [ ] Documentation is updated if needed
- [ ] CHANGELOG.md is updated (if maintaining one)
- [ ] Version number follows semantic versioning

## Post-Release

After a successful release:

1. Verify on [PyPI](https://pypi.org/project/pinboard-tools/)
2. Test installation: `pip install pinboard-tools=={new_version}`
3. Create a GitHub announcement if it's a major release
4. Update any dependent projects
