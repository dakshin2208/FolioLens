import { Component, type ReactNode } from "react";

/** Shows a readable error with a reload button instead of a blank screen if anything crashes. */
export class ErrorBoundary extends Component<{ children: ReactNode }, { error: Error | null }> {
  state = { error: null as Error | null };

  static getDerivedStateFromError(error: Error) {
    return { error };
  }

  componentDidCatch(error: Error) {
    console.error("[FolioLens] UI crashed:", error);
  }

  render() {
    if (!this.state.error) return this.props.children;
    return (
      <div className="flex min-h-screen items-center justify-center bg-page p-6">
        <div className="w-full max-w-lg rounded-lg border border-line-strong bg-surface p-6">
          <div className="text-[13px] font-semibold text-bad">Something went wrong</div>
          <h1 className="mt-2 text-xl font-semibold text-ink">This screen failed to load</h1>
          <pre className="mt-4 overflow-x-auto rounded-md bg-page p-3 font-mono text-xs text-ink-2">{this.state.error.message}</pre>
          <div className="mt-5 flex gap-3">
            <button className="h-9 rounded-md bg-accent px-4 text-sm font-semibold text-accent-ink" onClick={() => location.reload()}>Reload</button>
            <button className="h-9 rounded-md border border-line-strong px-4 text-sm text-ink" onClick={() => { try { localStorage.clear(); } catch { /* ignore */ } location.href = "/"; }}>Sign out and go home</button>
          </div>
        </div>
      </div>
    );
  }
}
