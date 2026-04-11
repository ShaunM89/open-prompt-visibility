'use client';

import { Line, LineChart, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import type { VisibilityScoreData } from '../../lib/api';

interface VisibilityScoreCardProps {
  brand: string;
  scoreData: VisibilityScoreData;
  trends: any[];
}

export default function VisibilityScoreCard({ brand, scoreData, trends }: VisibilityScoreCardProps) {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold text-gray-900 mb-6">Visibility Score - {brand}</h2>
      
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg bg-blue-50 p-4">
          <p className="text-sm text-gray-600">Overall Score</p>
          <p className="text-4xl font-bold text-blue-600">{scoreData.score?.toFixed(1)}%</p>
        </div>
        
        <div className="rounded-lg bg-emerald-50 p-4">
          <p className="text-sm text-gray-600">Successful Prompts</p>
          <p className="text-2xl font-bold text-emerald-600">{scoreData.successful_prompts}</p>
        </div>
        
        <div className="rounded-lg bg-purple-50 p-4">
          <p className="text-sm text-gray-600">Total Prompts</p>
          <p className="text-2xl font-bold text-purple-600">{scoreData.total_prompts}</p>
        </div>
      </div>

      <div className="mb-4 rounded-lg bg-yellow-50 border border-yellow-200 p-3">
        <h3 className="font-medium text-yellow-900 mb-2">Model Score Breakdown</h3>
        <ul className="space-y-1">
          {scoreData.by_model?.map((m) => (
            <li key={m.model_name} className="text-sm flex justify-between">
              <span className="text-gray-700">{m.model_name}</span>
              <span className="text-gray-600">
                {m.score?.toFixed(1)}%
                {m.confidence_interval && (
                  <span className="text-xs text-gray-500 ml-1">
                    (CI: {m.confidence_interval[0].toFixed(1)}-{m.confidence_interval[1].toFixed(1)})
                  </span>
                )}
              </span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mb-4 rounded-lg bg-indigo-50 border border-indigo-200 p-3">
        <h3 className="font-medium text-indigo-900 mb-2">Confidence Interval</h3>
        {scoreData.confidence_interval ? (
          <p className="text-sm text-indigo-900">
            95% CI: [{scoreData.confidence_interval[0].toFixed(1)}% - {scoreData.confidence_interval[1].toFixed(1)}%]
          </p>
        ) : (
          <p className="text-sm text-indigo-900">Insufficient data for CI calculation</p>
        )}
      </div>

      <div className="rounded-lg border bg-gray-50 p-4">
        <h3 className="font-medium text-gray-900 mb-3">Mention Trend (Last 30 days)</h3>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trends}>
              {Object.keys(trends[0] || {}).filter((k: string) => k !== 'date').map((key: string, i: number) => (
                <Line
                  key={key}
                  type="monotone"
                  dataKey={key}
                  stroke={`hsl(${i * 60}, 70%, 50%)`}
                  strokeWidth={2}
                  dot={false}
                />
              ))}
              <Tooltip contentStyle={{ borderRadius: '8px' }} />
              <Legend />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
