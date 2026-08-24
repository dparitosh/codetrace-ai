/**
 * Complete Traceability Matrix Generator
 * Maps all pages -> UI components -> Python services -> Database schemas
 */

import fs from 'fs';
import path from 'path';
import { fileURLToPath } from 'url';

// ES module compatibility
const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

class TraceabilityMatrixGenerator {
    constructor() {
        this.matrix = {
            pages: {},
            components: {},
            services: {},
            databases: {},
            mappings: {
                pageToComponent: {},
                componentToService: {},
                serviceToDatabase: {},
                fullTrace: {}
            }
        };
    }

    /**
     * Scan for all React pages
     */
    async scanPages(srcDir) {
        const pagesDir = path.join(srcDir, 'pages');
        const pages = [];

        if (fs.existsSync(pagesDir)) {
            const pageFiles = fs.readdirSync(pagesDir);
            pageFiles.forEach(file => {
                if (file.endsWith('.jsx') || file.endsWith('.js')) {
                    const pageName = file.replace(/\.(jsx?|tsx?)$/, '');
                    const filePath = path.join(pagesDir, file);
                    const content = fs.readFileSync(filePath, 'utf8');
                    
                    pages.push({
                        name: pageName,
                        file: file,
                        path: filePath,
                        imports: this.extractImports(content),
                        components: this.extractComponentUsage(content),
                        services: this.extractServiceUsage(content)
                    });
                }
            });
        }

        // Also scan for route components in other directories
        const additionalPages = this.scanForRouteComponents(srcDir);
        pages.push(...additionalPages);

        return pages;
    }

    /**
     * Scan for route components in other directories
     */
    scanForRouteComponents(srcDir) {
        const routeComponents = [];
        const componentsDir = path.join(srcDir, 'components');
        
        // Known page-level components based on the codebase
        const pageComponents = [
            'SystemSettings',
            'WorkflowManager', 
            'GraphExplorer',
            'DataMigration',
            'QualityMonitor',
            'Dashboard',
            'XMLMapper',
            'PLMConnector',
            'Analytics'
        ];

        pageComponents.forEach(componentName => {
            const possiblePaths = [
                path.join(componentsDir, `${componentName}.jsx`),
                path.join(componentsDir, `${componentName}`, 'index.jsx'),
                path.join(componentsDir, `${componentName}`, `${componentName}.jsx`),
                path.join(srcDir, `${componentName}.jsx`)
            ];

            possiblePaths.forEach(filePath => {
                if (fs.existsSync(filePath)) {
                    const content = fs.readFileSync(filePath, 'utf8');
                    routeComponents.push({
                        name: componentName,
                        file: path.basename(filePath),
                        path: filePath,
                        imports: this.extractImports(content),
                        components: this.extractComponentUsage(content),
                        services: this.extractServiceUsage(content),
                        isPageComponent: true
                    });
                }
            });
        });

        return routeComponents;
    }

    /**
     * Extract import statements from file content
     */
    extractImports(content) {
        const imports = [];
        const importRegex = /import\s+(?:{[^}]*}|\*\s+as\s+\w+|\w+)\s+from\s+['"`]([^'"`]+)['"`]/g;
        let match;

        while ((match = importRegex.exec(content)) !== null) {
            imports.push(match[1]);
        }

        return imports;
    }

    /**
     * Extract component usage from JSX content
     */
    extractComponentUsage(content) {
        const components = [];
        // Match JSX component tags
        const componentRegex = /<([A-Z][a-zA-Z0-9]*)/g;
        let match;

        while ((match = componentRegex.exec(content)) !== null) {
            if (!components.includes(match[1])) {
                components.push(match[1]);
            }
        }

        return components;
    }

    /**
     * Extract service usage from content
     */
    extractServiceUsage(content) {
        const services = [];
        const servicePatterns = [
            /(\w+Service)\.(\w+)/g,
            /api\/(\w+)/g,
            /fetch.*\/api\/([^\/\s'"]+)/g,
            /useQuery.*['"`]([^'"`]+)['"`]/g
        ];

        servicePatterns.forEach(pattern => {
            let match;
            while ((match = pattern.exec(content)) !== null) {
                const service = match[1];
                if (service && !services.includes(service)) {
                    services.push(service);
                }
            }
        });

        return services;
    }

