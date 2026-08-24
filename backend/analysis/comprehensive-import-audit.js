#!/usr/bin/env node

/**
 * Comprehensive Import Audit Script
 * Analyzes all files for import statements and validates file existence
 * Supports: ES6 imports, dynamic imports, require statements, relative/absolute paths
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// ES module compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class ImportAuditor {
    constructor(rootDir) {
        this.rootDir = rootDir;
        this.results = {
            totalFiles: 0,
            filesWithImports: 0,
            totalImports: 0,
            validImports: 0,
            invalidImports: 0,
            issues: [],
            summary: {}
        };
        this.extensions = ['.js', '.jsx', '.ts', '.tsx', '.vue', '.json'];
        this.nodeModulesCache = new Set();
    }

    /**
     * Main audit function
     */
    async audit() {
        console.log('🔍 Starting Comprehensive Import Audit...\n');
        console.log(`📁 Root Directory: ${this.rootDir}\n`);

        const files = await this.getAllFiles(this.rootDir);
        this.results.totalFiles = files.length;

        console.log(`📊 Found ${files.length} files to analyze\n`);

        for (const file of files) {
            await this.analyzeFile(file);
        }

        this.generateReport();
        return this.results;
    }

    /**
     * Recursively get all relevant files
     */
    async getAllFiles(dir, files = []) {
        try {
            const entries = fs.readdirSync(dir, { withFileTypes: true });

            for (const entry of entries) {
                const fullPath = path.join(dir, entry.name);
                
                if (entry.isDirectory()) {
                    // Skip node_modules, .git, dist, build directories
                    if (!['node_modules', '.git', 'dist', 'build', '.next', '.nuxt'].includes(entry.name)) {
                        await this.getAllFiles(fullPath, files);
                    }
                } else if (entry.isFile()) {
                    const ext = path.extname(entry.name);
                    if (this.extensions.includes(ext)) {
                        files.push(fullPath);
                    }
                }
            }
        } catch (error) {
            console.error(`❌ Error reading directory ${dir}:`, error.message);
        }

        return files;
    }

    /**
     * Analyze a single file for import statements
     */
    async analyzeFile(filePath) {
        try {
            const content = fs.readFileSync(filePath, 'utf-8');
            const imports = this.extractImports(content);

            if (imports.length > 0) {
                this.results.filesWithImports++;
                console.log(`📄 Analyzing: ${path.relative(this.rootDir, filePath)}`);

                for (const importStatement of imports) {
                    await this.validateImport(filePath, importStatement);
                }
                console.log('');
            }
        } catch (error) {
            this.addIssue('FILE_READ_ERROR', filePath, null, error.message);
        }
    }

    /**
     * Extract all import statements from file content
     */
    extractImports(content) {
        const imports = [];
        const lines = content.split('\n');

        // Patterns for different import types
        const patterns = [
            // ES6 imports
            /import\s+(?:(?:\{[^}]*\}|\*\s+as\s+\w+|\w+)(?:\s*,\s*(?:\{[^}]*\}|\*\s+as\s+\w+|\w+))*\s+from\s+)?['"`]([^'"`]+)['"`]/g,
            // Dynamic imports
            /import\s*\(\s*['"`]([^'"`]+)['"`]\s*\)/g,
            // CommonJS require
            /require\s*\(\s*['"`]([^'"`]+)['"`]\s*\)/g,
            // Export from
            /export\s+(?:\{[^}]*\}|\*)\s+from\s+['"`]([^'"`]+)['"`]/g
        ];

        lines.forEach((line, lineNumber) => {
            patterns.forEach(pattern => {
                let match;
                const regex = new RegExp(pattern.source, pattern.flags);
                
                while ((match = regex.exec(line)) !== null) {
                    imports.push({
                        statement: match[0],
                        path: match[1],
                        line: lineNumber + 1,
                        type: this.getImportType(match[0])
                    });
                }
            });
        });

        return imports;
    }

    /**
     * Determine import type
     */
    getImportType(statement) {
        if (statement.includes('import(')) return 'dynamic';
        if (statement.includes('require(')) return 'require';
        if (statement.includes('export')) return 'export-from';
        return 'es6';
    }

    /**
     * Validate a single import statement
     */
    async validateImport(filePath, importStatement) {
        this.results.totalImports++;
        const { path: importPath, line, type, statement } = importStatement;

        console.log(`  📦 Line ${line}: ${importPath} (${type})`);

        // Skip external packages (node_modules)
        if (this.isExternalPackage(importPath)) {
            this.results.validImports++;
            console.log(`    ✅ External package`);
            return;
        }

        // Resolve the actual file path
        const resolvedPath = this.resolveImportPath(filePath, importPath);
        
        if (resolvedPath) {
            this.results.validImports++;
            console.log(`    ✅ Valid: ${path.relative(this.rootDir, resolvedPath)}`);
        } else {
            this.results.invalidImports++;
            console.log(`    ❌ Invalid: File not found`);
            this.addIssue('INVALID_IMPORT', filePath, importStatement, `Cannot resolve import: ${importPath}`);
        }
    }

    /**
     * Check if import is an external package
     */
    isExternalPackage(importPath) {
        // External packages don't start with ./ or ../
        return !importPath.startsWith('./') && !importPath.startsWith('../') && !path.isAbsolute(importPath);
    }

    /**
     * Resolve import path to actual file
     */
    resolveImportPath(currentFile, importPath) {
        const currentDir = path.dirname(currentFile);
        
        // Handle relative imports
        let resolvedPath = path.resolve(currentDir, importPath);
        
        // Try different extensions if file doesn't exist
        if (fs.existsSync(resolvedPath)) {
            return resolvedPath;
        }

        // Try with different extensions
        for (const ext of this.extensions) {
            const pathWithExt = resolvedPath + ext;
            if (fs.existsSync(pathWithExt)) {
                return pathWithExt;
            }
        }

        // Try index files in directory
        if (fs.existsSync(resolvedPath) && fs.statSync(resolvedPath).isDirectory()) {
            for (const ext of this.extensions) {
                const indexPath = path.join(resolvedPath, 'index' + ext);
                if (fs.existsSync(indexPath)) {
                    return indexPath;
                }
            }
        }

        return null;
    }

    /**
     * Add issue to results
     */
    addIssue(type, filePath, importStatement, message) {
        this.results.issues.push({
            type,
            file: path.relative(this.rootDir, filePath),
            import: importStatement,
            message,
            timestamp: new Date().toISOString()
        });
    }

    /**
     * Generate comprehensive report
     */
    generateReport() {
        console.log('\n' + '='.repeat(80));
        console.log('📊 COMPREHENSIVE IMPORT AUDIT REPORT');
        console.log('='.repeat(80));

        // Summary statistics
        console.log('\n📈 SUMMARY STATISTICS:');
        console.log(`  Total Files Scanned: ${this.results.totalFiles}`);
        console.log(`  Files with Imports: ${this.results.filesWithImports}`);
        console.log(`  Total Import Statements: ${this.results.totalImports}`);
        console.log(`  Valid Imports: ${this.results.validImports} ✅`);
        console.log(`  Invalid Imports: ${this.results.invalidImports} ❌`);
        
        const successRate = this.results.totalImports > 0 
            ? ((this.results.validImports / this.results.totalImports) * 100).toFixed(2)
            : '100.00';
        console.log(`  Success Rate: ${successRate}%`);

        // Issues breakdown
        if (this.results.issues.length > 0) {
            console.log('\n🚨 ISSUES FOUND:');
            console.log('-'.repeat(50));

            const issuesByType = this.results.issues.reduce((acc, issue) => {
                acc[issue.type] = (acc[issue.type] || 0) + 1;
                return acc;
            }, {});

            Object.entries(issuesByType).forEach(([type, count]) => {
                console.log(`  ${type}: ${count} issues`);
            });

            console.log('\n📋 DETAILED ISSUES:');
            this.results.issues.forEach((issue, index) => {
                console.log(`\n  ${index + 1}. ${issue.type}`);
                console.log(`     File: ${issue.file}`);
                if (issue.import) {
                    console.log(`     Line: ${issue.import.line}`);
                    console.log(`     Import: ${issue.import.path}`);
                    console.log(`     Statement: ${issue.import.statement}`);
                }
                console.log(`     Message: ${issue.message}`);
            });
        } else {
            console.log('\n✅ NO ISSUES FOUND - All imports are valid!');
        }

        // Recommendations
        console.log('\n💡 RECOMMENDATIONS:');
        if (this.results.invalidImports > 0) {
            console.log('  1. Fix invalid import paths listed above');
            console.log('  2. Ensure file extensions match content type (.js vs .jsx)');
            console.log('  3. Verify relative path calculations');
            console.log('  4. Check for typos in file names');
        } else {
            console.log('  🎉 Great! All imports are valid. Your codebase is healthy!');
        }

        console.log('\n' + '='.repeat(80));
        console.log(`Audit completed at: ${new Date().toLocaleString()}`);
        console.log('='.repeat(80));

        // Save detailed report to file
        this.saveDetailedReport();
    }

    /**
     * Save detailed report to JSON file
     */
    saveDetailedReport() {
        const reportPath = path.join(this.rootDir, 'import-audit-report.json');
        const detailedReport = {
            ...this.results,
            auditDate: new Date().toISOString(),
            rootDirectory: this.rootDir,
            configuration: {
                supportedExtensions: this.extensions,
                excludedDirectories: ['node_modules', '.git', 'dist', 'build', '.next', '.nuxt']
            }
        };

        try {
            fs.writeFileSync(reportPath, JSON.stringify(detailedReport, null, 2));
            console.log(`\n📄 Detailed report saved to: ${reportPath}`);
        } catch (error) {
            console.error(`❌ Failed to save report: ${error.message}`);
        }
    }
}

// Execute audit if run directly
if (import.meta.url === `file://${process.argv[1]}`) {
    const auditor = new ImportAuditor(process.cwd());
    auditor.audit().catch(console.error);
}

module.exports = ImportAuditor;
