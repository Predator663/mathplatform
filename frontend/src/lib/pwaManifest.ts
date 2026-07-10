/**
 * Dynamic PWA manifest.
 *
 * vite-plugin-pwa bakes a static /manifest.webmanifest at build time, which is
 * what makes the app installable in the first place. But it can't know about
 * an admin-uploaded icon that's set later, at runtime, from Settings.
 *
 * To let a Settings change actually change the icon someone sees on their
 * home screen, we fetch that static manifest once, patch its name/icons using
 * the current site settings, and re-point <link rel="manifest"> at a Blob URL
 * containing the patched copy. This runs client-side and same-origin, so it
 * works without any backend changes and without touching CORS.
 *
 * iOS ignores the manifest for its home-screen icon — it reads
 * <link rel="apple-touch-icon">  instead — so we patch those tags too.
 */

import type { SiteSettings } from '../store/siteSettings';

let cachedDefaultManifest: Record<string, unknown> | null = null;
let currentBlobUrl: string | null = null;
let lastAppliedIconUrl: string | null = null;

async function getDefaultManifest(): Promise<Record<string, unknown> | null> {
  if (cachedDefaultManifest) return cachedDefaultManifest;
  try {
    const res = await fetch('/manifest.webmanifest');
    if (!res.ok) return null;
    cachedDefaultManifest = await res.json();
    return cachedDefaultManifest;
  } catch {
    return null;
  }
}

function setManifestLink(href: string) {
  let link = document.querySelector<HTMLLinkElement>('link[rel="manifest"]');
  if (!link) {
    link = document.createElement('link');
    link.rel = 'manifest';
    document.head.appendChild(link);
  }
  link.href = href;
}

function setAppleTouchIcons(iconUrl: string) {
  const sizes = ['', '152x152', '144x144'];
  sizes.forEach(size => {
    const selector = size
      ? `link[rel="apple-touch-icon"][sizes="${size}"]`
      : 'link[rel="apple-touch-icon"]:not([sizes])';
    let link = document.querySelector<HTMLLinkElement>(selector);
    if (!link) {
      link = document.createElement('link');
      link.rel = 'apple-touch-icon';
      if (size) link.setAttribute('sizes', size);
      document.head.appendChild(link);
    }
    link.href = iconUrl;
  });
}

/**
 * Rebuilds the manifest + touch icons from current site settings.
 * Safe to call repeatedly (e.g. on every settings change) — it no-ops if
 * nothing actually changed since the last call.
 */
export async function applyPwaBranding(settings: SiteSettings) {
  const customIcon = settings.pwa_icon_url?.trim();
  const nameChanged = true; // name/subtitle are cheap to recompute; icon is the expensive/visible part
  const iconKey = customIcon || '';

  if (iconKey === lastAppliedIconUrl && !nameChanged) return;

  const base = await getDefaultManifest();
  if (!base) return;

  const patched: Record<string, unknown> = { ...base };

  if (settings.platform_name) {
    patched.name = settings.platform_subtitle
      ? `${settings.platform_name} — ${settings.platform_subtitle}`
      : settings.platform_name;
    patched.short_name = settings.platform_name.slice(0, 12);
  }

  if (customIcon) {
    // Reuse the custom image at the sizes installers care about most.
    // Browsers scale a single square source down fine for the smaller slots.
    patched.icons = [
      { src: customIcon, sizes: '192x192', type: guessType(customIcon), purpose: 'any' },
      { src: customIcon, sizes: '512x512', type: guessType(customIcon), purpose: 'any' },
      { src: customIcon, sizes: '192x192', type: guessType(customIcon), purpose: 'maskable' },
      { src: customIcon, sizes: '512x512', type: guessType(customIcon), purpose: 'maskable' },
    ];
  }
  // else: keep the bundled default icons already present in `base`

  const blob = new Blob([JSON.stringify(patched)], { type: 'application/manifest+json' });
  const newUrl = URL.createObjectURL(blob);
  setManifestLink(newUrl);

  if (currentBlobUrl) URL.revokeObjectURL(currentBlobUrl);
  currentBlobUrl = newUrl;
  lastAppliedIconUrl = iconKey;

  // iOS home-screen icon (manifest doesn't apply there)
  setAppleTouchIcons(customIcon || '/icons/icon-192.png');
}

function guessType(url: string): string {
  const ext = url.split('.').pop()?.toLowerCase().split('?')[0];
  if (ext === 'svg') return 'image/svg+xml';
  if (ext === 'webp') return 'image/webp';
  if (ext === 'jpg' || ext === 'jpeg') return 'image/jpeg';
  return 'image/png';
}
