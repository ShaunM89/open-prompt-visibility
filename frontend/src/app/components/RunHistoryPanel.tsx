import type { RunHistoryEntry } from '../../lib/api';

export default function RunHistoryPanel({ runs }: { runs: RunHistoryEntry[] }) {
  if (!runs || runs.length === 0) {
    return null;
  }

  const rateClass = (rate: number) => {
    if (rate >= 70) return 'bg-green-100 text-green-800';
    if (rate >= 40) return 'bg-yellow-100 text-yellow-800';
    return 'bg-red-100 text-red-800';
  };

  return (
    <div className="rounded-lg border bg-white p-4 shadow-sm">
      <h2 className="text-lg font-semibold text-gray-900 mb-4">Run History</h2>
      
      <div className="overflow-x-auto">
        <table className="min-w-full">
          <thead>
            <tr className="border-b">
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Run ID</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Date</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Duration</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Queries</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Success Rate</th>
              <th className="px-4 py-3 text-left text-xs font-medium text-gray-700 uppercase">Models</th>
            </tr>
          </thead>
          <tbody className="divide-y">
            {runs.slice(0, 20).map((run) => (
              <tr key={run.run_id} className="hover:bg-gray-50">
                <td className="px-4 py-3 text-sm font-medium text-gray-900">#{run.run_id}</td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {new Date(run.started_at).toLocaleString()}
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">{run.duration || 'N/A'}</td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {run.successful_queries}/{run.total_queries}
                </td>
                <td className="px-4 py-3 whitespace-nowrap">
                  <span className={`inline-flex items-center rounded px-2.5 py-0.5 text-xs font-medium ${rateClass(run.success_rate)}`}>
                    {run.success_rate?.toFixed(1)}%
                  </span>
                </td>
                <td className="px-4 py-3 text-sm text-gray-600">
                  {run.models_used?.join(', ') || 'Unknown'}
                </td>
              </tr>
            ))}
          </tbody>
        </table>
      </div>
      
      {runs.length > 20 && (
        <p className="text-xs text-gray-700 text-center pt-2">
          Showing {runs.slice(0, 20).length} of {runs.length} runs
        </p>
      )}
    </div>
  );
}
