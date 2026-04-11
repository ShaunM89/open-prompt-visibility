'use client';

import type { CompetitorComparison } from '../../lib/api';

export default function CompetitorComparisonChart({ 
  brand, 
  competitorData, 
  period 
}: { 
  brand: string; 
  competitorData: CompetitorComparison; 
  period: number 
}) {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <div className="mb-4">
        <h2 className="text-xl font-semibold text-gray-900">Competitor Comparison</h2>
        <p className="text-sm text-gray-600">{period} days</p>
      </div>

      <div className="space-y-3">
        {(competitorData.all_brands || []).map((br) => (
          <div key={br.name} className="flex items-center gap-3">
            <div className="flex-1">
              <p className="font-medium">
                {br.name}
                {br.is_target && <span className="ml-1 text-xs text-indigo-600">(target)</span>}
              </p>
              <p className="text-xs text-gray-700">{br.successful_prompts}/{br.total_prompts} queries</p>
            </div>
            <div className="flex items-center gap-2">
              <div className="w-32 bg-gray-200 rounded-full h-4">
                <div
                  className={`h-4 rounded-full ${br.is_target ? 'bg-indigo-600' : 'bg-gray-500'}`}
                  style={{ width: `${Math.min(100, br.score)}%` }}
                />
              </div>
              <span className={`inline-flex items-center rounded-full px-2.5 py-0.5 text-xs font-medium ${
                br.score > 70 ? 'bg-green-100 text-green-800' : 
                br.score > 40 ? 'bg-yellow-100 text-yellow-800' : 
                'bg-gray-100 text-gray-800'
              }`}>
                {br.score?.toFixed(1)}%
              </span>
            </div>
          </div>
        ))}
        {(!competitorData.all_brands || competitorData.all_brands.length === 0) && (
          <p className="text-sm text-gray-700 text-center py-4">No competitor data available</p>
        )}
      </div>
    </div>
  );
}
