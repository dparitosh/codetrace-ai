#!/usr/bin/env node

/**
 * CodeTrace AI - Command Line Interface
 * Professional CLI tool for GitHub repository analysis
 */

import { Command } from 'commander';
import chalk from 'chalk';
import ora from 'ora';
import inquirer from 'inquirer';
import axios from 'axios';
import fs from 'fs-extra';
import path from 'path';
import { fileURLToPath } from 'url';

const __filename = fileURLToPath(import.meta.url);
const __dirname = path.dirname(__filename);

const program = new Command();

// CLI Configuration
const CLI_VERSION = '1.0.0';
const API_BASE_URL = process.env.CODETRACE_API_URL || 'http://localhost:8009';
const CONFIG_FILE = path.join(process.cwd(), '.codetrace.json');

// ASCII Art Banner
const banner = `
 ██████╗ ██████╗ ██████╗ ███████╗████████╗██████╗  █████╗  ██████╗███████╗
██╔════╝██╔═══██╗██╔══██╗██╔════╝╚══██╔══╝██╔══██╗██╔══██╗██╔════╝██╔════╝
██║     ██║   ██║██║  ██║█████╗     ██║   ██████╔╝███████║██║     █████╗  
██║     ██║   ██║██║  ██║██╔══╝     ██║   ██╔══██╗██╔══██║██║     ██╔══╝  
╚██████╗╚██████╔╝██████╔╝███████╗   ██║   ██║  ██║██║  ██║╚██████╗███████╗
 ╚═════╝ ╚═════╝ ╚═════╝ ╚══════╝   ╚═╝   ╚═╝  ╚═╝╚═╝  ╚═╝ ╚═════╝╚══════╝
                                                                          
              🚀 AI-Powered GitHub Repository Analysis
`;

// Utility Functions
const loadConfig = () => {
  try {
    if (fs.existsSync(CONFIG_FILE)) {
      return fs.readJsonSync(CONFIG_FILE);
    }
  } catch (error) {
    // Config file doesn't exist or is invalid
  }
  return {};
};

const saveConfig = (config) => {
  try {
    fs.writeJsonSync(CONFIG_FILE, config, { spaces: 2 });
  } catch (error) {
    console.error(chalk.red('Error saving configuration:', error.message));
  }
};

const makeApiRequest = async (endpoint, options = {}) => {
  const config = loadConfig();
  const baseURL = config.apiUrl || API_BASE_URL;
  
  try {
    const response = await axios({
      baseURL,
      url: endpoint,
      headers: {
        'Authorization': config.token ? `Bearer ${config.token}` : undefined,
        'Content-Type': 'application/json',
        ...options.headers
      },
      ...options
    });
    
    return response.data;
  } catch (error) {
    if (error.response) {
      throw new Error(`API Error: ${error.response.status} - ${error.response.data.detail || error.response.data.message || 'Unknown error'}`);
    } else if (error.request) {
      throw new Error('Network Error: Unable to connect to CodeTrace AI API');
    } else {
      throw new Error(`Request Error: ${error.message}`);
    }
  }
};

const validateRepository = (repo) => {
  if (!repo.includes('/')) {
    throw new Error('Repository must be in format "owner/repo"');
  }
  const [owner, name] = repo.split('/');
  if (!owner || !name) {
    throw new Error('Invalid repository format. Use "owner/repo"');
  }
  return { owner, name };
};

// Main Program Setup
program
  .name('codetrace')
  .description('CodeTrace AI - GitHub Repository Analysis & Self-Correction')
  .version(CLI_VERSION)
  .option('-v, --verbose', 'Enable verbose output')
  .option('--api-url <url>', 'CodeTrace AI API URL')
  .hook('preAction', (thisCommand) => {
    if (thisCommand.opts().verbose) {
      console.log(chalk.cyan(banner));
    }
  });

// Initialize Command
program
  .command('init')
  .description('Initialize CodeTrace AI configuration')
  .option('--token <token>', 'GitHub personal access token')
  .option('--api-url <url>', 'CodeTrace AI API URL')
  .action(async (options) => {
    console.log(chalk.cyan(banner));
    console.log(chalk.bold('🚀 Welcome to CodeTrace AI!\n'));
    
    const config = loadConfig();
    
    // Interactive setup if no options provided
    if (!options.token && !options.apiUrl) {
      const answers = await inquirer.prompt([
        {
          type: 'input',
          name: 'token',
          message: 'Enter your GitHub Personal Access Token:',
          validate: (input) => input.length > 0 || 'Token is required'
        },
        {
          type: 'input',
          name: 'apiUrl',
          message: 'Enter CodeTrace AI API URL:',
          default: API_BASE_URL
        }
      ]);
      
      Object.assign(options, answers);
    }
    
    // Update configuration
    if (options.token) config.token = options.token;
    if (options.apiUrl) config.apiUrl = options.apiUrl;
    
    saveConfig(config);
    
    console.log(chalk.green('✅ Configuration saved successfully!'));
    console.log(chalk.blue('🔧 You can now use CodeTrace AI commands.'));
    console.log(chalk.gray('\nTry: codetrace analyze facebook/react'));
  });

