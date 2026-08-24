#!/usr/bin/env node

/**
 * 🕸️ NETWORKX-STYLE TRACEABILITY GRAPH GENERATOR
 * 
 * Creates directed graphs showing relationships between:
 * - Files and their dependencies
 * - Components and their method calls
 * - Services and their connections
 * - Database relationships
 */

const fs = require('fs');
const path = require('path');

console.log('🕸️ NETWORKX TRACEABILITY GRAPH GENERATOR');
console.log('='.repeat(50));

class TraceabilityGraphGenerator {
    constructor() {
        this.nodes = new Map();
        this.edges = [];
        this.nodeId = 0;
        this.srcRoot = './src';
        this.backendRoot = '../python_backend';
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
                size: this.getSizeByType(type),
                color: this.getColorByType(type)
            });
        }
        return this.nodes.get(key).id;
    }

    getGroupByType(type) {
        const groups = {
            'frontend_file': 1,
            'component': 2,
            'service': 3,
            'method': 4,
            'api_endpoint': 5,
            'backend_file': 6,
            'database': 7,
            'config': 8
        };
        return groups[type] || 0;
    }

    getSizeByType(type) {
        const sizes = {
            'frontend_file': 15,
            'component': 12,
            'service': 18,
            'method': 8,
            'api_endpoint': 14,
            'backend_file': 16,
            'database': 20,
            'config': 10
        };
        return sizes[type] || 8;
    }

    getColorByType(type) {
        const colors = {
            'frontend_file': '#3498db',    // Blue
            'component': '#2ecc71',        // Green
            'service': '#e74c3c',          // Red
            'method': '#f39c12',           // Orange
            'api_endpoint': '#9b59b6',     // Purple
            'backend_file': '#1abc9c',     // Teal
            'database': '#34495e',         // Dark Gray
            'config': '#95a5a6'            // Gray
        };
        return colors[type] || '#bdc3c7';
    }

    // Add edge between nodes
    addEdge(sourceLabel, sourceType, targetLabel, targetType, relationshipType = 'depends_on') {
        const sourceId = this.getNodeId(sourceLabel, sourceType);
        const targetId = this.getNodeId(targetLabel, targetType);
        
        this.edges.push({
            source: sourceId,
            target: targetId,
            type: relationshipType,
            weight: this.getWeightByRelationType(relationshipType)
        });
    }

    getWeightByRelationType(type) {
        const weights = {
            'imports': 3,
            'calls': 2,
            'depends_on': 1,
            'contains': 4,
            'uses': 2,
            'connects_to': 3
        };
        return weights[type] || 1;
    }

    // Scan frontend files for imports and dependencies
    scanFrontendFiles() {
        console.log('📁 Scanning frontend files...');
        
        if (!fs.existsSync(this.srcRoot)) {
            console.log('⚠️ Frontend src directory not found');
            return;
        }

        this.scanDirectory(this.srcRoot, 'frontend');
    }

    // Scan backend files
    scanBackendFiles() {
        console.log('🐍 Scanning backend files...');
        
        if (!fs.existsSync(this.backendRoot)) {
            console.log('⚠️ Backend directory not found');
            return;
        }

        this.scanDirectory(this.backendRoot, 'backend');
    }

    // Recursively scan directory
    scanDirectory(dirPath, context) {
        try {
            const files = fs.readdirSync(dirPath);
            
            for (const file of files) {
                const filePath = path.join(dirPath, file);
                const stat = fs.statSync(filePath);
                
                if (stat.isDirectory() && !file.startsWith('.') && file !== 'node_modules') {
                    this.scanDirectory(filePath, context);
                } else if (stat.isFile()) {
                    this.analyzeFile(filePath, context);
                }
            }
        } catch (error) {
            console.log(`⚠️ Error scanning ${dirPath}: ${error.message}`);
        }
    }

    // Analyze individual file
    analyzeFile(filePath, context) {
        try {
            const content = fs.readFileSync(filePath, 'utf8');
            const fileName = path.basename(filePath);
            const ext = path.extname(fileName);
            
            // Skip binary files and node_modules
            if (this.isBinaryFile(ext) || filePath.includes('node_modules')) {
                return;
            }

            const fileType = context === 'frontend' ? 'frontend_file' : 'backend_file';
            
            if (context === 'frontend') {
                this.analyzeFrontendFile(filePath, fileName, content);
            } else {
                this.analyzeBackendFile(filePath, fileName, content);
            }

        } catch (error) {
            // Silently skip files that can't be read
        }
    }

    // Analyze frontend file (JS, TS, JSX, TSX, Vue)
    analyzeFrontendFile(filePath, fileName, content) {
        const fileNode = fileName;
        
        // Extract imports
        const imports = this.extractImports(content);
        for (const importPath of imports) {
            this.addEdge(fileNode, 'frontend_file', importPath, 'frontend_file', 'imports');
        }

        // Extract components
        const components = this.extractComponents(content);
        for (const component of components) {
            this.addEdge(fileNode, 'frontend_file', component, 'component', 'contains');
        }

        // Extract methods
        const methods = this.extractMethods(content);
        for (const method of methods) {
            this.addEdge(fileNode, 'frontend_file', method, 'method', 'contains');
        }

        // Extract API calls
        const apiCalls = this.extractApiCalls(content);
        for (const apiCall of apiCalls) {
            this.addEdge(fileNode, 'frontend_file', apiCall, 'api_endpoint', 'calls');
        }
    }

    // Analyze backend file (Python)
    analyzeBackendFile(filePath, fileName, content) {
        const fileNode = fileName;
        
        // Extract imports
        const imports = this.extractPythonImports(content);
        for (const importPath of imports) {
            this.addEdge(fileNode, 'backend_file', importPath, 'backend_file', 'imports');
        }

        // Extract functions
        const functions = this.extractPythonFunctions(content);
        for (const func of functions) {
            this.addEdge(fileNode, 'backend_file', func, 'method', 'contains');
        }

        // Extract API endpoints
        const endpoints = this.extractApiEndpoints(content);
        for (const endpoint of endpoints) {
            this.addEdge(fileNode, 'backend_file', endpoint, 'api_endpoint', 'contains');
        }

        // Extract database connections
        const dbConnections = this.extractDatabaseConnections(content);
        for (const db of dbConnections) {
            this.addEdge(fileNode, 'backend_file', db, 'database', 'connects_to');
        }
    }

    // Extract JavaScript/TypeScript imports
    extractImports(content) {
        const imports = [];
        const importRegex = /import.*?from\s+['"](.*?)['"];?/g;
        let match;
        
        while ((match = importRegex.exec(content)) !== null) {
            let importPath = match[1];
            // Clean up relative paths
            if (importPath.startsWith('./') || importPath.startsWith('../')) {
                importPath = path.basename(importPath);
            }
            imports.push(importPath);
        }

        // Also check require statements
        const requireRegex = /require\s*\(\s*['"](.*?)['"]s*\)/g;
        while ((match = requireRegex.exec(content)) !== null) {
            let requirePath = match[1];
            if (requirePath.startsWith('./') || requirePath.startsWith('../')) {
                requirePath = path.basename(requirePath);
            }
            imports.push(requirePath);
        }
        
        return imports;
    }

    // Extract React/Vue components
    extractComponents(content) {
        const components = [];
        
        // React component patterns
        const reactRegex = /(?:export\s+(?:default\s+)?)?(?:const|function|class)\s+(\w+).*?(?:React\.Component|extends\s+Component|=>\s*{|:\s*React\.FC)/g;
        let match;
        
        while ((match = reactRegex.exec(content)) !== null) {
            components.push(match[1]);
        }

        // Vue component patterns
        const vueRegex = /<template.*?>(.*?)<\/template>/s;
        if (vueRegex.test(content)) {
            const nameMatch = content.match(/name:\s*['"](.*?)['"],?/);
            if (nameMatch) {
                components.push(nameMatch[1]);
            }
        }
        
        return components;
    }

    // Extract methods and functions
    extractMethods(content) {
        const methods = [];
        
        // Function declarations
        const funcRegex = /(?:function\s+(\w+)|const\s+(\w+)\s*=.*?(?:function|\(.*?\)\s*=>))/g;
        let match;
        
        while ((match = funcRegex.exec(content)) !== null) {
            const methodName = match[1] || match[2];
            if (methodName) {
                methods.push(methodName);
            }
        }

        // Class methods
        const methodRegex = /(?:async\s+)?(\w+)\s*\([^)]*\)\s*{/g;
        while ((match = methodRegex.exec(content)) !== null) {
            if (!['constructor', 'render', 'componentDidMount'].includes(match[1])) {
                methods.push(match[1]);
            }
        }
        
        return methods;
    }

    // Extract API calls
    extractApiCalls(content) {
        const apiCalls = [];
        
        // Fetch calls
        const fetchRegex = /fetch\s*\(\s*['"](.*?)['"],?/g;
        let match;
        
        while ((match = fetchRegex.exec(content)) !== null) {
            apiCalls.push(this.extractEndpointFromUrl(match[1]));
        }

        // Axios calls
        const axiosRegex = /axios\.(?:get|post|put|delete|patch)\s*\(\s*['"](.*?)['"],?/g;
        while ((match = axiosRegex.exec(content)) !== null) {
            apiCalls.push(this.extractEndpointFromUrl(match[1]));
        }

        // HTTP client calls
        const httpRegex = /(?:GET|POST|PUT|DELETE|PATCH)\s+['"](.*?)['"];?/g;
        while ((match = httpRegex.exec(content)) !== null) {
            apiCalls.push(this.extractEndpointFromUrl(match[1]));
        }
        
        return apiCalls;
    }

    // Extract Python imports
    extractPythonImports(content) {
        const imports = [];
        
        // from x import y
        const fromImportRegex = /from\s+([\w.]+)\s+import/g;
        let match;
        
        while ((match = fromImportRegex.exec(content)) !== null) {
            imports.push(match[1]);
        }

        // import x
        const importRegex = /^import\s+([\w.]+)/gm;
        while ((match = importRegex.exec(content)) !== null) {
            imports.push(match[1]);
        }
        
        return imports;
    }

    // Extract Python functions
    extractPythonFunctions(content) {
        const functions = [];
        const funcRegex = /def\s+(\w+)\s*\(/g;
        let match;
        
        while ((match = funcRegex.exec(content)) !== null) {
            if (!match[1].startsWith('_')) { // Skip private methods
                functions.push(match[1]);
            }
        }
        
        return functions;
    }

    // Extract API endpoints from FastAPI/Flask
    extractApiEndpoints(content) {
        const endpoints = [];
        
        // FastAPI decorators
        const fastapiRegex = /@app\.(?:get|post|put|delete|patch)\s*\(\s*['"](.*?)['"],?/g;
        let match;
        
        while ((match = fastapiRegex.exec(content)) !== null) {
            endpoints.push(match[1]);
        }

        // Flask decorators
        const flaskRegex = /@app\.route\s*\(\s*['"](.*?)['"],?/g;
        while ((match = flaskRegex.exec(content)) !== null) {
            endpoints.push(match[1]);
        }
        
        return endpoints;
    }

    // Extract database connections
    extractDatabaseConnections(content) {
        const databases = [];
        
        // PostgreSQL
        if (content.includes('psycopg2') || content.includes('asyncpg') || content.includes('PostgreSQL')) {
            databases.push('PostgreSQL');
        }

        // Neo4j
        if (content.includes('neo4j') || content.includes('Neo4j')) {
            databases.push('Neo4j');
        }

        // MongoDB
        if (content.includes('pymongo') || content.includes('MongoDB')) {
            databases.push('MongoDB');
        }

        // SQLite
        if (content.includes('sqlite3') || content.includes('SQLite')) {
            databases.push('SQLite');
        }
        
        return databases;
    }

    // Extract endpoint from URL
    extractEndpointFromUrl(url) {
        // Remove base URL and query parameters
        let endpoint = url.replace(/^https?:\/\/[^\/]+/, '');
        endpoint = endpoint.split('?')[0];
        return endpoint || url;
    }

    // Check if file is binary
    isBinaryFile(ext) {
        const binaryExts = ['.jpg', '.jpeg', '.png', '.gif', '.ico', '.pdf', '.zip', '.tar', '.gz'];
        return binaryExts.includes(ext.toLowerCase());
    }

    // Generate NetworkX-compatible graph data
    generateGraphData() {
        const nodesArray = Array.from(this.nodes.values());
        
        return {
            directed: true,
            multigraph: false,
            graph: {
                name: "GraphTrace System Traceability",
                description: "File and method relationships in the GraphTrace system"
            },
            nodes: nodesArray,
            links: this.edges
        };
    }

    // Generate D3.js interactive visualization
    generateVisualization(graphData) {
        return `
<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>🕸️ GraphTrace Traceability Network</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            margin: 0;
            padding: 20px;
            font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            color: white;
        }
        
        .header {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .controls {
            text-align: center;
            margin-bottom: 20px;
        }
        
        .controls button {
            margin: 0 10px;
            padding: 8px 16px;
            border: none;
            border-radius: 5px;
            background: rgba(255,255,255,0.2);
            color: white;
            cursor: pointer;
            font-size: 14px;
        }
        
        .controls button:hover {
            background: rgba(255,255,255,0.3);
        }
        
        .graph-container {
            background: rgba(255,255,255,0.1);
            border-radius: 10px;
            padding: 20px;
            box-shadow: 0 8px 32px rgba(0,0,0,0.1);
        }
        
        #graph {
            width: 100%;
            height: 600px;
            border: 1px solid rgba(255,255,255,0.2);
            border-radius: 5px;
            background: rgba(0,0,0,0.1);
        }
        
        .legend {
            margin-top: 20px;
            display: flex;
            flex-wrap: wrap;
            justify-content: center;
            gap: 15px;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            background: rgba(255,255,255,0.1);
            padding: 5px 10px;
            border-radius: 15px;
            font-size: 12px;
        }
        
        .legend-color {
            width: 12px;
            height: 12px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .stats {
            margin-top: 20px;
            text-align: center;
            background: rgba(255,255,255,0.1);
            padding: 15px;
            border-radius: 10px;
        }
        
        .node {
            stroke: #fff;
            stroke-width: 2px;
            cursor: pointer;
        }
        
        .link {
            stroke: rgba(255,255,255,0.6);
            stroke-width: 1px;
            marker-end: url(#arrowhead);
        }
        
        .node-label {
            font-size: 10px;
            fill: white;
            text-anchor: middle;
            pointer-events: none;
            text-shadow: 1px 1px 2px rgba(0,0,0,0.7);
        }
        
        .tooltip {
            position: absolute;
            background: rgba(0,0,0,0.8);
            color: white;
            padding: 8px;
            border-radius: 5px;
            font-size: 12px;
            pointer-events: none;
            opacity: 0;
            transition: opacity 0.3s;
        }
    </style>
</head>
<body>
    <div class="header">
        <h1>🕸️ GraphTrace System Traceability Network</h1>
        <p>Interactive directed graph showing file and method relationships</p>
    </div>
    
    <div class="controls">
        <button onclick="zoomToFit()">🔍 Zoom to Fit</button>
        <button onclick="resetSimulation()">🔄 Reset Layout</button>
        <button onclick="exportGraph()">💾 Export Data</button>
        <button onclick="toggleLabels()">🏷️ Toggle Labels</button>
    </div>
    
    <div class="graph-container">
        <svg id="graph"></svg>
    </div>
    
    <div class="legend">
        <div class="legend-item">
            <div class="legend-color" style="background: #3498db;"></div>
            Frontend Files
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #2ecc71;"></div>
            Components
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #e74c3c;"></div>
            Services
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #f39c12;"></div>
            Methods
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #9b59b6;"></div>
            API Endpoints
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #1abc9c;"></div>
            Backend Files
        </div>
        <div class="legend-item">
            <div class="legend-color" style="background: #34495e;"></div>
            Databases
        </div>
    </div>
    
    <div class="stats">
        <strong>Graph Statistics:</strong>
        Nodes: <span id="node-count">${graphData.nodes.length}</span> |
        Edges: <span id="edge-count">${graphData.links.length}</span> |
        Types: <span id="type-count">${new Set(graphData.nodes.map(n => n.type)).size}</span>
    </div>
    
    <div class="tooltip" id="tooltip"></div>

    <script>
        // Graph data
        const graphData = ${JSON.stringify(graphData, null, 2)};
        
        // SVG setup
        const svg = d3.select("#graph");
        const width = 800;
        const height = 600;
        svg.attr("width", width).attr("height", height);
        
        // Create arrowhead marker
        svg.append("defs").append("marker")
            .attr("id", "arrowhead")
            .attr("viewBox", "0 -5 10 10")
            .attr("refX", 20)
            .attr("refY", 0)
            .attr("markerWidth", 6)
            .attr("markerHeight", 6)
            .attr("orient", "auto")
            .append("path")
            .attr("d", "M0,-5L10,0L0,5")
            .attr("fill", "rgba(255,255,255,0.6)");
        
        // Zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 3])
            .on("zoom", (event) => {
                g.attr("transform", event.transform);
            });
        
        svg.call(zoom);
        
        // Container group
        const g = svg.append("g");
        
        // Force simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force("link", d3.forceLink(graphData.links).id(d => d.id).distance(100))
            .force("charge", d3.forceManyBody().strength(-300))
            .force("center", d3.forceCenter(width / 2, height / 2))
            .force("collision", d3.forceCollide().radius(d => d.size + 5));
        
        // Links
        const link = g.append("g")
            .selectAll("line")
            .data(graphData.links)
            .enter().append("line")
            .attr("class", "link")
            .attr("stroke-width", d => d.weight);
        
        // Nodes
        const node = g.append("g")
            .selectAll("circle")
            .data(graphData.nodes)
            .enter().append("circle")
            .attr("class", "node")
            .attr("r", d => d.size)
            .attr("fill", d => d.color)
            .call(d3.drag()
                .on("start", dragstarted)
                .on("drag", dragged)
                .on("end", dragended))
            .on("mouseover", showTooltip)
            .on("mouseout", hideTooltip);
        
        // Labels
        let labelsVisible = true;
        const labels = g.append("g")
            .selectAll("text")
            .data(graphData.nodes)
            .enter().append("text")
            .attr("class", "node-label")
            .text(d => d.label.length > 15 ? d.label.substring(0, 15) + "..." : d.label);
        
        // Tooltip
        const tooltip = d3.select("#tooltip");
        
        // Update positions on simulation tick
        simulation.on("tick", () => {
            link
                .attr("x1", d => d.source.x)
                .attr("y1", d => d.source.y)
                .attr("x2", d => d.target.x)
                .attr("y2", d => d.target.y);
            
            node
                .attr("cx", d => d.x)
                .attr("cy", d => d.y);
            
            labels
                .attr("x", d => d.x)
                .attr("y", d => d.y + 5);
        });
        
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
        
        // Tooltip functions
        function showTooltip(event, d) {
            tooltip
                .style("opacity", 1)
                .style("left", (event.pageX + 10) + "px")
                .style("top", (event.pageY - 10) + "px")
                .html(\`
                    <strong>\${d.label}</strong><br>
                    Type: \${d.type}<br>
                    Group: \${d.group}<br>
                    ID: \${d.id}
                \`);
        }
        
        function hideTooltip() {
            tooltip.style("opacity", 0);
        }
        
        // Control functions
        function zoomToFit() {
            const bounds = g.node().getBBox();
            const fullWidth = bounds.width;
            const fullHeight = bounds.height;
            const widthScale = width / fullWidth;
            const heightScale = height / fullHeight;
            const scale = 0.9 * Math.min(widthScale, heightScale);
            const translate = [width / 2 - scale * (bounds.x + fullWidth / 2), height / 2 - scale * (bounds.y + fullHeight / 2)];
            
            svg.transition()
                .duration(750)
                .call(zoom.transform, d3.zoomIdentity.translate(translate[0], translate[1]).scale(scale));
        }
        
        function resetSimulation() {
            simulation.alpha(1).restart();
        }
        
        function exportGraph() {
            const dataStr = "data:text/json;charset=utf-8," + encodeURIComponent(JSON.stringify(graphData, null, 2));
            const downloadAnchorNode = document.createElement('a');
            downloadAnchorNode.setAttribute("href", dataStr);
            downloadAnchorNode.setAttribute("download", "traceability-graph.json");
            document.body.appendChild(downloadAnchorNode);
            downloadAnchorNode.click();
            downloadAnchorNode.remove();
        }
        
        function toggleLabels() {
            labelsVisible = !labelsVisible;
            labels.style("opacity", labelsVisible ? 1 : 0);
        }
        
        // Initial zoom to fit
        setTimeout(zoomToFit, 1000);
    </script>
</body>
</html>`;
    }

    // Main execution
    async generate() {
        console.log('🚀 Starting traceability analysis...');
        
        // Scan files
        this.scanFrontendFiles();
        this.scanBackendFiles();
        
        // Generate graph data
        const graphData = this.generateGraphData();
        
        console.log(`📊 Generated graph with ${graphData.nodes.length} nodes and ${graphData.links.length} edges`);
        
        // Create output directory
        const outputDir = 'TRACEABILITY_GRAPH';
        if (!fs.existsSync(outputDir)) {
            fs.mkdirSync(outputDir, { recursive: true });
        }
        
        // Save graph data
        const graphDataPath = path.join(outputDir, 'graph-data.json');
        fs.writeFileSync(graphDataPath, JSON.stringify(graphData, null, 2));
        console.log(`💾 Graph data saved: ${graphDataPath}`);
        
        // Generate and save visualization
        const visualization = this.generateVisualization(graphData);
        const htmlPath = path.join(outputDir, 'traceability-graph.html');
        fs.writeFileSync(htmlPath, visualization);
        console.log(`🌐 Interactive visualization saved: ${htmlPath}`);
        
        console.log('✅ Traceability graph generation completed!');
        console.log(`🔗 Open ${htmlPath} in your browser to view the interactive network`);
        
        return {
            nodes: graphData.nodes.length,
            edges: graphData.links.length,
            htmlPath: htmlPath,
            dataPath: graphDataPath
        };
    }
}

// Execute if run directly
if (require.main === module) {
    const generator = new TraceabilityGraphGenerator();
    generator.generate().catch(console.error);
}

module.exports = TraceabilityGraphGenerator;
