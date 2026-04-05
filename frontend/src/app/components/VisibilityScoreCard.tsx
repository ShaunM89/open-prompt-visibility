'use client';

import { Line, LineChart, ResponsiveContainer, Tooltip, Legend } from 'recharts';

interface VisibilityScoreCardProps {
  brand: string;
  scoreData: any;
  trends: any[];
}

export default function VisibilityScoreCard({ brand, scoreData, trends }: VisibilityScoreCardProps) {
  return (
    <div className="rounded-lg border bg-white p-6 shadow-sm">
      <h2 className="text-xl font-semibold text-gray-900 mb-6">Visibility Score - {brand}</h2>
      
      <div className="grid grid-cols-3 gap-4 mb-6">
        <div className="rounded-lg bg-blue-50 p-4">
          <p className="text-sm text-gray-600">Overall Score</p>
          <p className="text-4xl font-bold text-blue-600">{scoreData.brand_score_pct?.toFixed(1)}%</p>
        </div>
        
        <div className="rounded-lg bg-emerald-50 p-4">
          <p className="text-sm text-gray-600">Successful Prompts</p>
          <p className="text-2xl font-bold text-emerald-600">{scoreData.prompt_count}</p>
        </div>
        
        <div className="rounded-lg bg-purple-50 p-4">
          <p className="text-sm text-gray-600">By Prompt</p>
          <p className="text-2xl font-bold text-purple-600">{scoreData.brand_score_count}</p>
        </div>
      </div>

      <div className="mb-4 rounded-lg bg-yellow-50 border border-yellow-200 p-3">
        <h3 className="font-medium text-yellow-900 mb-2">Model Score Breakdown</h3>
        <ul className="space-y-1">
          {scoreData.by_model?.map((m: any) => (
            <li key={m.model} className="text-sm flex justify-between">
              <span className="text-gray-700">{m.model}</span>
              <span className="text-gray-600">{m.score?.toFixed(0)}% {m.model_name === 'nemotron' ? '(lower volume)' : ''}</span>
            </li>
          ))}
        </ul>
      </div>

      <div className="mb-4 rounded-lg bg-indigo-50 border border-indigo-200 p-3">
        <h3 className="font-medium text-indigo-900 mb-2">Confidence Interval</h3>
        <p className="text-sm text-indigo-900">
          Sample quality: {scoreData.sample_size_adq ? 'Adequate (CV < 20%)' : 'Insufficient (CV >= 20%)'}
        </p>
      </div>

      <div className="rounded-lg border bg-gray-50 p-4">
        <h3 className="font-medium text-gray-900 mb-3">Mention Trend (Last 30 days)</h3>
        <div className="h-32">
          <ResponsiveContainer width="100%" height="100%">
            <LineChart data={trends}>
              {trends.some((d: any) => d.model === 'nemotron') && (
                <Line
                  type="monotone"
                  dataKey="mentions"
                  stroke="#2563eb"
                  strokeWidth={2}
                  dot={false}
                  strokeDasharray={6}
                />
              )}
              <Tooltip contentStyle={{ borderRadius: '8px' }} />
            </LineChart>
          </ResponsiveContainer>
        </div>
      </div>
    </div>
  );
}
