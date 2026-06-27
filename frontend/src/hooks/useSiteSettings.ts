import { useEffect } from 'react';
import { useSiteSettingsStore } from '../store/siteSettings';
import api from '../api';

function applyFavicon(url: string) {
  if (!url) return;
  const existing = document.querySelector<HTMLLinkElement>('link[rel="icon"]');
  if (existing) {
    existing.href = url;
  } else {
    const link = document.createElement('link');
    link.rel = 'icon';
    link.href = url;
    document.head.appendChild(link);
  }
}

function applyTitle(name: string, subtitle: string) {
  if (name) {
    document.title = subtitle ? `${name} — ${subtitle}` : name;
  }
}

export function useSiteSettings() {
  const { settings, loaded, setSettings, getPage } = useSiteSettingsStore();

  useEffect(() => {
    // Apply cached settings immediately (before network)
    if (settings.favicon_url) applyFavicon(settings.favicon_url);
    if (settings.platform_name) applyTitle(settings.platform_name, settings.platform_subtitle);

    // Always refresh on mount to stay up-to-date
    api.get('/auth/settings/').then(r => {
      setSettings(r.data);
      if (r.data.favicon_url) applyFavicon(r.data.favicon_url);
      if (r.data.platform_name) applyTitle(r.data.platform_name, r.data.platform_subtitle);
    }).catch(() => {/* use cached */});
  }, []);

  return { settings, loaded, getPage };
}
