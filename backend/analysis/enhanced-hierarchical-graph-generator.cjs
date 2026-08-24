#!/usr/bin/env node

/**
 * 🌳 ENHANCED HIERARCHICAL TRACEABILITY GRAPH GENERATOR
 * 
 * Creates expandable/collapsible directed graphs with hierarchical relationships:
 * Pages → Functional Capabilities → Children Files → UI/UX Features → Python Services → Schema
 */

const fs = require('fs');
const path = require('path');

console.log('🌳 ENHANCED HIERARCHICAL TRACEABILITY GRAPH GENERATOR');
console.log('='.repeat(60));

class HierarchicalGraphGenerator {
    constructor() {
        this.nodes = new Map();
        this.edges = [];
        this.nodeId = 0;
        this.hierarchy = {
            pages: new Map(),
            capabilities: new Map(),
            files: new Map(),
            uiFeatures: new Map(),
            services: new Map(),
            schemas: new Map()
        };
        this.impactGraph = new Map(); // For impact analysis
        this.centralHub = null; // Central landing page node
    }

    // Generate unique node ID
    getNodeId(label, type) {
        const key = `${type}:${label}`;
        if (!this.nodes.has(key)) {
            this.nodeId++;
            this.nodes.set(key, {
                id: this.nodeId,
                label: label,
                type: type,
                group: this.getGroupByType(type),
                level: this.getLevelByType(type),
                size: this.getSizeByType(type),
                color: this.getColorByType(type),
                expandable: this.isExpandable(type),
                expanded: type === 'page', // Pages start expanded
                children: [],
                parent: null
            });
        }
        return this.nodes.get(key);
    }

    getLevelByType(type) {
        const levels = {
            'central_hub': 0,        // Central landing page
            'page': 1,
            'frontend_file': 2,
            'component': 3,
            'service': 4,
            'method': 5,
            'api_endpoint': 6,
            'backend_file': 7,
            'database_schema': 8
        };
        return levels[type] || 9;
    }

    getGroupByType(type) {
        const groups = {
            'central_hub': 0,
            'page': 1,
            'frontend_file': 2,
            'component': 3,
            'service': 4,
            'method': 5,
            'api_endpoint': 6,
            'backend_file': 7,
            'database_schema': 8
        };
        return groups[type] || 9;
    }

    getSizeByType(type) {
        const sizes = {
            'central_hub': 35,
            'page': 25,
            'frontend_file': 18,
            'component': 15,
            'service': 20,
            'method': 12,
            'api_endpoint': 16,
            'backend_file': 18,
            'database_schema': 14
        };
        return sizes[type] || 10;
    }

    getColorByType(type) {
        const colors = {
            'central_hub': '#e74c3c',     // Red - Central hub
            'page': '#3498db',            // Blue - Pages
            'frontend_file': '#2ecc71',   // Green - Frontend files
            'component': '#f39c12',       // Orange - Components
            'service': '#9b59b6',         // Purple - Services
            'method': '#1abc9c',          // Teal - Methods
            'api_endpoint': '#e67e22',    // Dark orange - API endpoints
            'backend_file': '#34495e',    // Dark gray - Backend files
            'database_schema': '#95a5a6'  // Gray - Database schema
        };
        return colors[type] || '#bdc3c7';
    }

    isExpandable(type) {
        return ['central_hub', 'page', 'frontend_file', 'component', 'service', 'backend_file'].includes(type);
    }

    // Add hierarchical edge with impact tracking
    addHierarchicalEdge(parentLabel, parentType, childLabel, childType, relationshipType = 'contains') {
        const parent = this.getNodeId(parentLabel, parentType);
        const child = this.getNodeId(childLabel, childType);
        
        // Set parent-child relationship
        child.parent = parent.id;
        parent.children.push(child.id);
        
        // Add to impact graph for analysis
        if (!this.impactGraph.has(parent.id)) {
            this.impactGraph.set(parent.id, { dependencies: [], dependents: [] });
        }
        if (!this.impactGraph.has(child.id)) {
            this.impactGraph.set(child.id, { dependencies: [], dependents: [] });
        }
        
        this.impactGraph.get(parent.id).dependents.push(child.id);
        this.impactGraph.get(child.id).dependencies.push(parent.id);
        
        this.edges.push({
            source: parent.id,
            target: child.id,
            type: relationshipType,
            hierarchical: true,
            weight: this.getWeightByRelationType(relationshipType)
        });
    }

    // Add cross-reference edge (non-hierarchical)
    addCrossReferenceEdge(sourceLabel, sourceType, targetLabel, targetType, relationshipType = 'uses') {
        const source = this.getNodeId(sourceLabel, sourceType);
        const target = this.getNodeId(targetLabel, targetType);
        
        // Add to impact graph
        if (!this.impactGraph.has(source.id)) {
            this.impactGraph.set(source.id, { dependencies: [], dependents: [] });
        }
        if (!this.impactGraph.has(target.id)) {
            this.impactGraph.set(target.id, { dependencies: [], dependents: [] });
        }
        
        this.impactGraph.get(source.id).dependents.push(target.id);
        this.impactGraph.get(target.id).dependencies.push(source.id);
        
        this.edges.push({
            source: source.id,
            target: target.id,
            type: relationshipType,
            hierarchical: false,
            weight: this.getWeightByRelationType(relationshipType)
        });
    }

    getWeightByRelationType(type) {
        const weights = {
            'contains': 5,
            'uses': 3,
            'connects_to': 4,
            'implements': 3,
            'depends_on': 2
        };
        return weights[type] || 1;
    }

    // Generate hierarchical structure with central hub
    generateHierarchy() {
        console.log('🔨 Building hierarchical structure with central hub...');
        
        // Level 0: Central Hub (Landing Page)
        this.createCentralHub();
        
        // Level 1: Pages
        this.createPages();
        
        // Level 2: Frontend Files
        this.createFrontendFiles();
        
        // Level 3: Components
        this.createComponents();
        
        // Level 4: Services
        this.createServices();
        
        // Level 5: Methods
        this.createMethods();
        
        // Level 6: API Endpoints
        this.createAPIEndpoints();
        
        // Level 7: Backend Files
        this.createBackendFiles();
        
        // Level 8: Database Schema
        this.createDatabaseSchema();
        
        // Add cross-reference relationships
        this.createCrossReferences();
    }

    createCentralHub() {
        console.log('🏠 Creating central hub...');
        
        const centralHub = this.getNodeId('GraphTrace System Hub', 'central_hub');
        centralHub.expanded = true;
        centralHub.isHub = true;
        this.centralHub = centralHub;
        
        this.hierarchy.pages.set('GraphTrace System Hub', {
            name: 'GraphTrace System Hub',
            description: 'Central navigation hub for the entire GraphTrace system',
            node: centralHub,
            type: 'central_hub'
        });
    }

    createPages() {
        console.log('📄 Creating pages...');
        
        const pages = [
            {
                name: 'Landing Page',
                route: '/',
                file: 'fluent-landing-page.jsx',
                description: 'Main entry point with system overview'
            },
            {
                name: 'Main Dashboard',
                route: '/dashboard',
                file: 'fluent-main-dashboard.jsx',
                description: 'Primary dashboard with metrics and analytics'
            },
            {
                name: 'Graph Explorer',
                route: '/graph',
                file: 'fluent-graph-explorer-final.jsx',
                description: 'Interactive graph visualization and exploration'
            },
            {
                name: 'PLM Orchestrator',
                route: '/orchestrator',
                file: 'PLMOrchestratorPage.jsx',
                description: 'Workflow orchestration and agent management'
            },
            {
                name: 'AI ETL Pipeline',
                route: '/ai-etl',
                file: 'AIETLPipelinePage.jsx',
                description: 'AI-powered ETL pipeline configuration'
            },
            {
                name: 'Data Mapping',
                route: '/data-mapping',
                file: 'fluent-data-mapping-page.jsx',
                description: 'Data mapping and transformation configuration'
            },
            {
                name: 'System Settings',
                route: '/settings',
                file: 'ModularSystemSettingsPage.jsx',
                description: 'System configuration and settings management'
            },
            {
                name: 'Monitoring Dashboard',
                route: '/monitoring',
                file: 'fluent-monitoring-page.jsx',
                description: 'System monitoring and health tracking'
            }
        ];

        pages.forEach(page => {
            const pageNode = this.getNodeId(page.name, 'page');
            pageNode.route = page.route;
            pageNode.file = page.file;
            
            this.hierarchy.pages.set(page.name, {
                ...page,
                node: pageNode
            });
            
            // Connect to central hub
            this.addHierarchicalEdge('GraphTrace System Hub', 'central_hub', page.name, 'page', 'navigates_to');
        });
    }

