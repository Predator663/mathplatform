import { useEffect } from 'react';
import { useNavigate } from 'react-router-dom';
import { ArrowLeft } from 'lucide-react';
import { useSiteSettingsStore } from '../../store/siteSettings';
import api from '../../api';
import { useAuthStore } from '../../store/auth';

interface LegalPageProps {
  title: string;
  field: 'privacy_policy' | 'terms_of_use' | 'about_me';
  fallback: string;
}

export default function LegalPage({ title, field, fallback }: LegalPageProps) {
  const navigate = useNavigate();
  const { settings, setSettings, loaded } = useSiteSettingsStore();
  const { isAuthenticated } = useAuthStore();

  // Refresh settings on mount so edits made in Settings show up without a full reload
  useEffect(() => {
    api.get('/auth/settings/').then(r => setSettings(r.data)).catch(() => {});
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, []);

  const platformName = settings.platform_name || 'MathPlatform';
  const content = settings[field]?.trim();
  const paragraphs = (content || fallback)
    .split(/\n\s*\n/)
    .map(p => p.trim())
    .filter(Boolean);

  return (
    <div className="min-h-screen bg-surface-950 px-4 py-8 sm:py-12">
      <div className="max-w-2xl mx-auto">
        <button
          onClick={() => (isAuthenticated ? navigate(-1) : navigate('/login'))}
          className="flex items-center gap-1.5 text-sm text-secondary hover:text-primary transition-colors mb-6"
        >
          <ArrowLeft size={14} /> Back
        </button>

        <div className="card p-5 sm:p-8">
          <h1 className="page-title mb-1">{title}</h1>
          <p className="text-xs text-secondary mb-6">{platformName}{loaded && settings.platform_subtitle ? ` · ${settings.platform_subtitle}` : ''}</p>

          <div className="flex flex-col gap-4">
            {paragraphs.map((p, i) => (
              <p key={i} className="text-sm text-secondary leading-relaxed whitespace-pre-wrap break-words">
                {p}
              </p>
            ))}
          </div>
        </div>
      </div>
    </div>
  );
}
