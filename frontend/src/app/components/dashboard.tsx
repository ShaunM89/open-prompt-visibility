'use client';

import { useEffect, useState } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import VisibilityScoreCard from './VisibilityScoreCard';
import CompetitorComparisonChart from './CompetitorComparisonChart';
import PromptTable from './PromptTable';
import QuickStats from './QuickStats';
import RunHistoryPanel from './RunHistoryPanel';
import type { VisibilityScore, CompetitorData, PromptResults } from '../../types';

interface DashboardProps {
  brand: string;
  days: number;
}

export default function Dashboard({ brand, days }: DashboardProps) {
  const [data, setData] = useState<{
    stats: {
      total_runs: number;
      total_records: number;
      unique_models: number;
      total_mentions: number;
    } | null;
    modelStats: any[];
    trends: any[];
  } | null>(null);
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<string | null>(null);
  
  const [score, setScore] = useState<VisibilityScore | null>(null);
  const [competitors, setCompetitors] = useState<CompetitorData | null>(null);
  const [prompts, setPrompts] = useState<PromptResults>({
    prompts: [],
    pagination: { page: 1, limit: 25, total: 0, total_pages: 1 },
    filters: { brand, model: null, days }
  });
  const [runHistory, setRunHistory] = useState<any[]>([]);

  useEffect(() => {
    loadData();
  }, [brand, days]);

  const loadData = async () => {
    try {
      setLoading(true);
      const [
        dataJson,
        scoreJson,
        competitorsJson,
        promptsJson,
        historyJson
      ] = await Promise.all([
        fetch(`/api/data?brand=${brand}&days=${days}`).then(r => r.json()),
        fetch(`/api/statistical-summary?brand=${brand}&days=${days}&ci_level=95`).then(r => r.json()),
        fetch(`/api/competitors?brand=${brand}&days=${days}`).then(r => r.json()),
        fetch(`/api/prompts?brand=${brand}&days=${days}&limit=10&page=1`).then(r => r.json()),
        fetch(`/api/run-history?days=${days}`).then(r => r.json())
      ]);

      setData(dataJson);
      setScore(scoreJson);
      setCompetitors(competitorsJson);
      setPrompts(promptsJson);
      setRunHistory(historyJson.run_history);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (page: number) => {
    setPrompts(prev => ({
      ...prev,
      pagination: { ...prev.pagination, page }
    }));
  };

  if (loading) return <div className="flex items-center justify-center h-64"><div className="animate-spin rounded-full h-8 w-8 border-b-2 border-blue-600"></div></div>;
  if (error) return <div className="text-red-600">{error}</div>;

  return (
    <div className="space-y-6">
      <div className="flex items-center justify-between">
        <div>
          <h1 className="text-2xl font-bold text-gray-900">{brand}</h1>
          <p className="text-gray-600">Analysis period: {days} days</p>
        </div>
        
        <QuickStats 
          stats={data?.stats || { total_mentions: 0, unique_models: 0, total_records: 0, total_runs: 0 }}
          brand={brand}
        />
      </div>

      {score && (
        <div className="grid grid-cols-1 lg:grid-cols-2 gap-6">
          <VisibilityScoreCard 
            brand={brand}
            scoreData={score}
            trends={data?.modelStats || []}
          />
          
          {competitors && (
            <CompetitorComparisonChart 
              brand={brand}
              competitors={competitors}
              period={days}
            />
          )}
        </div>
      )}

      {data?.modelStats.length > 1 && score && (
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <div className="flex items-center justify-between mb-4">
            <h2 className="text-lg font-semibold text-gray-900">Mention Frequency Over Time</h2>
          </div>
          <div className="h-64">
            <ResponsiveContainer width="100%" height="100%">
              <LineChart data={data?.modelStats || []}>
                {data?.modelStats.some((d: any) => d.model === 'nemotron') && (
                  <Line
                    type="monotone"
                    dataKey="mentions"
                    stroke="#2563eb"
                    strokeWidth={2}
                    dot={false}
                    strokeDasharray={6}
                  />
                )}
                {data?.modelStats.some((d: any) => d.model === 'qwen') && (
                  <Line
                    type="monotone"
                    dataKey="mentions"
                    stroke="#10b981"
                    strokeWidth={2}
                    dot={false}
                  />
                )}
                <Tooltip
                  content={({ active, payload }) => {
                    if (active && payload && payload[0]) {
                      const val = payload[0].value;
                      return (
                        <div className="bg-white border rounded shadow p-2">
                          <p className="font-medium">{new Date(payload[0].payload.date).toLocaleDateString()}</p>
                          <p className="text-sm text-gray-600">{val} mentions</p>
                        </div>
                      );
                    }
                    return null;
                  }}
                />
                <Legend />
              </LineChart>
            </ResponsiveContainer>
          </div>
        </div>
      )}

      {score && (
        <div className="rounded-lg border bg-white p-4 shadow-sm">
          <h2 className="text-lg font-semibold text-gray-900 mb-4">Statistical Summary</h2>
          <div className="grid grid-cols-2 md:grid-cols-4 gap-4">
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Mean Mention Rate</p>
              <p className="text-2xl font-bold text-gray-900">{score.mean_mention_rate?.toFixed(1) + '%'}</p>
            </div>
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Sample Adequacy</p>
              <p className={`text-lg font-semibold ${score.sample_size_adq ? 'text-green-600' : 'text-red-600'}`}>{score.sample_size_adq ? 'Yes (CV < 20%)' : 'Insufficient'}</p>
            </div>
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Total Runs</p>
              <p className="text-2xl font-bold text-gray-900">{score.n_runs?.toString() || '-'}<br/><span className="text-xs text-gray-400">Unique tracking runs</span></p>
            </div>
            <div className="rounded-lg border border-gray-200 p-4">
              <p className="text-sm text-gray-500">Total Queries</p>
              <p className="text-2xl font-bold text-gray-900">{score.total_queries?.toString() || 'N/A'}<br/><span className="text-xs text-gray-400">All prompts analyzed</span></p>
            </div>
          </div>
        </div>
      )}

      {prompts.prompts.length > 0 && (
        <PromptTable
          prompts={prompts.prompts}
          page={prompts.pagination.page}
          totalPages={prompts.pagination.total_pages}
          onNavigate={handlePageChange}
        />
      )}

      <RunHistoryPanel 
        runs={runHistory}
      />
    </div>
  );
}