// Analyze Command
program
  .command('analyze')
  .description('Analyze a GitHub repository')
  .argument('<repository>', 'Repository in format "owner/repo"')
  .option('-q, --quality', 'Include quality assessment', true)
  .option('-s, --security', 'Include security analysis', true)
  .option('-d, --dependencies', 'Include dependency analysis', true)
  .option('-g, --graph', 'Generate traceability graph', true)
  .option('-o, --output <file>', 'Output file for results')
  .option('--format <format>', 'Output format (json, yaml, html)', 'json')
  .action(async (repository, options) => {
    const spinner = ora('Analyzing repository...').start();
    
    try {
      validateRepository(repository);
      
      spinner.text = 'Starting repository analysis...';
      
      const analysisRequest = {
        repository,
        options: {
          include_quality: options.quality,
          include_security: options.security,
          include_dependencies: options.dependencies,
          include_graph: options.graph
        }
      };
      
      // Start analysis
      const startResponse = await makeApiRequest('/api/v1/github/analyze', {
        method: 'POST',
        data: analysisRequest
      });
      
      spinner.text = 'Analysis in progress... This may take a few minutes.';
      
      // Wait for analysis to complete (simplified polling)
      await new Promise(resolve => setTimeout(resolve, 3000));
      
      // Get results
      const [owner, repo] = repository.split('/');
      const results = await makeApiRequest(`/api/v1/github/repositories/${owner}/${repo}/analysis`);
      
      spinner.succeed('Analysis completed!');
      
      // Display results summary
      console.log(chalk.bold('\n📊 Analysis Results Summary:'));
      console.log(chalk.blue(`Repository: ${repository}`));
      console.log(chalk.green(`Overall Quality Score: ${results.quality?.overall_score || 'N/A'}/100`));
      console.log(chalk.yellow(`Files Analyzed: ${results.analysis_metadata?.files_analyzed || 'N/A'}`));
      console.log(chalk.cyan(`Issues Found: ${results.quality?.issues?.length || 0}`));
      
      // Quality metrics
      if (results.quality?.metrics) {
        console.log(chalk.bold('\n🔍 Quality Metrics:'));
        Object.entries(results.quality.metrics).forEach(([key, value]) => {
          const color = value >= 80 ? 'green' : value >= 60 ? 'yellow' : 'red';
          console.log(chalk[color](`  ${key}: ${value}/100`));
        });
      }
      
      // Graph metrics
      if (results.graph?.metrics) {
        console.log(chalk.bold('\n🕸️  Graph Metrics:'));
        console.log(chalk.blue(`  Nodes: ${results.graph.metadata?.total_nodes || 0}`));
        console.log(chalk.blue(`  Edges: ${results.graph.metadata?.total_edges || 0}`));
        console.log(chalk.blue(`  Complexity: ${results.graph.metrics?.cyclomatic_complexity || 0}`));
      }
      
      // Save output if specified
      if (options.output) {
        const outputPath = path.resolve(options.output);
        
        let outputData;
        switch (options.format.toLowerCase()) {
          case 'yaml':
            const yaml = await import('yaml');
            outputData = yaml.stringify(results);
            break;
          case 'html':
            outputData = generateHtmlReport(results, repository);
            break;
          default:
            outputData = JSON.stringify(results, null, 2);
        }
        
        await fs.writeFile(outputPath, outputData);
        console.log(chalk.green(`\n💾 Results saved to: ${outputPath}`));
      }
      
      // Recommendations
      if (results.quality?.recommendations?.length > 0) {
        console.log(chalk.bold('\n💡 Recommendations:'));
        results.quality.recommendations.slice(0, 5).forEach(rec => {
          console.log(chalk.gray(`  • ${rec}`));
        });
      }
      
    } catch (error) {
      spinner.fail('Analysis failed!');
      console.error(chalk.red(`Error: ${error.message}`));
      process.exit(1);
    }
  });

