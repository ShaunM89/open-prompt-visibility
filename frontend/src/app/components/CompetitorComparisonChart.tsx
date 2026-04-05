'use client';

export interface CompetitorData {
  competitors: Array<{
    competitor: string;
    share: number;
  }>;
  competitor_names: string[];
  max_shares: Record<string, number>;
}

export default function CompetitorComparisonChart({ 
  brand, 
  competitors, 
  period 
}: { 
  brand: string; 
  competitors: CompetitorData; 
  period: number 
}) {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-900">Competitor Comparison</h2>
        <p className="text-sm text-gray-600">{period} days</p>
      </div>

      <div className="space-y-3">
        {competitors.competitors.map((item) => (
          <div key={item.competitor} className="flex items-center gap-3">
            <div className="flex-1">
              <p className="font-medium">{item.competitor}</p>
              <p className="text-xs text-gray-500">Mention share</p>
            </div>
            <div className="flex items-center gap-2">
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                item.share > 50 ? 'bg-green-100 text-green-800' : 
                item.share > 25 ? 'bg-yellow-100 text-yellow-800' : 
                'bg-gray-100 text-gray-800'
              }`}>
                {(item.share / 100).toFixed(1)}%
              </span>
            </div>
          </div>
        ))}
        {competitors.competitors.length === 0 && (
          <p className="text-sm text-gray-500 text-center py-4">No competitor data available</p>
        )}
      </div>
    </div>
  );
}