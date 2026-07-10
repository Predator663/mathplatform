import { useEffect, useState, useCallback } from 'react';

interface BeforeInstallPromptEvent extends Event {
  prompt: () => Promise<void>;
  userChoice: Promise<{ outcome: 'accepted' | 'dismissed'; platform: string }>;
}

function isStandalone(): boolean {
  return (
    window.matchMedia?.('(display-mode: standalone)').matches ||
    // iOS Safari
    (window.navigator as unknown as { standalone?: boolean }).standalone === true
  );
}

function isIOS(): boolean {
  return /iphone|ipad|ipod/i.test(window.navigator.userAgent);
}

/**
 * Wraps the browser's `beforeinstallprompt` flow.
 *
 * - Chrome/Edge/Android: fires `beforeinstallprompt`, we stash the event and
 *   expose `promptInstall()` to trigger the native install dialog on demand.
 * - iOS Safari: never fires this event — there is no programmatic install API,
 *   so we expose `isIOS` so the UI can show manual "Share → Add to Home
 *   Screen" instructions instead.
 * - Already installed (running standalone): `isInstalled` is true so the UI
 *   can hide the install button entirely.
 */
export function useInstallPrompt() {
  const [deferredEvent, setDeferredEvent] = useState<BeforeInstallPromptEvent | null>(null);
  const [isInstalled, setIsInstalled] = useState(isStandalone());

  useEffect(() => {
    const onBeforeInstall = (e: Event) => {
      e.preventDefault();
      setDeferredEvent(e as BeforeInstallPromptEvent);
    };
    const onInstalled = () => {
      setIsInstalled(true);
      setDeferredEvent(null);
    };
    const mql = window.matchMedia('(display-mode: standalone)');
    const onDisplayModeChange = () => setIsInstalled(isStandalone());

    window.addEventListener('beforeinstallprompt', onBeforeInstall);
    window.addEventListener('appinstalled', onInstalled);
    mql.addEventListener?.('change', onDisplayModeChange);

    return () => {
      window.removeEventListener('beforeinstallprompt', onBeforeInstall);
      window.removeEventListener('appinstalled', onInstalled);
      mql.removeEventListener?.('change', onDisplayModeChange);
    };
  }, []);

  const promptInstall = useCallback(async (): Promise<'accepted' | 'dismissed' | 'unavailable'> => {
    if (!deferredEvent) return 'unavailable';
    await deferredEvent.prompt();
    const { outcome } = await deferredEvent.userChoice;
    setDeferredEvent(null);
    return outcome;
  }, [deferredEvent]);

  return {
    /** True once Chrome/Edge/Android has signaled the app is installable right now. */
    canInstall: !!deferredEvent,
    /** True if the app is already running as an installed/standalone app. */
    isInstalled,
    /** True on iOS Safari, where there's no install prompt — show manual steps instead. */
    isIOS: isIOS(),
    promptInstall,
  };
}