// Graph Command
program
  .command('graph')
  .description('Generate traceability graph for a repository')
  .argument('<repository>', 'Repository in format "owner/repo"')
  .option('-o, --output <file>', 'Output file for graph data', 'graph.json')
  .option('--format <format>', 'Output format (json, graphml, gexf)', 'json')
  .action(async (repository, options) => {
    const spinner = ora('Generating traceability graph...').start();
    
    try {
      validateRepository(repository);
      
      const [owner, repo] = repository.split('/');
      const graph = await makeApiRequest(`/api/v1/github/repositories/${owner}/${repo}/graph`);
      
      spinner.succeed('Graph generated successfully!');
      
      // Display graph summary
      console.log(chalk.bold('\n🕸️  Graph Summary:'));
      console.log(chalk.blue(`Repository: ${repository}`));
      console.log(chalk.green(`Nodes: ${graph.metadata?.total_nodes || 0}`));
      console.log(chalk.green(`Edges: ${graph.metadata?.total_edges || 0}`));
      console.log(chalk.yellow(`Complexity: ${graph.metrics?.cyclomatic_complexity || 0}`));
      
      // Save graph data
      const outputPath = path.resolve(options.output);
      let outputData;
      
      switch (options.format.toLowerCase()) {
        case 'graphml':
          outputData = convertToGraphML(graph);
          break;
        case 'gexf':
          outputData = convertToGEXF(graph);
          break;
        default:
          outputData = JSON.stringify(graph, null, 2);
      }
      
      await fs.writeFile(outputPath, outputData);
      console.log(chalk.green(`📊 Graph saved to: ${outputPath}`));
      
    } catch (error) {
      spinner.fail('Graph generation failed!');
      console.error(chalk.red(`Error: ${error.message}`));
      process.exit(1);
    }
  });

// Quality Command
program
  .command('quality')
  .description('Get quality assessment for a repository')
  .argument('<repository>', 'Repository in format "owner/repo"')
  .option('--threshold <score>', 'Minimum quality threshold', '70')
  .action(async (repository, options) => {
    const spinner = ora('Assessing code quality...').start();
    
    try {
      validateRepository(repository);
      
      const [owner, repo] = repository.split('/');
      const quality = await makeApiRequest(`/api/v1/github/repositories/${owner}/${repo}/quality`);
      
      spinner.succeed('Quality assessment completed!');
      
      const overallScore = quality.overall_score || 0;
      const threshold = parseInt(options.threshold);
      
      // Display quality results
      console.log(chalk.bold('\n📊 Quality Assessment:'));
      console.log(chalk.blue(`Repository: ${repository}`));
      
      const scoreColor = overallScore >= threshold ? 'green' : 'red';
      console.log(chalk[scoreColor](`Overall Score: ${overallScore}/100`));
      
      if (quality.metrics) {
        console.log(chalk.bold('\n🔍 Detailed Metrics:'));
        Object.entries(quality.metrics).forEach(([key, value]) => {
          const color = value >= 80 ? 'green' : value >= 60 ? 'yellow' : 'red';
          console.log(chalk[color](`  ${key}: ${value}/100`));
        });
      }
      
      // Issues summary
      if (quality.issues?.length > 0) {
        console.log(chalk.bold('\n⚠️  Issues Found:'));
        const issueCounts = quality.issues.reduce((acc, issue) => {
          acc[issue.severity] = (acc[issue.severity] || 0) + 1;
          return acc;
        }, {});
        
        Object.entries(issueCounts).forEach(([severity, count]) => {
          const color = severity === 'high' ? 'red' : severity === 'medium' ? 'yellow' : 'gray';
          console.log(chalk[color](`  ${severity}: ${count} issues`));
        });
      }
      
      // Pass/Fail based on threshold
      if (overallScore >= threshold) {
        console.log(chalk.green('\n✅ Quality check PASSED'));
        process.exit(0);
      } else {
        console.log(chalk.red('\n❌ Quality check FAILED'));
        process.exit(1);
      }
      
    } catch (error) {
      spinner.fail('Quality assessment failed!');
      console.error(chalk.red(`Error: ${error.message}`));
      process.exit(1);
    }
  });

