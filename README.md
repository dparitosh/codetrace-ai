# CodeTrace AI

CodeTrace AI is a local-first source-code analysis application. Select a folder in the browser to build a semantic dependency graph, run structural quality checks, and scan for a small set of static security patterns. No cloud account, token, or repository-host integration is required for the primary workflow.

GitLab project URLs are also supported by the graph API. The backend clones the project into a temporary directory, analyzes it, and removes the clone before returning the graph. Public projects work directly; private projects use the credentials already available to your local Git installation.

## Windows quick start

In PowerShell from the project root:

```powershell
Set-ExecutionPolicy -Scope Process Bypass
.\install.ps1
.\start.ps1
```

Open `http://localhost:3001`, choose a local folder, then run Analysis, Quality, Security, or Dependency Graph.

The installer requires a real Python 3.9+ installation; the Windows Store app-execution alias is not sufficient.

## Inputs

- Local folder: supported in all product pages through the browser folder picker.
- GitLab project: `POST /api/v1/graph/gitlab` with `{"project_url":"https://gitlab.com/group/project"}`.
- Self-hosted GitLab: add its hostname to `GITLAB_ALLOWED_HOSTS` in `.env`.

## API

The live OpenAPI contract is available at `http://localhost:8009/docs`.

- `POST /api/v1/graph/local`
- `POST /api/v1/graph/local/analyze`
- `POST /api/v1/graph/gitlab`
- `POST /api/v1/quality/local`
- `POST /api/v1/security/local`

The API limits browser submissions to 500 files and 10 MB of text content per request.

For a VS Code coding-agent integration, see [the agent integration guide](docs/vscode-agent.md).

## Verification

After installation, run the core and API regression tests with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest codegraph_core\tests backend\tests
Set-Location frontend; npm run build
```
