"""
Security Configuration Validator
Validates environment variables and security settings
"""

import os
import re
import secrets
from typing import List, Dict, Any
from pydantic import ValidationError
from core.config import settings


class SecurityValidator:
    """Validates security configuration and settings"""
    
    def __init__(self):
        self.issues: List[Dict[str, Any]] = []
        self.warnings: List[Dict[str, Any]] = []
    
    def validate_all(self) -> Dict[str, Any]:
        """Run all security validations"""
        self.issues = []
        self.warnings = []
        
        # Validate critical security settings
        self._validate_secrets()
        self._validate_database_config()
        self._validate_jwt_config()
        self._validate_cors_config()
        self._validate_environment_settings()
        self._validate_production_readiness()
        
        return {
            "is_secure": len(self.issues) == 0,
            "security_score": self._calculate_security_score(),
            "issues": self.issues,
            "warnings": self.warnings,
            "recommendations": self._get_recommendations()
        }
    
    def _validate_secrets(self):
        """Validate secret strength and presence"""
        # Check JWT secret
        try:
            jwt_secret = settings.JWT_SECRET
            if not jwt_secret:
                self.issues.append({
                    "type": "missing_secret",
                    "field": "JWT_SECRET",
                    "severity": "critical",
                    "message": "JWT_SECRET is required and not set"
                })
            elif len(jwt_secret) < 32:
                self.issues.append({
                    "type": "weak_secret",
                    "field": "JWT_SECRET", 
                    "severity": "high",
                    "message": "JWT_SECRET should be at least 32 characters long"
                })
            elif jwt_secret == "codetrace-ai-secret-change-in-production":
                self.issues.append({
                    "type": "default_secret",
                    "field": "JWT_SECRET",
                    "severity": "critical",
                    "message": "JWT_SECRET is using default value - change immediately"
                })
        except Exception:
            self.issues.append({
                "type": "missing_secret",
                "field": "JWT_SECRET",
                "severity": "critical",
                "message": "JWT_SECRET environment variable is not set"
            })
        
        # Check database password
        try:
            db_password = settings.POSTGRES_PASSWORD
            if not db_password:
                self.issues.append({
                    "type": "missing_secret",
                    "field": "DB_PASSWORD",
                    "severity": "critical",
                    "message": "DB_PASSWORD is required and not set"
                })
            elif db_password == "password":
                self.issues.append({
                    "type": "default_password",
                    "field": "DB_PASSWORD",
                    "severity": "critical",
                    "message": "Database password is using default value"
                })
            elif len(db_password) < 12:
                self.issues.append({
                    "type": "weak_password",
                    "field": "DB_PASSWORD",
                    "severity": "high",
                    "message": "Database password should be at least 12 characters long"
                })
        except Exception:
            self.issues.append({
                "type": "missing_secret",
                "field": "DB_PASSWORD",
                "severity": "critical",
                "message": "DB_PASSWORD environment variable is not set"
            })
    
    def _validate_database_config(self):
        """Validate database security configuration"""
        # Check database name for injection risks
        db_name = settings.POSTGRES_DB
        if not re.match(r'^[a-zA-Z0-9_-]+$', db_name):
            self.issues.append({
                "type": "insecure_config",
                "field": "DB_NAME",
                "severity": "medium",
                "message": "Database name contains potentially unsafe characters"
            })
        
        # Check if using default ports
        if settings.POSTGRES_PORT == 5432:
            self.warnings.append({
                "type": "default_port",
                "field": "DB_PORT",
                "severity": "low",
                "message": "Using default PostgreSQL port (consider changing for security)"
            })
    
    def _validate_jwt_config(self):
        """Validate JWT configuration"""
        # Check JWT algorithm
        if settings.JWT_ALGORITHM not in ["HS256", "HS384", "HS512", "RS256", "RS384", "RS512"]:
            self.issues.append({
                "type": "insecure_config",
                "field": "JWT_ALGORITHM",
                "severity": "high",
                "message": f"Unsupported or insecure JWT algorithm: {settings.JWT_ALGORITHM}"
            })
        
        # Check JWT expiration
        if settings.JWT_EXPIRATION > 30 * 24 * 60 * 60:  # 30 days
            self.warnings.append({
                "type": "long_expiration",
                "field": "JWT_EXPIRATION",
                "severity": "medium",
                "message": "JWT expiration time is very long (>30 days)"
            })
    
    def _validate_cors_config(self):
        """Validate CORS configuration"""
        cors_origins = settings.CORS_ORIGINS
        
        # Check for wildcard origins
        if "*" in cors_origins:
            self.issues.append({
                "type": "insecure_cors",
                "field": "CORS_ORIGINS",
                "severity": "high",
                "message": "CORS allows all origins (*) - security risk"
            })
        
        # Check for non-HTTPS origins in production
        if not settings.DEBUG:
            http_origins = [origin for origin in cors_origins if origin.startswith("http://")]
            if http_origins:
                self.warnings.append({
                    "type": "insecure_origin",
                    "field": "CORS_ORIGINS",
                    "severity": "medium",
                    "message": f"HTTP origins in production: {http_origins}"
                })
    
    def _validate_environment_settings(self):
        """Validate environment-specific settings"""
        # Check debug mode in production
        if not settings.DEBUG and os.getenv("ENVIRONMENT") == "production":
            # This is good - no issue
            pass
        elif settings.DEBUG and os.getenv("ENVIRONMENT") == "production":
            self.issues.append({
                "type": "debug_in_production",
                "field": "DEBUG",
                "severity": "high",
                "message": "Debug mode is enabled in production environment"
            })
        
        # Check authentication settings
        if not settings.ENABLE_AUTH and os.getenv("ENVIRONMENT") == "production":
            self.issues.append({
                "type": "auth_disabled",
                "field": "ENABLE_AUTH",
                "severity": "critical",
                "message": "Authentication is disabled in production environment"
            })
    
    def _validate_production_readiness(self):
        """Check production readiness"""
        production_checks = {
            "ENABLE_AUTH": settings.ENABLE_AUTH,
            "DEBUG": not settings.DEBUG,
            "ENABLE_MONITORING": settings.ENABLE_MONITORING,
        }
        
        failed_checks = [check for check, passed in production_checks.items() if not passed]
        
        if failed_checks:
            self.warnings.append({
                "type": "production_readiness",
                "field": "MULTIPLE",
                "severity": "medium",
                "message": f"Production readiness checks failed: {failed_checks}"
            })
    
    def _calculate_security_score(self) -> float:
        """Calculate overall security score (0-100)"""
        max_score = 100
        deductions = 0
        
        # Deduct points for issues
        for issue in self.issues:
            if issue["severity"] == "critical":
                deductions += 30
            elif issue["severity"] == "high":
                deductions += 20
            elif issue["severity"] == "medium":
                deductions += 10
            else:
                deductions += 5
        
        # Deduct points for warnings
        for warning in self.warnings:
            if warning["severity"] == "medium":
                deductions += 5
            else:
                deductions += 2
        
        return max(0, max_score - deductions)
    
    def _get_recommendations(self) -> List[str]:
        """Get security recommendations"""
        recommendations = []
        
        if any(issue["type"] == "missing_secret" for issue in self.issues):
            recommendations.append("Set all required environment variables before deployment")
        
        if any(issue["type"] in ["default_secret", "default_password"] for issue in self.issues):
            recommendations.append("Change all default passwords and secrets immediately")
        
        if any(issue["type"] == "weak_secret" for issue in self.issues):
            recommendations.append("Use strong, randomly generated secrets (32+ characters)")
        
        if any(issue["type"] == "auth_disabled" for issue in self.issues):
            recommendations.append("Enable authentication for production deployment")
        
        if any(issue["type"] == "debug_in_production" for issue in self.issues):
            recommendations.append("Disable debug mode in production environment")
        
        if any(issue["type"] == "insecure_cors" for issue in self.issues):
            recommendations.append("Configure CORS to allow only specific trusted origins")
        
        recommendations.extend([
            "Regularly rotate secrets and API keys",
            "Enable monitoring and logging in production",
            "Use HTTPS for all external communications",
            "Implement rate limiting on API endpoints",
            "Regular security audits and penetration testing"
        ])
        
        return recommendations


