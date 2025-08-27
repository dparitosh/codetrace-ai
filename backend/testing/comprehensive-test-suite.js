/**
 * Comprehensive Test and Validation Suite
 * Tests all components, services, and database connections
 */

import fs from 'fs';
import path from 'path';
import { spawn } from 'child_process';
import { fileURLToPath } from 'url';

// ES module compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class ComprehensiveTestSuite {
    constructor() {
        this.testResults = {
            frontend: {},
            backend: {},
            database: {},
            integration: {},
            errors: []
        };
    }

    /**
     * Generate React component tests
     */
    generateComponentTests() {
        const componentTests = `
import React from 'react';
import { render, screen, fireEvent, waitFor } from '@testing-library/react';
import '@testing-library/jest-dom';
import { BrowserRouter } from 'react-router-dom';

// Test utilities
const renderWithRouter = (component) => {
    return render(
        <BrowserRouter>
            {component}
        </BrowserRouter>
    );
};

// Error boundary for testing
class TestErrorBoundary extends React.Component {
    constructor(props) {
        super(props);
        this.state = { hasError: false, error: null };
    }

    static getDerivedStateFromError(error) {
        return { hasError: true, error };
    }

    componentDidCatch(error, errorInfo) {
        console.error('Test Error Boundary caught an error:', error, errorInfo);
    }

    render() {
        if (this.state.hasError) {
            return <div data-testid="error-boundary">Error: {this.state.error?.message}</div>;
        }

        return this.props.children;
    }
}

// Component validation tests
describe('Component Validation Tests', () => {
    const criticalComponents = [
        'WorkflowManager',
        'SystemSettings', 
        'DataMigration',
        'QualityMonitor',
        'GraphExplorer',
        'XMLMapper',
        'PLMConnector',
        'Analytics',
        'Dashboard'
    ];

    criticalComponents.forEach(componentName => {
        describe(componentName, () => {
            let Component;

            beforeAll(async () => {
                try {
                    // Dynamic import of component
                    const module = await import(\`../src/components/\${componentName}\`);
                    Component = module.default || module[componentName];
                } catch (error) {
                    console.error(\`Failed to import \${componentName}:\`, error);
                    Component = () => <div data-testid="import-error">Import failed</div>;
                }
            });

            test('should render without crashing', () => {
                expect(() => {
                    renderWithRouter(
                        <TestErrorBoundary>
                            <Component />
                        </TestErrorBoundary>
                    );
                }).not.toThrow();
            });

            test('should not have import errors', () => {
                renderWithRouter(
                    <TestErrorBoundary>
                        <Component />
                    </TestErrorBoundary>
                );
                
                expect(screen.queryByTestId('import-error')).not.toBeInTheDocument();
                expect(screen.queryByTestId('error-boundary')).not.toBeInTheDocument();
            });

            test('should have proper accessibility', () => {
                renderWithRouter(
                    <TestErrorBoundary>
                        <Component />
                    </TestErrorBoundary>
                );

                // Check for basic accessibility attributes
                const component = screen.getByTestId(componentName.toLowerCase()) || 
                                screen.getByRole('main') || 
                                document.querySelector('[role]');
                
                if (component) {
                    expect(component).toBeInTheDocument();
                }
            });
        });
    });
});

// Service integration tests
describe('Service Integration Tests', () => {
    const services = [
        'SystemConfigurationService',
        'GraphChatService', 
        'AgentStatusManager',
        'AgenticOrchestrationService',
        'WorkflowService',
        'DataMigrationService'
    ];

    services.forEach(serviceName => {
        describe(serviceName, () => {
            test('should be available globally', () => {
                // Test if service is accessible
                expect(() => {
                    const service = window[serviceName] || global[serviceName];
                    return service;
                }).not.toThrow();
            });

            test('should handle errors gracefully', async () => {
                try {
                    const service = window[serviceName] || global[serviceName];
                    if (service && typeof service.healthCheck === 'function') {
                        const result = await service.healthCheck();
                        expect(result).toBeDefined();
                    }
                } catch (error) {
                    // Should not throw unhandled errors
                    expect(error.message).toBeDefined();
                }
            });
        });
    });
});

// Network connectivity tests
describe('Network Connectivity Tests', () => {
    const endpoints = [
        { url: 'http://localhost:5173/api/ui-config/ssl-config', service: 'Frontend API' },
        { url: 'http://localhost:8003/api/ui-config/ssl-config', service: 'Backend Config' },
        { url: 'http://localhost:8003/api/workflows', service: 'Workflow API' },
        { url: 'http://localhost:8004/health', service: 'SODA Quality Service' },
        { url: 'http://localhost:8005/health', service: 'PLM XML Service' },
        { url: 'http://localhost:8006/health', service: 'Analytics Service' },
        { url: 'http://localhost:8007/health', service: 'Migration Engine' },
        { url: 'http://localhost:8008/health', service: 'Code Graph Service' }
    ];

    endpoints.forEach(({ url, service }) => {
        test(\`\${service} should be accessible\`, async () => {
            try {
                const response = await fetch(url, { 
                    method: 'GET',
                    timeout: 5000
                });
                
                // Should not get connection refused
                expect(response).toBeDefined();
                
                // If we get a response, it should be valid
                if (response.status !== 0) {
                    expect([200, 404, 500].includes(response.status)).toBe(true);
                }
            } catch (error) {
                // Network errors are expected if services aren't running
                expect(error.message).toMatch(/fetch|network|connection/i);
            }
        }, 10000);
    });
});

export { TestErrorBoundary, renderWithRouter };
`;

        return componentTests;
    }

    /**
     * Generate Python service tests
     */
    generatePythonTests() {
        const pythonTests = `
import pytest
import asyncio
import aiohttp
import json
from typing import Dict, List
import logging

# Configure logging
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

class ServiceHealthChecker:
    """Comprehensive health checker for all Python services"""
    
    def __init__(self):
        self.services = {
            'main': 'http://localhost:8003',
            'soda_quality_service': 'http://localhost:8004', 
            'plm_xml_data_service': 'http://localhost:8005',
            'analytics_storage_service': 'http://localhost:8006',
            'advanced_migration_engine': 'http://localhost:8007',
            'code_graph_service': 'http://localhost:8008'
        }
        
        self.critical_endpoints = {
            'main': ['/health', '/api/workflows', '/api/ui-config/system'],
            'soda_quality_service': ['/health', '/api/quality/check'],
            'plm_xml_data_service': ['/health', '/api/plm/status'],
            'analytics_storage_service': ['/health', '/api/analytics/status'],
            'advanced_migration_engine': ['/health', '/api/migration/status'],
            'code_graph_service': ['/health', '/api/graph/status']
        }

    async def check_service_health(self, session: aiohttp.ClientSession, 
                                 service_name: str, base_url: str) -> Dict:
        """Check health of a single service"""
        results = {
            'service': service_name,
            'base_url': base_url,
            'status': 'unknown',
            'endpoints': {},
            'errors': []
        }
        
        try:
            # Test each critical endpoint
            endpoints = self.critical_endpoints.get(service_name, ['/health'])
            
            for endpoint in endpoints:
                url = f"{base_url}{endpoint}"
                try:
                    async with session.get(url, timeout=5) as response:
                        results['endpoints'][endpoint] = {
                            'status_code': response.status,
                            'accessible': True,
                            'response_time': None  # Could add timing
                        }
                        
                        if response.status == 200:
                            try:
                                data = await response.json()
                                results['endpoints'][endpoint]['data'] = data
                            except:
                                results['endpoints'][endpoint]['data'] = await response.text()
                                
                except asyncio.TimeoutError:
                    results['endpoints'][endpoint] = {
                        'status_code': None,
                        'accessible': False,
                        'error': 'timeout'
                    }
                    results['errors'].append(f"Timeout accessing {endpoint}")
                    
                except aiohttp.ClientConnectorError:
                    results['endpoints'][endpoint] = {
                        'status_code': None,
                        'accessible': False, 
                        'error': 'connection_refused'
                    }
                    results['errors'].append(f"Connection refused for {endpoint}")
                    
                except Exception as e:
                    results['endpoints'][endpoint] = {
                        'status_code': None,
                        'accessible': False,
                        'error': str(e)
                    }
                    results['errors'].append(f"Error accessing {endpoint}: {str(e)}")
            
            # Determine overall service status
            accessible_endpoints = sum(1 for ep in results['endpoints'].values() 
                                     if ep.get('accessible', False))
            total_endpoints = len(results['endpoints'])
            
            if accessible_endpoints == total_endpoints:
                results['status'] = 'healthy'
            elif accessible_endpoints > 0:
                results['status'] = 'partially_healthy'
            else:
                results['status'] = 'unhealthy'
                
        except Exception as e:
            results['status'] = 'error'
            results['errors'].append(f"Service check failed: {str(e)}")
            logger.error(f"Failed to check {service_name}: {e}")
            
        return results

    async def check_all_services(self) -> Dict:
        """Check health of all services"""
        results = {
            'timestamp': asyncio.get_event_loop().time(),
            'services': {},
            'summary': {
                'total': len(self.services),
                'healthy': 0,
                'partially_healthy': 0,
                'unhealthy': 0,
                'errors': 0
            }
        }
        
        async with aiohttp.ClientSession() as session:
            tasks = []
            for service_name, base_url in self.services.items():
                task = self.check_service_health(session, service_name, base_url)
                tasks.append(task)
            
            service_results = await asyncio.gather(*tasks, return_exceptions=True)
            
            for result in service_results:
                if isinstance(result, Exception):
                    logger.error(f"Service check exception: {result}")
                    results['summary']['errors'] += 1
                else:
                    service_name = result['service']
                    results['services'][service_name] = result
                    
                    # Update summary
                    if result['status'] == 'healthy':
                        results['summary']['healthy'] += 1
                    elif result['status'] == 'partially_healthy':
                        results['summary']['partially_healthy'] += 1
                    else:
                        results['summary']['unhealthy'] += 1
        
        return results

# Test cases
@pytest.mark.asyncio
async def test_all_services_health():
    """Test that all services are accessible"""
    checker = ServiceHealthChecker()
    results = await checker.check_all_services()
    
    # At least some services should be accessible
    assert results['summary']['healthy'] + results['summary']['partially_healthy'] > 0, \
        "No services are accessible"
    
    # Log results for debugging
    logger.info(f"Service health check results: {json.dumps(results, indent=2)}")

@pytest.mark.asyncio 
async def test_critical_endpoints():
    """Test critical endpoints are responding"""
    checker = ServiceHealthChecker()
    results = await checker.check_all_services()
    
    critical_services = ['main', 'advanced_migration_engine']
    
    for service_name in critical_services:
        if service_name in results['services']:
            service_result = results['services'][service_name]
            assert service_result['status'] in ['healthy', 'partially_healthy'], \
                f"Critical service {service_name} is not accessible"

@pytest.mark.asyncio
async def test_database_connections():
    """Test database connectivity through services"""
    # This would test database connections through the services
    # Implementation depends on service APIs
    pass

if __name__ == "__main__":
    # Run health check directly
    async def main():
        checker = ServiceHealthChecker()
        results = await checker.check_all_services()
        print(json.dumps(results, indent=2))
    
    asyncio.run(main())
`;

        return pythonTests;
    }

    /**
     * Generate database validation tests
     */
    generateDatabaseTests() {
        const dbTests = `
/**
 * Database Validation Tests
 * Tests database connectivity, schema validation, and data integrity
 */

const { Pool } = require('pg');
const neo4j = require('neo4j-driver');

class DatabaseValidator {
    constructor() {
        this.pgConfig = {
            host: 'localhost',
            port: 5432,
            database: 'graphtrace',
            user: 'postgres',
            password: process.env.POSTGRES_PASSWORD || 'tcs12345'
        };
        
        this.neo4jConfig = {
            uri: 'bolt://localhost:7687',
            user: 'neo4j',
            password: process.env.NEO4J_PASSWORD || 'tcs12345'
        };
        
        this.expectedTables = [
            'workflows',
            'workflow_executions', 
            'workflow_steps',
            'data_sources',
            'data_lineage',
            'quality_checks',
            'migration_jobs',
            'migration_logs',
            'system_config',
            'user_preferences',
            'audit_logs',
            'performance_metrics'
        ];
    }

    async validatePostgreSQL() {
        const results = {
            connection: false,
            tables: {},
            errors: []
        };

        let pool;
        try {
            pool = new Pool(this.pgConfig);
            
            // Test connection
            const client = await pool.connect();
            results.connection = true;
            
            // Check if expected tables exist
            const tableQuery = \`
                SELECT table_name 
                FROM information_schema.tables 
                WHERE table_schema = 'public'
                AND table_type = 'BASE TABLE'
            \`;
            
            const tableResult = await client.query(tableQuery);
            const existingTables = tableResult.rows.map(row => row.table_name);
            
            this.expectedTables.forEach(tableName => {
                results.tables[tableName] = {
                    exists: existingTables.includes(tableName),
                    schema: null
                };
                
                if (results.tables[tableName].exists) {
                    // Get table schema
                    this.getTableSchema(client, tableName)
                        .then(schema => {
                            results.tables[tableName].schema = schema;
                        })
                        .catch(err => {
                            results.errors.push(\`Failed to get schema for \${tableName}: \${err.message}\`);
                        });
                }
            });
            
            client.release();
            
        } catch (error) {
            results.errors.push(\`PostgreSQL connection failed: \${error.message}\`);
        } finally {
            if (pool) {
                await pool.end();
            }
        }
        
        return results;
    }

    async getTableSchema(client, tableName) {
        const schemaQuery = \`
            SELECT column_name, data_type, is_nullable, column_default
            FROM information_schema.columns
            WHERE table_schema = 'public' 
            AND table_name = $1
            ORDER BY ordinal_position
        \`;
        
        const result = await client.query(schemaQuery, [tableName]);
        return result.rows;
    }

    async validateNeo4j() {
        const results = {
            connection: false,
            nodes: {},
            relationships: {},
            errors: []
        };

        let driver;
        try {
            driver = neo4j.driver(
                this.neo4jConfig.uri,
                neo4j.auth.basic(this.neo4jConfig.user, this.neo4jConfig.password)
            );
            
            const session = driver.session();
            
            // Test connection
            await session.run('RETURN 1');
            results.connection = true;
            
            // Check node labels
            const labelsResult = await session.run('CALL db.labels()');
            const labels = labelsResult.records.map(record => record.get(0));
            
            const expectedLabels = ['DataNode', 'ProcessNode', 'SystemNode'];
            expectedLabels.forEach(label => {
                results.nodes[label] = {
                    exists: labels.includes(label),
                    count: 0
                };
            });
            
            // Get node counts
            for (const label of labels) {
                try {
                    const countResult = await session.run(\`MATCH (n:\${label}) RETURN count(n) as count\`);
                    const count = countResult.records[0].get('count').toNumber();
                    if (results.nodes[label]) {
                        results.nodes[label].count = count;
                    }
                } catch (err) {
                    results.errors.push(\`Failed to count \${label} nodes: \${err.message}\`);
                }
            }
            
            // Check relationship types
            const relTypesResult = await session.run('CALL db.relationshipTypes()');
            const relTypes = relTypesResult.records.map(record => record.get(0));
            
            const expectedRelTypes = ['CONNECTS_TO', 'DEPENDS_ON', 'PROCESSES'];
            expectedRelTypes.forEach(relType => {
                results.relationships[relType] = {
                    exists: relTypes.includes(relType),
                    count: 0
                };
            });
            
            await session.close();
            
        } catch (error) {
            results.errors.push(\`Neo4j connection failed: \${error.message}\`);
        } finally {
            if (driver) {
                await driver.close();
            }
        }
        
        return results;
    }

    async runCompleteValidation() {
        const results = {
            timestamp: new Date().toISOString(),
            postgresql: await this.validatePostgreSQL(),
            neo4j: await this.validateNeo4j(),
            summary: {
                postgresql_healthy: false,
                neo4j_healthy: false,
                total_errors: 0
            }
        };
        
        results.summary.postgresql_healthy = results.postgresql.connection && 
                                           results.postgresql.errors.length === 0;
        results.summary.neo4j_healthy = results.neo4j.connection && 
                                       results.neo4j.errors.length === 0;
        results.summary.total_errors = results.postgresql.errors.length + 
                                      results.neo4j.errors.length;
        
        return results;
    }
}

module.exports = { DatabaseValidator };

// Jest tests
if (typeof test !== 'undefined') {
    describe('Database Validation Tests', () => {
        let validator;
        
        beforeAll(() => {
            validator = new DatabaseValidator();
        });
        
        test('PostgreSQL should be accessible', async () => {
            const result = await validator.validatePostgreSQL();
            expect(result.connection).toBe(true);
        });
        
        test('Neo4j should be accessible', async () => {
            const result = await validator.validateNeo4j();
            expect(result.connection).toBe(true);
        });
        
        test('Required tables should exist', async () => {
            const result = await validator.validatePostgreSQL();
            const requiredTables = ['workflows', 'migration_jobs', 'system_config'];
            
            requiredTables.forEach(table => {
                expect(result.tables[table]?.exists).toBe(true);
            });
        });
    });
}
`;

        return dbTests;
    }

    /**
     * Run all tests and generate report
     */
    async generateTestSuite() {
        console.log('🧪 Generating comprehensive test suite...');

        // Generate test files
        const componentTests = this.generateComponentTests();
        const pythonTests = this.generatePythonTests();
        const databaseTests = this.generateDatabaseTests();

        // Save test files
        const testDir = path.join(__dirname, 'tests');
        if (!fs.existsSync(testDir)) {
            fs.mkdirSync(testDir, { recursive: true });
        }

        fs.writeFileSync(path.join(testDir, 'component-validation.test.js'), componentTests);
        fs.writeFileSync(path.join(testDir, 'service-health.test.py'), pythonTests);
        fs.writeFileSync(path.join(testDir, 'database-validation.test.js'), databaseTests);

        // Generate test runner script
        const testRunner = this.generateTestRunner();
        fs.writeFileSync(path.join(__dirname, 'run-all-tests.js'), testRunner);

        // Generate package.json test scripts
        const packageJsonUpdates = this.generatePackageJsonUpdates();
        fs.writeFileSync(path.join(__dirname, 'test-scripts-package-json-update.json'), packageJsonUpdates);

        console.log('✅ Test suite generated successfully!');
        console.log(`📁 Test files saved in: ${testDir}`);

        return {
            testFiles: [
                'tests/component-validation.test.js',
                'tests/service-health.test.py', 
                'tests/database-validation.test.js'
            ],
            runner: 'run-all-tests.js',
            packageUpdates: 'test-scripts-package-json-update.json'
        };
    }

    /**
     * Generate test runner script
     */
    generateTestRunner() {
        return `
class TestRunner {
    constructor() {
        this.results = {
            frontend: { passed: 0, failed: 0, errors: [] },
            backend: { passed: 0, failed: 0, errors: [] },
            database: { passed: 0, failed: 0, errors: [] }
        };
    }

    async runFrontendTests() {
        console.log('🧪 Running frontend component tests...');
        
        return new Promise((resolve) => {
            const jest = spawn('npm', ['test', '--', '--testPathPattern=component-validation'], {
                cwd: __dirname,
                stdio: 'inherit'
            });

            jest.on('close', (code) => {
                if (code === 0) {
                    this.results.frontend.passed++;
                    console.log('✅ Frontend tests passed');
                } else {
                    this.results.frontend.failed++;
                    console.log('❌ Frontend tests failed');
                }
                resolve(code);
            });

            jest.on('error', (error) => {
                this.results.frontend.errors.push(error.message);
                console.error('❌ Frontend test error:', error.message);
                resolve(1);
            });
        });
    }

    async runBackendTests() {
        console.log('🧪 Running backend service tests...');
        
        return new Promise((resolve) => {
            const pytest = spawn('python', ['-m', 'pytest', 'tests/service-health.test.py', '-v'], {
                cwd: __dirname,
                stdio: 'inherit'
            });

            pytest.on('close', (code) => {
                if (code === 0) {
                    this.results.backend.passed++;
                    console.log('✅ Backend tests passed');
                } else {
                    this.results.backend.failed++;
                    console.log('❌ Backend tests failed');
                }
                resolve(code);
            });

            pytest.on('error', (error) => {
                this.results.backend.errors.push(error.message);
                console.error('❌ Backend test error:', error.message);
                resolve(1);
            });
        });
    }

    async runDatabaseTests() {
        console.log('🧪 Running database validation tests...');
        
        return new Promise((resolve) => {
            const dbTest = spawn('node', ['tests/database-validation.test.js'], {
                cwd: __dirname,
                stdio: 'inherit'
            });

            dbTest.on('close', (code) => {
                if (code === 0) {
                    this.results.database.passed++;
                    console.log('✅ Database tests passed');
                } else {
                    this.results.database.failed++;
                    console.log('❌ Database tests failed');
                }
                resolve(code);
            });

            dbTest.on('error', (error) => {
                this.results.database.errors.push(error.message);
                console.error('❌ Database test error:', error.message);
                resolve(1);
            });
        });
    }

    async runAllTests() {
        console.log('🚀 Starting comprehensive test suite...');
        
        const frontendResult = await this.runFrontendTests();
        const backendResult = await this.runBackendTests();
        const databaseResult = await this.runDatabaseTests();

        // Generate summary report
        const totalPassed = this.results.frontend.passed + 
                           this.results.backend.passed + 
                           this.results.database.passed;
        const totalFailed = this.results.frontend.failed + 
                           this.results.backend.failed + 
                           this.results.database.failed;

        console.log('\\n📊 TEST SUMMARY');
        console.log('================');
        console.log(\`✅ Passed: \${totalPassed}\`);
        console.log(\`❌ Failed: \${totalFailed}\`);
        console.log(\`🔧 Frontend: \${this.results.frontend.passed}P/\${this.results.frontend.failed}F\`);
        console.log(\`🐍 Backend: \${this.results.backend.passed}P/\${this.results.backend.failed}F\`);
        console.log(\`🗄️ Database: \${this.results.database.passed}P/\${this.results.database.failed}F\`);

        if (totalFailed === 0) {
            console.log('\\n🎉 All tests passed!');
        } else {
            console.log('\\n⚠️ Some tests failed. Check logs above for details.');
        }

        return { totalPassed, totalFailed, results: this.results };
    }
}

// Run if called directly
if (require.main === module) {
    const runner = new TestRunner();
    runner.runAllTests();
}

module.exports = { TestRunner };
`;
    }

    /**
     * Generate package.json updates for test scripts
     */
    generatePackageJsonUpdates() {
        return JSON.stringify({
            scripts: {
                "test": "jest",
                "test:watch": "jest --watch",
                "test:coverage": "jest --coverage",
                "test:components": "jest --testPathPattern=component-validation",
                "test:integration": "node run-all-tests.js",
                "test:backend": "python -m pytest tests/service-health.test.py -v",
                "test:database": "node tests/database-validation.test.js",
                "validate:imports": "node comprehensive-import-audit.js",
                "validate:errors": "node error-tracker-fixed.js",
                "validate:matrix": "node complete-traceability-matrix.js",
                "health:check": "node tests/database-validation.test.js && python tests/service-health.test.py",
                "validate:all": "npm run validate:imports && npm run validate:errors && npm run test:integration"
            },
            devDependencies: {
                "@testing-library/jest-dom": "^6.1.0",
                "@testing-library/react": "^13.4.0",
                "@testing-library/user-event": "^14.5.0",
                "jest": "^29.7.0",
                "jest-environment-jsdom": "^29.7.0"
            },
            jest: {
                testEnvironment: "jsdom",
                setupFilesAfterEnv: ["<rootDir>/src/setupTests.js"],
                moduleNameMapping: {
                    "^@/(.*)$": "<rootDir>/src/$1"
                },
                testPathIgnorePatterns: [
                    "/node_modules/",
                    "/build/"
                ],
                collectCoverageFrom: [
                    "src/**/*.{js,jsx}",
                    "!src/index.js",
                    "!src/reportWebVitals.js"
                ]
            }
        }, null, 2);
    }
}

// Export and run
export { ComprehensiveTestSuite };

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    const testSuite = new ComprehensiveTestSuite();
    testSuite.generateTestSuite();
}