    createFrontendFiles() {
        console.log('📁 Creating frontend files...');
        
        const frontendFiles = [
            { name: 'App.jsx', page: 'Landing Page', components: ['SideMenu', 'ErrorBoundary'] },
            { name: 'fluent-landing-page.jsx', page: 'Landing Page', components: ['LandingHeader', 'FeatureCards', 'ActionButtons'] },
            { name: 'fluent-main-dashboard.jsx', page: 'Main Dashboard', components: ['DashboardContent', 'AnalyticsContent', 'PageHeader'] },
            { name: 'fluent-graph-explorer-final.jsx', page: 'Graph Explorer', components: ['GraphCanvas', 'GraphControls', 'GraphChatPanel'] },
            { name: 'PLMOrchestratorPage.jsx', page: 'PLM Orchestrator', components: ['WorkflowDesigner', 'EnhancedAgentCanvas', 'StateMachineWorkflowEngine'] },
            { name: 'AIETLPipelinePage.jsx', page: 'AI ETL Pipeline', components: ['ETLPipelineBuilder', 'DataFlowCanvas', 'QualityDashboard'] },
            { name: 'fluent-data-mapping-page.jsx', page: 'Data Mapping', components: ['MappingCanvas', 'SchemaViewer', 'TransformationRules'] },
            { name: 'ModularSystemSettingsPage.jsx', page: 'System Settings', components: ['ConfigurationPanel', 'DataSourceDialog', 'ServiceStatus'] },
            { name: 'fluent-monitoring-page.jsx', page: 'Monitoring Dashboard', components: ['MetricsOverview', 'AlertsPanel', 'PerformanceCharts'] }
        ];

        frontendFiles.forEach(file => {
            const fileNode = this.getNodeId(file.name, 'frontend_file');
            fileNode.components = file.components;
            
            // Connect to page
            this.addHierarchicalEdge(file.page, 'page', file.name, 'frontend_file', 'contains');
        });
    }

    createComponents() {
        console.log('🧩 Creating components...');
        
        const components = {
            'SideMenu': { file: 'SideMenu.jsx', methods: ['handleNavigation', 'toggleCollapse'], apis: ['/api/navigation'] },
            'ErrorBoundary': { file: 'ErrorBoundary.jsx', methods: ['componentDidCatch', 'render'], apis: ['/api/error-log'] },
            'LandingHeader': { file: 'LandingHeader.jsx', methods: ['renderActions', 'handleGetStarted'], apis: ['/api/health'] },
            'FeatureCards': { file: 'FeatureCards.jsx', methods: ['renderCard', 'handleCardClick'], apis: ['/api/features'] },
            'ActionButtons': { file: 'ActionButtons.jsx', methods: ['handleAction', 'validatePermissions'], apis: ['/api/actions'] },
            'DashboardContent': { file: 'DashboardContent.jsx', methods: ['loadMetrics', 'refreshData'], apis: ['/api/dashboard', '/api/metrics'] },
            'AnalyticsContent': { file: 'AnalyticsContent.jsx', methods: ['processAnalytics', 'renderCharts'], apis: ['/api/analytics'] },
            'PageHeader': { file: 'PageHeader.jsx', methods: ['renderTitle', 'renderActions'], apis: [] },
            'GraphCanvas': { file: 'GraphCanvas.jsx', methods: ['renderGraph', 'handleNodeClick'], apis: ['/api/graph-data'] },
            'GraphControls': { file: 'GraphControls.jsx', methods: ['applyFilter', 'resetView'], apis: ['/api/graph-filters'] },
            'GraphChatPanel': { file: 'GraphChatPanel.jsx', methods: ['sendMessage', 'processResponse'], apis: ['/api/chat'] },
            'WorkflowDesigner': { file: 'WorkflowDesigner.jsx', methods: ['createWorkflow', 'saveWorkflow'], apis: ['/api/workflows'] },
            'EnhancedAgentCanvas': { file: 'EnhancedAgentCanvas.jsx', methods: ['renderAgent', 'connectAgents'], apis: ['/api/agents'] },
            'StateMachineWorkflowEngine': { file: 'StateMachineWorkflowEngine.jsx', methods: ['executeWorkflow', 'validateStates'], apis: ['/api/workflow-execution'] },
            'ETLPipelineBuilder': { file: 'ETLPipelineBuilder.jsx', methods: ['buildPipeline', 'testPipeline'], apis: ['/api/etl-pipeline'] },
            'DataFlowCanvas': { file: 'DataFlowCanvas.jsx', methods: ['renderFlow', 'validateFlow'], apis: ['/api/data-flow'] },
            'QualityDashboard': { file: 'QualityDashboard.jsx', methods: ['runQualityCheck', 'displayResults'], apis: ['/api/quality'] },
            'MappingCanvas': { file: 'MappingCanvas.jsx', methods: ['createMapping', 'validateMapping'], apis: ['/api/data-mapping'] },
            'SchemaViewer': { file: 'SchemaViewer.jsx', methods: ['loadSchema', 'renderSchema'], apis: ['/api/schema'] },
            'TransformationRules': { file: 'TransformationRules.jsx', methods: ['createRule', 'applyRule'], apis: ['/api/transformation'] },
            'ConfigurationPanel': { file: 'ConfigurationPanel.jsx', methods: ['loadConfig', 'saveConfig'], apis: ['/api/config'] },
            'DataSourceDialog': { file: 'DataSourceDialog.jsx', methods: ['testConnection', 'saveDataSource'], apis: ['/api/data-sources'] },
            'ServiceStatus': { file: 'ServiceStatus.jsx', methods: ['checkHealth', 'restartService'], apis: ['/api/services/health'] },
            'MetricsOverview': { file: 'MetricsOverview.jsx', methods: ['loadMetrics', 'refreshMetrics'], apis: ['/api/monitoring/metrics'] },
            'AlertsPanel': { file: 'AlertsPanel.jsx', methods: ['loadAlerts', 'acknowledgeAlert'], apis: ['/api/monitoring/alerts'] },
            'PerformanceCharts': { file: 'PerformanceCharts.jsx', methods: ['renderChart', 'updateData'], apis: ['/api/monitoring/performance'] }
        };

        Object.entries(components).forEach(([componentName, componentData]) => {
            const componentNode = this.getNodeId(componentName, 'component');
            componentNode.file = componentData.file;
            componentNode.methods = componentData.methods;
            componentNode.apis = componentData.apis;
            
            // Find the frontend file that contains this component
            const frontendFileNames = Array.from(this.nodes.keys())
                .filter(key => key.startsWith('frontend_file:'))
                .map(key => key.replace('frontend_file:', ''));
            
            frontendFileNames.forEach(fileName => {
                const fileNode = this.nodes.get(`frontend_file:${fileName}`);
                if (fileNode && fileNode.components && fileNode.components.includes(componentName)) {
                    this.addHierarchicalEdge(fileName, 'frontend_file', componentName, 'component', 'contains');
                }
            });
        });
    }

