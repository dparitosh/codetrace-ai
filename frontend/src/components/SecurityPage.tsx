import { AlertTriangle, BarChart, CheckCircle, Download, FileText, Search, Shield } from 'lucide-react';
import React, { useState } from 'react';
import { API_CONFIG } from '../config/api';

interface CVSSVulnerability {
  cve_id: string;
  cvss_base_score: number;
  cvss_severity: string;
  cvss_vector: string;
  description: string;
  affected_components: string[];
}

interface CVSSResponse {
  scan_id: string;
  repository_url: string;
  total_vulnerabilities: number;
  critical_count: number;
  high_count: number;
  medium_count: number;
  low_count: number;
  overall_risk_score: number;
  vulnerabilities: CVSSVulnerability[];
}

interface SBOMComponent {
  name: string;
  version: string;
  component_type: string;
  license: string | null;
  supplier: string | null;
  vulnerabilities: string[];
}

interface SBOMResponse {
  sbom_id: string;
  format: string;
  version: string;
  generated_at: string;
  total_components: number;
  components: SBOMComponent[];
  metadata: Record<string, any>;
}

interface ComplianceDashboard {
  repository_url: string;
  last_updated: string;
  compliance_score: number;
  security_posture: {
    cvss_scan: {
      last_scan: string;
      total_vulnerabilities: number;
      critical: number;
      high: number;
      medium: number;
      low: number;
      risk_score: number;
    };
    sbom_compliance: {
      generated: boolean;
      format: string;
      total_components: number;
      components_with_vulnerabilities: number;
      license_compliance_rate: number;
    };
    spdx_compliance: {
      document_exists: boolean;
      spdx_version: string;
      validation_status: string;
      packages_documented: number;
      relationships_mapped: number;
    };
  };
  license_analysis: {
    total_licenses: number;
    permissive_licenses: number;
    copyleft_licenses: number;
    proprietary_licenses: number;
    unknown_licenses: number;
    compliance_issues: number;
  };
  recommendations: string[];
}

