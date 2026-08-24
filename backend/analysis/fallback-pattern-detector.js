#!/usr/bin/env node

/**
 * 🔍 Fallback, Dummy, Demo, and Mockup Pattern Detector
 * 
 * Detects potentially problematic patterns in codebase:
 * - Fallback configurations that might mask real issues
 * - Dummy/mock data in production code
 * - Demo/example code that should be removed
 * - Placeholder content that needs implementation
 * - Test data patterns in production files
 */

import fs from 'fs';
import path from 'path';

class FallbackPatternDetector {
    constructor() {
        this.patterns = {
            fallback: {
                regex: /fallback|fall.*back|default.*config|backup.*config|emergency.*config/gi,
                severity: 'medium',
                description: 'Fallback configurations detected - verify these are intentional'
            },
            dummy: {
                regex: /dummy|fake.*data|sample.*data|placeholder.*data|test.*data(?!.*test\.js)/gi,
                severity: 'high',
                description: 'Dummy/fake data patterns - should not be in production'
            },
            demo: {
                regex: /demo|example|sample(?!.*test)|tutorial|getting.*started/gi,
                severity: 'medium',
                description: 'Demo/example code - verify this should be in production'
            },
            mockup: {
                regex: /mockup|mock(?!.*test)|stub(?!.*test)|temporary|temp(?!.*test)|todo|fixme|hack/gi,
                severity: 'high',
                description: 'Mockup/temporary code - needs proper implementation'
            },
            placeholder: {
                regex: /placeholder|coming.*soon|not.*implemented|under.*construction|work.*in.*progress/gi,
                severity: 'high',
                description: 'Placeholder content - requires implementation'
            },
            hardcoded: {
                regex: /localhost|127\.0\.0\.1|192\.168\.|10\.|172\.|hardcode|hard.*code/gi,
                severity: 'medium',
                description: 'Hardcoded values detected - should use configuration'
            },
            testPatterns: {
                regex: /"test.*user"|"admin"|"password"|"123456"|"secret"|"key123"/gi,
                severity: 'critical',
                description: 'Test credentials/data in production code - SECURITY RISK'
            },
            console: {
                regex: /console\.(log|debug|warn|error|info)\s*\(/gi,
                severity: 'low',
                description: 'Console statements - should use proper logging'
            }
        };

        this.results = {
            critical: [],
            high: [],
            medium: [],
            low: []
        };

        this.totalFiles = 0;
        this.scannedFiles = 0;
        this.issuesFound = 0;
    }

    async scanDirectory(dirPath = '.') {
        console.log('🔍 Starting Fallback Pattern Detection...\n');
        
        try {
            await this.walkDirectory(dirPath);
            return this.generateReport();
        } catch (error) {
            console.error('❌ Error during scan:', error.message);
            return null;
        }
    }

    async walkDirectory(dirPath) {
        const entries = fs.readdirSync(dirPath, { withFileTypes: true });
        
        for (const entry of entries) {
            const fullPath = path.join(dirPath, entry.name);
            
            if (entry.isDirectory()) {
                // Skip certain directories
                if (this.shouldSkipDirectory(entry.name)) {
                    continue;
                }
                await this.walkDirectory(fullPath);
            } else if (entry.isFile()) {
                this.totalFiles++;
                if (this.shouldScanFile(entry.name)) {
                    await this.scanFile(fullPath);
                }
            }
        }
    }

    shouldSkipDirectory(dirName) {
        const skipDirs = [
            'node_modules', '.git', 'dist', 'build', 'coverage',
            '.vscode', '.idea', 'temp', 'tmp', '__pycache__',
            '.pytest_cache', 'venv', 'env'
        ];
        return skipDirs.includes(dirName) || dirName.startsWith('.');
    }

    shouldScanFile(fileName) {
        const extensions = [
            '.js', '.jsx', '.ts', '.tsx', '.py', '.json',
            '.yaml', '.yml', '.md', '.txt', '.env',
            '.config', '.conf', '.ini'
        ];
        
        const skipFiles = [
            'package-lock.json', 'yarn.lock', '.gitignore',
            'LICENSE', 'CHANGELOG'
        ];
        
        if (skipFiles.includes(fileName)) return false;
        
        return extensions.some(ext => fileName.endsWith(ext)) || 
               fileName.includes('config') || 
               fileName.includes('settings');
    }

    async scanFile(filePath) {
        try {
            const content = fs.readFileSync(filePath, 'utf8');
            const lines = content.split('\n');
            this.scannedFiles++;
            
            // Show progress
            if (this.scannedFiles % 10 === 0) {
                process.stdout.write(`\r📊 Scanned ${this.scannedFiles} files...`);
            }
            
            for (const [patternName, pattern] of Object.entries(this.patterns)) {
                this.scanForPattern(filePath, content, lines, patternName, pattern);
            }
            
        } catch (error) {
            // Skip binary files or files that can't be read
            if (error.code !== 'EISDIR') {
                console.warn(`⚠️  Could not scan ${filePath}: ${error.message}`);
            }
        }
    }

    scanForPattern(filePath, content, lines, patternName, pattern) {
        const matches = content.match(pattern.regex);
        
        if (matches) {
            // Find line numbers for each match
            const issues = [];
            
            matches.forEach(match => {
                const lineIndex = lines.findIndex(line => line.includes(match));
                const lineNumber = lineIndex + 1;
                const contextLine = lines[lineIndex]?.trim() || '';
                
                issues.push({
                    file: path.relative('.', filePath),
                    line: lineNumber,
                    pattern: patternName,
                    match: match,
                    context: contextLine,
                    severity: pattern.severity,
                    description: pattern.description
                });
            });
            
            // Group by severity
            issues.forEach(issue => {
                this.results[issue.severity].push(issue);
                this.issuesFound++;
            });
        }
    }

    generateReport() {
        console.log('\n\n📋 FALLBACK PATTERN DETECTION REPORT\n');
        console.log('='.repeat(60));
        
        console.log(`📊 **Scan Summary:**`);
        console.log(`   📁 Total Files: ${this.totalFiles}`);
        console.log(`   🔍 Scanned Files: ${this.scannedFiles}`);
        console.log(`   ⚠️  Issues Found: ${this.issuesFound}\n`);
        
        // Report by severity
        this.reportBySeverity('critical', '🔥 CRITICAL ISSUES', 'red');
        this.reportBySeverity('high', '⚠️  HIGH PRIORITY ISSUES', 'yellow');
        this.reportBySeverity('medium', '⚡ MEDIUM PRIORITY ISSUES', 'cyan');
        this.reportBySeverity('low', '💡 LOW PRIORITY ISSUES', 'gray');
        
        // Generate summary
        this.generateSummary();
        
        // Save detailed report
        this.saveDetailedReport();
        
        return {
            totalFiles: this.totalFiles,
            scannedFiles: this.scannedFiles,
            issuesFound: this.issuesFound,
            results: this.results,
            summary: this.generateIssueSummary()
        };
    }

    reportBySeverity(severity, title, color) {
        const issues = this.results[severity];
        
        if (issues.length === 0) {
            console.log(`${title}: ✅ None found\n`);
            return;
        }
        
        console.log(`${title}: ${issues.length} issues\n`);
        
        // Group by pattern type
        const byPattern = {};
        issues.forEach(issue => {
            if (!byPattern[issue.pattern]) {
                byPattern[issue.pattern] = [];
            }
            byPattern[issue.pattern].push(issue);
        });
        
        // Show details for each pattern
        Object.entries(byPattern).forEach(([pattern, patternIssues]) => {
            console.log(`  📌 ${pattern.toUpperCase()} (${patternIssues.length} issues):`);
            console.log(`     ${patternIssues[0].description}\n`);
            
            patternIssues.slice(0, 5).forEach(issue => {
                console.log(`     📄 ${issue.file}:${issue.line}`);
                console.log(`        "${issue.match}" in: ${issue.context.substring(0, 80)}...`);
            });
            
            if (patternIssues.length > 5) {
                console.log(`     ... and ${patternIssues.length - 5} more`);
            }
            console.log();
        });
    }

    generateSummary() {
        console.log('📈 **RECOMMENDATIONS:**\n');
        
        if (this.results.critical.length > 0) {
            console.log('🔥 **CRITICAL - Fix Immediately:**');
            console.log('   - Remove test credentials and sensitive data');
            console.log('   - Replace hardcoded secrets with environment variables');
        }
        
        if (this.results.high.length > 0) {
            console.log('⚠️  **HIGH PRIORITY:**');
            console.log('   - Replace dummy/mock data with real implementations');
            console.log('   - Remove placeholder content and implement features');
            console.log('   - Clean up temporary/hack solutions');
        }
        
        if (this.results.medium.length > 0) {
            console.log('⚡ **MEDIUM PRIORITY:**');
            console.log('   - Review fallback configurations for appropriateness');
            console.log('   - Remove demo/example code not needed in production');
            console.log('   - Replace hardcoded values with configuration');
        }
        
        if (this.results.low.length > 0) {
            console.log('💡 **LOW PRIORITY:**');
            console.log('   - Replace console statements with proper logging');
            console.log('   - Clean up development debugging code');
        }
        
        console.log('\n🎯 **NEXT STEPS:**');
        console.log('1. Address critical issues first');
        console.log('2. Create configuration files for hardcoded values');
        console.log('3. Implement proper error handling instead of fallbacks');
        console.log('4. Set up proper logging infrastructure\n');
    }

    generateIssueSummary() {
        const summary = {};
        
        Object.entries(this.results).forEach(([severity, issues]) => {
            summary[severity] = {
                count: issues.length,
                patterns: {}
            };
            
            issues.forEach(issue => {
                if (!summary[severity].patterns[issue.pattern]) {
                    summary[severity].patterns[issue.pattern] = 0;
                }
                summary[severity].patterns[issue.pattern]++;
            });
        });
        
        return summary;
    }

    saveDetailedReport() {
        const timestamp = new Date().toISOString().replace(/[:.]/g, '-');
        const reportFile = `fallback-pattern-report-${timestamp}.json`;
        
        const report = {
            timestamp: new Date().toISOString(),
            scan_summary: {
                total_files: this.totalFiles,
                scanned_files: this.scannedFiles,
                issues_found: this.issuesFound
            },
            results: this.results,
            summary: this.generateIssueSummary(),
            patterns_detected: Object.keys(this.patterns)
        };
        
        try {
            // Save JSON report
            fs.writeFileSync(reportFile, JSON.stringify(report, null, 2));
            console.log(`💾 Detailed JSON report saved to: ${reportFile}`);
            
            // Generate HTML report
            this.generateHTMLReport(report);
            
        } catch (error) {
            console.warn(`⚠️  Could not save report: ${error.message}`);
        }
    }

    async generateHTMLReport(report) {
        try {
            // Dynamic import for HTML generator
            const { default: HTMLReportGenerator } = await import('./html-report-generator.js');
            
            const generator = new HTMLReportGenerator();
            
            // Convert pattern data to validation format for HTML generator
            const validationData = {
                timestamp: report.timestamp,
                overall_health: Math.max(0, 100 - this.issuesFound * 2),
                validations: [
                    {
                        name: 'Pattern Analysis',
                        score: Math.max(0, 100 - this.issuesFound * 2),
                        result: {
                            totalFiles: this.totalFiles,
                            scannedFiles: this.scannedFiles,
                            issuesFound: this.issuesFound,
                            summary: report.summary
                        }
                    }
                ],
                errors: [],
                recommendations: this.getHTMLRecommendations()
            };
            
            const reportPaths = generator.generateValidationReport(validationData, report);
            console.log(`🎨 HTML Pattern report saved to: ${reportPaths.filePath}`);
            console.log(`🔗 Open in browser: file://${reportPaths.latestPath}`);
            
        } catch (error) {
            console.warn(`⚠️  HTML report generation failed: ${error.message}`);
        }
    }

    getHTMLRecommendations() {
        const recommendations = [];
        
        if (this.results.critical.length > 0) {
            recommendations.push('🔥 CRITICAL: Remove test credentials and hardcoded secrets immediately');
        }
        
        if (this.results.high.length > 0) {
            recommendations.push('⚠️ HIGH: Replace dummy/mock data with real implementations');
            recommendations.push('⚠️ HIGH: Implement placeholder content and remove temporary solutions');
        }
        
        if (this.results.medium.length > 0) {
            recommendations.push('⚡ MEDIUM: Review fallback configurations for appropriateness');
            recommendations.push('⚡ MEDIUM: Replace hardcoded values with configuration files');
        }
        
        if (this.results.low.length > 0) {
            recommendations.push('💡 LOW: Replace console statements with proper logging framework');
        }
        
        if (recommendations.length === 0) {
            recommendations.push('✅ No problematic patterns detected - excellent code quality!');
        }
        
        return recommendations;
    }
}

// Main execution
async function main() {
    console.log('🚀 Fallback Pattern Detector v1.0\n');
    
    const detector = new FallbackPatternDetector();
    const scanPath = process.argv[2] || '.';
    
    console.log(`📁 Scanning directory: ${path.resolve(scanPath)}\n`);
    
    const startTime = Date.now();
    const results = await detector.scanDirectory(scanPath);
    const endTime = Date.now();
    
    if (results) {
        console.log(`⏱️  Scan completed in ${((endTime - startTime) / 1000).toFixed(2)} seconds`);
        
        // Exit with appropriate code
        const hasIssues = results.issuesFound > 0;
        process.exit(hasIssues ? 1 : 0);
    } else {
        console.log('❌ Scan failed');
        process.exit(1);
    }
}

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    main().catch(error => {
        console.error('❌ Fatal error:', error);
        process.exit(1);
    });
}

export default FallbackPatternDetector;
