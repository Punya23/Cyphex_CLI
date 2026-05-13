import { useState, useEffect } from 'react';
import { Play, Plus, User, MessageSquare, Shield } from 'lucide-react';
import './Header.css';

interface HeaderProps {
  onDeploy: (url: string) => void;
  isRunning: boolean;
}

export function Header({ onDeploy, isRunning }: HeaderProps) {
  const [mode, setMode] = useState<'sandbox' | 'live'>('sandbox');
  const [url, setUrl] = useState('');

  return (
    <header className="header hacker-header">
      <div className="header-left">
        <div className="logo-group">
          <Shield className="logo-icon glow-blue" size={24} />
          <h1 className="logo-text glitch-text" data-text="CYPHEX">CYPHEX</h1>
        </div>
      </div>

      <div className="header-center">
        <div className="segmented-toggle">
          <button 
            className={`toggle-item ${mode === 'sandbox' ? 'active' : ''}`}
            onClick={() => setMode('sandbox')}
          >
            <span className="mono">// MODE: SANDBOX //</span>
          </button>
          <button 
            className={`toggle-item ${mode === 'live' ? 'active' : ''}`}
            onClick={() => setMode('live')}
          >
            <span className="mono">// LIVE URL //</span>
          </button>
        </div>
        
        <div className="header-actions">
          {mode === 'sandbox' ? (
            <button className="hacker-btn secondary glow-green mono">
              <Plus size={14} /> //ADD SANDBOX//
            </button>
          ) : (
            <div className="hacker-input-group">
              <span className="prefix mono">{`> `}</span>
              <input 
                type="text" 
                className="hacker-input mono" 
                placeholder="TARGET_NODE:8080" 
                value={url}
                onChange={(e) => setUrl(e.target.value)}
              />
            </div>
          )}
        </div>
      </div>
      
      <div className="header-right">
        <div className="status-indicators">
          <div className="indicator">
            <MessageSquare size={16} className="glow-blue" />
            <span className="badge">12</span>
          </div>
          <div className="user-profile">
            <User size={18} />
          </div>
        </div>
        
        <button 
          className={`deploy-btn-hacker mono ${isRunning ? 'running' : ''}`} 
          onClick={() => onDeploy(mode === 'live' ? url || 'https://vulncorp.com' : 'VulnCorp Sandbox')}
          disabled={isRunning}
        >
          <Play size={16} fill="currentColor" />
          <span className="btn-text">
            {isRunning ? '> SYSTEM_ARMED' : '> DEPLOY_AGENTS'}
          </span>
        </button>
      </div>
    </header>
  );
}
