"""
CodeTrace AI - GitHub Integration Client
Handles all GitHub API interactions for repository analysis
"""

import asyncio
import aiohttp
import base64
import json
import logging
from typing import Dict, List, Optional, Any, Tuple
from datetime import datetime
from pathlib import Path

from core.config import settings

logger = logging.getLogger(__name__)


class GitHubClient:
    """GitHub API client for CodeTrace AI"""

    def __init__(self):
        self.token = settings.GITHUB_TOKEN
        self.base_url = "https://api.github.com"
        self.session: Optional[aiohttp.ClientSession] = None

        if not self.token:
            logger.warning("GitHub token not configured. Some features may be limited.")

    async def __aenter__(self):
        await self.init_session()
        return self

    async def __aexit__(self, exc_type, exc_val, exc_tb):
        await self.close()

    async def init_session(self):
        """Initialize HTTP session with GitHub API headers"""
        headers = {
            "Accept": "application/vnd.github.v3+json",
            "User-Agent": "CodeTrace-AI/1.0.0",
        }

        if self.token:
            headers["Authorization"] = f"token {self.token}"

        self.session = aiohttp.ClientSession(
            headers=headers, timeout=aiohttp.ClientTimeout(total=30)
        )

    async def close(self):
        """Close HTTP session"""
        if self.session:
            await self.session.close()

    async def _request(self, method: str, endpoint: str, **kwargs) -> Dict[str, Any]:
        """Make authenticated request to GitHub API"""
        if not self.session:
            await self.init_session()

        url = f"{self.base_url}/{endpoint.lstrip('/')}"

        try:
            async with self.session.request(method, url, **kwargs) as response:
                # Handle rate limiting
                if response.status == 403 and "rate limit" in response.headers.get(
                    "X-RateLimit-Remaining", ""
                ):
                    reset_time = int(response.headers.get("X-RateLimit-Reset", 0))
                    wait_time = reset_time - int(datetime.now().timestamp())
                    logger.warning(f"Rate limit exceeded. Waiting {wait_time} seconds.")
                    await asyncio.sleep(max(wait_time, 60))
                    return await self._request(method, endpoint, **kwargs)

                response.raise_for_status()
                return await response.json()

        except aiohttp.ClientError as e:
            logger.error(f"GitHub API request failed: {e}")
            raise

    async def get_repository(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information"""
        return await self._request("GET", f"/repos/{owner}/{repo}")

    async def get_repository_contents(
        self, owner: str, repo: str, path: str = ""
    ) -> List[Dict[str, Any]]:
        """Get repository contents at specified path"""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        return await self._request("GET", endpoint)

    async def get_file_content(
        self, owner: str, repo: str, path: str
    ) -> Tuple[str, str]:
        """Get file content and encoding"""
        endpoint = f"/repos/{owner}/{repo}/contents/{path}"
        response = await self._request("GET", endpoint)

        content = response.get("content", "")
        encoding = response.get("encoding", "base64")

        if encoding == "base64":
            content = base64.b64decode(content).decode("utf-8", errors="ignore")

        return content, encoding

    async def get_repository_tree(
        self, owner: str, repo: str, sha: str = "HEAD", recursive: bool = True
    ) -> Dict[str, Any]:
        """Get repository tree structure"""
        endpoint = f"/repos/{owner}/{repo}/git/trees/{sha}"
        params = {"recursive": "1" if recursive else "0"}
        return await self._request("GET", endpoint, params=params)

    async def get_commits(
        self, owner: str, repo: str, since: Optional[str] = None, limit: int = 100
    ) -> List[Dict[str, Any]]:
        """Get repository commits"""
        endpoint = f"/repos/{owner}/{repo}/commits"
        params = {"per_page": min(limit, 100)}

        if since:
            params["since"] = since

        return await self._request("GET", endpoint, params=params)

    async def get_pull_requests(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[Dict[str, Any]]:
        """Get repository pull requests"""
        endpoint = f"/repos/{owner}/{repo}/pulls"
        params = {"state": state, "per_page": 100}
        return await self._request("GET", endpoint, params=params)

    async def get_issues(
        self, owner: str, repo: str, state: str = "open"
    ) -> List[Dict[str, Any]]:
        """Get repository issues"""
        endpoint = f"/repos/{owner}/{repo}/issues"
        params = {"state": state, "per_page": 100}
        return await self._request("GET", endpoint, params=params)

    async def get_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get repository programming languages"""
        endpoint = f"/repos/{owner}/{repo}/languages"
        return await self._request("GET", endpoint)

    async def get_contributors(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get repository contributors"""
        endpoint = f"/repos/{owner}/{repo}/contributors"
        return await self._request("GET", endpoint)

    async def get_branches(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get repository branches"""
        endpoint = f"/repos/{owner}/{repo}/branches"
        return await self._request("GET", endpoint)

    async def get_releases(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get repository releases"""
        endpoint = f"/repos/{owner}/{repo}/releases"
        return await self._request("GET", endpoint)

    async def search_repositories(
        self, query: str, sort: str = "stars", order: str = "desc", limit: int = 30
    ) -> Dict[str, Any]:
        """Search repositories"""
        endpoint = "/search/repositories"
        params = {"q": query, "sort": sort, "order": order, "per_page": min(limit, 100)}
        return await self._request("GET", endpoint, params=params)

    async def create_issue(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        labels: Optional[List[str]] = None,
    ) -> Dict[str, Any]:
        """Create an issue"""
        endpoint = f"/repos/{owner}/{repo}/issues"
        data = {"title": title, "body": body}

        if labels:
            data["labels"] = labels

        return await self._request("POST", endpoint, json=data)

    async def create_pull_request(
        self,
        owner: str,
        repo: str,
        title: str,
        body: str,
        head: str,
        base: str = "main",
    ) -> Dict[str, Any]:
        """Create a pull request"""
        endpoint = f"/repos/{owner}/{repo}/pulls"
        data = {"title": title, "body": body, "head": head, "base": base}
        return await self._request("POST", endpoint, json=data)

    async def get_rate_limit(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        return await self._request("GET", "/rate_limit")

    async def analyze_repository_structure(
        self, owner: str, repo: str, branch: str = None, path: str = None
    ) -> Dict[str, Any]:
        """Comprehensive repository structure analysis"""
        logger.info(
            f"Analyzing repository structure: {owner}/{repo} (branch: {branch}, path: {path})"
        )

        try:
            # Get basic repository info
            repo_info = await self.get_repository(owner, repo)

            # Use specified branch or default branch
            target_branch = branch or repo_info["default_branch"]

            # Get repository tree from specific branch
            tree = await self.get_repository_tree(
                owner, repo, sha=target_branch, recursive=True
            )

            # Get languages
            languages = await self.get_languages(owner, repo)

            # Get recent commits from the target branch
            commits = await self.get_commits(owner, repo, limit=50)

            # Get branches
            branches = await self.get_branches(owner, repo)

            # Analyze file structure (filter by path if specified)
            files = tree.get("tree", [])
            if path and path != "/":
                # Filter files to only include those in the specified path
                path_prefix = path.strip("/") + "/"
                files = [f for f in files if f["path"].startswith(path_prefix)]

            file_analysis = self._analyze_files(files)

            # Calculate metrics
            metrics = self._calculate_repository_metrics(
                repo_info, files, languages, commits
            )

            return {
                "repository": {
                    "name": repo_info["name"],
                    "full_name": repo_info["full_name"],
                    "description": repo_info.get("description"),
                    "url": repo_info["html_url"],
                    "size": repo_info["size"],
                    "stars": repo_info["stargazers_count"],
                    "forks": repo_info["forks_count"],
                    "issues": repo_info["open_issues_count"],
                    "created_at": repo_info["created_at"],
                    "updated_at": repo_info["updated_at"],
                    "default_branch": repo_info["default_branch"],
                    "analyzed_branch": target_branch,
                    "analyzed_path": path or "/",
                },
                "structure": {
                    "total_files": len(files),
                    "directories": len([f for f in files if f["type"] == "tree"]),
                    "files_by_type": file_analysis["by_type"],
                    "largest_files": file_analysis["largest_files"],
                    "directory_structure": file_analysis["directories"],
                },
                "languages": languages,
                "branches": [b["name"] for b in branches],
                "metrics": metrics,
                "analysis_timestamp": datetime.utcnow().isoformat(),
            }

        except Exception as e:
            logger.error(f"Error analyzing repository {owner}/{repo}: {e}")
            raise

    def _analyze_files(self, files: List[Dict[str, Any]]) -> Dict[str, Any]:
        """Analyze file structure and types"""
        by_type = {}
        largest_files = []
        directories = set()

        for file_info in files:
            if file_info["type"] == "blob":  # Regular file
                path = file_info["path"]
                size = file_info["size"]

                # Extract file extension
                ext = Path(path).suffix.lower()
                if ext:
                    by_type[ext] = by_type.get(ext, 0) + 1
                else:
                    by_type["no_extension"] = by_type.get("no_extension", 0) + 1

                # Track large files
                largest_files.append({"path": path, "size": size})

                # Track directories
                dir_path = str(Path(path).parent)
                if dir_path != ".":
                    directories.add(dir_path)

        # Sort largest files
        largest_files.sort(key=lambda x: x["size"], reverse=True)
        largest_files = largest_files[:20]  # Top 20 largest files

        return {
            "by_type": by_type,
            "largest_files": largest_files,
            "directories": sorted(list(directories)),
        }

    def _calculate_repository_metrics(
        self,
        repo_info: Dict[str, Any],
        files: List[Dict[str, Any]],
        languages: Dict[str, int],
        commits: List[Dict[str, Any]],
    ) -> Dict[str, Any]:
        """Calculate repository health and complexity metrics"""

        # File metrics
        total_files = len([f for f in files if f["type"] == "blob"])
        total_size = sum(f["size"] for f in files if f["type"] == "blob")

        # Language diversity
        language_count = len(languages)
        primary_language = (
            max(languages.items(), key=lambda x: x[1])[0] if languages else "Unknown"
        )

        # Activity metrics
        recent_commits = len(commits)
        last_commit = commits[0]["commit"]["author"]["date"] if commits else None

        # Complexity indicators
        complexity_score = min(
            100, (total_files / 100) * 10 + (language_count * 5) + (recent_commits / 10)
        )

        # Health score based on various factors
        health_score = 100
        if repo_info["open_issues_count"] > 50:
            health_score -= 10
        if recent_commits < 10:
            health_score -= 20
        if not repo_info.get("description"):
            health_score -= 5

        return {
            "total_files": total_files,
            "total_size_bytes": total_size,
            "language_count": language_count,
            "primary_language": primary_language,
            "recent_commits": recent_commits,
            "last_commit": last_commit,
            "complexity_score": round(complexity_score, 2),
            "health_score": max(0, health_score),
            "stars_per_fork": round(
                repo_info["stargazers_count"] / max(repo_info["forks_count"], 1), 2
            ),
        }

    # Missing methods needed by routes
    async def get_repository_info(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository information - alias for get_repository"""
        return await self.get_repository(owner, repo)

    async def get_repository_structure(self, owner: str, repo: str) -> Dict[str, Any]:
        """Get repository structure using tree API"""
        try:
            tree = await self.get_repository_tree(owner, repo, recursive=True)
            return {
                "tree": tree,
                "files": [
                    item for item in tree.get("tree", []) if item.get("type") == "blob"
                ],
                "directories": [
                    item for item in tree.get("tree", []) if item.get("type") == "tree"
                ],
            }
        except Exception as e:
            logger.error(f"Failed to get repository structure: {e}")
            return {"tree": {}, "files": [], "directories": [], "error": str(e)}

    async def get_repository_files(self, owner: str, repo: str) -> List[Dict[str, Any]]:
        """Get all files in repository"""
        try:
            tree = await self.get_repository_tree(owner, repo, recursive=True)
            return [item for item in tree.get("tree", []) if item.get("type") == "blob"]
        except Exception as e:
            logger.error(f"Failed to get repository files: {e}")
            return []

    async def get_repository_languages(self, owner: str, repo: str) -> Dict[str, int]:
        """Get repository programming languages"""
        return await self.get_languages(owner, repo)

    async def analyze_repository_structure(
        self, owner: str, repo: str
    ) -> Dict[str, Any]:
        """Comprehensive repository analysis"""
        try:
            # Parallel fetch of repository data
            repo_info, tree_data, languages, contributors = await asyncio.gather(
                self.get_repository(owner, repo),
                self.get_repository_structure(owner, repo),
                self.get_languages(owner, repo),
                self.get_contributors(owner, repo),
                return_exceptions=True,
            )

            # Handle exceptions in results
            if isinstance(repo_info, Exception):
                logger.error(f"Failed to get repo info: {repo_info}")
                repo_info = {}
            if isinstance(tree_data, Exception):
                logger.error(f"Failed to get tree data: {tree_data}")
                tree_data = {"files": [], "directories": []}
            if isinstance(languages, Exception):
                logger.error(f"Failed to get languages: {languages}")
                languages = {}
            if isinstance(contributors, Exception):
                logger.error(f"Failed to get contributors: {contributors}")
                contributors = []

            # Build comprehensive analysis
            analysis = {
                "repository": repo_info,
                "structure": tree_data,
                "languages": languages,
                "contributors": contributors,
                "metrics": {
                    "total_files": len(tree_data.get("files", [])),
                    "total_directories": len(tree_data.get("directories", [])),
                    "language_count": len(languages),
                    "contributor_count": len(contributors),
                    "stars": repo_info.get("stargazers_count", 0),
                    "forks": repo_info.get("forks_count", 0),
                    "size": repo_info.get("size", 0),
                },
                "analysis_timestamp": datetime.now().isoformat(),
            }

            return analysis

        except Exception as e:
            logger.error(f"Failed to analyze repository structure: {e}")
            return {
                "repository": {},
                "structure": {"files": [], "directories": []},
                "languages": {},
                "contributors": [],
                "metrics": {},
                "error": str(e),
                "analysis_timestamp": datetime.now().isoformat(),
            }

    async def get_rate_limit(self) -> Dict[str, Any]:
        """Get current rate limit status"""
        try:
            return await self._request("GET", "/rate_limit")
        except Exception as e:
            logger.error(f"Failed to get rate limit: {e}")
            return {
                "rate": {
                    "limit": 5000,
                    "remaining": 5000,
                    "reset": int(datetime.now().timestamp()) + 3600,
                },
                "error": str(e),
            }
