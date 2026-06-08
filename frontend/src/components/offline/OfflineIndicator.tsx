import { useSync } from '../../hooks/usePWASync';
import { Wifi, WifiOff, RefreshCw, CheckCircle, AlertCircle } from 'lucide-react';
import { cn } from '../../utils';

export default function OfflineIndicator() {
  const { isOnline, pendingCount, isSyncing, lastSynced, syncError, syncNow } = useSync();

  // Don't show anything when fully online and no pending items
  if (isOnline && pendingCount === 0 && !isSyncing && !syncError) return null;

  const formatTime = (d: Date) =>
    d.toLocaleTimeString('en-TZ', { hour: '2-digit', minute: '2-digit' });

  return (
    <div className={cn(
      'fixed bottom-20 lg:bottom-5 right-4 z-50',
      'flex items-center gap-2.5 px-4 py-2.5 rounded-2xl shadow-2xl border',
      'text-sm font-display font-semibold transition-all duration-300',
      !isOnline
        ? 'bg-rose-500/15 border-rose-500/40 text-rose-400'
        : syncError
          ? 'bg-amber-500/15 border-amber-500/40 text-amber-400'
          : isSyncing
            ? 'bg-azure-500/15 border-azure-500/40 text-azure-400'
            : 'bg-amber-500/15 border-amber-500/40 text-amber-400'
    )}>
      {/* Icon */}
      {!isOnline ? (
        <WifiOff size={15} className="flex-shrink-0" />
      ) : syncError ? (
        <AlertCircle size={15} className="flex-shrink-0" />
      ) : isSyncing ? (
        <RefreshCw size={15} className="animate-spin flex-shrink-0" />
      ) : (
        <Wifi size={15} className="flex-shrink-0" />
      )}

      {/* Label */}
      <div className="flex flex-col leading-tight">
        <span>
          {!isOnline
            ? 'Offline mode'
            : syncError
              ? 'Sync error'
              : isSyncing
                ? 'Syncing…'
                : `${pendingCount} pending`}
        </span>
        {lastSynced && isOnline && !isSyncing && (
          <span className="text-[10px] opacity-60 font-body">
            Last sync {formatTime(lastSynced)}
          </span>
        )}
      </div>

      {/* Sync button */}
      {isOnline && !isSyncing && (pendingCount > 0 || syncError) && (
        <button
          onClick={syncNow}
          className="ml-1 p-1 hover:opacity-70 transition-opacity rounded-lg"
          title="Sync now"
        >
          <RefreshCw size={13} />
        </button>
      )}
    </div>
  );
}
