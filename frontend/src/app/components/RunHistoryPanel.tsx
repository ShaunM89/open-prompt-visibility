export default function RunHistoryPanel({ runs }: { runs: any[] }) {
  if (!runs || runs.length === 0) {
    return null;
  }

  const statusClass = (status: string) => {
    switch (status?.toLowerCase()) {
      case 'success': return 'bg-green-100 text-green-900 border-green-200';
      case 'failed': return 'bg-red-100 text-red-900 border-red-200';
      case 'running': return 'bg-yellow-100 text-yellow-900 border-yellow-200';
      default: return 'bg-gray-100 text-gray-800 border-gray-200';
    }
  };

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Run History</h2>
      
      <div className="space-y-2">
        {runs.slice(0, 10).map((run) => (
          <div key={run.id} className="flex items-center justify-between rounded border border-gray-100 p-3">
            <div className="flex-1">
              <p className="text-sm font-medium text-gray-900">
                {new Date(run.completed_at).toLocaleString()}
              </p>
              <p className="text-xs text-gray-500">
                Models: {run.model_counts?.map((m: any) => ` ${m.model}`) || 'Unknown'}
              </p>
            </div>
            <span className={`inline-flex items-center rounded px-2.5 py-0.5 text-xs font-medium border ${statusClass(run.status)}`}>
              {run.status || run.statuses?.[0] || 'unknown'}
            </span>
          </div>
        ))}
      </div>
      
      {runs.length > 10 && (
        <p className="text-xs text-gray-500 text-center pt-2">
          Showing {runs.slice(0, 10).length} of {runs.length} runs
        </p>
      )}
    </div>
  );
}