const SecurityPage: React.FC = () => {
  const [repositoryUrl, setRepositoryUrl] = useState('');
  const [cvssResults, setCvssResults] = useState<CVSSResponse | null>(null);
  const [sbomResults, setSbomResults] = useState<SBOMResponse | null>(null);
  const [dashboard, setDashboard] = useState<ComplianceDashboard | null>(null);
  const [loading, setLoading] = useState(false);
  const [error, setError] = useState<string | null>(null);
  const [activeTab, setActiveTab] = useState<'dashboard' | 'cvss' | 'sbom' | 'spdx'>('dashboard');

  const validateRepositoryUrl = (url: string): boolean => {
    const githubUrlPattern = /^https:\/\/github\.com\/[\w\-\.]+\/[\w\-\.]+(\/(tree|blob)\/[\w\-\.\/]+)?\/?$/;
    return githubUrlPattern.test(url.trim());
  };

  const getSeverityColor = (severity: string): string => {
    switch (severity.toLowerCase()) {
      case 'critical': return 'text-red-800 bg-red-100';
      case 'high': return 'text-orange-800 bg-orange-100';
      case 'medium': return 'text-yellow-800 bg-yellow-100';
      case 'low': return 'text-green-800 bg-green-100';
      default: return 'text-gray-800 bg-gray-100';
    }
  };

  const getScoreColor = (score: number): string => {
    if (score >= 90) return 'text-green-600';
    if (score >= 70) return 'text-yellow-600';
    if (score >= 50) return 'text-orange-600';
    return 'text-red-600';
  };

  const fetchComplianceDashboard = async () => {
    if (!validateRepositoryUrl(repositoryUrl)) {
      setError('Please enter a valid GitHub repository URL');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(API_CONFIG.SECURITY.COMPLIANCE(repositoryUrl));
      
      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setDashboard(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to fetch compliance dashboard');
    } finally {
      setLoading(false);
    }
  };

  const runCVSSScan = async () => {
    if (!validateRepositoryUrl(repositoryUrl)) {
      setError('Please enter a valid GitHub repository URL');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(API_CONFIG.SECURITY.CVSS_SCAN, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repository_url: repositoryUrl,
          scan_type: 'comprehensive',
          include_transitive: true
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setCvssResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to run CVSS scan');
    } finally {
      setLoading(false);
    }
  };

  const generateSBOM = async () => {
    if (!validateRepositoryUrl(repositoryUrl)) {
      setError('Please enter a valid GitHub repository URL');
      return;
    }

    setLoading(true);
    setError(null);

    try {
      const response = await fetch(API_CONFIG.SECURITY.SBOM_GENERATE, {
        method: 'POST',
        headers: {
          'Content-Type': 'application/json',
        },
        body: JSON.stringify({
          repository_url: repositoryUrl,
          sbom_format: 'CycloneDX',
          include_dev_dependencies: false,
          include_vulnerabilities: true
        }),
      });

      if (!response.ok) {
        throw new Error(`HTTP ${response.status}: ${response.statusText}`);
      }

      const data = await response.json();
      setSbomResults(data);
    } catch (err) {
      setError(err instanceof Error ? err.message : 'Failed to generate SBOM');
    } finally {
      setLoading(false);
    }
  };

  const renderDashboard = () => (
    <div className="space-y-6">
      {/* Compliance Score Overview */}
      <div className="bg-white rounded-lg shadow-md p-6">
        <div className="flex items-center justify-between mb-4">
          <h3 className="text-lg font-semibold text-gray-900">Compliance Overview</h3>
          <div className={`text-2xl font-bold ${getScoreColor(dashboard?.compliance_score || 0)}`}>
            {dashboard?.compliance_score}%
          </div>
        </div>
        
        <div className="grid grid-cols-1 md:grid-cols-3 gap-4">
          {/* Security Posture */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center mb-2">
              <Shield className="w-5 h-5 text-blue-500 mr-2" />
              <h4 className="font-medium text-gray-900">Security Posture</h4>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Vulnerabilities:</span>
                <span className="font-medium">{dashboard?.security_posture.cvss_scan.total_vulnerabilities}</span>
              </div>
              <div className="flex justify-between">
                <span>Risk Score:</span>
                <span className={`font-medium ${(dashboard?.security_posture.cvss_scan.risk_score ?? 0) >= 7 ? 'text-red-600' : 'text-green-600'}`}>
                  {dashboard?.security_posture.cvss_scan.risk_score}
                </span>
              </div>
            </div>
          </div>

          {/* SBOM Compliance */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center mb-2">
              <FileText className="w-5 h-5 text-green-500 mr-2" />
              <h4 className="font-medium text-gray-900">SBOM Compliance</h4>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Components:</span>
                <span className="font-medium">{dashboard?.security_posture.sbom_compliance.total_components}</span>
              </div>
              <div className="flex justify-between">
                <span>License Rate:</span>
                <span className="font-medium text-green-600">{dashboard?.security_posture.sbom_compliance.license_compliance_rate}%</span>
              </div>
            </div>
          </div>

          {/* License Analysis */}
          <div className="bg-gray-50 rounded-lg p-4">
            <div className="flex items-center mb-2">
              <CheckCircle className="w-5 h-5 text-purple-500 mr-2" />
              <h4 className="font-medium text-gray-900">License Analysis</h4>
            </div>
            <div className="space-y-2 text-sm">
              <div className="flex justify-between">
                <span>Total Licenses:</span>
                <span className="font-medium">{dashboard?.license_analysis.total_licenses}</span>
              </div>
              <div className="flex justify-between">
                <span>Issues:</span>
                <span className={`font-medium ${(dashboard?.license_analysis.compliance_issues ?? 0) > 0 ? 'text-red-600' : 'text-green-600'}`}>
                  {dashboard?.license_analysis.compliance_issues}
                </span>
              </div>
            </div>
          </div>
        </div>
      </div>

      {/* Recommendations */}
      {dashboard?.recommendations && dashboard.recommendations.length > 0 && (
        <div className="bg-white rounded-lg shadow-md p-6">
          <h3 className="text-lg font-semibold text-gray-900 mb-4">Recommendations</h3>
          <ul className="space-y-2">
            {dashboard.recommendations.map((rec, index) => (
              <li key={index} className="flex items-start">
                <AlertTriangle className="w-4 h-4 text-yellow-500 mt-0.5 mr-2 flex-shrink-0" />
                <span className="text-gray-700">{rec}</span>
              </li>
            ))}
          </ul>
        </div>
      )}
    </div>
  );

  const renderCVSSResults = () => (
    <div className="space-y-6">
      {cvssResults && (
        <>
          {/* CVSS Summary */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Vulnerability Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-5 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-red-600">{cvssResults.critical_count}</div>
                <div className="text-sm text-gray-600">Critical</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-orange-600">{cvssResults.high_count}</div>
                <div className="text-sm text-gray-600">High</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-yellow-600">{cvssResults.medium_count}</div>
                <div className="text-sm text-gray-600">Medium</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-green-600">{cvssResults.low_count}</div>
                <div className="text-sm text-gray-600">Low</div>
              </div>
              <div className="text-center">
                <div className="text-2xl font-bold text-gray-900">{cvssResults.overall_risk_score}</div>
                <div className="text-sm text-gray-600">Risk Score</div>
              </div>
            </div>
          </div>

          {/* Vulnerability Details */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Vulnerability Details</h3>
            <div className="space-y-4">
              {cvssResults.vulnerabilities.map((vuln, index) => (
                <div key={index} className="border rounded-lg p-4">
                  <div className="flex items-start justify-between mb-2">
                    <div>
                      <h4 className="font-medium text-gray-900">{vuln.cve_id}</h4>
                      <p className="text-sm text-gray-600 mt-1">{vuln.description}</p>
                    </div>
                    <div className="flex items-center space-x-2">
                      <span className={`px-2 py-1 rounded text-xs font-medium ${getSeverityColor(vuln.cvss_severity)}`}>
                        {vuln.cvss_severity}
                      </span>
                      <span className="text-sm font-medium text-gray-900">{vuln.cvss_base_score}</span>
                    </div>
                  </div>
                  <div className="text-xs text-gray-500 mb-2">
                    Vector: {vuln.cvss_vector}
                  </div>
                  <div className="text-sm">
                    <span className="font-medium">Affected Components:</span>
                    <div className="mt-1 flex flex-wrap gap-1">
                      {vuln.affected_components.map((comp, idx) => (
                        <span key={idx} className="px-2 py-1 bg-gray-100 rounded text-xs">
                          {comp}
                        </span>
                      ))}
                    </div>
                  </div>
                </div>
              ))}
            </div>
          </div>
        </>
      )}
    </div>
  );

  const renderSBOMResults = () => (
    <div className="space-y-6">
      {sbomResults && (
        <>
          {/* SBOM Summary */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">SBOM Summary</h3>
            <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
              <div className="text-center">
                <div className="text-2xl font-bold text-blue-600">{sbomResults.total_components}</div>
                <div className="text-sm text-gray-600">Components</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-medium text-gray-900">{sbomResults.format}</div>
                <div className="text-sm text-gray-600">Format</div>
              </div>
              <div className="text-center">
                <div className="text-lg font-medium text-gray-900">{sbomResults.version}</div>
                <div className="text-sm text-gray-600">Version</div>
              </div>
              <div className="text-center">
                <div className="text-sm font-medium text-gray-900">
                  {new Date(sbomResults.generated_at).toLocaleDateString()}
                </div>
                <div className="text-sm text-gray-600">Generated</div>
              </div>
            </div>
          </div>

          {/* Component Details */}
          <div className="bg-white rounded-lg shadow-md p-6">
            <h3 className="text-lg font-semibold text-gray-900 mb-4">Components</h3>
            <div className="overflow-x-auto">
              <table className="min-w-full table-auto">
                <thead>
                  <tr className="bg-gray-50">
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Name</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Version</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">License</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Supplier</th>
                    <th className="px-4 py-2 text-left text-sm font-medium text-gray-900">Vulnerabilities</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {sbomResults.components.map((comp, index) => (
                    <tr key={index}>
                      <td className="px-4 py-2 text-sm font-medium text-gray-900">{comp.name}</td>
                      <td className="px-4 py-2 text-sm text-gray-700">{comp.version}</td>
                      <td className="px-4 py-2 text-sm text-gray-700">{comp.license || 'N/A'}</td>
                      <td className="px-4 py-2 text-sm text-gray-700">{comp.supplier || 'N/A'}</td>
                      <td className="px-4 py-2 text-sm">
                        {comp.vulnerabilities.length > 0 ? (
                          <span className="px-2 py-1 bg-red-100 text-red-800 rounded text-xs">
                            {comp.vulnerabilities.length} issues
                          </span>
                        ) : (
                          <span className="px-2 py-1 bg-green-100 text-green-800 rounded text-xs">
                            Clean
                          </span>
                        )}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          </div>
        </>
      )}
    </div>
  );

  return (
    <div className="min-h-screen bg-gray-50 p-6">
      <div className="max-w-7xl mx-auto">
        {/* Header */}
        <div className="bg-white rounded-lg shadow-md p-6 mb-6">
          <div className="flex items-center justify-between mb-4">
            <div>
              <h1 className="text-2xl font-bold text-gray-900 flex items-center">
                <Shield className="w-8 h-8 text-blue-500 mr-3" />
                Security & Compliance
              </h1>
              <p className="text-gray-600 mt-2">
                Comprehensive security assessment with CVSS vulnerability scanning, SBOM generation, and SPDX compliance
              </p>
            </div>
          </div>
          
          {/* Repository URL Input */}
          <div className="flex flex-col sm:flex-row gap-4">
            <div className="flex-1">
              <input
                type="url"
                value={repositoryUrl}
                onChange={(e) => setRepositoryUrl(e.target.value)}
                placeholder="Enter GitHub repository URL (e.g., https://github.com/owner/repo)"
                className="w-full px-4 py-2 border border-gray-300 rounded-lg focus:ring-2 focus:ring-blue-500 focus:border-transparent"
              />
            </div>
            <button
              onClick={fetchComplianceDashboard}
              disabled={loading || !repositoryUrl.trim()}
              className="px-6 py-2 bg-blue-500 text-white rounded-lg hover:bg-blue-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center"
            >
              {loading ? (
                <>
                  <div className="animate-spin rounded-full h-4 w-4 border-b-2 border-white mr-2"></div>
                  Analyzing...
                </>
              ) : (
                <>
                  <BarChart className="w-4 h-4 mr-2" />
                  Analyze
                </>
              )}
            </button>
          </div>
        </div>

        {/* Error Display */}
        {error && (
          <div className="bg-red-50 border border-red-200 rounded-lg p-4 mb-6">
            <div className="flex items-center">
              <AlertTriangle className="w-5 h-5 text-red-500 mr-2" />
              <span className="text-red-700">{error}</span>
            </div>
          </div>
        )}

        {/* Navigation Tabs */}
        <div className="bg-white rounded-lg shadow-md mb-6">
          <div className="border-b border-gray-200">
            <nav className="flex space-x-8 px-6">
              {[
                { id: 'dashboard', label: 'Dashboard', icon: BarChart },
                { id: 'cvss', label: 'CVSS Scan', icon: Shield },
                { id: 'sbom', label: 'SBOM', icon: FileText },
                { id: 'spdx', label: 'SPDX', icon: CheckCircle }
              ].map(({ id, label, icon: Icon }) => (
                <button
                  key={id}
                  onClick={() => setActiveTab(id as any)}
                  className={`flex items-center py-4 px-1 border-b-2 font-medium text-sm ${
                    activeTab === id
                      ? 'border-blue-500 text-blue-600'
                      : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
                  }`}
                >
                  <Icon className="w-4 h-4 mr-2" />
                  {label}
                </button>
              ))}
            </nav>
          </div>

          {/* Tab Actions */}
          <div className="px-6 py-4 bg-gray-50 border-b border-gray-200">
            <div className="flex flex-wrap gap-3">
              {activeTab === 'cvss' && (
                <button
                  onClick={runCVSSScan}
                  disabled={loading || !repositoryUrl.trim()}
                  className="px-4 py-2 bg-red-500 text-white rounded-lg hover:bg-red-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center text-sm"
                >
                  <Search className="w-4 h-4 mr-2" />
                  Run CVSS Scan
                </button>
              )}
              
              {activeTab === 'sbom' && (
                <button
                  onClick={generateSBOM}
                  disabled={loading || !repositoryUrl.trim()}
                  className="px-4 py-2 bg-green-500 text-white rounded-lg hover:bg-green-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center text-sm"
                >
                  <FileText className="w-4 h-4 mr-2" />
                  Generate SBOM
                </button>
              )}
              
              {(activeTab === 'sbom' || activeTab === 'spdx') && (
                <button
                  disabled={loading}
                  className="px-4 py-2 bg-gray-500 text-white rounded-lg hover:bg-gray-600 disabled:opacity-50 disabled:cursor-not-allowed flex items-center text-sm"
                >
                  <Download className="w-4 h-4 mr-2" />
                  Export Report
                </button>
              )}
            </div>
          </div>
        </div>

        {/* Tab Content */}
        <div className="mb-6">
          {activeTab === 'dashboard' && renderDashboard()}
          {activeTab === 'cvss' && renderCVSSResults()}
          {activeTab === 'sbom' && renderSBOMResults()}
          {activeTab === 'spdx' && (
            <div className="bg-white rounded-lg shadow-md p-6">
              <h3 className="text-lg font-semibold text-gray-900 mb-4">SPDX Compliance</h3>
              <p className="text-gray-600">SPDX document generation and validation coming soon...</p>
            </div>
          )}
        </div>
      </div>
    </div>
  );
};

export default SecurityPage;
