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
console.log('=' * 50);

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
            this.nodes.set(key, {
                id: this.nodeId++,
                label: label,
                type: type,
                key: key
            });
        }
        return this.nodes.get(key).id;
    }

    // Add edge between nodes
    addEdge(sourceLabel, sourceType, targetLabel, targetType, relationship, metadata = {}) {
        const sourceId = this.getNodeId(sourceLabel, sourceType);
        const targetId = this.getNodeId(targetLabel, targetType);
        
        this.edges.push({
            source: sourceId,
            target: targetId,
            relationship: relationship,
            sourceLabel: sourceLabel,
            targetLabel: targetLabel,
            sourceType: sourceType,
            targetType: targetType,
            ...metadata
        });
    }

    // Scan frontend files for relationships
    scanFrontendFiles() {
        console.log('📁 Scanning frontend files for traceability...');
        
        if (!fs.existsSync(this.srcRoot)) {
            console.log('⚠️ src directory not found');
            return;
        }

        this.walkDirectory(this.srcRoot, (filePath, content) => {
            const relativePath = path.relative(this.srcRoot, filePath);
            const fileName = path.basename(filePath);
            const fileType = this.getFileType(filePath);
            
            // Add file node
            this.getNodeId(relativePath, 'file');
            
            // Extract imports and create edges
            this.extractImports(content, relativePath, fileType);
            
            // Extract component usage
            this.extractComponentUsage(content, relativePath);
            
            // Extract API calls
            this.extractAPICalls(content, relativePath);
            
            // Extract method definitions and calls
            this.extractMethods(content, relativePath);
        });
    }

    // Walk directory recursively
    walkDirectory(dir, callback) {
        try {
            const items = fs.readdirSync(dir);
            
            for (const item of items) {
                const fullPath = path.join(dir, item);
                
                try {
                    const stat = fs.statSync(fullPath);
                    
                    if (stat.isDirectory() && !item.startsWith('.') && item !== 'node_modules') {
                        this.walkDirectory(fullPath, callback);
                    } else if (stat.isFile() && this.isSourceFile(fullPath)) {
                        const content = fs.readFileSync(fullPath, 'utf8');
                        callback(fullPath, content);
                    }
                } catch (err) {
                    console.log(`⚠️ Could not process ${fullPath}: ${err.message}`);
                }
            }
        } catch (err) {
            console.log(`⚠️ Could not read directory ${dir}: ${err.message}`);
        }
    }

    // Check if file is a source file we want to analyze
    isSourceFile(filePath) {
        const ext = path.extname(filePath);
        return ['.js', '.jsx', '.ts', '.tsx', '.py'].includes(ext);
    }

    // Get file type
    getFileType(filePath) {
        const ext = path.extname(filePath);
        const typeMap = {
            '.jsx': 'react-component',
            '.js': 'javascript',
            '.tsx': 'typescript-react',
            '.ts': 'typescript',
            '.py': 'python'
        };
        return typeMap[ext] || 'other';
    }

    // Extract import relationships
    extractImports(content, filePath, fileType) {
        if (fileType.includes('react') || fileType === 'javascript' || fileType === 'typescript') {
            // ES6 imports
            const importRegex = /import\s+(?:\{[^}]*\}|\w+|\*\s+as\s+\w+)?\s*from\s+['"]([^'"]+)['"]/g;
            let match;
            
            while ((match = importRegex.exec(content)) !== null) {
                const importPath = match[1];
                
                // Skip node_modules imports for now
                if (!importPath.startsWith('.') && !importPath.startsWith('/')) {
                    this.addEdge(filePath, 'file', importPath, 'external-dependency', 'imports');
                } else {
                    // Resolve relative imports
                    const resolvedPath = this.resolveImportPath(filePath, importPath);
                    if (resolvedPath) {
                        this.addEdge(filePath, 'file', resolvedPath, 'file', 'imports');
                    }
                }
            }
        } else if (fileType === 'python') {
            // Python imports
            const importRegex = /(?:from\s+([^\s]+)\s+import\s+([^;\n]+)|import\s+([^;\n]+))/g;
            let match;
            
            while ((match = importRegex.exec(content)) !== null) {
                if (match[1] && match[2]) {
                    // from X import Y
                    this.addEdge(filePath, 'file', match[1], 'python-module', 'imports');
                } else if (match[3]) {
                    // import X
                    this.addEdge(filePath, 'file', match[3], 'python-module', 'imports');
                }
            }
        }
    }

    // Resolve relative import paths
    resolveImportPath(currentFile, importPath) {
        try {
            const currentDir = path.dirname(currentFile);
            const resolved = path.resolve(currentDir, importPath);
            const relativePath = path.relative(this.srcRoot, resolved);
            
            // Try common extensions
            const extensions = ['.js', '.jsx', '.ts', '.tsx', '.json'];
            for (const ext of extensions) {
                const fullPath = resolved + ext;
                if (fs.existsSync(fullPath)) {
                    return path.relative(this.srcRoot, fullPath);
                }
            }
            
            // Try index files
            for (const ext of extensions) {
                const indexPath = path.join(resolved, 'index' + ext);
                if (fs.existsSync(indexPath)) {
                    return path.relative(this.srcRoot, indexPath);
                }
            }
        } catch (err) {
            // Return null if can't resolve
        }
        
        return null;
    }

    // Extract component usage
    extractComponentUsage(content, filePath) {
        // React component usage
        const componentRegex = /<(\w+)(?:\s+[^>]*)?>/g;
        let match;
        
        while ((match = componentRegex.exec(content)) !== null) {
            const componentName = match[1];
            
            // Only include custom components (start with uppercase)
            if (componentName[0] === componentName[0].toUpperCase() && componentName !== 'div' && componentName !== 'span') {
                this.addEdge(filePath, 'file', componentName, 'component', 'uses', {
                    context: this.getContext(content, match.index)
                });
            }
        }
    }

    // Extract API calls
    extractAPICalls(content, filePath) {
        // Fetch calls
        const fetchRegex = /fetch\s*\(\s*['"`]([^'"`]+)['"`]/g;
        let match;
        
        while ((match = fetchRegex.exec(content)) !== null) {
            const endpoint = match[1];
            this.addEdge(filePath, 'file', endpoint, 'api-endpoint', 'calls', {
                method: 'fetch'
            });
        }

        // Axios calls
        const axiosRegex = /axios\.\w+\s*\(\s*['"`]([^'"`]+)['"`]/g;
        while ((match = axiosRegex.exec(content)) !== null) {
            const endpoint = match[1];
            this.addEdge(filePath, 'file', endpoint, 'api-endpoint', 'calls', {
                method: 'axios'
            });
        }
    }

    // Extract method definitions and calls
    extractMethods(content, filePath) {
        const fileType = this.getFileType(filePath);
        
        if (fileType.includes('react') || fileType === 'javascript' || fileType === 'typescript') {
            // Function definitions
            const functionRegex = /(?:function\s+(\w+)|const\s+(\w+)\s*=\s*(?:async\s+)?(?:\([^)]*\)|[\w$]+)\s*=>|(\w+)\s*:\s*(?:async\s+)?(?:\([^)]*\)|[\w$]+)\s*=>)/g;
            let match;
            
            while ((match = functionRegex.exec(content)) !== null) {
                const functionName = match[1] || match[2] || match[3];
                if (functionName) {
                    this.addEdge(filePath, 'file', functionName, 'method', 'defines');
                }
            }

            // Method calls
            const methodCallRegex = /(\w+)\.\w+\s*\(/g;
            while ((match = methodCallRegex.exec(content)) !== null) {
                const objectName = match[1];
                this.addEdge(filePath, 'file', objectName, 'object', 'calls-method-on');
            }
        } else if (fileType === 'python') {
            // Python function definitions
            const pythonFuncRegex = /def\s+(\w+)\s*\(/g;
            let match;
            
            while ((match = pythonFuncRegex.exec(content)) !== null) {
                const functionName = match[1];
                this.addEdge(filePath, 'file', functionName, 'method', 'defines');
            }

            // Python class definitions
            const pythonClassRegex = /class\s+(\w+)(?:\([^)]*\))?:/g;
            while ((match = pythonClassRegex.exec(content)) !== null) {
                const className = match[1];
                this.addEdge(filePath, 'file', className, 'class', 'defines');
            }
        }
    }

    // Get context around a match
    getContext(content, index, contextLength = 50) {
        const start = Math.max(0, index - contextLength);
        const end = Math.min(content.length, index + contextLength);
        return content.substring(start, end).replace(/\n/g, ' ').trim();
    }

    // Generate NetworkX-style graph data
    generateGraphData() {
        console.log('📊 Generating NetworkX-style graph data...');
        
        const graphData = {
            directed: true,
            multigraph: false,
            graph: {
                name: "System Traceability Graph",
                description: "File and method relationship graph",
                generated: new Date().toISOString()
            },
            nodes: Array.from(this.nodes.values()).map(node => ({
                id: node.id,
                label: node.label,
                type: node.type,
                size: this.getNodeSize(node.type),
                color: this.getNodeColor(node.type),
                group: this.getNodeGroup(node.type)
            })),
            links: this.edges.map(edge => ({
                source: edge.source,
                target: edge.target,
                relationship: edge.relationship,
                sourceLabel: edge.sourceLabel,
                targetLabel: edge.targetLabel,
                sourceType: edge.sourceType,
                targetType: edge.targetType,
                weight: 1,
                color: this.getEdgeColor(edge.relationship)
            }))
        };

        return graphData;
    }

    // Get node size based on type
    getNodeSize(type) {
        const sizeMap = {
            'file': 15,
            'component': 20,
            'method': 10,
            'class': 18,
            'api-endpoint': 16,
            'external-dependency': 12,
            'python-module': 14,
            'object': 8
        };
        return sizeMap[type] || 10;
    }

    // Get node color based on type
    getNodeColor(type) {
        const colorMap = {
            'file': '#4CAF50',
            'component': '#2196F3',
            'method': '#FF9800',
            'class': '#9C27B0',
            'api-endpoint': '#F44336',
            'external-dependency': '#607D8B',
            'python-module': '#795548',
            'object': '#E91E63'
        };
        return colorMap[type] || '#9E9E9E';
    }

    // Get node group for clustering
    getNodeGroup(type) {
        const groupMap = {
            'file': 'files',
            'component': 'ui',
            'method': 'functions',
            'class': 'classes',
            'api-endpoint': 'apis',
            'external-dependency': 'external',
            'python-module': 'backend',
            'object': 'objects'
        };
        return groupMap[type] || 'other';
    }

    // Get edge color based on relationship
    getEdgeColor(relationship) {
        const colorMap = {
            'imports': '#4CAF50',
            'uses': '#2196F3',
            'calls': '#FF5722',
            'defines': '#9C27B0',
            'calls-method-on': '#FF9800',
            'extends': '#607D8B'
        };
        return colorMap[relationship] || '#9E9E9E';
    }

    // Generate interactive HTML visualization
    generateVisualization(graphData) {
        console.log('🌐 Generating interactive HTML visualization...');
        
        const html = `<!DOCTYPE html>
<html lang="en">
<head>
    <meta charset="UTF-8">
    <meta name="viewport" content="width=device-width, initial-scale=1.0">
    <title>System Traceability Graph - NetworkX Style</title>
    <script src="https://d3js.org/d3.v7.min.js"></script>
    <style>
        body {
            font-family: 'Segoe UI', Tahoma, Geneva, Verdana, sans-serif;
            margin: 0;
            padding: 0;
            background: linear-gradient(135deg, #667eea 0%, #764ba2 100%);
            overflow: hidden;
        }
        
        .container {
            height: 100vh;
            display: flex;
            flex-direction: column;
        }
        
        .header {
            background: rgba(0, 0, 0, 0.8);
            color: white;
            padding: 15px 20px;
            z-index: 1000;
        }
        
        .header h1 {
            margin: 0;
            font-size: 1.5em;
            display: inline-block;
        }
        
        .controls {
            float: right;
            display: inline-block;
        }
        
        .controls button {
            background: #0078d4;
            color: white;
            border: none;
            padding: 8px 15px;
            margin: 0 5px;
            border-radius: 5px;
            cursor: pointer;
            font-size: 0.9em;
        }
        
        .controls button:hover {
            background: #106ebe;
        }
        
        .graph-container {
            flex: 1;
            position: relative;
            background: white;
        }
        
        .graph-svg {
            width: 100%;
            height: 100%;
        }
        
        .node {
            cursor: pointer;
            stroke: #fff;
            stroke-width: 2px;
        }
        
        .node:hover {
            stroke: #000;
            stroke-width: 3px;
        }
        
        .link {
            fill: none;
            stroke-width: 2px;
            opacity: 0.6;
        }
        
        .link:hover {
            opacity: 1;
            stroke-width: 3px;
        }
        
        .node-label {
            font-size: 12px;
            font-weight: bold;
            text-anchor: middle;
            pointer-events: none;
            fill: #333;
        }
        
        .tooltip {
            position: absolute;
            background: rgba(0, 0, 0, 0.9);
            color: white;
            padding: 10px;
            border-radius: 5px;
            pointer-events: none;
            font-size: 12px;
            max-width: 300px;
            z-index: 1000;
        }
        
        .legend {
            position: absolute;
            top: 80px;
            left: 20px;
            background: rgba(255, 255, 255, 0.95);
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            z-index: 1000;
            max-height: 300px;
            overflow-y: auto;
        }
        
        .legend h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #333;
        }
        
        .legend-item {
            display: flex;
            align-items: center;
            margin: 5px 0;
            font-size: 12px;
        }
        
        .legend-color {
            width: 16px;
            height: 16px;
            border-radius: 50%;
            margin-right: 8px;
        }
        
        .stats {
            position: absolute;
            bottom: 20px;
            left: 20px;
            background: rgba(255, 255, 255, 0.95);
            padding: 15px;
            border-radius: 8px;
            box-shadow: 0 4px 15px rgba(0, 0, 0, 0.2);
            z-index: 1000;
        }
        
        .stats h3 {
            margin: 0 0 10px 0;
            font-size: 14px;
            color: #333;
        }
        
        .stats div {
            font-size: 12px;
            margin: 3px 0;
        }
    </style>
</head>
<body>
    <div class="container">
        <div class="header">
            <h1>🕸️ System Traceability Graph</h1>
            <div class="controls">
                <button onclick="resetZoom()">Reset View</button>
                <button onclick="toggleLabels()">Toggle Labels</button>
                <button onclick="toggleLegend()">Toggle Legend</button>
                <button onclick="exportGraph()">Export Data</button>
            </div>
        </div>
        
        <div class="graph-container">
            <svg class="graph-svg"></svg>
            
            <div class="legend" id="legend">
                <h3>Node Types</h3>
                <div class="legend-item">
                    <div class="legend-color" style="background: #4CAF50;"></div>
                    <span>Files</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #2196F3;"></div>
                    <span>Components</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #FF9800;"></div>
                    <span>Methods</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #9C27B0;"></div>
                    <span>Classes</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #F44336;"></div>
                    <span>API Endpoints</span>
                </div>
                <div class="legend-item">
                    <div class="legend-color" style="background: #607D8B;"></div>
                    <span>External Dependencies</span>
                </div>
            </div>
            
            <div class="stats" id="stats">
                <h3>Graph Statistics</h3>
                <div>Nodes: <span id="nodeCount">${graphData.nodes.length}</span></div>
                <div>Edges: <span id="edgeCount">${graphData.links.length}</span></div>
                <div>Files: <span id="fileCount">${graphData.nodes.filter(n => n.type === 'file').length}</span></div>
                <div>Components: <span id="componentCount">${graphData.nodes.filter(n => n.type === 'component').length}</span></div>
                <div>Methods: <span id="methodCount">${graphData.nodes.filter(n => n.type === 'method').length}</span></div>
            </div>
            
            <div class="tooltip" id="tooltip" style="display: none;"></div>
        </div>
    </div>

    <script>
        // Graph data
        const graphData = ${JSON.stringify(graphData, null, 2)};
        
        // D3.js graph visualization
        const svg = d3.select('.graph-svg');
        const width = window.innerWidth;
        const height = window.innerHeight - 60;
        
        svg.attr('width', width).attr('height', height);
        
        // Create zoom behavior
        const zoom = d3.zoom()
            .scaleExtent([0.1, 4])
            .on('zoom', (event) => {
                container.attr('transform', event.transform);
            });
        
        svg.call(zoom);
        
        // Create container for graph elements
        const container = svg.append('g');
        
        // Create force simulation
        const simulation = d3.forceSimulation(graphData.nodes)
            .force('link', d3.forceLink(graphData.links).id(d => d.id).distance(100))
            .force('charge', d3.forceManyBody().strength(-300))
            .force('center', d3.forceCenter(width / 2, height / 2))
            .force('collision', d3.forceCollide().radius(d => d.size + 5));
        
        // Create links
        const link = container.append('g')
            .selectAll('line')
            .data(graphData.links)
            .enter()
            .append('line')
            .attr('class', 'link')
            .attr('stroke', d => d.color)
            .on('mouseover', function(event, d) {
                showTooltip(event, \`
                    <strong>Relationship:</strong> \${d.relationship}<br>
                    <strong>From:</strong> \${d.sourceLabel} (\${d.sourceType})<br>
                    <strong>To:</strong> \${d.targetLabel} (\${d.targetType})
                \`);
            })
            .on('mouseout', hideTooltip);
        
        // Create nodes
        const node = container.append('g')
            .selectAll('circle')
            .data(graphData.nodes)
            .enter()
            .append('circle')
            .attr('class', 'node')
            .attr('r', d => d.size)
            .attr('fill', d => d.color)
            .on('mouseover', function(event, d) {
                showTooltip(event, \`
                    <strong>Label:</strong> \${d.label}<br>
                    <strong>Type:</strong> \${d.type}<br>
                    <strong>Group:</strong> \${d.group}<br>
                    <strong>ID:</strong> \${d.id}
                \`);
            })
            .on('mouseout', hideTooltip)
            .call(d3.drag()
                .on('start', dragStarted)
                .on('drag', dragged)
                .on('end', dragEnded));
        
        // Create labels
        let labelsVisible = true;
        const labels = container.append('g')
            .selectAll('text')
            .data(graphData.nodes)
            .enter()
            .append('text')
            .attr('class', 'node-label')
            .text(d => d.label.length > 20 ? d.label.substring(0, 20) + '...' : d.label);
        
        // Update positions on simulation tick
        simulation.on('tick', () => {
            link
                .attr('x1', d => d.source.x)
                .attr('y1', d => d.source.y)
                .attr('x2', d => d.target.x)
                .attr('y2', d => d.target.y);
            
            node
                .attr('cx', d => d.x)
                .attr('cy', d => d.y);
            
            labels
                .attr('x', d => d.x)
                .attr('y', d => d.y + 25);
        });
        
        // Drag functions
        function dragStarted(event, d) {
            if (!event.active) simulation.alphaTarget(0.3).restart();
            d.fx = d.x;
            d.fy = d.y;
        }
        
        function dragged(event, d) {
            d.fx = event.x;
            d.fy = event.y;
        }
        
        function dragEnded(event, d) {
            if (!event.active) simulation.alphaTarget(0);
            d.fx = null;
            d.fy = null;
        }
        
        // Tooltip functions
        function showTooltip(event, content) {
            const tooltip = d3.select('#tooltip');
            tooltip
                .style('display', 'block')
                .style('left', (event.pageX + 10) + 'px')
                .style('top', (event.pageY - 10) + 'px')
                .html(content);
        }
        
        function hideTooltip() {
            d3.select('#tooltip').style('display', 'none');
        }
        
        // Control functions
        function resetZoom() {
            svg.transition().duration(750).call(
                zoom.transform,
                d3.zoomIdentity
            );
        }
        
        function toggleLabels() {
            labelsVisible = !labelsVisible;
            labels.style('display', labelsVisible ? 'block' : 'none');
        }
        
        function toggleLegend() {
            const legend = document.getElementById('legend');
            legend.style.display = legend.style.display === 'none' ? 'block' : 'none';
        }
        
        function exportGraph() {
            const dataStr = JSON.stringify(graphData, null, 2);
            const dataBlob = new Blob([dataStr], {type: 'application/json'});
            const url = URL.createObjectURL(dataBlob);
            const link = document.createElement('a');
            link.href = url;
            link.download = 'traceability-graph.json';
            link.click();
        }
        
        // Handle window resize
        window.addEventListener('resize', () => {
            const newWidth = window.innerWidth;
            const newHeight = window.innerHeight - 60;
            svg.attr('width', newWidth).attr('height', newHeight);
            simulation.force('center', d3.forceCenter(newWidth / 2, newHeight / 2));
            simulation.alpha(0.3).restart();
        });
    </script>
</body>
</html>`;

        return html;
    }

    // Main execution
    async execute() {
        try {
            console.log('🚀 Starting traceability graph generation...');
            
            // Scan frontend files
            this.scanFrontendFiles();
            
            // Generate graph data
            const graphData = this.generateGraphData();
            
            console.log(`📊 Graph generated with ${graphData.nodes.length} nodes and ${graphData.links.length} edges`);
            
            // Create output directory
            const outputDir = 'TRACEABILITY_GRAPH';
            if (!fs.existsSync(outputDir)) {
                fs.mkdirSync(outputDir, { recursive: true });
            }
            
            // Generate visualization
            const htmlContent = this.generateVisualization(graphData);
            
            // Save files
            const htmlFile = path.join(outputDir, 'traceability-graph.html');
            const jsonFile = path.join(outputDir, 'graph-data.json');
            
            fs.writeFileSync(htmlFile, htmlContent);
            fs.writeFileSync(jsonFile, JSON.stringify(graphData, null, 2));
            
            console.log(`✅ Files created:`);
            console.log(`   📄 ${htmlFile} - Interactive visualization`);
            console.log(`   📊 ${jsonFile} - Graph data (NetworkX compatible)`);
            
            return {
                htmlFile: path.resolve(htmlFile),
                jsonFile: path.resolve(jsonFile),
                stats: {
                    nodes: graphData.nodes.length,
                    edges: graphData.links.length,
                    files: graphData.nodes.filter(n => n.type === 'file').length,
                    components: graphData.nodes.filter(n => n.type === 'component').length,
                    methods: graphData.nodes.filter(n => n.type === 'method').length
                }
            };
            
        } catch (error) {
            console.error('❌ Error generating traceability graph:', error.message);
            console.error(error.stack);
            throw error;
        }
    }
}

// Execute the generator
const generator = new TraceabilityGraphGenerator();
generator.execute()
    .then((result) => {
        console.log('\n🎉 TRACEABILITY GRAPH GENERATION COMPLETED!');
        console.log(`📈 Statistics:`);
        console.log(`   🔹 Nodes: ${result.stats.nodes}`);
        console.log(`   🔹 Edges: ${result.stats.edges}`);
        console.log(`   🔹 Files: ${result.stats.files}`);
        console.log(`   🔹 Components: ${result.stats.components}`);
        console.log(`   🔹 Methods: ${result.stats.methods}`);
        console.log(`\n🌐 Open: ${result.htmlFile}`);
    })
    .catch((error) => {
        console.error('\n💥 GENERATION FAILED:', error.message);
        process.exit(1);
    });