    createServices() {
        console.log('⚙️ Creating services...');
        
        const services = [
            'SystemConfig', 'NotificationService', 'DashboardDataUtils', 'GraphExplorerService',
            'WorkflowService', 'AgenticETLService', 'DataMappingService', 'ConfigurationService',
            'MonitoringService', 'AlertService', 'ValidationService', 'TransformationService'
        ];

        services.forEach(serviceName => {
            const serviceNode = this.getNodeId(serviceName, 'service');
            
            // Connect services to components that use them
            const componentNames = Array.from(this.nodes.keys())
                .filter(key => key.startsWith('component:'))
                .map(key => key.replace('component:', ''));
            
            componentNames.forEach(componentName => {
                const serviceMap = {
                    'SystemConfig': ['LandingHeader', 'DashboardContent'],
                    'NotificationService': ['ErrorBoundary', 'ActionButtons'],
                    'DashboardDataUtils': ['DashboardContent', 'AnalyticsContent'],
                    'GraphExplorerService': ['GraphCanvas', 'GraphControls'],
                    'WorkflowService': ['WorkflowDesigner', 'StateMachineWorkflowEngine'],
                    'AgenticETLService': ['EnhancedAgentCanvas', 'ETLPipelineBuilder'],
                    'DataMappingService': ['MappingCanvas', 'TransformationRules'],
                    'ConfigurationService': ['ConfigurationPanel', 'DataSourceDialog'],
                    'MonitoringService': ['MetricsOverview', 'ServiceStatus'],
                    'AlertService': ['AlertsPanel'],
                    'ValidationService': ['QualityDashboard', 'SchemaViewer'],
                    'TransformationService': ['TransformationRules', 'DataFlowCanvas']
                };
                
                if (serviceMap[serviceName] && serviceMap[serviceName].includes(componentName)) {
                    this.addCrossReferenceEdge(componentName, 'component', serviceName, 'service', 'uses');
                }
            });
        });
    }

    createMethods() {
        console.log('🔧 Creating methods...');
        
        const methodsMap = {
            'handleNavigation': 'SideMenu',
            'toggleCollapse': 'SideMenu',
            'componentDidCatch': 'ErrorBoundary',
            'renderActions': 'LandingHeader',
            'handleGetStarted': 'LandingHeader',
            'renderCard': 'FeatureCards',
            'handleCardClick': 'FeatureCards',
            'handleAction': 'ActionButtons',
            'validatePermissions': 'ActionButtons',
            'loadMetrics': 'DashboardContent',
            'refreshData': 'DashboardContent',
            'processAnalytics': 'AnalyticsContent',
            'renderCharts': 'AnalyticsContent',
            'renderGraph': 'GraphCanvas',
            'handleNodeClick': 'GraphCanvas',
            'applyFilter': 'GraphControls',
            'resetView': 'GraphControls',
            'sendMessage': 'GraphChatPanel',
            'processResponse': 'GraphChatPanel',
            'createWorkflow': 'WorkflowDesigner',
            'saveWorkflow': 'WorkflowDesigner',
            'renderAgent': 'EnhancedAgentCanvas',
            'connectAgents': 'EnhancedAgentCanvas',
            'executeWorkflow': 'StateMachineWorkflowEngine',
            'validateStates': 'StateMachineWorkflowEngine',
            'buildPipeline': 'ETLPipelineBuilder',
            'testPipeline': 'ETLPipelineBuilder',
            'renderFlow': 'DataFlowCanvas',
            'validateFlow': 'DataFlowCanvas',
            'runQualityCheck': 'QualityDashboard',
            'displayResults': 'QualityDashboard',
            'createMapping': 'MappingCanvas',
            'validateMapping': 'MappingCanvas',
            'loadSchema': 'SchemaViewer',
            'renderSchema': 'SchemaViewer',
            'createRule': 'TransformationRules',
            'applyRule': 'TransformationRules',
            'loadConfig': 'ConfigurationPanel',
            'saveConfig': 'ConfigurationPanel',
            'testConnection': 'DataSourceDialog',
            'saveDataSource': 'DataSourceDialog',
            'checkHealth': 'ServiceStatus',
            'restartService': 'ServiceStatus',
            'refreshMetrics': 'MetricsOverview',
            'loadAlerts': 'AlertsPanel',
            'acknowledgeAlert': 'AlertsPanel',
            'renderChart': 'PerformanceCharts',
            'updateData': 'PerformanceCharts'
        };

        Object.entries(methodsMap).forEach(([methodName, componentName]) => {
            const methodNode = this.getNodeId(methodName, 'method');
            this.addHierarchicalEdge(componentName, 'component', methodName, 'method', 'contains');
        });
    }

    createAPIEndpoints() {
        console.log('🔌 Creating API endpoints...');
        
        const endpoints = [
            '/api/health', '/api/navigation', '/api/error-log', '/api/features', '/api/actions',
            '/api/dashboard', '/api/metrics', '/api/analytics', '/api/graph-data', '/api/graph-filters',
            '/api/chat', '/api/workflows', '/api/agents', '/api/workflow-execution', '/api/etl-pipeline',
            '/api/data-flow', '/api/quality', '/api/data-mapping', '/api/schema', '/api/transformation',
            '/api/config', '/api/data-sources', '/api/services/health', '/api/monitoring/metrics',
            '/api/monitoring/alerts', '/api/monitoring/performance'
        ];

        endpoints.forEach(endpoint => {
            const endpointNode = this.getNodeId(endpoint, 'api_endpoint');
            
            // Connect to methods that call these endpoints
            const methodEndpointMap = {
                '/api/health': ['handleGetStarted', 'checkHealth'],
                '/api/navigation': ['handleNavigation'],
                '/api/error-log': ['componentDidCatch'],
                '/api/features': ['renderCard'],
                '/api/actions': ['handleAction'],
                '/api/dashboard': ['loadMetrics'],
                '/api/metrics': ['refreshData', 'refreshMetrics'],
                '/api/analytics': ['processAnalytics'],
                '/api/graph-data': ['renderGraph'],
                '/api/graph-filters': ['applyFilter'],
                '/api/chat': ['sendMessage', 'processResponse'],
                '/api/workflows': ['createWorkflow', 'saveWorkflow'],
                '/api/agents': ['renderAgent', 'connectAgents'],
                '/api/workflow-execution': ['executeWorkflow'],
                '/api/etl-pipeline': ['buildPipeline', 'testPipeline'],
                '/api/data-flow': ['renderFlow', 'validateFlow'],
                '/api/quality': ['runQualityCheck'],
                '/api/data-mapping': ['createMapping', 'validateMapping'],
                '/api/schema': ['loadSchema', 'renderSchema'],
                '/api/transformation': ['createRule', 'applyRule'],
                '/api/config': ['loadConfig', 'saveConfig'],
                '/api/data-sources': ['testConnection', 'saveDataSource'],
                '/api/services/health': ['checkHealth', 'restartService'],
                '/api/monitoring/metrics': ['loadMetrics', 'refreshMetrics'],
                '/api/monitoring/alerts': ['loadAlerts', 'acknowledgeAlert'],
                '/api/monitoring/performance': ['renderChart', 'updateData']
            };
            
            if (methodEndpointMap[endpoint]) {
                methodEndpointMap[endpoint].forEach(methodName => {
                    this.addCrossReferenceEdge(methodName, 'method', endpoint, 'api_endpoint', 'calls');
                });
            }
        });
    }

    createBackendFiles() {
        console.log('🐍 Creating backend files...');
        
        const backendFiles = [
            { name: 'main.py', port: 8003, endpoints: ['/api/health', '/api/workflows', '/api/config'] },
            { name: 'soda_quality_service.py', port: 8004, endpoints: ['/api/quality'] },
            { name: 'plm_xml_data_service.py', port: 8005, endpoints: ['/api/schema', '/api/transformation'] },
            { name: 'analytics_storage_service.py', port: 8006, endpoints: ['/api/analytics', '/api/metrics'] },
            { name: 'advanced_migration_engine.py', port: 8007, endpoints: ['/api/workflow-execution'] },
            { name: 'code_graph_service.py', port: 8008, endpoints: ['/api/graph-data', '/api/graph-filters'] }
        ];

        backendFiles.forEach(file => {
            const fileNode = this.getNodeId(file.name, 'backend_file');
            fileNode.port = file.port;
            fileNode.endpoints = file.endpoints;
            
            // Connect to API endpoints
            file.endpoints.forEach(endpoint => {
                this.addHierarchicalEdge(file.name, 'backend_file', endpoint, 'api_endpoint', 'implements');
            });
        });
    }

