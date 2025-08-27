import React, { useEffect, useState } from 'react';
import {
    Bar,
    BarChart,
    CartesianGrid,
    Cell,
    Pie,
    PieChart,
    ResponsiveContainer,
    Tooltip,
    XAxis, YAxis
} from 'recharts';
import { Alert, AlertDescription } from '../ui/alert';
import { Badge } from '../ui/badge';
import { Button } from '../ui/button';
import { Card, CardContent, CardHeader, CardTitle } from '../ui/card';
import { Input } from '../ui/input';
import { Progress } from '../ui/progress';

interface MCPAnalysisData {
  repository: {
    url: string;
    analyzed_at: string;
    status: string;
  };
  overview: {
    total_files: number;
    languages: Record<string, number>;
    complexity_score: number;
    health_score: number;
  };
  quality_metrics: {
    overall_score: number;
    maintainability: number;
    reliability: number;
    security: number;
    test_coverage: number;
    code_duplication: number;
  };
  recommendations: Array<{
    type: string;
    priority: string;
    title: string;
    description: string;
    action: string;
  }>;
  visualizations: {
    complexity_heatmap: { files: string[]; scores: number[] };
    dependency_graph: { nodes: any[]; links: any[] };
    quality_trends: { dates: string[]; scores: number[] };
    language_distribution: { labels: string[]; values: number[] };
  };
}

interface FileInsight {
  file_path: string;
  language: string;
  complexity: Record<string, any>;
  quality_score: number;
  dependencies: string[];
  symbols: any[];
  recommendations: string[];
}