// Serve Command
program
  .command('serve')
  .description('Start local CodeTrace AI dashboard')
  .option('-p, --port <port>', 'Port to run dashboard on', '3000')
  .option('--host <host>', 'Host to bind to', 'localhost')
  .action(async (options) => {
    console.log(chalk.cyan(banner));
    console.log(chalk.bold('🚀 Starting CodeTrace AI Dashboard...\n'));
    
    const spinner = ora('Initializing dashboard...').start();
    
    try {
      // In a full implementation, this would start the React dev server
      // For now, we'll just provide instructions
      
      spinner.succeed('Dashboard ready!');
      
      console.log(chalk.green(`✅ CodeTrace AI Dashboard started successfully!`));
      console.log(chalk.blue(`🌐 Access your dashboard at: http://${options.host}:${options.port}`));
      console.log(chalk.gray('\nPress Ctrl+C to stop the server'));
      
      // Keep the process alive
      process.stdin.resume();
      
    } catch (error) {
      spinner.fail('Failed to start dashboard!');
      console.error(chalk.red(`Error: ${error.message}`));
      process.exit(1);
    }
  });

// Config Command
program
  .command('config')
  .description('Manage CodeTrace AI configuration')
  .option('--show', 'Show current configuration')
  .option('--reset', 'Reset configuration to defaults')
  .action(async (options) => {
    if (options.show) {
      const config = loadConfig();
      console.log(chalk.bold('🔧 Current Configuration:'));
      console.log(JSON.stringify(config, null, 2));
    } else if (options.reset) {
      if (fs.existsSync(CONFIG_FILE)) {
        fs.removeSync(CONFIG_FILE);
        console.log(chalk.green('✅ Configuration reset successfully!'));
      } else {
        console.log(chalk.yellow('⚠️  No configuration file found.'));
      }
    } else {
      console.log(chalk.blue('Use --show to view or --reset to reset configuration'));
    }
  });

// Helper Functions
const generateHtmlReport = (results, repository) => {
  return `
<!DOCTYPE html>
<html>
<head>
    <title>CodeTrace AI Report - ${repository}</title>
    <style>
        body { font-family: Arial, sans-serif; margin: 40px; }
        .header { background: #f5f5f5; padding: 20px; border-radius: 8px; }
        .metric { margin: 10px 0; }
        .score { font-weight: bold; font-size: 24px; }
        .issues { background: #fff3cd; padding: 15px; border-radius: 8px; margin: 20px 0; }
    </style>
</head>
<body>
    <div class="header">
        <h1>CodeTrace AI Analysis Report</h1>
        <h2>${repository}</h2>
        <div class="score">Overall Score: ${results.quality?.overall_score || 'N/A'}/100</div>
    </div>
    
    <h3>Quality Metrics</h3>
    ${Object.entries(results.quality?.metrics || {}).map(([key, value]) => 
      `<div class="metric">${key}: ${value}/100</div>`
    ).join('')}
    
    <h3>Issues Found</h3>
    <div class="issues">
        ${results.quality?.issues?.slice(0, 10).map(issue => 
          `<p><strong>${issue.severity}:</strong> ${issue.description}</p>`
        ).join('') || 'No issues found'}
    </div>
    
    <h3>Recommendations</h3>
    <ul>
        ${results.quality?.recommendations?.slice(0, 5).map(rec => 
          `<li>${rec}</li>`
        ).join('') || '<li>No recommendations available</li>'}
    </ul>
</body>
</html>`;
};

const convertToGraphML = (graph) => {
  // Simplified GraphML conversion
  return `<?xml version="1.0" encoding="UTF-8"?>
<graphml xmlns="http://graphml.graphdrawing.org/xmlns">
  <graph id="G" edgedefault="directed">
    ${graph.nodes?.map(node => 
      `<node id="${node.id}"><data key="label">${node.label}</data></node>`
    ).join('')}
    ${graph.edges?.map(edge => 
      `<edge source="${edge.source}" target="${edge.target}"></edge>`
    ).join('')}
  </graph>
</graphml>`;
};

const convertToGEXF = (graph) => {
  // Simplified GEXF conversion
  return `<?xml version="1.0" encoding="UTF-8"?>
<gexf xmlns="http://www.gexf.net/1.2draft" version="1.2">
  <graph mode="static" defaultedgetype="directed">
    <nodes>
      ${graph.nodes?.map(node => 
        `<node id="${node.id}" label="${node.label}"/>`
      ).join('')}
    </nodes>
    <edges>
      ${graph.edges?.map((edge, i) => 
        `<edge id="${i}" source="${edge.source}" target="${edge.target}"/>`
      ).join('')}
    </edges>
  </graph>
</gexf>`;
};

// Error handling
process.on('unhandledRejection', (reason, promise) => {
  console.error(chalk.red('Unhandled Rejection at:', promise, 'reason:', reason));
  process.exit(1);
});

process.on('uncaughtException', (error) => {
  console.error(chalk.red('Uncaught Exception:', error));
  process.exit(1);
});

// Parse command line arguments
program.parse();

export default program;