    createDatabaseSchema() {
        console.log('🗄️ Creating database schema...');
        
        const schemas = {
            'workflows': 'main.py',
            'data_sources': 'main.py',
            'audit_logs': 'main.py',
            'quality_rules': 'soda_quality_service.py',
            'quality_reports': 'soda_quality_service.py',
            'plm_data': 'plm_xml_data_service.py',
            'transformations': 'plm_xml_data_service.py',
            'analytics_data': 'analytics_storage_service.py',
            'metrics': 'analytics_storage_service.py',
            'migration_jobs': 'advanced_migration_engine.py',
            'code_graph': 'code_graph_service.py'
        };

        Object.entries(schemas).forEach(([schemaName, backendFile]) => {
            const schemaNode = this.getNodeId(schemaName, 'database_schema');
            this.addHierarchicalEdge(backendFile, 'backend_file', schemaName, 'database_schema', 'connects_to');
        });
    }

    createCrossReferences() {
        console.log('🔗 Creating cross-references...');
        
        // Add additional cross-reference relationships
        // Frontend to Backend connections
        this.addCrossReferenceEdge('DashboardContent', 'component', 'main.py', 'backend_file', 'communicates_with');
        this.addCrossReferenceEdge('GraphCanvas', 'component', 'code_graph_service.py', 'backend_file', 'communicates_with');
        this.addCrossReferenceEdge('QualityDashboard', 'component', 'soda_quality_service.py', 'backend_file', 'communicates_with');
        this.addCrossReferenceEdge('MappingCanvas', 'component', 'plm_xml_data_service.py', 'backend_file', 'communicates_with');
        this.addCrossReferenceEdge('WorkflowDesigner', 'component', 'main.py', 'backend_file', 'communicates_with');
        this.addCrossReferenceEdge('EnhancedAgentCanvas', 'component', 'advanced_migration_engine.py', 'backend_file', 'communicates_with');
    }

    // Impact Analysis Algorithm
    performImpactAnalysis(nodeId, depth = 3) {
        const visited = new Set();
        const impactedNodes = new Set();
        const impactLevels = new Map();
        
        const traverse = (currentNodeId, currentDepth, direction = 'both') => {
            if (currentDepth > depth || visited.has(currentNodeId)) return;
            
            visited.add(currentNodeId);
            impactedNodes.add(currentNodeId);
            impactLevels.set(currentNodeId, currentDepth);
            
            const impactData = this.impactGraph.get(currentNodeId);
            if (impactData) {
                // Traverse dependencies (what this node depends on)
                if (direction === 'both' || direction === 'dependencies') {
                    impactData.dependencies.forEach(depId => {
                        traverse(depId, currentDepth + 1, 'dependencies');
                    });
                }
                
                // Traverse dependents (what depends on this node)
                if (direction === 'both' || direction === 'dependents') {
                    impactData.dependents.forEach(depId => {
                        traverse(depId, currentDepth + 1, 'dependents');
                    });
                }
            }
        };
        
        traverse(nodeId, 0);
        
        return {
            impactedNodes: Array.from(impactedNodes),
            impactLevels: Object.fromEntries(impactLevels),
            totalImpacted: impactedNodes.size,
            riskLevel: this.calculateRiskLevel(impactedNodes.size)
        };
    }
    
    calculateRiskLevel(impactedCount) {
        if (impactedCount <= 5) return 'LOW';
        if (impactedCount <= 15) return 'MEDIUM';
        if (impactedCount <= 30) return 'HIGH';
        return 'CRITICAL';
    }
    
    // Fix relationship issues by ensuring all connections are valid
    validateAndFixRelationships() {
        console.log('🔧 Validating and fixing relationships...');
        
        // Remove edges with missing nodes
        this.edges = this.edges.filter(edge => {
            const sourceExists = Array.from(this.nodes.values()).some(node => node.id === edge.source);
            const targetExists = Array.from(this.nodes.values()).some(node => node.id === edge.target);
            
            if (!sourceExists || !targetExists) {
                console.log(`Removing invalid edge: ${edge.source} -> ${edge.target}`);
                return false;
            }
            return true;
        });
        
        // Ensure all nodes have proper parent-child relationships
        this.nodes.forEach(node => {
            if (node.children) {
                node.children = node.children.filter(childId => 
                    Array.from(this.nodes.values()).some(n => n.id === childId)
                );
            }
        });
        
        console.log(`✅ Validated ${this.edges.length} edges and ${this.nodes.size} nodes`);
    }

    // Generate enhanced graph data with hierarchy and impact analysis
    generateEnhancedGraphData() {
        // Validate and fix relationships first
        this.validateAndFixRelationships();
        
        const nodesArray = Array.from(this.nodes.values());
        
        return {
            directed: true,
            multigraph: false,
            hierarchical: true,
            hasImpactAnalysis: true,
            graph: {
                name: "GraphTrace Enhanced Hierarchical Traceability with Impact Analysis",
                description: "Interactive expandable graph: Central Hub → Pages → Frontend Files → Components → Services → Methods → API Endpoints → Backend Files → Schema"
            },
            nodes: nodesArray,
            links: this.edges,
            hierarchy: {
                levels: [
                    { level: 0, name: 'Central Hub', color: '#e74c3c', description: 'Main system navigation hub' },
                    { level: 1, name: 'Pages', color: '#3498db', description: 'Application pages and routes' },
                    { level: 2, name: 'Frontend Files', color: '#2ecc71', description: 'React component files' },
                    { level: 3, name: 'Components', color: '#f39c12', description: 'UI components and widgets' },
                    { level: 4, name: 'Services', color: '#9b59b6', description: 'Frontend service layer' },
                    { level: 5, name: 'Methods', color: '#1abc9c', description: 'Component methods and functions' },
                    { level: 6, name: 'API Endpoints', color: '#e67e22', description: 'REST API endpoints' },
                    { level: 7, name: 'Backend Files', color: '#34495e', description: 'Python FastAPI services' },
                    { level: 8, name: 'Database Schema', color: '#95a5a6', description: 'Database tables and structures' }
                ]
            },
            centralHub: this.centralHub ? this.centralHub.id : null,
            stats: {
                totalNodes: nodesArray.length,
                totalEdges: this.edges.length,
                hierarchicalEdges: this.edges.filter(e => e.hierarchical).length,
                crossReferenceEdges: this.edges.filter(e => !e.hierarchical).length,
                nodesByLevel: this.getNodesByLevel(nodesArray)
            }
        };
    }
    
    getNodesByLevel(nodes) {
        const byLevel = {};
        nodes.forEach(node => {
            if (!byLevel[node.level]) byLevel[node.level] = 0;
            byLevel[node.level]++;
        });
        return byLevel;
    }

    // Generate enhanced interactive visualization with expand/collapse
    generateEnhancedVisualization(graphData) {
        return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🌳 GraphTrace Hierarchical Traceability Network</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #2c3e50 0%, #34495e 100%);
            color: white;
        }
        
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .header h1 {
            margin: 0;
            font-size: 2.5em;
            font-weight: 300;
            text-shadow: 2px 2px 4px rgba(0,0,0,0.5);
        }
        
        .controls {
            text-align: center;
            margin-bottom: 20px;
            display: flex;
            justify-content: center;
            gap: 10px;
            flex-wrap: wrap;
        }
        
        .filter-section {
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            margin-bottom: 20px;
            display: flex;
            flex-wrap: wrap;
            gap: 10px;
            align-items: center;
        }
        
        .filter-group {
            display: flex;
            flex-direction: column;
            gap: 5px;
        }
        
        .filter-label {
            font-size: 12px;
            font-weight: bold;
            opacity: 0.8;
        }
        
        .filter-buttons {
            display: flex;
            gap: 5px;
            flex-wrap: wrap;
        }
        
        .controls button, .filter-buttons button {
            padding: 8px 16px;
            border: none;
            border-radius: 20px;
            background: rgba(255,255,255,0.2);
            color: white;
            cursor: pointer;
            font-size: 12px;
            transition: all 0.3s ease;
        }
        
