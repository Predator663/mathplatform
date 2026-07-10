import { useState, useEffect } from 'react';
import { Outlet, useLocation, Link } from 'react-router-dom';
import Sidebar from './Sidebar';
import MobileNav from './MobileNav';
import ErrorBoundary from '../ErrorBoundary';
import { Menu } from 'lucide-react';
import { useSiteSettingsStore } from '../../store/siteSettings';
import ThemeToggle from '../ui/ThemeToggle';
import api from '../../api';

export default function AppLayout() {
  const [sidebarOpen, setSidebarOpen] = useState(false);
  const location = useLocation();
  const { settings, setSettings } = useSiteSettingsStore();

  // Fetch settings on mount
  useEffect(() => {
    api.get('/auth/settings/').then(r => {
      setSettings(r.data);
      // Apply favicon if set
      if (r.data.favicon_url) {
        let link = document.querySelector<HTMLLinkElement>("link[rel~='icon']");
        if (!link) {
          link = document.createElement('link');
          link.rel = 'icon';
          document.head.appendChild(link);
        }
        link.href = r.data.favicon_url;
      }
    }).catch(() => {});
  }, []);

  // Close drawer on route change
  useEffect(() => { setSidebarOpen(false); }, [location.pathname]);

  // Close on escape
  useEffect(() => {
    const handler = (e: KeyboardEvent) => { if (e.key === 'Escape') setSidebarOpen(false); };
    window.addEventListener('keydown', handler);
    return () => window.removeEventListener('keydown', handler);
  }, []);

  const platformName = settings.platform_name || 'MathPlatform';
  const logoLetter = settings.logo_letter || 'Σ';

  return (
    <div className="flex h-screen overflow-hidden" style={{backgroundColor: 'var(--bg-950)', color: 'var(--text-primary)'}}>
      {/* Desktop sidebar */}
      <div className="hidden lg:block flex-shrink-0">
        <Sidebar />
      </div>

      {/* Mobile sidebar drawer */}
      {sidebarOpen && (
        <div className="fixed inset-0 z-50 lg:hidden flex">
          <div
            className="absolute inset-0 bg-black/70 backdrop-blur-sm"
            onClick={() => setSidebarOpen(false)}
          />
          <div className="relative z-10 flex-shrink-0 animate-[slideInLeft_0.2s_ease-out]">
            <Sidebar onClose={() => setSidebarOpen(false)} />
          </div>
        </div>
      )}

      {/* Main content */}
      <div className="flex-1 flex flex-col min-w-0 overflow-hidden">
        {/* Mobile top bar */}
        <div className="lg:hidden flex items-center gap-3 px-4 py-3 bg-surface-900 border-b border-surface flex-shrink-0" style={{borderColor: 'var(--border)'}}>
          <button
            onClick={() => setSidebarOpen(true)}
            className="p-2 text-secondary hover:text-primary transition-colors rounded-xl hover:bg-surface-700"
            aria-label="Open menu"
          >
            <Menu size={20} />
          </button>
          <div className="flex items-center gap-2 flex-1">
            {settings.logo_url ? (
              <img src={settings.logo_url} alt={platformName} className="w-6 h-6 rounded-md object-contain" />
            ) : (
              <div className="w-6 h-6 bg-azure-500 rounded-md flex items-center justify-center">
                <span className="font-display font-black text-xs text-white">{logoLetter}</span>
              </div>
            )}
            <span className="font-display font-bold text-sm text-primary">{platformName}</span>
          </div>
          <ThemeToggle />
        </div>

        {/* Scrollable page content */}
        <main className="flex-1 overflow-y-auto flex flex-col">
          <div className="flex-1 p-4 md:p-6 lg:p-8 pb-24 lg:pb-8 page-enter">
            <ErrorBoundary key={location.pathname}>
              <Outlet />
            </ErrorBoundary>
          </div>

          {/* Footer */}
          <footer className="hidden lg:block px-8 py-3 border-t border-surface flex-shrink-0" style={{borderColor: 'var(--border)'}}>
            <div className="flex items-center justify-center gap-4 flex-wrap">
              {settings.footer_text && (
                <p className="text-xs text-secondary text-center">{settings.footer_text}</p>
              )}
              <div className="flex items-center gap-3">
                <Link to="/about" className="text-xs text-secondary hover:text-primary transition-colors">About</Link>
                <span className="text-xs text-secondary">·</span>
                <Link to="/privacy-policy" className="text-xs text-secondary hover:text-primary transition-colors">Privacy Policy</Link>
                <span className="text-xs text-secondary">·</span>
                <Link to="/terms-of-use" className="text-xs text-secondary hover:text-primary transition-colors">Terms of Use</Link>
              </div>
            </div>
          </footer>
        </main>

        {/* Mobile bottom navigation */}
        <MobileNav />
      </div>
    </div>
  );
}
