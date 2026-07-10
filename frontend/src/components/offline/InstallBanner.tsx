import { useState } from 'react';
import { Download, X } from 'lucide-react';
import toast from 'react-hot-toast';
import { useInstallPrompt } from '../../hooks/useInstallPrompt';
import { useSiteSettingsStore } from '../../store/siteSettings';

const DISMISS_KEY = 'install-banner-dismissed';

export default function InstallBanner() {
  const { canInstall, isInstalled, promptInstall } = useInstallPrompt();
  const { settings } = useSiteSettingsStore();
  const [dismissed, setDismissed] = useState(() => sessionStorage.getItem(DISMISS_KEY) === '1');

  if (isInstalled || !canInstall || dismissed) return null;

  const dismiss = () => {
    sessionStorage.setItem(DISMISS_KEY, '1');
    setDismissed(true);
  };

  return (
    <div className="fixed bottom-20 lg:bottom-5 left-4 z-50 flex items-center gap-3 px-4 py-2.5 rounded-2xl shadow-2xl border bg-azure-500/15 border-azure-500/40 text-azure-400 max-w-[min(92vw,380px)]">
      <Download size={16} className="flex-shrink-0" />
      <p className="text-sm font-body text-primary flex-1 min-w-0 truncate">
        Install {settings.platform_name || 'MathPlatform'} for one-tap, offline access
      </p>
      <button
        onClick={async () => {
          const outcome = await promptInstall();
          if (outcome === 'accepted') toast.success('Installing…');
          else if (outcome === 'dismissed') dismiss();
        }}
        className="flex-shrink-0 bg-azure-500 text-white text-xs px-3 py-1.5 rounded-lg font-display font-semibold"
      >
        Install
      </button>
      <button onClick={dismiss} className="flex-shrink-0 text-secondary hover:text-primary p-1" title="Dismiss">
        <X size={14} />
      </button>
    </div>
  );
}