        .controls button:hover, .filter-buttons button:hover {
            background: rgba(255,255,255,0.3);
            transform: translateY(-2px);
        }
        
        .controls button.active, .filter-buttons button.active {
            background: #3498db;
        }
        
        .impact-analysis {
            position: fixed;
            right: 20px;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(0,0,0,0.8);
            padding: 20px;
            border-radius: 10px;
            width: 280px;
            max-height: 500px;
            overflow-y: auto;
        }
        
        .impact-result {
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 10px;
        }
        
        .risk-level {
            display: inline-block;
            padding: 4px 8px;
            border-radius: 4px;
            font-size: 11px;
            font-weight: bold;
        }
        
        .risk-low { background: #27ae60; }
        .risk-medium { background: #f39c12; }
        .risk-high { background: #e74c3c; }
        .risk-critical { background: #8e44ad; }
        
        .graph-container {
            background: rgba(255,255,255,0.1);
            border-radius: 15px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.2);
            backdrop-filter: blur(10px);
        }
        
        #graph {
            width: 100%;
            height: 700px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 10px;
            background: rgba(0,0,0,0.1);
        }
        
        .hierarchy-panel {
            position: fixed;
            left: 20px;
            top: 50%;
            transform: translateY(-50%);
            background: rgba(0,0,0,0.8);
            padding: 20px;
            border-radius: 10px;
            width: 250px;
            max-height: 500px;
            overflow-y: auto;
        }
        
        .level-info {
            margin-bottom: 15px;
            padding: 10px;
            border-radius: 8px;
            background: rgba(255,255,255,0.1);
            border-left: 4px solid;
        }
        
        .level-info h4 {
            margin: 0 0 5px 0;
            font-size: 14px;
        }
        
        .level-info p {
            margin: 0;
            font-size: 12px;
            opacity: 0.8;
        }
        
        .stats {
            margin-top: 20px;
            text-align: center;
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(120px, 1fr));
            gap: 15px;
        }
        
        .stat-item {
            text-align: center;
        }
        
        .stat-value {
            font-size: 2em;
            font-weight: bold;
            color: #3498db;
        }
        
        .stat-label {
            font-size: 0.9em;
            opacity: 0.8;
        }
        
        .node {
            stroke: #fff;
            stroke-width: 2px;
            cursor: pointer;
            transition: all 0.3s ease;
        }
        
        .node.collapsed {
            opacity: 0.6;
        }
        
        .node.expandable {
            stroke-width: 3px;
        }
        
        .node.expandable:hover {
            stroke-width: 4px;
            filter: brightness(1.2);
        }
        
        .link {
            stroke: rgba(255,255,255,0.4);
            stroke-width: 1px;
            marker-end: url(#arrowhead);
            transition: all 0.3s ease;
        }
        
        .link.hierarchical {
            stroke: rgba(52, 152, 219, 0.6);
            stroke-width: 2px;
        }
        
        .link.hidden {
            opacity: 0;
        }
        
        .node-label {
            font-size: 10px;
            fill: white;
            text-anchor: middle;
            pointer-events: none;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.8);
            font-weight: bold;
        }
        
        .expand-icon {
            font-size: 12px;
            fill: white;
            text-anchor: middle;
            pointer-events: none;
            font-weight: bold;
        }
        
        .tooltip {
            position: absolute;
            background: rgba(0,0,0,0.9);
            color: white;
            padding: 12px;
            border-radius: 8px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
            border: 1px solid rgba(255,255,255,0.2);
            max-width: 300px;
        }
        
        .breadcrumb {
            background: rgba(255,255,255,0.1);
            padding: 10px;
            border-radius: 8px;
            margin-bottom: 20px;
            font-size: 14px;
        }
        
        @media (max-width: 768px) {
            .hierarchy-panel {
                position: relative;
                left: auto;
                top: auto;
                transform: none;
                width: 100%;
                margin-bottom: 20px;
            }
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🌳 GraphTrace Hierarchical Traceability</h1>
        <p>Expandable network showing Pages → Capabilities → Files → UI Features → Services → Schema</p>
    </div>
    
    <div class="breadcrumb">
        <span id="breadcrumb-text">📍 Central Hub Active: Click nodes to expand/collapse • Double-click for impact analysis</span>
    </div>
    
    <div class="filter-section">
        <div class="filter-group">
            <div class="filter-label">View Mode:</div>
            <div class="filter-buttons">
                <button onclick="showHubView()" class="active" id="hub-btn">🏠 Hub View</button>
                <button onclick="showDirectRelationships()" id="direct-btn">🔗 Direct Only</button>
                <button onclick="showAllRelationships()" id="all-btn">🌐 All Relations</button>
            </div>
        </div>
        
        <div class="filter-group">
            <div class="filter-label">Filter by Type:</div>
            <div class="filter-buttons">
                <button onclick="filterByType('all')" class="active" id="filter-all">All Types</button>
                <button onclick="filterByType('frontend_file')" id="filter-frontend">� Frontend Files</button>
                <button onclick="filterByType('component')" id="filter-components">🧩 Components</button>
                <button onclick="filterByType('service')" id="filter-services">⚙️ Services</button>
                <button onclick="filterByType('method')" id="filter-methods">🔧 Methods</button>
                <button onclick="filterByType('api_endpoint')" id="filter-apis">🔌 API Endpoints</button>
                <button onclick="filterByType('backend_file')" id="filter-backend">� Backend Files</button>
            </div>
        </div>
        
        <div class="filter-group">
            <div class="filter-label">Hierarchy Level:</div>
            <div class="filter-buttons">
                <button onclick="showLevel(0)" id="level-0">🏠 Hub</button>
                <button onclick="showLevel(1)" id="level-1">📄 Pages</button>
                <button onclick="showLevel(2)" id="level-2">📁 Files</button>
                <button onclick="showLevel(3)" id="level-3">🧩 Components</button>
                <button onclick="showLevel(4)" id="level-4">⚙️ Services</button>
                <button onclick="showLevel(5)" id="level-5">🔧 Methods</button>
                <button onclick="showLevel(6)" id="level-6">� APIs</button>
                <button onclick="showLevel(7)" id="level-7">🐍 Backend</button>
                <button onclick="showLevel(8)" id="level-8">🗄️ Schema</button>
            </div>
        </div>
    </div>
    
    <div class="controls">
        <button onclick="expandAll()">🔽 Expand All</button>
        <button onclick="collapseAll()">🔼 Collapse All</button>
        <button onclick="focusOnHub()">🎯 Focus Hub</button>
        <button onclick="resetView()">🔄 Reset View</button>
        <button onclick="exportHierarchy()">💾 Export</button>
    </div>
    
    <div class="hierarchy-panel">
        <h3>🗂️ Hierarchy Levels</h3>
        ${graphData.hierarchy.levels.map(level => `
            <div class="level-info" style="border-left-color: ${level.color};">
                <h4>${level.level}. ${level.name}</h4>
                <p>${level.description}</p>
            </div>
        `).join('')}
    </div>
    
    <div class="graph-container">
        <svg id="graph"></svg>
    </div>
    
    <div class="stats">
        <div class="stat-item">
            <div class="stat-value" id="visible-nodes">${graphData.nodes.length}</div>
            <div class="stat-label">Visible Nodes</div>
        </div>
        <div class="stat-item">
            <div class="stat-value" id="visible-edges">${graphData.links.length}</div>
            <div class="stat-label">Visible Edges</div>
        </div>
        <div class="stat-item">
            <div class="stat-value" id="max-level">6</div>
            <div class="stat-label">Hierarchy Levels</div>
        </div>
        <div class="stat-item">
            <div class="stat-value" id="expanded-nodes">8</div>
            <div class="stat-label">Expanded Nodes</div>
        </div>
    </div>
    
    <div class="tooltip" id="tooltip"></div>

    <script>
        // Graph data
        const graphData = ${JSON.stringify(graphData, null, 2)};
        
        // Global variables
        let svg, g, simulation, nodes, links, expandedNodes = new Set(), selectedNode = null;
        let filteredData = { nodes: [], links: [] };
        let currentViewMode = 'hub';
        let currentFilter = 'all';
        let impactAnalysisActive = false;
        
        // Initialize the graph
        function initGraph() {
            const container = d3.select('#graph-container');
            if (container.empty()) {
                // Fallback to inline SVG
                svg = d3.select('#graph');
                const width = 800;
                const height = 700;
                svg.attr('width', width).attr('height', height);
            } else {
                const width = container.node().getBoundingClientRect().width;
                const height = 600;
                
                svg = container.append('svg')
                    .attr('width', width)
                    .attr('height', height);
            }
            
            // Add zoom and pan capabilities
            const zoom = d3.zoom()
                .scaleExtent([0.1, 4])
                .on('zoom', function(event) {
                    g.attr('transform', event.transform);
                });
            
            svg.call(zoom);
            
            // Create arrowhead marker
            svg.append("defs").append("marker")
                .attr("id", "arrowhead")
                .attr("viewBox", "0 -5 10 10")
                .attr("refX", 25)
                .attr("refY", 0)
                .attr("markerWidth", 6)
                .attr("markerHeight", 6)
                .attr("orient", "auto")
                .append("path")
                .attr("d", "M0,-5L10,0L0,5")
                .attr("fill", "rgba(255,255,255,0.6)");
            
            g = svg.append('g');
            
            // Initialize with central hub
            focusOnHub();
        }
        
        // Show central hub view
        function showHubView() {
            currentViewMode = 'hub';
            updateActiveButton('hub-btn', 'filter-buttons');
            focusOnHub();
        }
        
        // Show only direct relationships
        function showDirectRelationships() {
            currentViewMode = 'direct';
            updateActiveButton('direct-btn', 'filter-buttons');
            if (selectedNode) {
                showDirectRelationshipsForNode(selectedNode);
            } else {
                focusOnHub();
            }
        }
        
        // Show all relationships
        function showAllRelationships() {
            currentViewMode = 'all';
            updateActiveButton('all-btn', 'filter-buttons');
            resetView();
        }
        
        // Filter by node type
        function filterByType(type) {
            currentFilter = type;
            updateActiveButton('filter-' + type, 'filter-buttons');
            applyFilters();
        }
        
        // Show specific hierarchy level
        function showLevel(level) {
            const hubNode = graphData.nodes.find(n => n.id === 'hub_central');
            const levelNodes = graphData.nodes.filter(n => n.level <= level);
            const levelLinks = graphData.links.filter(l => 
                levelNodes.some(n => n.id === l.source) && 
                levelNodes.some(n => n.id === l.target)
            );
            
            updateGraph(levelNodes, levelLinks);
            updateActiveButton('level-' + level, 'filter-buttons');
            updateBreadcrumb(\`📍 Showing Level \${level} and below\`);
        }
        
        // Apply current filters
        function applyFilters() {
            let filtered = { nodes: [...graphData.nodes], links: [...graphData.links] };
            
            // Apply type filter
            if (currentFilter !== 'all') {
                filtered.nodes = filtered.nodes.filter(n => 
                    n.type === currentFilter || n.id === 'hub_central'
                );
                filtered.links = filtered.links.filter(l =>
                    filtered.nodes.some(n => n.id === l.source) &&
                    filtered.nodes.some(n => n.id === l.target)
                );
            }
            
            updateGraph(filtered.nodes, filtered.links);
        }
        
        // Focus on central hub
        function focusOnHub() {
            const hubNode = graphData.nodes.find(n => n.id === 'hub_central');
            if (!hubNode) return;
            
            selectedNode = hubNode;
            expandedNodes.clear();
            expandedNodes.add('hub_central');
            
            // Show hub and immediate children
            const hubChildren = graphData.links
                .filter(l => l.source === 'hub_central')
                .map(l => l.target);
            
            const visibleNodes = [hubNode, ...graphData.nodes.filter(n => hubChildren.includes(n.id))];
            const visibleLinks = graphData.links.filter(l => l.source === 'hub_central');
            
            updateGraph(visibleNodes, visibleLinks);
            updateBreadcrumb('📍 Central Hub Active: Click pages to explore system');
        }
        
        // Show direct relationships for a node
        function showDirectRelationshipsForNode(node) {
            const directNodes = new Set([node.id]);
            
            // Find all directly connected nodes
            graphData.links.forEach(link => {
                if (link.source === node.id) directNodes.add(link.target);
                if (link.target === node.id) directNodes.add(link.source);
            });
            
            const visibleNodes = graphData.nodes.filter(n => directNodes.has(n.id));
            const visibleLinks = graphData.links.filter(l => 
                directNodes.has(l.source) && directNodes.has(l.target)
            );
            
            updateGraph(visibleNodes, visibleLinks);
            updateBreadcrumb(\`📍 Direct relationships for: \${node.label}\`);
        }
        
        // Expand all nodes
        function expandAll() {
            graphData.nodes.forEach(n => expandedNodes.add(n.id));
            updateGraph(graphData.nodes, graphData.links);
            updateBreadcrumb('📍 All nodes expanded');
        }
        
        // Collapse all nodes
        function collapseAll() {
            expandedNodes.clear();
            focusOnHub();
        }
        
        // Reset view to full graph
        function resetView() {
            expandedNodes.clear();
            graphData.nodes.forEach(n => expandedNodes.add(n.id));
            currentFilter = 'all';
            currentViewMode = 'all';
            updateActiveButton('filter-all', 'filter-buttons');
            updateActiveButton('all-btn', 'filter-buttons');
            updateGraph(graphData.nodes, graphData.links);
            updateBreadcrumb('📍 Full system view');
        }
        
        // Export hierarchy data
        function exportHierarchy() {
            const exportData = {
                nodes: filteredData.nodes,
                links: filteredData.links,
                hierarchy: generateHierarchyTree(),
                timestamp: new Date().toISOString(),
                expandedNodes: Array.from(expandedNodes)
            };
            
            const blob = new Blob([JSON.stringify(exportData, null, 2)], 
                { type: 'application/json' });
            const url = URL.createObjectURL(blob);
            const a = document.createElement('a');
            a.href = url;
            a.download = 'hierarchical-traceability-graph.json';
            a.click();
            URL.revokeObjectURL(url);
        }
        
        // Generate hierarchy tree for export
        function generateHierarchyTree() {
            const tree = {};
            graphData.nodes.forEach(node => {
                if (!tree[node.level]) tree[node.level] = [];
                tree[node.level].push({
                    id: node.id,
                    label: node.label,
                    type: node.type,
                    children: getChildrenIds(node.id)
                });
            });
            return tree;
        }
        
        // Get children IDs for a node
        function getChildrenIds(nodeId) {
            return graphData.links
                .filter(l => l.source === nodeId)
                .map(l => l.target);
        }
        
        // Update active button
        function updateActiveButton(activeId, groupClass) {
            document.querySelectorAll('.' + groupClass + ' button').forEach(btn => {
                btn.classList.remove('active');
            });
            const activeBtn = document.getElementById(activeId);
            if (activeBtn) activeBtn.classList.add('active');
        }
        
        // Update graph with filtered data
        function updateGraph(visibleNodes, visibleLinks) {
            filteredData = { nodes: visibleNodes, links: visibleLinks };
            
            // Clear existing elements
            g.selectAll("*").remove();
            
            // Create force simulation
            simulation = d3.forceSimulation(visibleNodes)
                .force("link", d3.forceLink(visibleLinks).id(d => d.id).distance(100))
                .force("charge", d3.forceManyBody().strength(-300))
                .force("center", d3.forceCenter(400, 350))
                .force("collision", d3.forceCollide().radius(40));
            
            // Create links
            const link = g.append("g")
                .attr("class", "links")
                .selectAll("line")
                .data(visibleLinks)
                .enter().append("line")
                .attr("stroke", "#666")
                .attr("stroke-opacity", 0.6)
                .attr("stroke-width", d => Math.sqrt(d.value || 1))
                .attr("marker-end", "url(#arrowhead)");
            
            // Create nodes
            const node = g.append("g")
                .attr("class", "nodes")
                .selectAll("g")
                .data(visibleNodes)
                .enter().append("g")
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended));
            
            // Node circles
            node.append("circle")
                .attr("r", d => d.type === 'hub' ? 25 : (15 + d.level * 2))
                .attr("fill", d => getNodeColor(d))
                .attr("stroke", "#fff")
                .attr("stroke-width", 2);
            
            // Node labels
            node.append("text")
                .attr("dy", ".35em")
                .attr("text-anchor", "middle")
                .attr("fill", "white")
                .attr("font-size", d => d.type === 'hub' ? "12px" : "10px")
                .text(d => d.label.length > 10 ? d.label.substring(0, 10) + "..." : d.label);
            
            // Node click handlers
            node.on("click", (event, d) => handleNodeClick(event, d))
                .on("dblclick", (event, d) => handleNodeDoubleClick(event, d))
                .on("mouseover", (event, d) => showTooltip(event, d))
                .on("mouseout", hideTooltip);
            
            // Update simulation
            simulation.nodes(visibleNodes);
            simulation.force("link").links(visibleLinks);
            simulation.alpha(1).restart();
            
            // Update positions on simulation tick
            simulation.on("tick", () => {
                link
                    .attr("x1", d => d.source.x)
                    .attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x)
                    .attr("y2", d => d.target.y);
                
                node.attr("transform", d => \`translate(\${d.x},\${d.y})\`);
            });
            
            updateStats(visibleNodes.length, visibleLinks.length);
        }
        
        // Handle node click - expand/collapse
        function handleNodeClick(event, d) {
            event.stopPropagation();
            selectedNode = d;
            
            if (currentViewMode === 'hub' && d.id !== 'hub_central') {
                // In hub mode, clicking non-hub nodes shows their immediate children
                const children = getChildrenIds(d.id);
                const childNodes = graphData.nodes.filter(n => children.includes(n.id));
                const childLinks = graphData.links.filter(l => 
                    l.source === d.id && children.includes(l.target)
                );
                
                // Add current node and its children to visible set
                const currentVisible = [d, ...childNodes];
                const currentLinks = [...filteredData.links, ...childLinks];
                
                updateGraph(currentVisible, currentLinks);
                updateBreadcrumb(\`📍 Exploring: \${d.label} and children\`);
            } else if (currentViewMode === 'direct') {
                showDirectRelationshipsForNode(d);
            }
        }
        
        // Handle node double-click - impact analysis
        function handleNodeDoubleClick(event, d) {
            event.stopPropagation();
            performImpactAnalysis(d);
        }
        
        // Perform impact analysis for a node
        function performImpactAnalysis(node) {
            impactAnalysisActive = true;
            const impactedNodes = new Set([node.id]);
            const impactQueue = [node.id];
            
            // Traverse dependencies
            while (impactQueue.length > 0) {
                const currentId = impactQueue.shift();
                
                // Find all nodes that depend on current node
                graphData.links.forEach(link => {
                    if (link.source === currentId && !impactedNodes.has(link.target)) {
                        impactedNodes.add(link.target);
                        impactQueue.push(link.target);
                    }
                });
            }
            
            const impactNodes = graphData.nodes.filter(n => impactedNodes.has(n.id));
            const impactLinks = graphData.links.filter(l => 
                impactedNodes.has(l.source) && impactedNodes.has(l.target)
            );
            
            updateGraph(impactNodes, impactLinks);
            updateBreadcrumb(\`🎯 Impact Analysis: \${node.label} affects \${impactedNodes.size} components\`);
        }
        
        // Get node color based on type and level
        function getNodeColor(d) {
            if (d.type === 'hub') return '#ff6b6b';
            
            const colors = {
                'page': '#4ecdc4',
                'frontend_file': '#45b7d1', 
                'component': '#96ceb4',
                'service': '#feca57',
                'method': '#ff9ff3',
                'api_endpoint': '#54a0ff',
                'backend_file': '#5f27cd',
                'database_schema': '#00d2d3'
            };
            
            return colors[d.type] || '#74b9ff';
        }
        
        // Tooltip functions
        function showTooltip(event, d) {
            const tooltip = d3.select("#tooltip");
            if (tooltip.empty()) return;
            
            tooltip.style("opacity", 1)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px")
                .html(\`
                    <strong>\${d.label}</strong><br/>
                    Type: \${d.type}<br/>
                    Level: \${d.level}<br/>
                    Children: \${getChildrenIds(d.id).length}
                \`);
        }
        
        function hideTooltip() {
            const tooltip = d3.select("#tooltip");
            if (!tooltip.empty()) {
                tooltip.style("opacity", 0);
            }
        }
        
        // Update statistics
        function updateStats(nodeCount, linkCount) {
            const visibleNodesEl = document.getElementById('visible-nodes');
            const visibleEdgesEl = document.getElementById('visible-edges');
            
            if (visibleNodesEl) visibleNodesEl.textContent = nodeCount || filteredData.nodes.length;
            if (visibleEdgesEl) visibleEdgesEl.textContent = linkCount || filteredData.links.length;
        }
        
        // Drag functions
        function dragstarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        // Initialize on page load
        document.addEventListener('DOMContentLoaded', function() {
            initGraph();
        });
        
        updateGraph();
        
        function updateGraph() {
            // Filter visible data
            const filteredNodes = graphData.nodes.filter(node => visibleNodes.has(node.id));
            const filteredLinks = graphData.links.filter(link => 
                visibleNodes.has(link.source.id || link.source) && 
                visibleNodes.has(link.target.id || link.target)
            );
            
            // Force simulation
            const simulation = d3.forceSimulation(filteredNodes)
                .force("link", d3.forceLink(filteredLinks).id(d => d.id).distance(d => d.hierarchical ? 80 : 120))
                .force("charge", d3.forceManyBody().strength(-400))
                .force("center", d3.forceCenter(width / 2, height / 2))
                .force("collision", d3.forceCollide().radius(d => d.size + 10))
                .force("y", d3.forceY().y(d => d.level * 100).strength(0.1));
            
            // Clear previous elements
            g.selectAll("*").remove();
            
            // Links
            const link = g.append("g")
                .selectAll("line")
                .data(filteredLinks)
                .enter().append("line")
                .attr("class", d => \`link \${d.hierarchical ? 'hierarchical' : ''}\`)
                .attr("stroke-width", d => d.weight);
            
            // Nodes
            const nodeGroup = g.append("g")
                .selectAll("g")
                .data(filteredNodes)
                .enter().append("g")
                .attr("class", "node-group")
                .call(d3.drag()
                    .on("start", dragstarted)
                    .on("drag", dragged)
                    .on("end", dragended))
                .on("click", handleNodeClick)
                .on("dblclick", handleNodeDoubleClick)
                .on("mouseover", showTooltip)
                .on("mouseout", hideTooltip);
            
            // Node circles
            const node = nodeGroup.append("circle")
                .attr("class", d => \`node \${d.expandable ? 'expandable' : ''} \${!d.expanded && d.children.length > 0 ? 'collapsed' : ''}\`)
                .attr("r", d => d.size)
                .attr("fill", d => d.color);
            
            // Node labels
            const labels = nodeGroup.append("text")
                .attr("class", "node-label")
                .attr("dy", d => d.size + 15)
                .text(d => d.label.length > 12 ? d.label.substring(0, 12) + "..." : d.label);
            
            // Expand/collapse icons
            const icons = nodeGroup.append("text")
                .attr("class", "expand-icon")
                .attr("dy", 4)
                .text(d => {
                    if (!d.expandable || d.children.length === 0) return "";
                    return d.expanded ? "−" : "+";
                });
            
            // Update positions on simulation tick
            simulation.on("tick", () => {
                link
                    .attr("x1", d => d.source.x)
                    .attr("y1", d => d.source.y)
                    .attr("x2", d => d.target.x)
                    .attr("y2", d => d.target.y);
                
                nodeGroup
                    .attr("transform", d => \`translate(\${d.x},\${d.y})\`);
            });
            
            updateStats();
        }
        
        function handleNodeClick(event, d) {
            event.stopPropagation();
            
            if (d.expandable && d.children.length > 0) {
                d.expanded = !d.expanded;
                
                if (d.expanded) {
                    // Show children
                    d.children.forEach(childId => {
                        const childNode = graphData.nodes.find(n => n.id === childId);
                        if (childNode && childNode.level <= currentLevel) {
                            visibleNodes.add(childId);
                        }
                    });
                } else {
                    // Hide children recursively
                    hideNodeChildren(d);
                }
                
                updateGraph();
            }
        }
        
        function handleNodeDoubleClick(event, d) {
            event.stopPropagation();
            
            // Focus on this node and its immediate connections
            visibleNodes.clear();
            visibleNodes.add(d.id);
            
            // Add parent
            if (d.parent) {
                visibleNodes.add(d.parent);
            }
            
            // Add children
            d.children.forEach(childId => {
                visibleNodes.add(childId);
            });
            
            updateGraph();
            
            // Update breadcrumb
            document.getElementById('breadcrumb-text').textContent = \`📍 Focused on: \${d.label} (\${d.type})\`;
        }
        
        function hideNodeChildren(node) {
            node.children.forEach(childId => {
                visibleNodes.delete(childId);
                const childNode = graphData.nodes.find(n => n.id === childId);
                if (childNode) {
                    hideNodeChildren(childNode);
                }
            });
        }
        
        function expandAll() {
            graphData.nodes.forEach(node => {
                if (node.expandable) {
                    node.expanded = true;
                }
                if (node.level <= currentLevel) {
                    visibleNodes.add(node.id);
                }
            });
            updateGraph();
        }
        
        function collapseAll() {
            visibleNodes.clear();
            graphData.nodes.forEach(node => {
                if (node.level === 1) {
                    visibleNodes.add(node.id);
                }
                node.expanded = false;
            });
            updateGraph();
        }
        
        function showLevel(level) {
            currentLevel = level;
            visibleNodes.clear();
            
            graphData.nodes.forEach(node => {
                if (node.level <= level) {
                    visibleNodes.add(node.id);
                }
                if (node.level < level) {
                    node.expanded = true;
                } else {
                    node.expanded = false;
                }
            });
            
            updateGraph();
            
            // Update active button
            document.querySelectorAll('.controls button').forEach(btn => btn.classList.remove('active'));
            event.target.classList.add('active');
        }
        
        function resetView() {
            currentLevel = 6;
            visibleNodes.clear();
            
            graphData.nodes.forEach(node => {
                visibleNodes.add(node.id);
                node.expanded = true;
            });
            
            updateGraph();
            
            document.getElementById('breadcrumb-text').textContent = '📍 Navigate: Click nodes to expand/collapse • Double-click to focus';
        }
        
        function exportHierarchy() {
            const exportData = {
                hierarchy: graphData,
                timestamp: new Date().toISOString(),
                visibleNodes: Array.from(visibleNodes),
                currentLevel: currentLevel
            };
            
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(exportData, null, 2));
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", "hierarchical-traceability-graph.json");
            document.body.appendChild(downloadAnchorNode);
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        }
        
        function updateStats() {
            document.getElementById('visible-nodes').textContent = visibleNodes.size;
            document.getElementById('visible-edges').textContent = 
                graphData.links.filter(link => 
                    visibleNodes.has(link.source.id || link.source) && 
                    visibleNodes.has(link.target.id || link.target)
                ).length;
            document.getElementById('expanded-nodes').textContent = 
                graphData.nodes.filter(node => node.expanded && visibleNodes.has(node.id)).length;
        }
        
        // Drag functions
        function dragstarted(event, d) {
            if (!event.active) d3.select(this).select('circle').attr('stroke-width', 4);
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragended(event, d) {
            if (!event.active) d3.select(this).select('circle').attr('stroke-width', 2);
            d.fx = null;
            d.fy = null;
        }
        
        // Tooltip functions
        const tooltip = d3.select("#tooltip");
        
        function showTooltip(event, d) {
            const childrenInfo = d.children.length > 0 ? \`<br><strong>Children:</strong> \${d.children.length}\` : '';
            const parentInfo = d.parent ? \`<br><strong>Parent:</strong> Node #\${d.parent}\` : '';
            
            tooltip
                .style("opacity", 1)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px")
                .html(\`
                    <strong>\${d.label}</strong><br>
                    <strong>Type:</strong> \${d.type}<br>
                    <strong>Level:</strong> \${d.level}<br>
                    <strong>ID:</strong> \${d.id}<br>
                    <strong>Expandable:</strong> \${d.expandable ? 'Yes' : 'No'}
                    \${childrenInfo}
                    \${parentInfo}
                \`);
        }
        
        function hideTooltip() {
            tooltip.style("opacity", 0);
        }
        
        // Initial setup
        setTimeout(() => {
            const bounds = g.node().getBBox();
            const fullWidth = bounds.width;
            const fullHeight = bounds.height;
            const widthScale = width / fullWidth;
            const heightScale = height / fullHeight;
            const scale = 0.8 * Math.min(widthScale, heightScale);
            const translate = [width / 2 - scale * (bounds.x + fullWidth / 2), height / 2 - scale * (bounds.y + fullHeight / 2)];
            
            svg.transition()
                .duration(1000)
                .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
        }, 1500);
    </script>
</body>
</html>`;
    }

    // Main execution
    async generate() {
        console.log('🚀 Starting enhanced hierarchical analysis...');
        
        // Generate hierarchy
        this.generateHierarchy();
        
        // Generate graph data
        const graphData = this.generateEnhancedGraphData();
        
        console.log(`📊 Generated hierarchical graph:`);
        console.log(`   📄 Pages: ${this.hierarchy.pages.size}`);
        console.log(`   ⚙️ Capabilities: ${this.hierarchy.capabilities.size}`);
        console.log(`   📁 Files: ${this.hierarchy.files.size}`);
        console.log(`   🎨 UI Features: ${this.hierarchy.uiFeatures.size}`);
        console.log(`   🐍 Services: ${this.hierarchy.services.size}`);
        console.log(`   🗄️ Schemas: ${this.hierarchy.schemas.size}`);
        console.log(`   🔗 Total Nodes: ${graphData.nodes.length}`);
        console.log(`   🔗 Total Edges: ${graphData.links.length}`);
        
        // Create output directory
        const outputDir = 'ENHANCED_TRACEABILITY_GRAPH';
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        
        // Save graph data
        const graphDataPath = path.join(outputDir, 'hierarchical-graph-data.json');
        fs.writeFileSync(graphDataPath, JSON.stringify(graphData, null, 2));
        console.log(`💾 Hierarchical graph data saved: ${graphDataPath}`);
        
        // Generate and save visualization
        const visualization = this.generateEnhancedVisualization(graphData);
        const htmlPath = path.join(outputDir, 'enhanced-traceability-graph.html');
        fs.writeFileSync(htmlPath, visualization);
        console.log(`🌐 Enhanced interactive visualization saved: ${htmlPath}`);
        
        console.log('✅ Enhanced hierarchical traceability graph generation completed!');
        console.log(`🌳 Open ${htmlPath} in your browser to explore the hierarchical network`);
        
        return {
            hierarchy: {
                pages: this.hierarchy.pages.size,
                capabilities: this.hierarchy.capabilities.size,
                files: this.hierarchy.files.size,
                uiFeatures: this.hierarchy.uiFeatures.size,
                services: this.hierarchy.services.size,
                schemas: this.hierarchy.schemas.size
            },
            nodes: graphData.nodes.length,
            edges: graphData.links.length,
            htmlPath: htmlPath,
            dataPath: graphDataPath
        };
    }
}

// Execute if run directly
if (require.main === module) {
    const generator = new HierarchicalGraphGenerator();
    generator.generate().catch(console.error);
}

module.exports = HierarchicalGraphGenerator;
