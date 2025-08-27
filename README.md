# 🚀 CodeTrace AI - GitHub Repository Analysis Platform

[![Version](https://img.shields.io/badge/version-1.0.0-blue.svg)](https://github.com/dparitosh/codeace-ai)
[![License](https://img.shields.io/badge/license-MIT-green.svg)](LICENSE)
[![Documentation](https://img.shields.io/badge/docs-latest-brightgreen.svg)](docs/)
[![FRS Compliant](https://img.shields.io/badge/FRS-compliant-success.svg)](docs/FRS.md)
[![TSD Documented](https://img.shields.io/badge/TSD-documented-success.svg)](docs/TSD.md)

**Enterprise-Grade Code Intelligence & Repository Analysis Platform**

CodeTrace AI is a comprehensive GitHub repository analysis platform that provides advanced code intelligence, interactive dependency visualization, and quality assessment capabilities. Built with enterprise standards and optimized for scalability.

## 📋 **Core Features**

### 🔍 **Repository Analysis Engine**

- **GitHub Integration**: Seamless repository access via GitHub API
- **Multi-Language Support**: Python, JavaScript, TypeScript, Java, C#, C++
- **Code Structure Analysis**: AST-based parsing and dependency detection
- **Real-time Processing**: Live analysis with progress tracking
- **Batch Processing**: Support for multiple repositories

### 📊 **Interactive Visualization**

- **Dependency Graphs**: Interactive D3.js and Cytoscape.js visualizations
- **Multiple Layouts**: Force-directed, hierarchical, circular, and grid layouts
- **Graph Filtering**: Filter by file type, dependency type, complexity
- **Export Capabilities**: PNG, SVG, PDF, and JSON formats
- **Responsive Design**: Desktop, tablet, and mobile support

### 🎯 **Quality Assessment**

- **Quality Metrics**: Comprehensive code quality scoring (0-100)
- **Issue Detection**: Circular dependencies, dead code, complexity hotspots
- **Recommendations**: Actionable improvement suggestions with effort estimates
- **Historical Tracking**: Quality trends over time
- **Benchmarking**: Industry standard comparisons

### 🤖 **Model Context Protocol (MCP) Server**

- **AI Integration**: Provides rich code context to AI models and tools
- **WebSocket & HTTP APIs**: Real-time communication with AI systems
- **Resource Management**: Access repository files, functions, and documentation
- **Tool Execution**: Automated code analysis, quality assessment, and search
- **Prompt Generation**: Contextual prompts for code review and explanation
- **Multi-Protocol Support**: Compatible with various AI frameworks

## �️ **System Architecture**

```
┌─────────────────┐    ┌─────────────────┐    ┌─────────────────┐
│   Frontend      │    │    Backend      │    │   Database      │
│   React + TS    │◄──►│   FastAPI       │◄──►│ PostgreSQL      │
│   Port: 3000    │    │   Port: 8009    │    │   Port: 5433    │
└─────────────────┘    └─────────────────┘    └─────────────────┘
         │                       │                       │
         │                       ▼                       │
         │              ┌─────────────────┐              │
         │              │  GitHub API     │              │
         │              │  Integration    │              │
         │              └─────────────────┘              │
         │                                               │
         ▼                                               ▼
┌─────────────────┐                            ┌─────────────────┐
│   CLI Tools     │                            │   MCP Server    │
│   Node.js       │                            │   AI Context    │
│   Port: 3000    │                            │   ws://8009/mcp │
└─────────────────┘                            └─────────────────┘
                                                         │
                                                         ▼
                                               ┌─────────────────┐
                                               │   AI Models     │
                                               │   & Tools       │
                                               │   (External)    │
                                               └─────────────────┘
```

│ Graph Engine │ │ Redis Cache │
│ NetworkX+D3 │ │ (Optional) │
└─────────────────┘ └─────────────────┘

```

## �🎯 **Project Structure**

```

codetrace-ai/
├── 📁 backend/ # Python FastAPI backend
│ ├── 📁 api/ # API routes and endpoints
│ ├── 📁 core/ # Core analysis engines
│ ├── 📁 github/ # GitHub integration
│ ├── 📁 quality/ # Quality assessment
│ ├── 📁 graph/ # Graph generation + codegraph integration
│ └── 📁 services/ # Microservices
├── 📁 frontend/ # React frontend application
│ ├── 📁 src/ # Source code
│ ├── 📁 components/ # UI components
│ └── 📁 pages/ # Application pages
├── 📁 cli/ # Command-line interface
├── 📁 codegraph_core/ # 🆕 Advanced Code Analysis Engine
│ ├── 📁 codegraph_core/ # Core code graph functionality
│ │ ├── core.py # In-memory graph + AST analysis
│ │ ├── graph/ # NetworkX adapters
│ │ └── **main**.py # CLI interface
│ ├── pyproject.toml # Package configuration
│ └── README.md # Code graph documentation
├── 📁 docker/ # Docker configurations
├── 📁 kubernetes/ # K8s deployment manifests
├── 📁 docs/ # Documentation
├── 📁 tests/ # Test suites
└── 📁 deployment/ # Deployment scripts

````

## 🚀 Quick Start

```bash
# Clone this repository
git clone https://github.com/codetrace-ai/codetrace-ai.git
cd codetrace-ai

# Setup environment
cp .env.example .env
# Edit .env with your GitHub token

# Launch with Docker
docker-compose up -d

# Access CodeTrace AI
open http://localhost:3000
````

## 📋 Features

- ✅ **GitHub Repository Analysis** - Complete codebase scanning and analysis
- ✅ **Quality Assessment** - SODA-powered quality validation
- ✅ **Traceability Graphs** - Hierarchical dependency visualization
- ✅ **Self-Correction Engine** - Automated issue detection and fixing
- ✅ **CLI Tool** - Professional command-line interface
- ✅ **Docker Ready** - Production deployment ready
- ✅ **GitHub Actions** - CI/CD workflow integration

## 🔧 Technology Stack

- **Backend**: Python 3.11+, FastAPI, PostgreSQL, Neo4j, Redis
- **Frontend**: React 18+, TypeScript, Vite, TailwindCSS
- **Deployment**: Docker, Kubernetes, GitHub Actions
- **Analysis**: SODA Core, tree-sitter, D3.js

## 📚 Documentation

- [Quick Start Guide](docs/quick-start.md)
- [API Documentation](docs/api.md)
- [Deployment Guide](docs/deployment.md)
- [Development Guide](docs/development.md)

---

Built with ❤️ for the developer community
