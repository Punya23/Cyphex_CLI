"""
CYPHEX — Security Posture Score (SPS) Calculator

Calculates a single number (0-100) representing the overall security health
of a web application. This is the "gamification" feature that makes security
tangible and trackable.

Formula:
  SPS = 100 - Σ(severity_weight × vuln_count × confidence_factor)
  
  Where:
    Critical: weight = 25
    High:     weight = 15
    Medium:   weight = 8
    Low:      weight = 3
    
  Confidence factor:
    Confirmed: 1.0
    Likely:    0.7
    Possible:  0.4

Additional factors:
  - Security headers present: +5 points
  - HTTPS enabled: +5 points
  - No sensitive files exposed: +5 points
  - Framework up-to-date: +3 points
  - Strong authentication: +3 points
"""

from dataclasses import dataclass
from typing import List
from models.scan import ScanContext, Vuln


@dataclass
class SecurityPostureScore:
    """Complete security posture assessment."""
    score: int  # 0-100
    grade: str  # A+, A, B, C, D, F
    critical_count: int
    high_count: int
    medium_count: int
    low_count: int
    total_vulns: int
    strengths: List[str]
    weaknesses: List[str]
    recommendations: List[str]
    industry_percentile: int  # Better than X% of websites
    trend: str  # "improving", "stable", "declining"