def validate_security_config() -> Dict[str, Any]:
    """Validate security configuration and return results"""
    validator = SecurityValidator()
    return validator.validate_all()


def generate_secure_secret(length: int = 32) -> str:
    """Generate a cryptographically secure secret"""
    return secrets.token_hex(length)


if __name__ == "__main__":
    # Run security validation
    results = validate_security_config()
    
    print("🔒 Security Configuration Validation Report")
    print("=" * 50)
    print(f"Security Score: {results['security_score']}/100")
    print(f"Is Secure: {'✅ Yes' if results['is_secure'] else '❌ No'}")
    print()
    
    if results['issues']:
        print("🚨 Critical Issues:")
        for issue in results['issues']:
            severity_emoji = {"critical": "🔴", "high": "🟠", "medium": "🟡", "low": "🔵"}
            print(f"  {severity_emoji.get(issue['severity'], '⚪')} {issue['field']}: {issue['message']}")
        print()
    
    if results['warnings']:
        print("⚠️ Warnings:")
        for warning in results['warnings']:
            print(f"  • {warning['field']}: {warning['message']}")
        print()
    
    print("💡 Recommendations:")
    for rec in results['recommendations'][:5]:  # Show top 5
        print(f"  • {rec}")
    
    if not results['is_secure']:
        print("\n❌ Security validation failed. Fix critical issues before deployment.")
        exit(1)
    else:
        print("\n✅ Security validation passed!")
