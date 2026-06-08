import React from 'react';
import ReactDOM from 'react-dom/client';
import { QueryClient, QueryClientProvider } from '@tanstack/react-query';
import { Toaster, toast } from 'react-hot-toast';
import App from './App';
import './index.css';
import { registerSW } from 'virtual:pwa-register';

registerSW({
  onNeedRefresh() {
    toast(
      (t) => (
        <div className="flex items-center gap-3">
          <span className="text-sm font-body">New version available</span>
          <button
            className="bg-azure-500 text-white text-xs px-3 py-1.5 rounded-lg font-display font-semibold flex-shrink-0"
            onClick={() => window.location.reload()}
          >
            Update
          </button>
          <button onClick={() => toast.dismiss(t.id)} className="text-secondary hover:text-primary text-xs">✕</button>
        </div>
      ),
      { duration: Infinity, id: 'sw-update' }
    );
  },
  onOfflineReady() {
    toast.success('App ready for offline use', { duration: 3000, id: 'offline-ready' });
  },
});

const queryClient = new QueryClient({
  defaultOptions: {
    queries: {
      retry: 1,
      staleTime: 1000 * 60 * 5,      // 5 min — don't refetch if data is fresh
      gcTime:    1000 * 60 * 30,      // 30 min in memory cache
      refetchOnWindowFocus: false,    // DISABLED — was causing refetch every tab switch
      refetchOnReconnect: false,      // DISABLED — usePWASync handles reconnect sync
      refetchOnMount: false,          // DISABLED — only fetch when staleTime has expired
    },
  },
});

ReactDOM.createRoot(document.getElementById('root')!).render(
  <React.StrictMode>
    <QueryClientProvider client={queryClient}>
      <App />
      <Toaster
        position="top-right"
        toastOptions={{
          style: {
            background: '#1a1a26',
            color: '#fff',
            border: '1px solid #2e2e42',
            fontFamily: 'DM Sans, sans-serif',
            fontSize: '14px',
            borderRadius: '14px',
          },
          success: { iconTheme: { primary: '#10b981', secondary: '#fff' } },
          error:   { iconTheme: { primary: '#f43f5e', secondary: '#fff' } },
        }}
      />
    </QueryClientProvider>
  </React.StrictMode>
);
