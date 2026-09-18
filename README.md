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

The installer requires Python 3.10+; the Windows Store app-execution alias is not sufficient. An existing project virtual environment is reused. To select an interpreter explicitly, run `./install.ps1 -PythonPath C:\Python312\python.exe`.

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

GitLab analysis uses relative source paths, excludes dependency/build folders and symbolic links, and enforces the same analysis limits after cloning. Git clone itself has a 60-second timeout but no disk quota. Private access uses an already configured Git credential helper without interactive prompts.

The graph page renders a bounded preview; it reports when nodes are omitted. Legacy static traceability pages and mock analysis routes have been removed. Agent context ranks symbols by the query, preserves file-qualified identities, and reports analysis limitations. Complete cross-module call/import resolution remains pending.

For a VS Code coding-agent integration, see [the agent integration guide](docs/vscode-agent.md).

## Verification

After installation, run the core and API regression tests with:

```powershell
.\.venv\Scripts\python.exe -m pip install -r backend\requirements-dev.txt
.\.venv\Scripts\python.exe -m pytest codegraph_core\tests backend\tests
Set-Location frontend; npm run build
```
