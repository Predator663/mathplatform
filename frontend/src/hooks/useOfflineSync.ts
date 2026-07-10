/**
 * Backward-compatible re-export.
 * All new code should import from usePWASync directly.
 */
export { useSync as useOfflineSync, type SyncProvider } from './usePWASync';
export type { PendingScore } from '../db';