const MCPIntegratedDashboard: React.FC = () => {
  const [repositoryUrl, setRepositoryUrl] = useState('');
  const [analysisData, setAnalysisData] = useState<MCPAnalysisData | null>(null);
  const [fileInsights, setFileInsights] = useState<FileInsight | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [selectedFile, setSelectedFile] = useState('');
  const [liveProgress, setLiveProgress] = useState(0);
  const [wsConnected, setWsConnected] = useState(false);

  // WebSocket for real-time updates
  useEffect(() => {
    const ws = new WebSocket('ws://localhost:8009/api/v1/mcp/frontend/live-analysis');
    
    ws.onopen = () => {
      setWsConnected(true);
      console.log('Connected to MCP WebSocket');
    };
    
    ws.onmessage = (event) => {
      const data = JSON.parse(event.data);
      
      if (data.progress) {
        setLiveProgress(data.progress);
      }
      
      if (data.status === 'completed' && data.data) {
        setAnalysisData(data.data);
        setLoading(false);
      }
      
      if (data.status === 'error') {
        setError(data.error);
        setLoading(false);
      }
    };
    
    ws.onclose = () => {
      setWsConnected(false);
      console.log('Disconnected from MCP WebSocket');
    };
    
    return () => ws.close();
  }, []);

  const analyzeRepository = async () => {
    if (!repositoryUrl) return;
    
    setLoading(true);
    setError(null);
    setLiveProgress(0);
    
    try {
      // Use WebSocket for real-time updates if available
      if (wsConnected) {
        const ws = new WebSocket('ws://localhost:8009/api/v1/mcp/frontend/live-analysis');
        ws.send(JSON.stringify({ repository_url: repositoryUrl }));
      } else {
        // Fallback to HTTP API
        const response = await fetch('/api/v1/mcp/frontend/repository-analysis', {
          method: 'POST',
          headers: { 'Content-Type': 'application/json' },
          body: JSON.stringify({ repository_url: repositoryUrl })
        });
        
        const result = await response.json();
        
        if (result.success) {
          setAnalysisData(result.data);
        } else {
          setError('Analysis failed');
        }
        
        setLoading(false);
      }
    } catch (err) {
      setError('Failed to analyze repository');
      setLoading(false);
    }
  };

  const analyzeFile = async () => {
    if (!repositoryUrl || !selectedFile) return;
    
    try {
      const response = await fetch('/api/v1/mcp/frontend/file-insights', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          repository_url: repositoryUrl,
          file_path: selectedFile
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        setFileInsights(result.data);
      }
    } catch (err) {
      setError('Failed to analyze file');
    }
  };

  const generateAIPrompt = async (promptType: string) => {
    try {
      const response = await fetch('/api/v1/mcp/frontend/ai-prompt', {
        method: 'POST',
        headers: { 'Content-Type': 'application/json' },
        body: JSON.stringify({
          prompt_type: promptType,
          repository_url: repositoryUrl,
          file_path: selectedFile
        })
      });
      
      const result = await response.json();
      
      if (result.success) {
        // Copy prompt to clipboard or open in AI tool
        navigator.clipboard.writeText(
          result.data.generated_prompt.map((msg: any) => msg.content.text).join('\n')
        );
        alert('AI prompt copied to clipboard!');
      }
    } catch (err) {
      setError('Failed to generate AI prompt');
    }
  };

  const COLORS = ['#0088FE', '#00C49F', '#FFBB28', '#FF8042', '#8884D8'];

  return (
    <div className="container mx-auto p-6 space-y-6">
      {/* Header */}
      <div className="flex items-center justify-between">
        <h1 className="text-3xl font-bold">MCP-Powered Code Analysis</h1>
        <Badge variant={wsConnected ? "default" : "secondary"}>
          {wsConnected ? "Live Updates" : "HTTP Mode"}
        </Badge>
      </div>

      {/* Repository Input */}
      <Card>
        <CardHeader>
          <CardTitle>Repository Analysis</CardTitle>
        </CardHeader>
        <CardContent>
          <div className="flex gap-4">
            <Input
              placeholder="https://github.com/owner/repo"
              value={repositoryUrl}
              onChange={(e) => setRepositoryUrl(e.target.value)}
              className="flex-1"
            />
            <Button onClick={analyzeRepository} disabled={loading}>
              {loading ? 'Analyzing...' : 'Analyze with MCP'}
            </Button>
          </div>
          
          {loading && (
            <div className="mt-4">
              <Progress value={liveProgress} className="w-full" />
              <p className="text-sm text-gray-600 mt-2">
                Analysis in progress... {liveProgress}%
              </p>
            </div>
          )}
        </CardContent>
      </Card>

      {/* Error Display */}
      {error && (
        <Alert variant="destructive">
          <AlertDescription>{error}</AlertDescription>
        </Alert>
      )}

      {/* Analysis Results */}
      {analysisData && (
        <div className="grid grid-cols-1 lg:grid-cols-2 xl:grid-cols-3 gap-6">
          
          {/* Overview Metrics */}
          <Card>
            <CardHeader>
              <CardTitle>Repository Overview</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <div className="grid grid-cols-2 gap-4">
                  <div className="text-center">
                    <p className="text-2xl font-bold text-blue-600">
                      {analysisData.overview.total_files}
                    </p>
                    <p className="text-sm text-gray-600">Total Files</p>
                  </div>
                  <div className="text-center">
                    <p className="text-2xl font-bold text-green-600">
                      {analysisData.overview.health_score}
                    </p>
                    <p className="text-sm text-gray-600">Health Score</p>
                  </div>
                </div>
                
                <div className="text-center">
                  <p className="text-2xl font-bold text-purple-600">
                    {analysisData.overview.complexity_score}
                  </p>
                  <p className="text-sm text-gray-600">Complexity Score</p>
                </div>
              </div>
            </CardContent>
          </Card>

          {/* Quality Metrics Chart */}
          <Card>
            <CardHeader>
              <CardTitle>Quality Metrics</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <BarChart data={[
                  { name: 'Overall', value: analysisData.quality_metrics.overall_score },
                  { name: 'Maintain', value: analysisData.quality_metrics.maintainability },
                  { name: 'Reliable', value: analysisData.quality_metrics.reliability },
                  { name: 'Security', value: analysisData.quality_metrics.security },
                  { name: 'Tests', value: analysisData.quality_metrics.test_coverage }
                ]}>
                  <CartesianGrid strokeDasharray="3 3" />
                  <XAxis dataKey="name" />
                  <YAxis domain={[0, 100]} />
                  <Tooltip />
                  <Bar dataKey="value" fill="#8884d8" />
                </BarChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Language Distribution */}
          <Card>
            <CardHeader>
              <CardTitle>Language Distribution</CardTitle>
            </CardHeader>
            <CardContent>
              <ResponsiveContainer width="100%" height={200}>
                <PieChart>
                  <Pie
                    data={Object.entries(analysisData.overview.languages).map(([lang, count]) => ({
                      name: lang,
                      value: count
                    }))}
                    cx="50%"
                    cy="50%"
                    outerRadius={80}
                    dataKey="value"
                  >
                    {Object.keys(analysisData.overview.languages).map((_, index) => (
                      <Cell key={`cell-${index}`} fill={COLORS[index % COLORS.length]} />
                    ))}
                  </Pie>
                  <Tooltip />
                </PieChart>
              </ResponsiveContainer>
            </CardContent>
          </Card>

          {/* Recommendations */}
          <Card className="lg:col-span-2">
            <CardHeader>
              <CardTitle>MCP-Generated Recommendations</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-3">
                {analysisData.recommendations.map((rec, index) => (
                  <div key={index} className="border rounded-lg p-4">
                    <div className="flex items-center justify-between mb-2">
                      <h4 className="font-semibold">{rec.title}</h4>
                      <Badge variant={rec.priority === 'high' ? 'destructive' : 'secondary'}>
                        {rec.priority}
                      </Badge>
                    </div>
                    <p className="text-sm text-gray-600 mb-2">{rec.description}</p>
                    <p className="text-sm font-medium text-blue-600">{rec.action}</p>
                  </div>
                ))}
              </div>
            </CardContent>
          </Card>

          {/* File Analysis */}
          <Card>
            <CardHeader>
              <CardTitle>File Analysis</CardTitle>
            </CardHeader>
            <CardContent>
              <div className="space-y-4">
                <Input
                  placeholder="src/main.py"
                  value={selectedFile}
                  onChange={(e) => setSelectedFile(e.target.value)}
                />
                <Button onClick={analyzeFile} className="w-full">
                  Analyze File with MCP
                </Button>
                
                {fileInsights && (
                  <div className="space-y-2">
                    <p><strong>Language:</strong> {fileInsights.language}</p>
                    <p><strong>Quality Score:</strong> {fileInsights.quality_score}/100</p>
                    <p><strong>Dependencies:</strong> {fileInsights.dependencies.length}</p>
                  </div>
                )}
              </div>
            </CardContent>
          </Card>
        </div>
      )}

      {/* AI Integration */}
      {analysisData && (
        <Card>
          <CardHeader>
            <CardTitle>AI-Powered Assistance</CardTitle>
          </CardHeader>
          <CardContent>
            <div className="flex gap-4">
              <Button onClick={() => generateAIPrompt('code_review')}>
                Generate Code Review Prompt
              </Button>
              <Button onClick={() => generateAIPrompt('explain_code')}>
                Generate Code Explanation
              </Button>
              <Button onClick={() => generateAIPrompt('suggest_improvements')}>
                Generate Improvement Suggestions
              </Button>
            </div>
            <p className="text-sm text-gray-600 mt-2">
              Prompts will be copied to clipboard for use with your preferred AI tool
            </p>
          </CardContent>
        </Card>
      )}
    </div>
  );
};

export default MCPIntegratedDashboard;