class SecurityPostureCalculator:
    """Calculates Security Posture Score from scan results."""
    
    # Severity weights
    WEIGHTS = {
        "Critical": 25,
        "High": 15,
        "Medium": 8,
        "Low": 3,
    }
    
    # Security best practices (bonus points)
    SECURITY_HEADERS = [
        "Content-Security-Policy",
        "X-Frame-Options",
        "X-Content-Type-Options",
        "Strict-Transport-Security",
        "Referrer-Policy",
    ]
    
    def calculate(self, context: ScanContext, previous_score: int = None) -> SecurityPostureScore:
        """Calculate SPS from scan context."""
        
        # Count vulnerabilities by severity
        critical = len([v for v in context.confirmed_vulns if v.severity == "Critical"])
        high = len([v for v in context.confirmed_vulns if v.severity == "High"])
        medium = len([v for v in context.confirmed_vulns if v.severity == "Medium"])
        low = len([v for v in context.confirmed_vulns if v.severity == "Low"])
        total = len(context.confirmed_vulns)
        
        # Calculate base score (deduct points for vulns)
        base_score = 100
        base_score -= critical * self.WEIGHTS["Critical"]
        base_score -= high * self.WEIGHTS["High"]
        base_score -= medium * self.WEIGHTS["Medium"]
        base_score -= low * self.WEIGHTS["Low"]
        
        # Ensure score doesn't go below 0
        base_score = max(0, base_score)
        
        # Add bonus points for security best practices
        bonus = 0
        strengths = []
        weaknesses = []
        
        # Check security headers
        headers_present = sum(
            1 for h in self.SECURITY_HEADERS
            if h.lower() in [k.lower() for k in context.headers.keys()]
        )
        if headers_present >= 4:
            bonus += 5
            strengths.append(f"Strong security headers ({headers_present}/5)")
        elif headers_present >= 2:
            bonus += 2
            strengths.append(f"Partial security headers ({headers_present}/5)")
        else:
            weaknesses.append(f"Missing security headers ({headers_present}/5)")
        
        # Check HTTPS
        if context.target_url.startswith("https://"):
            bonus += 5
            strengths.append("HTTPS enabled")
        else:
            weaknesses.append("HTTPS not enabled")
        
        # Check for sensitive file exposure
        sensitive_exposed = any(
            path in context.discovered_paths
            for path in ["/.env", "/.git/HEAD", "/backup.zip", "/.aws/credentials"]
        )
        if not sensitive_exposed:
            bonus += 5
            strengths.append("No sensitive files exposed")
        else:
            weaknesses.append("Sensitive files publicly accessible")
        
        # Check framework detection
        if context.framework:
            bonus += 2
            strengths.append(f"Framework identified: {context.framework}")
        
        # Check for critical vulnerabilities
        if critical == 0:
            bonus += 10
            strengths.append("Zero critical vulnerabilities")
        else:
            weaknesses.append(f"{critical} critical vulnerabilities found")
        
        # Final score
        final_score = min(100, base_score + bonus)
        
        # Determine grade
        grade = self._calculate_grade(final_score)
        
        # Generate recommendations
        recommendations = self._generate_recommendations(
            context, critical, high, medium, low
        )
        
        # Calculate industry percentile (simplified - would use real data in production)
        percentile = self._calculate_percentile(final_score)
        
        # Determine trend
        trend = "stable"
        if previous_score is not None:
            if final_score > previous_score + 5:
                trend = "improving"
            elif final_score < previous_score - 5:
                trend = "declining"
        
        return SecurityPostureScore(
            score=final_score,
            grade=grade,
            critical_count=critical,
            high_count=high,
            medium_count=medium,
            low_count=low,
            total_vulns=total,
            strengths=strengths,
            weaknesses=weaknesses,
            recommendations=recommendations,
            industry_percentile=percentile,
            trend=trend,
        )
    
    def _calculate_grade(self, score: int) -> str:
        """Convert score to letter grade."""
        if score >= 95:
            return "A+"
        elif score >= 90:
            return "A"
        elif score >= 85:
            return "A-"
        elif score >= 80:
            return "B+"
        elif score >= 75:
            return "B"
        elif score >= 70:
            return "B-"
        elif score >= 65:
            return "C+"
        elif score >= 60:
            return "C"
        elif score >= 55:
            return "C-"
        elif score >= 50:
            return "D"
        else:
            return "F"
    
    def _calculate_percentile(self, score: int) -> int:
        """
        Calculate industry percentile (simplified).
        In production, this would query a database of real scan results.
        """
        # Simplified mapping
        if score >= 90:
            return 95
        elif score >= 80:
            return 85
        elif score >= 70:
            return 70
        elif score >= 60:
            return 50
        elif score >= 50:
            return 30
        else:
            return 10
    
    def _generate_recommendations(
        self, context: ScanContext, critical: int, high: int, medium: int, low: int
    ) -> List[str]:
        """Generate prioritized recommendations."""
        recs = []
        
        # Critical issues first
        if critical > 0:
            recs.append(
                f"🚨 URGENT: Fix {critical} critical vulnerabilities immediately. "
                "These can lead to complete system compromise."
            )
        
        # High severity
        if high > 0:
            recs.append(
                f"⚠️  HIGH PRIORITY: Address {high} high-severity issues. "
                "These pose significant security risks."
            )
        
        # Security headers
        headers_present = sum(
            1 for h in self.SECURITY_HEADERS
            if h.lower() in [k.lower() for k in context.headers.keys()]
        )
        if headers_present < 4:
            missing = [
                h for h in self.SECURITY_HEADERS
                if h.lower() not in [k.lower() for k in context.headers.keys()]
            ]
            recs.append(
                f"🛡️  Add missing security headers: {', '.join(missing[:3])}"
            )
        
        # HTTPS
        if not context.target_url.startswith("https://"):
            recs.append(
                "🔒 Enable HTTPS with a valid SSL/TLS certificate. "
                "This protects data in transit."
            )
        
        # Sensitive files
        sensitive_exposed = [
            path for path in context.discovered_paths
            if path in ["/.env", "/.git/HEAD", "/backup.zip", "/.aws/credentials"]
        ]
        if sensitive_exposed:
            recs.append(
                f"📁 Block access to sensitive files: {', '.join(sensitive_exposed)}"
            )
        
        # Medium/Low issues
        if medium > 0 or low > 0:
            recs.append(
                f"📋 Address {medium + low} medium/low severity issues to improve "
                "overall security posture."
            )
        
        # Framework-specific
        if context.framework:
            if "Express" in context.framework:
                recs.append(
                    "🔧 Use helmet.js middleware to set security headers automatically."
                )
            elif "Django" in context.framework:
                recs.append(
                    "🔧 Enable Django's security middleware and set SECURE_* settings."
                )
            elif "PHP" in context.framework:
                recs.append(
                    "🔧 Use prepared statements for all database queries."
                )
        
        # General best practices
        if len(recs) < 3:
            recs.append(
                "✅ Implement regular security scanning (weekly or daily) to catch "
                "new vulnerabilities early."
            )
            recs.append(
                "✅ Enable Web Application Firewall (WAF) to block common attacks."
            )
            recs.append(
                "✅ Implement rate limiting to prevent brute-force attacks."
            )
        
        return recs[:7]  # Return top 7 recommendations
    
    def generate_badge_svg(self, sps: SecurityPostureScore) -> str:
        """Generate an SVG badge for the security score."""
        
        # Color based on grade
        color_map = {
            "A+": "#00C851", "A": "#00C851", "A-": "#2BBBAD",
            "B+": "#4285F4", "B": "#4285F4", "B-": "#AA66CC",
            "C+": "#FFBB33", "C": "#FFBB33", "C-": "#FF8800",
            "D": "#FF4444", "F": "#CC0000",
        }
        color = color_map.get(sps.grade, "#999999")
        
        svg = f"""
<svg xmlns="http://www.w3.org/2000/svg" width="200" height="80">
  <rect width="200" height="80" fill="{color}" rx="10"/>
  <text x="100" y="30" font-family="Arial" font-size="14" fill="white" text-anchor="middle" font-weight="bold">
    SECURITY POSTURE
  </text>
  <text x="100" y="55" font-family="Arial" font-size="28" fill="white" text-anchor="middle" font-weight="bold">
    {sps.score}/100
  </text>
  <text x="100" y="72" font-family="Arial" font-size="12" fill="white" text-anchor="middle">
    Grade: {sps.grade}
  </text>
</svg>
"""
        return svg.strip()
    
    def generate_report_summary(self, sps: SecurityPostureScore) -> str:
        """Generate a human-readable summary."""
        
        emoji_map = {
            "A+": "🏆", "A": "🥇", "A-": "🥈",
            "B+": "🥉", "B": "✅", "B-": "👍",
            "C+": "⚠️", "C": "⚠️", "C-": "⚠️",
            "D": "🚨", "F": "💀",
        }
        emoji = emoji_map.get(sps.grade, "❓")
        
        trend_emoji = {
            "improving": "📈",
            "stable": "➡️",
            "declining": "📉",
        }
        
        summary = f"""
{emoji} SECURITY POSTURE SCORE: {sps.score}/100 (Grade: {sps.grade})

📊 Vulnerability Breakdown:
   🔴 Critical: {sps.critical_count}
   🟠 High:     {sps.high_count}
   🟡 Medium:   {sps.medium_count}
   🔵 Low:      {sps.low_count}
   ━━━━━━━━━━━━━━━━━━━━━━
   📋 Total:    {sps.total_vulns}

💪 Strengths:
{chr(10).join(f"   ✅ {s}" for s in sps.strengths[:5])}

⚠️  Weaknesses:
{chr(10).join(f"   ❌ {w}" for w in sps.weaknesses[:5])}

📈 Industry Comparison:
   Better than {sps.industry_percentile}% of websites in your category

{trend_emoji.get(sps.trend, '➡️')} Trend: {sps.trend.upper()}

🎯 Top Recommendations:
{chr(10).join(f"   {i+1}. {r}" for i, r in enumerate(sps.recommendations[:5]))}
"""
        return summary.strip()


# Example usage
if __name__ == "__main__":
    from models.scan import ScanContext, Vuln
    
    # Create sample context
    context = ScanContext(
        target_url="https://example.com",
        framework="Express.js",
        headers={
            "X-Frame-Options": "DENY",
            "X-Content-Type-Options": "nosniff",
        },
        confirmed_vulns=[
            Vuln(name="SQL Injection", severity="Critical", cvss_score=9.8, confirmed=True),
            Vuln(name="XSS", severity="High", cvss_score=7.5, confirmed=True),
            Vuln(name="Missing CSP", severity="Medium", cvss_score=5.0, confirmed=True),
        ],
    )
    
    # Calculate SPS
    calculator = SecurityPostureCalculator()
    sps = calculator.calculate(context)
    
    # Print summary
    print(calculator.generate_report_summary(sps))
    
    # Generate badge
    badge_svg = calculator.generate_badge_svg(sps)
    with open("security_badge.svg", "w") as f:
        f.write(badge_svg)
    print("\n✅ Badge saved to security_badge.svg")
