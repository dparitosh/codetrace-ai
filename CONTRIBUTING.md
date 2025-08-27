# Contributing to CodeAce AI

We love your input! We want to make contributing to CodeAce AI as easy and transparent as possible.

## GitHub Copilot Integration Guidelines

This project is designed to work seamlessly with GitHub Copilot. Follow these guidelines:

### Code Style
- Use descriptive variable and function names
- Add comprehensive docstrings and comments
- Include type hints for all Python functions
- Use JSDoc comments for JavaScript/TypeScript

### Example Python Function
```python
def analyze_code_dependencies(
    file_path: str, 
    include_external: bool = True
) -> Dict[str, List[str]]:
    """
    Analyze code dependencies for a given file.
    
    Args:
        file_path: Path to the source code file
        include_external: Whether to include external dependencies
    
    Returns:
        Dictionary mapping modules to their dependencies
        
    Example:
        >>> deps = analyze_code_dependencies("src/main.py")
        >>> print(deps["main"])
        ["requests", "json", "pathlib"]
    """
    # Implementation here...
```

### Example TypeScript Interface
```typescript
/**
 * Configuration for code analysis engine
 */
interface AnalysisConfig {
  /** Maximum depth for dependency traversal */
  maxDepth: number;
  /** File patterns to include in analysis */
  includePatterns: string[];
  /** Whether to analyze test files */
  includeTests: boolean;
}
```

## Development Process

1. **Fork & Clone**
   ```bash
   git clone https://github.com/dparitosh/codeace-ai.git
   cd codeace-ai
   ```

2. **Setup Development Environment**
   ```bash
   # Backend
   cd backend
   python -m venv venv
   source venv/bin/activate  # or `venv\Scripts\activate` on Windows
   pip install -r requirements.txt
   
   # Frontend
   cd ../frontend
   npm install
   
   # CLI
   cd ../cli
   npm install
   ```

3. **Create Feature Branch**
   ```bash
   git checkout -b feature/amazing-feature
   ```

4. **Make Changes**
   - Write tests first (TDD approach)
   - Implement feature with clear comments
   - Update documentation

5. **Run Tests**
   ```bash
   # Python tests
   pytest tests/
   
   # JavaScript tests
   npm test
   ```

6. **Commit & Push**
   ```bash
   git add .
   git commit -m "feat: add amazing feature with Copilot-friendly docs"
   git push origin feature/amazing-feature
   ```

## Pull Request Process

1. Update README.md with details of changes if needed
2. Update version numbers following [SemVer](http://semver.org/)
3. Fill out the PR template completely
4. Ensure all tests pass
5. Request review from maintainers

## Code Review Checklist

- [ ] Code follows project conventions
- [ ] Includes comprehensive tests
- [ ] Documentation is updated
- [ ] Comments explain complex logic
- [ ] Type hints are included (Python)
- [ ] JSDoc comments are present (JavaScript/TypeScript)
- [ ] No sensitive data exposed

## Reporting Issues

Use GitHub Issues to report bugs or request features:

1. **Bug Reports**: Include steps to reproduce, expected vs actual behavior
2. **Feature Requests**: Describe the use case and proposed solution
3. **Questions**: Use GitHub Discussions for general questions

## License

By contributing, you agree that your contributions will be licensed under the MIT License.