    /**
     * Scan Python backend services
     */
    async scanPythonServices(backendDir) {
        const services = [];
        const serviceFiles = [
            'main.py',
            'services/soda_quality_service.py',
            'services/plm_xml_data_service.py', 
            'services/analytics_storage_service.py',
            'services/advanced_migration_engine.py',
            'services/code_graph_service.py'
        ];

        serviceFiles.forEach(serviceFile => {
            const filePath = path.join(backendDir, serviceFile);
            if (fs.existsSync(filePath)) {
                const content = fs.readFileSync(filePath, 'utf8');
                const serviceName = path.basename(serviceFile, '.py');
                
                services.push({
                    name: serviceName,
                    file: serviceFile,
                    path: filePath,
                    endpoints: this.extractAPIEndpoints(content),
                    models: this.extractDatabaseModels(content),
                    dependencies: this.extractPythonImports(content)
                });
            }
        });

        return services;
    }

    /**
     * Extract API endpoints from Python content
     */
    extractAPIEndpoints(content) {
        const endpoints = [];
        const endpointRegex = /@app\.(get|post|put|delete|patch)\(['"`]([^'"`]+)['"`]/g;
        let match;

        while ((match = endpointRegex.exec(content)) !== null) {
            endpoints.push({
                method: match[1].toUpperCase(),
                path: match[2]
            });
        }

        return endpoints;
    }

    /**
     * Extract database model references
     */
    extractDatabaseModels(content) {
        const models = [];
        const modelPatterns = [
            /class\s+(\w+)\(.*Base.*\):/g,
            /Table\(['"`]([^'"`]+)['"`]/g,
            /SELECT.*FROM\s+(\w+)/gi,
            /INSERT\s+INTO\s+(\w+)/gi,
            /UPDATE\s+(\w+)/gi
        ];

        modelPatterns.forEach(pattern => {
            let match;
            while ((match = pattern.exec(content)) !== null) {
                const model = match[1];
                if (model && !models.includes(model)) {
                    models.push(model);
                }
            }
        });

        return models;
    }

    /**
     * Extract Python imports
     */
    extractPythonImports(content) {
        const imports = [];
        const importRegex = /(?:from\s+(\S+)\s+import|import\s+(\S+))/g;
        let match;

        while ((match = importRegex.exec(content)) !== null) {
            const importName = match[1] || match[2];
            if (importName && !imports.includes(importName)) {
                imports.push(importName);
            }
        }

        return imports;
    }

    /**
     * Generate complete traceability matrix
     */
    generateMatrix(pages, services) {
        // Define known database schemas
        const databaseSchemas = {
            postgresql: [
                'workflows', 'workflow_executions', 'workflow_steps',
                'data_sources', 'data_lineage', 'quality_checks',
                'migration_jobs', 'migration_logs', 'system_config',
                'user_preferences', 'audit_logs', 'performance_metrics'
            ],
            neo4j: [
                'DataNode', 'ProcessNode', 'SystemNode', 'RelationshipEdge',
                'DataLineage', 'ProcessFlow', 'Dependencies', 'Impacts'
            ]
        };

        // Create comprehensive mapping
        const matrix = {
            overview: {
                totalPages: pages.length,
                totalServices: services.length,
                totalComponents: this.getAllUniqueComponents(pages),
                totalDatabaseTables: Object.values(databaseSchemas).flat().length
            },
            detailed_mapping: {},
            service_endpoints: {},
            database_schemas: databaseSchemas,
            error_tracking: this.generateErrorTrackingMatrix()
        };

        // Map each page to its complete dependency chain
        pages.forEach(page => {
            matrix.detailed_mapping[page.name] = {
                file: page.file,
                path: page.path,
                ui_components: page.components,
                imported_modules: page.imports,
                connected_services: this.mapPageToServices(page, services),
                database_tables: this.mapPageToDatabase(page, services, databaseSchemas),
                potential_errors: this.identifyPotentialErrors(page)
            };
        });

        // Map service endpoints
        services.forEach(service => {
            matrix.service_endpoints[service.name] = {
                file: service.file,
                endpoints: service.endpoints,
                models: service.models,
                dependencies: service.dependencies
            };
        });

        return matrix;
    }

    /**
     * Get all unique components across pages
     */
    getAllUniqueComponents(pages) {
        const allComponents = new Set();
        pages.forEach(page => {
            page.components.forEach(comp => allComponents.add(comp));
        });
        return Array.from(allComponents);
    }

    /**
     * Map page to connected services
     */
    mapPageToServices(page, services) {
        const connectedServices = [];
        
        // Direct service references
        page.services.forEach(serviceName => {
            const matchingService = services.find(s => 
                s.name.includes(serviceName) || serviceName.includes(s.name)
            );
            if (matchingService) {
                connectedServices.push({
                    service: matchingService.name,
                    endpoints: matchingService.endpoints,
                    connection_type: 'direct_api_call'
                });
            }
        });

        // Inferred connections based on page functionality
        const pageTypeConnections = {
            'WorkflowManager': ['main', 'advanced_migration_engine'],
            'DataMigration': ['advanced_migration_engine', 'plm_xml_data_service'],
            'QualityMonitor': ['soda_quality_service'],
            'Analytics': ['analytics_storage_service'],
            'SystemSettings': ['main'],
            'XMLMapper': ['plm_xml_data_service'],
            'GraphExplorer': ['code_graph_service']
        };

        if (pageTypeConnections[page.name]) {
            pageTypeConnections[page.name].forEach(serviceName => {
                const service = services.find(s => s.name.includes(serviceName));
                if (service && !connectedServices.find(cs => cs.service === service.name)) {
                    connectedServices.push({
                        service: service.name,
                        endpoints: service.endpoints,
                        connection_type: 'inferred_functionality'
                    });
                }
            });
        }

        return connectedServices;
    }

    /**
     * Map page to database tables
     */
    mapPageToDatabase(page, services, databaseSchemas) {
        const dbTables = [];
        
        // Map through connected services
        const connectedServices = this.mapPageToServices(page, services);
        connectedServices.forEach(conn => {
            const service = services.find(s => s.name === conn.service);
            if (service && service.models) {
                service.models.forEach(model => {
                    dbTables.push({
                        table: model,
                        database: 'postgresql', // Default
                        via_service: service.name
                    });
                });
            }
        });

        // Add inferred database connections
        const pageDBMappings = {
            'WorkflowManager': ['workflows', 'workflow_executions', 'workflow_steps'],
            'DataMigration': ['migration_jobs', 'migration_logs', 'data_sources'],
            'QualityMonitor': ['quality_checks', 'performance_metrics'],
            'Analytics': ['performance_metrics', 'audit_logs'],
            'SystemSettings': ['system_config', 'user_preferences']
        };

        if (pageDBMappings[page.name]) {
            pageDBMappings[page.name].forEach(table => {
                if (!dbTables.find(db => db.table === table)) {
                    dbTables.push({
                        table: table,
                        database: 'postgresql',
                        via_service: 'inferred'
                    });
                }
            });
        }

        return dbTables;
    }

    /**
     * Identify potential errors for each page
     */
    identifyPotentialErrors(page) {
        const potentialErrors = [];

        // Network connection errors
        if (page.services.length > 0) {
            potentialErrors.push({
                type: 'network',
                description: 'API connection failures',
                services: page.services
            });
        }

        // Component loading errors
        if (page.components.length > 0) {
            potentialErrors.push({
                type: 'component',
                description: 'Component rendering failures',
                components: page.components
            });
        }

        // Import resolution errors
        if (page.imports.length > 0) {
            potentialErrors.push({
                type: 'import', 
                description: 'Module resolution failures',
                imports: page.imports
            });
        }

        return potentialErrors;
    }

    /**
     * Generate error tracking matrix
     */
    generateErrorTrackingMatrix() {
        return {
            error_types: {
                network: {
                    description: 'API connection failures, CORS issues, timeout errors',
                    common_causes: ['Backend service down', 'Wrong port', 'CORS misconfiguration'],
                    monitoring: ['Check service health endpoints', 'Verify network connectivity']
                },
                import: {
                    description: 'Module resolution failures, missing dependencies',
                    common_causes: ['File path incorrect', 'Module not installed', 'Case sensitivity'],
                    monitoring: ['Import validation scripts', 'Build process checks']
                },
                component: {
                    description: 'React component errors, rendering failures',
                    common_causes: ['Props mismatch', 'State errors', 'Lifecycle issues'],
                    monitoring: ['Error boundaries', 'Console monitoring']
                },
                database: {
                    description: 'SQL errors, connection failures, data validation',
                    common_causes: ['Connection string wrong', 'Schema mismatch', 'Query errors'],
                    monitoring: ['Database health checks', 'Query performance monitoring']
                }
            },
            validation_scripts: [
                'comprehensive-error-tracker.js',
                'error-validator.js', 
                'network-health-checker.js',
                'component-validator.js'
            ]
        };
    }
}

// Main execution function
async function generateCompleteTraceabilityMatrix() {
    const generator = new TraceabilityMatrixGenerator();
    const srcDir = path.join(__dirname, 'src');
    const backendDir = path.join(__dirname, '..', 'python_backend');

    console.log('🔍 Scanning frontend pages and components...');
    const pages = await generator.scanPages(srcDir);
    
    console.log('🔍 Scanning Python backend services...');
    const services = await generator.scanPythonServices(backendDir);
    
    console.log('🔗 Generating complete traceability matrix...');
    const matrix = generator.generateMatrix(pages, services);

    // Save the complete matrix
    const matrixPath = path.join(__dirname, 'COMPLETE_TRACEABILITY_MATRIX.json');
    fs.writeFileSync(matrixPath, JSON.stringify(matrix, null, 2));

    console.log('✅ Complete Traceability Matrix Generated!');
    console.log(`📊 Found: ${matrix.overview.totalPages} pages, ${matrix.overview.totalServices} services`);
    console.log(`📁 Saved to: ${matrixPath}`);

    // Generate summary report
    const summaryReport = {
        timestamp: new Date().toISOString(),
        summary: matrix.overview,
        pages: Object.keys(matrix.detailed_mapping),
        services: Object.keys(matrix.service_endpoints),
        critical_paths: generator.identifyCriticalPaths(matrix),
        recommendations: generator.generateRecommendations(matrix)
    };

    const summaryPath = path.join(__dirname, 'TRACEABILITY_SUMMARY.json');
    fs.writeFileSync(summaryPath, JSON.stringify(summaryReport, null, 2));

    return { matrix, summaryReport };
}

// Add critical path identification
TraceabilityMatrixGenerator.prototype.identifyCriticalPaths = function(matrix) {
    return {
        high_traffic_pages: ['WorkflowManager', 'DataMigration', 'SystemSettings'],
        critical_services: ['main', 'advanced_migration_engine', 'soda_quality_service'],
        core_components: ['WorkflowDetailsDialog', 'SystemConfigurationService', 'AgenticOrchestrationService'],
        essential_databases: ['workflows', 'migration_jobs', 'system_config']
    };
};

// Add recommendations
TraceabilityMatrixGenerator.prototype.generateRecommendations = function(matrix) {
    return [
        'Implement error boundaries for all page components',
        'Add health check endpoints for all backend services',
        'Create automated testing for critical user paths',
        'Monitor database connection pools and query performance',
        'Set up comprehensive logging for error tracking',
        'Implement circuit breakers for external service calls'
    ];
};

// Run if called directly
if (import.meta.url === `file://${process.argv[1]}`) {
    generateCompleteTraceabilityMatrix();
}

export { TraceabilityMatrixGenerator, generateCompleteTraceabilityMatrix };
