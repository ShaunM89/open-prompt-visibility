'use client';

import { useEffect, useState } from 'react';
import { Line, LineChart, ResponsiveContainer, Tooltip, Legend } from 'recharts';
import VisibilityScoreCard from '../components/VisibilityScoreCard';
import CompetitorComparisonChart from '../components/CompetitorComparisonChart';
import PromptTable from '../components/PromptTable';
import QuickStats from '../components/QuickStats';
import RunHistoryPanel from '../components/RunHistoryPanel';
import { VisibilityScore, CompetitorData, PromptResults } from '../types';

type DashboardProps = {
  brand: string;
  days: number;
};

declare global {
  namespace JSX {
    interface IntrinsicElements {
      h2: any;
      h3: any;
    }
  }
}

function Metric({ label, value, description }: { label: string; value: string; description: string }) {
  return (
    <div className="rounded-lg border border-gray-200 p-4">
      <p className="text-sm text-gray-500">{label}</p>
      <p className="text-2xl font-bold text-gray-900">{value}</p>
      <p className="text-xs text-gray-400 mt-1">{description}</p>
    </div>
  );
}

function ConfidenceIntervalBadge({ ci, label }: { ci: [number, number] | null; label: string }) {
  if (!ci) return null;
  return (
    <span className="flex items-center gap-2 bg-blue-50 text-blue-700 px-3 py-1 rounded-full text-sm">
      <svg className="w-4 h-4" fill="none" stroke="currentColor" viewBox="0 0 24 24">
        <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 19v-6a2 2 0 00-2-2H5a2 2 0 00-2 2v6a2 2 0 002 2h2a2 2 0 002-2zm0 0V9a2 2 0 012-2h2a2 2 0 012 2v10m-6 0a2 2 0 002 2h2a2 2 0 002-2m0 0V5a2 2 0 012-2h2a2 2 0 012 2v14a2 2 0 002 2h-2a2 2 0 00-2-2" />
      </svg>
      {label}
    </span>
  );
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
    pagination: { page: 1, limit: 25, total: 0 },
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
        dataResult,
        scoreResult,
        competitorsResult,
        promptsResult,
        historyResult
      ] = await Promise.all([
        fetch(`/api/data?brand=${brand}&days=${days}`),
        fetch(`/api/statistical-summary?brand=${brand}&days=${days}&ci_level=95`),
        fetch(`/api/competitors?brand=${brand}&days=${days}`),
        fetch(`/api/prompts?brand=${brand}&days=${days}&limit=10&page=1`),
        fetch(`/api/run-history?days=${days}`)
      ]);

      setData(dataResult.json());
      const scoreJson = await scoreResult.json();
      setScore(scoreJson);
      setCompetitors(competitorsResult.json());
      setPrompts(promptsResult.json());
      setRunHistory((await historyResult.json()).run_history);
    } catch (e) {
      setError(e instanceof Error ? e.message : 'Failed to load data');
    } finally {
      setLoading(false);
    }
  };

  const handlePageChange = (page: number) => {
    setPrompts({
      ...prompts,
      pagination: { ...prompts.pagination, page }
    });
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
            <span className="text-sm text-gray-500 flex items-center">
              <ConfidenceIntervalBadge ci={score.confidence_interval} label={`${score.confidence_interval?.[0]?.toFixed(1)}% - ${score.confidence_interval?.[1]?.toFixed(1)}%`} />
            </span>
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
            <Metric label="Mean Mention Rate" value={`${score.mean_mention_rate?.toFixed(1)}%`} description={`±${score.std_deviation?.toFixed(2)}%`} />
            <Metric label="Sample Adequacy" value={score.sample_size_adq ? '✓ Yes (CV < 20%)' : '✗ Insufficient'} description={`CV: ${score.coefficient_of_variation?.toFixed(0)}%`} />
            <Metric label="Total Runs" value={score.n_runs?.toString()} description="Unique tracking runs" />
            <Metric label="Total Queries" value={score.total_queries?.toString() || 'N/A'} description="All prompts analyzed" />
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
