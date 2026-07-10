import { Component, type ErrorInfo, type ReactNode } from 'react';
import { AlertTriangle, RefreshCcw } from 'lucide-react';

interface Props {
  children: ReactNode;
}

interface State {
  hasError: boolean;
}

/**
 * Catches uncaught errors thrown while rendering any page beneath it.
 *
 * Before this existed, the app had no error boundary anywhere — a single
 * uncaught exception during render (e.g. calling .map on a field the API
 * didn't include) unmounted the entire React tree and left the user staring
 * at a blank white page with no indication anything had gone wrong.
 */
export default class ErrorBoundary extends Component<Props, State> {
  state: State = { hasError: false };

  static getDerivedStateFromError(): State {
    return { hasError: true };
  }

  componentDidCatch(error: Error, info: ErrorInfo) {
    // eslint-disable-next-line no-console
    console.error('Unhandled error in page render:', error, info.componentStack);
  }

  handleReload = () => {
    this.setState({ hasError: false });
    window.location.reload();
  };

  render() {
    if (this.state.hasError) {
      return (
        <div
          className="min-h-screen flex items-center justify-center p-6"
          style={{ backgroundColor: 'var(--bg-950)', color: 'var(--text-primary)' }}
        >
          <div className="card p-6 md:p-8 max-w-sm w-full text-center flex flex-col items-center gap-3">
            <div className="w-12 h-12 rounded-2xl bg-rose-500/15 text-rose-400 flex items-center justify-center">
              <AlertTriangle size={22} />
            </div>
            <h1 className="font-display font-bold text-lg">Something went wrong</h1>
            <p className="text-secondary text-sm">
              This page hit an unexpected error. Reloading usually fixes it — if it keeps
              happening, please let us know what you were doing.
            </p>
            <button onClick={this.handleReload} className="btn-primary mt-2 inline-flex items-center gap-2">
              <RefreshCcw size={14} /> Reload page
            </button>
          </div>
        </div>
      );
    }
    return this.props.children;
  }
}
