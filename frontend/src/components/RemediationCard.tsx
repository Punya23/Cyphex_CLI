import { FileText, ShieldCheck, Zap } from 'lucide-react';
import './RemediationCard.css';

interface Props {
  riskScore: number;
}

export function RemediationCard({ riskScore }: Props) {
  const securityScore = 100 - riskScore;
  
  return (
    <div className="card remediation-card">
      <div className="card-header">
        <span className="card-title mono">//PROTOCOL: REMEDIATION_STRATEGY//</span>
      </div>
      
      <div className="strategy-status">
        <div className="status-label mono">CRITICAL ACTIONS REQUIRED</div>
        <div className="progress-meter">
          <div 
            className="progress-fill bg-glow-green" 
            style={{ width: `${securityScore}%` }}
          ></div>
        </div>
        <div className="status-meta mono">
          <span>PRIORITY: HIGH</span>
          <span className="glow-green">S-SCORE: {securityScore}</span>
        </div>
      </div>

      <div className="btn-grid">
        <button className="hacker-btn mono" onClick={() => alert('Generating Threat Deck Report...')}>
          <FileText size={16} /> //REPORT: THREAT_DECK//
        </button>
        <button className="hacker-btn mono accent-purple" onClick={() => alert('Optimizing Cure Algorithm...')}>
          <Zap size={16} /> //ENHANCE: CURE_ALGORITHM//
        </button>
        <button className="hacker-btn mono accent-blue" onClick={() => alert('Deploying Sandbox Fixes...')}>
          <ShieldCheck size={16} /> //DEPLOY: SANDBOX_FIX//
        </button>
      </div>
    </div>
  );
}
