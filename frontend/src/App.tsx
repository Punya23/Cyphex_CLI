import { BrowserRouter, Routes, Route } from 'react-router-dom';
import { PipelineProvider } from './contexts/PipelineContext';
import { Layout } from './components/Layout';
import { Overview } from './pages/Overview';
import { ReportPage } from './pages/Report';
import { ScanHistoryPage } from './pages/ScanHistory';
import { SandboxPage } from './pages/SandboxPage';
import {
  CrawlerPage, InjectionPage, XSSPage, ReconPage,
  AnalysisPage, CurePlannerPage, AuthPage, LFIPage,
  LogicPage, SupplyChainPage
} from './pages/Modules';
import './App.css';

function App() {
  return (
    <PipelineProvider>
      <BrowserRouter>
        <Routes>
          <Route path="/" element={<Layout />}>
            <Route index element={<Overview />} />
            <Route path="sandbox" element={<SandboxPage />} />
            <Route path="recon" element={<ReconPage />} />
            <Route path="crawler" element={<CrawlerPage />} />
            <Route path="injection" element={<InjectionPage />} />
            <Route path="sqli" element={<InjectionPage />} />
            <Route path="xss" element={<XSSPage />} />
            <Route path="auth" element={<AuthPage />} />
            <Route path="lfi" element={<LFIPage />} />
            <Route path="logic" element={<LogicPage />} />
            <Route path="supply-chain" element={<SupplyChainPage />} />
            <Route path="analysis" element={<AnalysisPage />} />
            <Route path="cure-planner" element={<CurePlannerPage />} />
            <Route path="report" element={<ReportPage />} />
            <Route path="history" element={<ScanHistoryPage />} />
          </Route>
        </Routes>
      </BrowserRouter>
    </PipelineProvider>
  );
}

export default App;
