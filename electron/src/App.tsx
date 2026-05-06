import { useEffect, useState } from 'react';
import { HashRouter as Router, Routes, Route } from 'react-router-dom';
import { Sidebar } from './components/Sidebar';
import Dashboard from './pages/Dashboard';
import { Tools } from './pages/Tools';
import { Terminal } from './pages/Terminal';
import { Settings } from './pages/Settings';
import { HostDetails } from './pages/HostDetails';
import { Security } from './pages/Security';

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
                      <Routes>
                        <Route path="/" element={<Dashboard />} />
                        <Route path="/dashboard" element={<Dashboard />} />
                        <Route path="/host/:ip" element={<HostDetails />} />
                        <Route path="/tools" element={<Tools />} />
                        <Route path="/terminal" element={<Terminal />} />
                        <Route path="/settings" element={<Settings />} />
                        <Route path="/security" element={<Security />} />
                      </Routes>
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
