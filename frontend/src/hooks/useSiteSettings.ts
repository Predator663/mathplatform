import { useEffect } from 'react';
import { useSiteSettingsStore } from '../store/siteSettings';
import type { SiteSettings } from '../store/siteSettings';
import api from '../api';
import { applyPwaBranding } from '../lib/pwaManifest';

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
    applyPwaBranding(settings);

    // Always refresh on mount to stay up-to-date
    api.get('/auth/settings/').then(r => {
      const data = r.data as SiteSettings;
      setSettings(data);
      if (data.favicon_url) applyFavicon(data.favicon_url);
      if (data.platform_name) applyTitle(data.platform_name, data.platform_subtitle);
      applyPwaBranding(data);
    }).catch(() => {/* use cached */});
  }, []);

  return { settings, loaded, getPage };
}
