export default function QuickStats({ stats, brand }: { stats: any; brand: string }) {
  return (
    <div className="grid grid-cols-3 gap-4">
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <p className="text-sm text-gray-700">Total Mentions</p>
          <p className="text-2xl font-bold text-gray-900">{stats.total_mentions || 0}</p>
        </div>
      </div>
      
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <p className="text-sm text-gray-700">Unique Models</p>
          <p className="text-2xl font-bold text-gray-900">{stats.unique_models || 0}</p>
        </div>
      </div>
      
      <div className="rounded-lg border border-gray-200 bg-white p-4 shadow-sm">
        <div>
          <p className="text-sm text-gray-700">All Queries</p>
          <p className="text-2xl font-bold text-gray-900">{stats.total_runs || 0}</p>
        </div>
      </div>
    </div>
  );
}
