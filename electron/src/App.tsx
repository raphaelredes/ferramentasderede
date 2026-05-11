import { useEffect, useState, lazy, Suspense } from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import Dashboard from './pages/Dashboard';

// Lazy-load secondary routes — Dashboard is the landing page so it stays in the
// main bundle to avoid a Suspense flash on app open. Tools (recharts-heavy),
// Settings, Security (vault UI), Terminal and HostDetails are split into their
// own chunks. Cuts the initial JS from ~1MB to roughly half.
const Tools = lazy(() => import('./pages/Tools').then(m => ({ default: m.Tools })));
const Terminal = lazy(() => import('./pages/Terminal').then(m => ({ default: m.Terminal })));
const Settings = lazy(() => import('./pages/Settings').then(m => ({ default: m.Settings })));
const HostDetails = lazy(() => import('./pages/HostDetails').then(m => ({ default: m.HostDetails })));
const Security = lazy(() => import('./pages/Security').then(m => ({ default: m.Security })));

import { LoadingScreen } from './components/LoadingScreen';

import { VaultProvider } from './contexts/VaultContext';
import { ToastProvider } from './contexts/ToastContext';
import { ToolsProvider } from './contexts/ToolsContext';
import { LoadingProvider } from './contexts/LoadingContext';
import { MonitoringProvider } from './contexts/MonitoringContext';
import { TrustedHostsSessionProvider } from './contexts/TrustedHostsSessionContext';

function App() {
  const [isLoaded, setIsLoaded] = useState(false);

  useEffect(() => {
    // Remove o loader estático do HTML imediatamente, pois o React vai renderizar o LoadingScreen
    const staticLoader = document.getElementById('initial-loader');
    if (staticLoader) {
      staticLoader.style.display = 'none';
    }
  }, []);

  if (!isLoaded) return <LoadingScreen onComplete={() => setIsLoaded(true)} />;

  return (
    <LoadingProvider>
      <VaultProvider>
        <ToastProvider>
          <ToolsProvider>
            <MonitoringProvider>
              <TrustedHostsSessionProvider>
                <Router>
                  <div className="flex h-screen bg-zinc-950 text-zinc-100 font-sans overflow-hidden">
                    <Sidebar />
                    <main className="flex-1 overflow-auto">
                      <Suspense fallback={<div className="p-8 text-zinc-500 text-sm">Carregando…</div>}>
                        <Routes>
                          <Route path="/" element={<Dashboard />} />
                          <Route path="/dashboard" element={<Dashboard />} />
                          <Route path="/host/:ip" element={<HostDetails />} />
                          <Route path="/tools" element={<Tools />} />
                          <Route path="/terminal" element={<Terminal />} />
                          <Route path="/settings" element={<Settings />} />
                          <Route path="/security" element={<Security />} />
                        </Routes>
                      </Suspense>
                    </main>
                  </div>
                </Router>
              </TrustedHostsSessionProvider>
            </MonitoringProvider>
          </ToolsProvider>
        </ToastProvider>
      </VaultProvider>
    </LoadingProvider>
  );
}

export default App;
