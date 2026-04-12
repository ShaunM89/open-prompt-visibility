'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, ErrorBar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';
import { fetchData, fetchVisibilityScore, fetchCompetitorComparison, fetchPromptList, fetchPromptDetail, fetchRunHistory, fetchStatisticalSummary, fetchConvergenceStatus, fetchLatestSentiment, fetchModelComparison, VisibilityScoreData, CompetitorComparison, PromptListData, StatisticalSummary, RunHistoryEntry, ConvergenceStatus, SentimentData, ModelComparisonData } from '../lib/api';

type Tab = 'overview' | 'compare' | 'competitors' | 'prompts' | 'history' | 'stats' | 'sentiment' | 'settings';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [brand, setBrand] = useState('Nike');
  const [days, setDays] = useState(30);
  
  const [overview, setOverview] = useState<any>(null);
  const [visibilityScore, setVisibilityScore] = useState<VisibilityScoreData | null>(null);
  
  const [competitorData, setCompetitorData] = useState<CompetitorComparison | null>(null);
  
  const [promptList, setPromptList] = useState<PromptListData | null>(null);
  const [promptPage, setPromptPage] = useState(1);
  const [selectedPrompt, setSelectedPrompt] = useState<any>(null);
  const [successFilter, setSuccessFilter] = useState<boolean | null>(null);
  
  const [runHistory, setRunHistory] = useState<RunHistoryEntry[]>([]);
  
  const [statSummary, setStatSummary] = useState<StatisticalSummary | null>(null);
  const [convergenceStatus, setConvergenceStatus] = useState<ConvergenceStatus | null>(null);
  const [sentimentData, setSentimentData] = useState<SentimentData | null>(null);
  const [modelComparisonData, setModelComparisonData] = useState<ModelComparisonData | null>(null);

  useEffect(() => {
    const loadData = async () => {
      setLoading(true);
      
      if (activeTab === 'overview') {
        const [overviewData, visibilityData] = await Promise.all([
          fetchData(brand, days),
          fetchVisibilityScore(brand, days)
        ]);
        setOverview(overviewData);
        setVisibilityScore(visibilityData);
      } else if (activeTab === 'competitors') {
        const compData = await fetchCompetitorComparison(brand, days);
        setCompetitorData(compData);
      } else if (activeTab === 'compare') {
        const compData = await fetchModelComparison(brand, days);
        setModelComparisonData(compData);
      } else if (activeTab === 'prompts') {
        const promptsData = await fetchPromptList(brand, days, promptPage, 25, null, successFilter);
        setPromptList(promptsData);
      } else if (activeTab === 'history') {
        const historyData = await fetchRunHistory(days);
        setRunHistory(historyData);
      } else if (activeTab === 'stats') {
        const summary = await fetchStatisticalSummary(brand, days);
        setStatSummary(summary);
        const runs = await fetchRunHistory(days);
        if (runs.length > 0) {
          const conv = await fetchConvergenceStatus(runs[0].run_id);
          setConvergenceStatus(conv);
        }
      } else if (activeTab === 'sentiment') {
        const sentiment = await fetchLatestSentiment();
        setSentimentData(sentiment);
      }
      
      setLoading(false);
    };
    
    loadData();
  }, [brand, days, activeTab, promptPage, successFilter]);

  const chartData = overview?.trends?.reduce((acc: any[], t: any) => {
    const existing = acc.find(d => d.date === t.date);
    if (existing) {
      existing[t.model_name] = t.mention_count;
    } else {
      acc.push({ date: t.date, [t.model_name]: t.mention_count });
    }
    return acc;
  }, []) || [];

  const chartModelKeys = Array.from(new Set(chartData.flatMap((d: any) => Object.keys(d)).filter((k: string) => k !== 'date'))) as string[];

  const radarData = visibilityScore?.by_model?.map(m => ({
    model: m.model_name,
    score: m.score,
    ci_lower: m.confidence_interval ? m.score - m.confidence_interval[0] : 0,
    ci_upper: m.confidence_interval ? m.confidence_interval[1] - m.score : 0,
  })) || [];

  const competitorBarData = competitorData?.all_brands?.map(br => ({
    name: br.name,
    score: br.score,
    is_target: br.is_target,
  })) || [];

  const getSuccessBadge = (isSuccess: boolean) => (
    <span className={`px-2 py-1 text-xs rounded-full ${
      isSuccess 
        ? 'bg-green-100 text-green-800' 
        : 'bg-red-100 text-red-800'
    }`}>
      {isSuccess ? 'Success' : 'No mention'}
    </span>
  );

  return (
    <main className="min-h-screen bg-gray-50">
      <header className="bg-white shadow">
        <div className="max-w-7xl mx-auto px-4 py-6 sm:px-6 lg:px-8">
          <h1 className="text-3xl font-bold text-gray-900">AI Visibility Tracker</h1>
        </div>
      </header>

      <div className="max-w-7xl mx-auto px-4 py-8 sm:px-6 lg:px-8">
        {/* Controls */}
        <div className="mb-6 flex gap-4 flex-wrap items-center">
            <select
              value={brand}
              onChange={(e) => setBrand(e.target.value)}
              className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border text-gray-900"
            >
            <option>Nike</option>
            <option>Adidas</option>
            <option>Reebok</option>
            <option>New Balance</option>
            <option>Under Armour</option>
            <option>Puma</option>
          </select>
          
            <select
              value={days}
              onChange={(e) => setDays(Number(e.target.value))}
              className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border text-gray-900"
            >
            <option value={7}>Last 7 days</option>
            <option value={30}>Last 30 days</option>
            <option value={90}>Last 90 days</option>
          </select>

          <div className="flex gap-2">
            <button
              onClick={() => setSuccessFilter(null)}
              className={`px-3 py-1 rounded text-sm ${
                successFilter === null 
                  ? 'bg-indigo-600 text-white' 
                  : 'bg-gray-200 text-gray-900'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setSuccessFilter(true)}
              className={`px-3 py-1 rounded text-sm ${
                successFilter === true 
                  ? 'bg-green-600 text-white' 
                  : 'bg-gray-200 text-gray-900'
              }`}
            >
              Success only
            </button>
            <button
              onClick={() => setSuccessFilter(false)}
              className={`px-3 py-1 rounded text-sm ${
                successFilter === false 
                  ? 'bg-red-600 text-white' 
                  : 'bg-gray-200 text-gray-900'
              }`}
            >
              No mentions
            </button>
          </div>
        </div>

        {/* Tabs */}
        <div className="mb-6 border-b border-gray-200">
          <nav className="-mb-px flex space-x-8">
            {[
              { id: 'overview', label: 'Overview' },
              { id: 'compare', label: 'Compare' },
              { id: 'competitors', label: 'Competitors' },
              { id: 'prompts', label: 'Prompt Details' },
              { id: 'history', label: 'Run History' },
              { id: 'stats', label: 'Statistics' },
              { id: 'sentiment', label: 'Sentiment' },
              { id: 'settings', label: 'Settings' },
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id as Tab); setSelectedPrompt(null); }}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-900 hover:text-gray-900 hover:border-gray-300'
                }`}
              >
                {tab.label}
              </button>
            ))}
          </nav>
        </div>

        {loading && <div className="text-center py-12">Loading...</div>}
        
        {!loading && activeTab === 'overview' && overview && (
          <>
            {/* Visibility Score KPI */}
            {visibilityScore && (
              <div className="grid grid-cols-1 gap-5 sm:grid-cols-4 mb-8">
                <div className="bg-white overflow-hidden shadow rounded-lg p-5">
                  <dt className="text-sm font-medium text-gray-900 truncate">Visibility Score</dt>
                  <dd className={`mt-2 text-4xl font-bold ${
                    visibilityScore.score >= 70 ? 'text-green-600' : 
                    visibilityScore.score >= 40 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {visibilityScore.score}%
                  </dd>
                  {visibilityScore.confidence_interval && (
                    <dd className="mt-1 text-xs text-gray-900">
                      95% CI: [{visibilityScore.confidence_interval[0].toFixed(1)} - {visibilityScore.confidence_interval[1].toFixed(1)}]%
                    </dd>
                  )}
                </div>
                
                <div className="bg-white overflow-hidden shadow rounded-lg p-5">
                  <dt className="text-sm font-medium text-gray-900 truncate">Successful Prompts</dt>
                  <dd className="mt-2 text-3xl font-semibold text-gray-900">
                    {visibilityScore.successful_prompts}
                  </dd>
                  <dd className="mt-1 text-xs text-gray-900">
                    of {visibilityScore.total_prompts} total
                  </dd>
                </div>

                <div className="bg-white overflow-hidden shadow rounded-lg p-5">
                  <dt className="text-sm font-medium text-gray-900 truncate">Total Runs</dt>
                  <dd className="mt-1 text-3xl font-semibold text-gray-900">{overview.stats?.total_runs}</dd>
                </div>
                
                <div className="bg-white overflow-hidden shadow rounded-lg p-5">
                  <dt className="text-sm font-medium text-gray-900 truncate">Total Queries</dt>
                  <dd className="mt-1 text-3xl font-semibold text-gray-900">{overview.stats?.total_records}</dd>
                </div>
              </div>
            )}

            {/* Overview Charts */}
            <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
              <div className="bg-white shadow rounded-lg p-6">
                <h2 className="text-lg font-medium text-gray-900 mb-4">Mention Trends for {brand}</h2>
                {chartData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <LineChart data={chartData}>
                      <CartesianGrid strokeDasharray="3 3" />
                      <XAxis dataKey="date" />
                      <YAxis />
                      <Tooltip />
                      <Legend />
                      {chartModelKeys.map((model: string, i: number) => (
                        <Line key={model} type="monotone" dataKey={model} stroke={`hsl(${i * 60}, 70%, 50%)`} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-gray-900 text-center py-8">No trend data available</p>
                )}
              </div>

              <div className="bg-white shadow rounded-lg p-6">
                <h2 className="text-lg font-medium text-gray-900 mb-4">Performance by Model</h2>
                {radarData.length > 0 ? (
                  <ResponsiveContainer width="100%" height={300}>
                    <RadarChart cx="50%" cy="50%" outerRadius="80%" data={radarData}>
                      <PolarGrid />
                      <PolarAngleAxis dataKey="model" />
                      <PolarRadiusAxis angle={30} domain={[0, 100]} />
                      <Radar name="Score" dataKey="score" stroke="#8884d8" fill="#8884d8" fillOpacity={0.6} />
                      <Tooltip />
                    </RadarChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-gray-900 text-center py-8">No model data available</p>
                )}
              </div>
            </div>

            {/* Model Comparison Table with CI */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Model Comparison</h2>
              {overview.modelStats.length > 0 ? (
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Model</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Query Count</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Mention Rate</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">95% CI</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {overview.modelStats.map((row: any) => (
                      <tr key={row.model_name}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {row.model_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row.total_runs}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row.mention_rate_pct}%
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {visibilityScore?.by_model.find(m => m.model_name === row.model_name)?.confidence_interval 
                            ? `[${visibilityScore.by_model.find(m => m.model_name === row.model_name)!.confidence_interval![0].toFixed(1)} - ${visibilityScore.by_model.find(m => m.model_name === row.model_name)!.confidence_interval![1].toFixed(1)}]%`
                            : 'N/A'
                          }
                        </td>
                      </tr>
                    ))}
                  </tbody>
                </table>
              ) : (
                <p className="text-gray-900 text-center py-8">No model comparison data available</p>
              )}
            </div>
          </>
        )}

        {!loading && activeTab === 'compare' && modelComparisonData && (
          <>
            {modelComparisonData.models.length < 2 ? (
              <div className="bg-white shadow rounded-lg p-8 text-center">
                <p className="text-gray-900 text-lg font-medium mb-2">Not enough models to compare</p>
                <p className="text-gray-600 text-sm">
                  Run a batch with multiple models to see head-to-head comparison. Use:
                </p>
                <pre className="bg-gray-50 p-3 rounded mt-3 text-xs overflow-x-auto inline-block text-left">{`pvt run --models "ollama:model-a,ollama:model-b"
pvt run --scenario full_comparison`}</pre>
              </div>
            ) : (
              <>
                {/* Head-to-head comparison chart */}
                <div className="grid grid-cols-1 lg:grid-cols-2 gap-8 mb-8">
                  <div className="bg-white shadow rounded-lg p-6">
                    <h2 className="text-lg font-medium text-gray-900 mb-4">Mention Rate by Model</h2>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={modelComparisonData.models.map(m => ({
                        name: m.model_name,
                        rate: m.mention_rate,
                        ci_lower: m.confidence_interval ? m.mention_rate - m.confidence_interval[0] : 0,
                        ci_upper: m.confidence_interval ? m.confidence_interval[1] - m.mention_rate : 0,
                      }))}>
                        <CartesianGrid strokeDasharray="3 3" />
                        <XAxis dataKey="name" />
                        <YAxis domain={[0, 100]} />
                        <Tooltip formatter={(value) => `${Number(value).toFixed(1)}%`} />
                        <Bar dataKey="rate" fill="#6366f1">
                          {modelComparisonData.models[0] && (
                            <ErrorBar dataKey="ci_lower" width={4} strokeWidth={2} direction="y" />
                          )}
                        </Bar>
                      </BarChart>
                    </ResponsiveContainer>
                  </div>

                  <div className="bg-white shadow rounded-lg p-6">
                    <h2 className="text-lg font-medium text-gray-900 mb-4">Delta from Best Model</h2>
                    <ResponsiveContainer width="100%" height={300}>
                      <BarChart data={modelComparisonData.models.map((m, _i) => {
                        const bestRate = modelComparisonData.models[0]?.mention_rate || 0;
                        return {
                          name: m.model_name,
                          delta: m.mention_rate - bestRate,
                        };
                      })} layout="vertical">
                        <XAxis type="number" tickFormatter={(v: number) => `${v > 0 ? '+' : ''}${v.toFixed(1)}%`} />
                        <YAxis type="category" dataKey="name" width={140} />
                        <CartesianGrid strokeDasharray="3 3" />
                        <Tooltip formatter={(value) => `${Number(value) > 0 ? '+' : ''}${Number(value).toFixed(1)}%`} />
                        <Bar dataKey="delta" fill="#f59e0b" />
                      </BarChart>
                    </ResponsiveContainer>
                  </div>
                </div>

                {/* Detailed comparison table */}
                <div className="bg-white shadow rounded-lg p-6 mb-8">
                  <h2 className="text-lg font-medium text-gray-900 mb-4">
                    Head-to-Head Comparison for {brand} ({days} days)
                  </h2>
                  <table className="min-w-full divide-y divide-gray-200">
                    <thead className="bg-gray-50">
                      <tr>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Model</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Mention Rate</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">95% CI</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Queries</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Mentions</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Std Error</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Significance</th>
                        <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Delta</th>
                      </tr>
                    </thead>
                    <tbody className="bg-white divide-y divide-gray-200">
                      {modelComparisonData.models.map((m, i) => {
                        const bestRate = modelComparisonData.models[0]?.mention_rate || 0;
                        const delta = i === 0 ? 0 : m.mention_rate - bestRate;
                        return (
                          <tr key={m.model_name} className={i === 0 ? 'bg-green-50' : ''}>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                              {m.model_name}
                              {i === 0 && <span className="ml-2 text-xs bg-green-100 text-green-800 px-2 py-0.5 rounded">Best</span>}
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm font-semibold text-gray-900">
                              {m.mention_rate.toFixed(1)}%
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {m.confidence_interval
                                ? `[${m.confidence_interval[0].toFixed(1)} - ${m.confidence_interval[1].toFixed(1)}]%`
                                : 'N/A'
                              }
                            </td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{m.total_runs}</td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{m.mentions}</td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">{m.standard_error.toFixed(2)}%</td>
                            <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                              {m.statistical_significance === 'significant' ? (
                                <span className="px-2 py-1 text-xs rounded-full bg-green-100 text-green-800">Significant</span>
                              ) : m.statistical_significance === 'N/A' ? (
                                <span className="px-2 py-1 text-xs rounded-full bg-gray-100 text-gray-800">N/A</span>
                              ) : (
                                <span className="px-2 py-1 text-xs rounded-full bg-yellow-100 text-yellow-800">{m.statistical_significance}</span>
                              )}
                            </td>
                            <td className={`px-6 py-4 whitespace-nowrap text-sm font-medium ${i === 0 ? 'text-green-600' : delta >= 0 ? 'text-green-600' : 'text-red-600'}`}>
                              {i === 0 ? '\u2014' : `${delta >= 0 ? '+' : ''}${delta.toFixed(1)}%`}
                            </td>
                          </tr>
                        );
                      })}
                    </tbody>
                  </table>
                </div>

                {/* Overlap analysis */}
                {modelComparisonData.models.length === 2 && modelComparisonData.models[0].confidence_interval && modelComparisonData.models[1].confidence_interval && (
                  <div className="bg-white shadow rounded-lg p-6">
                    <h2 className="text-lg font-medium text-gray-900 mb-4">CI Overlap Analysis</h2>
                    {(() => {
                      const m1 = modelComparisonData.models[0];
                      const m2 = modelComparisonData.models[1];
                      const ci1 = m1.confidence_interval!;
                      const ci2 = m2.confidence_interval!;
                      const overlaps = ci1[1] >= ci2[0] && ci2[1] >= ci1[0];
                      return (
                        <div>
                          <div className="flex items-center gap-4 mb-4">
                            <span className={`px-3 py-1 rounded-full text-sm font-medium ${overlaps ? 'bg-yellow-100 text-yellow-800' : 'bg-green-100 text-green-800'}`}>
                              {overlaps ? 'CIs Overlap' : 'CIs Do Not Overlap'}
                            </span>
                            <span className="text-sm text-gray-600">
                              {overlaps
                                ? 'The confidence intervals overlap, meaning the difference between models may not be statistically significant.'
                                : 'The confidence intervals do not overlap, suggesting a statistically meaningful difference between models.'}
                            </span>
                          </div>
                          {/* Visual CI comparison */}
                          <div className="space-y-3">
                            {modelComparisonData.models.map((m) => {
                              const ci = m.confidence_interval!;
                              const range = Math.max(modelComparisonData.models[0].confidence_interval![1], modelComparisonData.models[1]?.confidence_interval![1] || 0) -
                                            Math.min(modelComparisonData.models[0].confidence_interval![0], modelComparisonData.models[1]?.confidence_interval![0] || 100);
                              const left = ((ci[0] - Math.min(modelComparisonData.models[0].confidence_interval![0], modelComparisonData.models[1]?.confidence_interval![0] || 100)) / (range || 1)) * 100;
                              const width = ((ci[1] - ci[0]) / (range || 1)) * 100;
                              return (
                                <div key={m.model_name} className="flex items-center gap-3">
                                  <span className="text-sm font-medium text-gray-900 w-40 truncate">{m.model_name}</span>
                                  <div className="flex-1 bg-gray-100 rounded-full h-6 relative">
                                    <div
                                      className="absolute h-full bg-indigo-400 rounded-full opacity-60"
                                      style={{ left: `${left}%`, width: `${Math.max(width, 1)}%` }}
                                    />
                                    <div
                                      className="absolute h-full w-0.5 bg-indigo-900"
                                      style={{ left: `${((m.mention_rate - (Math.min(modelComparisonData.models[0].confidence_interval![0], modelComparisonData.models[1]?.confidence_interval![0] || 100))) / (range || 1)) * 100}%` }}
                                    />
                                  </div>
                                  <span className="text-xs text-gray-600 w-32 text-right">
                                    {ci[0].toFixed(1)}% \u2013 {ci[1].toFixed(1)}%
                                  </span>
                                </div>
                              );
                            })}
                          </div>
                        </div>
                      );
                    })()}
                  </div>
                )}
              </>
            )}
          </>
        )}

        {!loading && activeTab === 'competitors' && competitorData && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Competitor Comparison ({brand} vs competitors)
            </h2>
            
            {/* Bar chart with competitor comparison */}
            {competitorBarData.length > 0 && (
              <div className="mb-6">
                <ResponsiveContainer width="100%" height={300}>
                  <BarChart data={competitorBarData} layout="vertical">
                    <XAxis type="number" domain={[0, 100]} />
                    <YAxis type="category" dataKey="name" width={120} />
                    <CartesianGrid strokeDasharray="3 3" />
                    <Tooltip formatter={(value) => `${value}%`} />
                    <Bar dataKey="score" fill="#6366f1" />
                  </BarChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="mb-6">
              <p className="text-sm text-gray-900 mb-2">
                All brands sorted by mention rate ({days} days)
              </p>
              <div className="space-y-3">
                {(competitorData.all_brands || []).map((br, idx) => (
                  <div key={br.name} className="flex items-center">
                    <div className="w-48 text-sm font-medium text-gray-900 truncate">
                      {br.name}
                      {br.is_target && <span className="ml-1 text-xs text-indigo-600">(target)</span>}
                    </div>
                    <div className="flex-1 mx-4 bg-gray-200 rounded-full h-6">
                      <div 
                        className={`h-6 rounded-full ${br.is_target ? 'bg-indigo-600' : 'bg-gray-500'}`}
                        style={{ width: `${br.score}%` }}
                      />
                    </div>
                    <div className="w-24 text-sm font-medium text-gray-900 text-right">
                      {br.score}%
                    </div>
                    <div className="w-48 text-xs text-gray-900 text-right pl-4">
                      {br.successful_prompts}/{br.total_prompts}
                    </div>
                  </div>
                ))}
              </div>
            </div>

            <h3 className="text-md font-medium text-gray-900 mb-3">Detailed Breakdown</h3>
            <table className="min-w-full divide-y divide-gray-200">
              <thead className="bg-gray-50">
                <tr>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Brand</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Query Count</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-900 uppercase">Mention Rate</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {(competitorData.all_brands || []).map((br) => (
                  <tr key={br.name}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {br.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {br.is_target ? 'Target' : 'Competitor'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {br.total_prompts}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                      {br.score}%
                    </td>
                  </tr>
                ))}
              </tbody>
            </table>
          </div>
        )}

        {!loading && activeTab === 'prompts' && promptList && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Prompt List ({promptList.pagination.total} results)
            </h2>
            
            {selectedPrompt && (
              <div className="mb-6 bg-gray-50 p-4 rounded-lg border border-gray-200">
                <div className="flex justify-between items-start mb-3">
                  <h3 className="font-medium text-gray-900">Prompt Details</h3>
                  <button
                    onClick={() => setSelectedPrompt(null)}
                    className="text-gray-900 hover:text-gray-900"
                  >
                    ✕
                  </button>
                </div>
                
                <div className="mb-4">
                  <p className="text-sm text-gray-900 mb-2">Prompt:</p>
                  <div className="bg-white p-3 rounded border text-sm font-mono text-gray-900">
                    {selectedPrompt.prompt}
                  </div>
                </div>
                
                {selectedPrompt.highlighted_response ? (
                  <div>
                    <p className="text-sm text-gray-900 mb-2">Response (highlighted):</p>
                     <div 
                       className="bg-white p-3 rounded border text-sm prose max-w-none text-gray-900"
                       dangerouslySetInnerHTML={{ __html: selectedPrompt.highlighted_response }}
                     />
                  </div>
                ) : (
                  <div>
                    <p className="text-sm text-gray-900 mb-2">Response:</p>
                    <div className="bg-white p-3 rounded border text-sm whitespace-pre-wrap text-gray-900">
                      {selectedPrompt.response_text}
                    </div>
                  </div>
                )}
                
                <div className="mt-3 flex gap-4 text-sm text-gray-900">
                  <div>Model: {selectedPrompt.model_name}</div>
                  <div>Date: {new Date(selectedPrompt.detected_at).toLocaleString()}</div>
                  <div>Mentions: {JSON.stringify(selectedPrompt.mentions)}</div>
                </div>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Prompt</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Model</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Mentions</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Date</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {promptList.prompts.map((prompt) => (
                    <tr 
                      key={prompt.id} 
                      onClick={() => fetchPromptDetail(prompt.id).then(setSelectedPrompt)}
                      className="cursor-pointer hover:bg-gray-50"
                    >
                      <td className="px-4 py-3 whitespace-nowrap">
                        {getSuccessBadge(prompt.is_success)}
                      </td>
                      <td className="px-4 py-3 text-sm text-gray-900 max-w-md truncate">
                        {prompt.prompt}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {prompt.model_name}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {Object.keys(prompt.mentions).join(', ') || 'None'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {new Date(prompt.detected_at).toLocaleDateString()}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>

            {/* Pagination */}
            {promptList.pagination.total_pages > 1 && (
              <div className="mt-4 flex justify-between items-center">
                <button
                  onClick={() => setPromptPage(p => Math.max(1, p - 1))}
                  disabled={promptPage === 1}
                  className="px-4 py-2 bg-gray-200 text-gray-900 rounded disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-900">
                  Page {promptPage} of {promptList.pagination.total_pages}
                </span>
                <button
                  onClick={() => setPromptPage(p => Math.min(promptList.pagination.total_pages, p + 1))}
                  disabled={promptPage === promptList.pagination.total_pages}
                  className="px-4 py-2 bg-gray-200 text-gray-900 rounded disabled:opacity-50"
                >
                  Next
                </button>
              </div>
            )}
          </div>
        )}

        {!loading && activeTab === 'history' && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Run History ({runHistory.length} runs)</h2>
            
            {/* Run rate trend chart */}
            {runHistory.length > 1 && (
              <div className="mb-6">
                <h3 className="text-md font-medium text-gray-900 mb-3">Success Rate Over Runs</h3>
                <ResponsiveContainer width="100%" height={250}>
                  <LineChart data={runHistory.map(r => ({
                    name: `#${r.run_id}`,
                    rate: r.success_rate,
                    queries: r.total_queries,
                  }))}>
                    <CartesianGrid strokeDasharray="3 3" />
                    <XAxis dataKey="name" />
                    <YAxis domain={[0, 100]} />
                    <Tooltip />
                    <Line type="monotone" dataKey="rate" stroke="#6366f1" strokeWidth={2} />
                  </LineChart>
                </ResponsiveContainer>
              </div>
            )}

            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Run ID</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Duration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Queries</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Success Rate</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-900 uppercase">Models</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {runHistory.map((run) => (
                    <tr key={run.run_id}>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        #{run.run_id}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {new Date(run.started_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {run.duration || 'N/A'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {run.successful_queries}/{run.total_queries}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm">
                        <span className={`px-2 py-1 rounded ${
                          run.success_rate >= 70 ? 'bg-green-100 text-green-800' :
                          run.success_rate >= 40 ? 'bg-yellow-100 text-yellow-800' :
                          'bg-red-100 text-red-800'
                        }`}>
                          {run.success_rate}%
                        </span>
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-900">
                        {run.models_used.join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          
            {!runHistory.length && (
              <p className="text-gray-900 text-center py-8">No runs found in this period</p>
            )}
          </div>
        )}

        {!loading && activeTab === 'stats' && statSummary && (
          <>
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Statistical Summary ({statSummary.brand})</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900 mb-3">Key Metrics</h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Analysis Period:</dt>
                    <dd className="font-medium">{statSummary.period_days} days</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Number of Runs:</dt>
                    <dd className="font-medium">{statSummary.n_runs}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Mean Mention Rate:</dt>
                    <dd className="font-medium">{statSummary.mean_mention_rate}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Std Deviation:</dt>
                    <dd className="font-medium">{statSummary.std_deviation.toFixed(2)}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Std Error:</dt>
                    <dd className="font-medium">{statSummary.std_error.toFixed(2)}%</dd>
                  </div>
                </dl>
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900 mb-3">Confidence Analysis</h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-900">95% Confidence Interval:</dt>
                    <dd className="font-medium">
                      {statSummary.confidence_interval_95 
                        ? `[${statSummary.confidence_interval_95[0].toFixed(1)} - ${statSummary.confidence_interval_95[1].toFixed(1)}]%`
                        : 'N/A'
                      }
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Coefficient of Variation:</dt>
                    <dd className="font-medium">
                      <span className={
                        statSummary.coefficient_of_variation < 20 ? 'text-green-600' :
                        statSummary.coefficient_of_variation < 30 ? 'text-yellow-600' :
                        'text-red-600'
                      }>
                        {statSummary.coefficient_of_variation.toFixed(1)}%
                      </span>
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Min Rate:</dt>
                    <dd className="font-medium">{statSummary.min_rate}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Max Rate:</dt>
                    <dd className="font-medium">{statSummary.max_rate}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-900">Range:</dt>
                    <dd className="font-medium">{statSummary.rate_range.toFixed(1)}%</dd>
                  </div>
                </dl>
              </div>
            </div>

            {/* CI Visualization */}
            {statSummary.confidence_interval_95 && (
              <div className="bg-white border border-gray-200 rounded-lg p-4 mb-6">
                <h3 className="font-medium text-gray-900 mb-3">95% Confidence Interval Visualization</h3>
                <div className="relative h-12 bg-gray-100 rounded-full overflow-hidden">
                  <div
                    className="absolute h-full bg-indigo-200 rounded-full"
                    style={{
                      left: `${Math.max(0, statSummary.confidence_interval_95[0])}%`,
                      width: `${Math.min(100, statSummary.confidence_interval_95[1]) - Math.max(0, statSummary.confidence_interval_95[0])}%`,
                    }}
                  />
                  <div
                    className="absolute h-full w-1 bg-indigo-600"
                    style={{ left: `${statSummary.mean_mention_rate}%` }}
                  />
                </div>
                <div className="flex justify-between text-xs text-gray-500 mt-1">
                  <span>0%</span>
                  <span className="text-indigo-600 font-medium">
                    Mean: {statSummary.mean_mention_rate}% (CI: {statSummary.confidence_interval_95[0].toFixed(1)}% - {statSummary.confidence_interval_95[1].toFixed(1)}%)
                  </span>
                  <span>100%</span>
                </div>
              </div>
            )}

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <h3 className="font-medium text-blue-900 mb-2">Interpretation</h3>
              <p className="text-sm text-blue-800">{statSummary.interpretation}</p>
            </div>

            {/* Drift / Anomaly indicators */}
            {statSummary.anomalies.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h3 className="font-medium text-yellow-900 mb-3">
                  <span className="inline-flex items-center">
                    <svg className="w-5 h-5 mr-2 text-yellow-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                      <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M12 9v2m0 4h.01m-6.938 4h13.856c1.54 0 2.502-1.667 1.732-2.5L13.732 4c-.77-.833-1.964-.833-2.732 0L4.082 16.5c-.77.833.192 2.5 1.732 2.5z" />
                    </svg>
                    Drift Detected ({statSummary.anomalies.length} anomalous run{statSummary.anomalies.length > 1 ? 's' : ''})
                  </span>
                </h3>
                <p className="text-sm text-yellow-800 mb-2">
                  These runs show mention rates &gt;2 standard deviations from the mean — possible data drift or model behavior changes:
                </p>
                <ul className="text-sm text-yellow-800 space-y-2">
                  {statSummary.anomalies.map((anom) => (
                    <li key={anom.run_id} className="flex items-center gap-2">
                      <span className={`inline-flex items-center rounded-full px-2 py-0.5 text-xs font-medium ${
                        anom.deviation > 0 ? 'bg-green-100 text-green-800' : 'bg-red-100 text-red-800'
                      }`}>
                        {anom.deviation > 0 ? 'Above' : 'Below'} mean
                      </span>
                      <span>
                        Run #{anom.run_id}: <strong>{anom.rate}%</strong> (deviation: {anom.deviation.toFixed(2)}σ)
                      </span>
                    </li>
                  ))}
                </ul>
              </div>
            )}

            {statSummary.anomalies.length === 0 && statSummary.n_runs > 0 && (
              <div className="bg-green-50 border border-green-200 rounded-lg p-4">
                <h3 className="font-medium text-green-900 mb-2 flex items-center">
                  <svg className="w-5 h-5 mr-2 text-green-600" fill="none" stroke="currentColor" viewBox="0 0 24 24">
                    <path strokeLinecap="round" strokeLinejoin="round" strokeWidth={2} d="M9 12l2 2 4-4m6 2a9 9 0 11-18 0 9 9 0 0118 0z" />
                  </svg>
                  No Drift Detected
                </h3>
                <p className="text-sm text-green-800">
                  All runs are within 2 standard deviations of the mean. Brand visibility is stable.
                </p>
              </div>
            )}
          </div>

          {convergenceStatus && convergenceStatus.adaptive_enabled && (
            <div className="bg-white shadow rounded-lg p-6 mt-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Convergence Report (Run #{convergenceStatus.run_id})</h2>
              <div className="grid grid-cols-2 md:grid-cols-4 gap-4 mb-6">
                <div className="bg-gray-50 p-3 rounded">
                  <p className="text-xs text-gray-900">Pairs Converged</p>
                  <p className="text-lg font-bold text-gray-900">
                    {convergenceStatus.summary.converged_pairs}/{convergenceStatus.summary.total_pairs}
                  </p>
                </div>
                <div className="bg-gray-50 p-3 rounded">
                  <p className="text-xs text-gray-900">Total Queries</p>
                  <p className="text-lg font-bold text-gray-900">{convergenceStatus.summary.total_queries}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded">
                  <p className="text-xs text-gray-900">Queries Saved</p>
                  <p className="text-lg font-bold text-green-600">~{convergenceStatus.summary.estimated_queries_saved}</p>
                </div>
                <div className="bg-gray-50 p-3 rounded">
                  <p className="text-xs text-gray-900">Target CI Width</p>
                  <p className="text-lg font-bold text-gray-900">{convergenceStatus.target_ci_width}%</p>
                </div>
              </div>
              <h3 className="font-medium text-gray-900 mb-3">Per-Model Status</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-3">
                {(() => {
                  const byModel: Record<string, any[]> = {};
                  for (const p of convergenceStatus.pairs) {
                    if (!byModel[p.model]) byModel[p.model] = [];
                    byModel[p.model].push(p);
                  }
                  return Object.entries(byModel).map(([model, pairs]) => {
                    const primary = pairs.find((p: any) => p.brand === brand);
                    const allDone = pairs.every((p: any) => p.converged);
                    return (
                      <div key={model} className={`p-3 rounded border ${allDone ? 'border-green-200 bg-green-50' : 'border-amber-200 bg-amber-50'}`}>
                        <div className="flex justify-between items-center mb-1">
                          <span className="text-sm font-medium text-gray-900">{model}</span>
                          <span className={`text-xs px-2 py-0.5 rounded ${allDone ? 'bg-green-200 text-green-800' : 'bg-amber-200 text-amber-800'}`}>
                            {allDone ? 'Converged' : 'Sampling'}
                          </span>
                        </div>
                        {primary && (
                          <div className="text-xs text-gray-900">
                            {primary.queries_completed} queries | CI width: {primary.ci_width?.toFixed(1) ?? 'N/A'}%
                            {primary.ci && <span className="ml-1">[{primary.ci[0].toFixed(1)}-{primary.ci[1].toFixed(1)}]</span>}
                          </div>
                        )}
                      </div>
                    );
                  });
                })()}
              </div>
            </div>
          )}
          </>
        )}

        {!loading && activeTab === 'sentiment' && (
          <div className="space-y-6">
            <div className="bg-white shadow rounded-lg p-6">
              <div className="flex items-center justify-between mb-4">
                <h2 className="text-lg font-medium text-gray-900">Sentiment Analysis</h2>
                {sentimentData && sentimentData.mode !== 'none' && (
                  <span className={`text-xs px-2 py-1 rounded ${
                    sentimentData.mode === 'fast' ? 'bg-blue-100 text-blue-800' : 'bg-purple-100 text-purple-800'
                  }`}>
                    {sentimentData.mode === 'fast' ? 'Fast Mode' : 'Detailed Mode'}
                  </span>
                )}
              </div>

              {!sentimentData || sentimentData.mode === 'none' ? (
                <div className="text-center py-12">
                  <p className="text-gray-500">No sentiment data available for this run.</p>
                  <p className="text-sm text-gray-400 mt-2">
                    Enable sentiment analysis in config or run with <code className="bg-gray-100 px-1 rounded text-xs">--sentiment-mode fast</code>
                  </p>
                </div>
              ) : (
                <>
                  <div className="grid grid-cols-1 md:grid-cols-2 lg:grid-cols-3 gap-4 mb-6">
                    {Object.entries(sentimentData.brands).map(([brandName, data]) => {
                      const composite = data.avg_composite ?? data.composite;
                      const prominence = data.avg_prominence ?? data.prominence;
                      const sentiment = data.avg_sentiment ?? data.sentiment;
                      const sampleSize = data.sample_size ?? 0;
                      const colorClass = composite >= 0.3
                        ? 'border-green-400 bg-green-50'
                        : composite <= -0.3
                        ? 'border-red-400 bg-red-50'
                        : 'border-yellow-400 bg-yellow-50';
                      const textColor = composite >= 0.3
                        ? 'text-green-700'
                        : composite <= -0.3
                        ? 'text-red-700'
                        : 'text-yellow-700';

                      return (
                        <div key={brandName} className={`border-l-4 ${colorClass} rounded-lg p-4 shadow-sm`}>
                          <div className="flex items-center justify-between mb-3">
                            <h3 className="font-semibold text-gray-900">{brandName}</h3>
                            <span className={`text-2xl font-bold ${textColor}`}>
                              {composite >= 0 ? '+' : ''}{composite.toFixed(3)}
                            </span>
                          </div>
                          <div className="space-y-2 text-sm">
                            <div className="flex justify-between">
                              <span className="text-gray-600">Prominence</span>
                              <span className="font-medium text-gray-900">{prominence.toFixed(3)}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-1.5">
                              <div className="bg-blue-500 h-1.5 rounded-full" style={{ width: `${prominence * 100}%` }} />
                            </div>
                            <div className="flex justify-between">
                              <span className="text-gray-600">Sentiment</span>
                              <span className={`font-medium ${textColor}`}>{sentiment >= 0 ? '+' : ''}{sentiment.toFixed(3)}</span>
                            </div>
                            <div className="w-full bg-gray-200 rounded-full h-1.5">
                              <div
                                className={`h-1.5 rounded-full ${composite >= 0 ? 'bg-green-500' : 'bg-red-500'}`}
                                style={{ width: `${Math.min(Math.abs(sentiment) * 100, 100)}%` }}
                              />
                            </div>
                            {sampleSize > 0 && (
                              <div className="flex justify-between text-xs text-gray-500 mt-1">
                                <span>Sample size</span>
                                <span>{sampleSize}</span>
                              </div>
                            )}
                          </div>
                          {data.summary && (
                            <p className="text-xs text-gray-500 mt-3 italic border-t pt-2">{data.summary}</p>
                          )}
                        </div>
                      );
                    })}
                  </div>

                  {sentimentData.mode === 'detailed' && Object.entries(sentimentData.brands).some(([_, d]) => d.scores && d.scores.length > 0) && (
                    <div className="border border-gray-200 rounded-lg p-4">
                      <h3 className="font-medium text-gray-900 mb-3">Sentiment Over Queries</h3>
                      <ResponsiveContainer width="100%" height={300}>
                        <LineChart>
                          <CartesianGrid strokeDasharray="3 3" />
                          <XAxis dataKey="query" type="number" domain={[1, 'auto']} label={{ value: 'Query #', position: 'insideBottom', offset: -5 }} />
                          <YAxis domain={[-1, 1]} label={{ value: 'Composite Score', angle: -90, position: 'insideLeft' }} />
                          <Tooltip />
                          <Legend />
                          {Object.entries(sentimentData.brands).map(([brandName, data], idx) => {
                            if (!data.scores || data.scores.length === 0) return null;
                            const colors = ['#3b82f6', '#ef4444', '#22c55e', '#f59e0b', '#8b5cf6'];
                            const lineData = data.scores.map((s, i) => ({ query: i + 1, [brandName]: s.composite }));
                            return (
                              <Line
                                key={brandName}
                                data={lineData}
                                dataKey={brandName}
                                stroke={colors[idx % colors.length]}
                                dot={{ r: 3 }}
                                type="monotone"
                              />
                            );
                          })}
                        </LineChart>
                      </ResponsiveContainer>
                    </div>
                  )}

                  {sentimentData.started_at && (
                    <div className="text-xs text-gray-400 mt-4">
                      Run #{sentimentData.run_id} | {sentimentData.started_at} → {sentimentData.completed_at}
                    </div>
                  )}
                </>
              )}
            </div>
          </div>
        )}

        {!loading && activeTab === 'settings' && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-6">Settings</h2>

            <div className="grid grid-cols-1 md:grid-cols-2 gap-8">
              {/* Prompt Variations */}
              <div className="border border-gray-200 rounded-lg p-5">
                <h3 className="font-medium text-gray-900 mb-4">Prompt Variations</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Generate semantically similar variations of base prompts to capture topic diversity
                  and average out wording bias.
                </p>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-900">Status</span>
                    <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Config-driven</span>
                  </div>
                  <div className="text-sm text-gray-700">
                    <p>Configure in <code className="bg-gray-100 px-1 rounded text-xs">configs/tool/config.yaml</code>:</p>
                    <pre className="bg-gray-50 p-3 rounded mt-2 text-xs overflow-x-auto">{`tracking:
  prompt_variations:
    enabled: true
    num_variations: 3
    strategy: "semantic"`}</pre>
                  </div>
                  <div className="text-sm text-gray-700">
                    <p>Or use CLI flags:</p>
                    <pre className="bg-gray-50 p-3 rounded mt-2 text-xs overflow-x-auto">{`python main.py run \\
  --enable-variations \\
  --num-variations 3 \\
  --variation-strategy semantic`}</pre>
                  </div>
                </div>
              </div>

              {/* Auto-Generated Prompts */}
              <div className="border border-gray-200 rounded-lg p-5">
                <h3 className="font-medium text-gray-900 mb-4">Auto-Generated Prompts</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Automatically generate relevant prompts based on brand domain and subtopics
                  to increase data depth.
                </p>
                <div className="space-y-3">
                  <div className="flex items-center justify-between">
                    <span className="text-sm text-gray-900">Status</span>
                    <span className="text-xs bg-yellow-100 text-yellow-800 px-2 py-1 rounded">Config-driven</span>
                  </div>
                  <div className="text-sm text-gray-700">
                    <p>Configure in <code className="bg-gray-100 px-1 rounded text-xs">configs/tool/config.yaml</code>:</p>
                    <pre className="bg-gray-50 p-3 rounded mt-2 text-xs overflow-x-auto">{`tracking:
  auto_prompt_generation:
    enabled: true
    per_brand_prompts: 15
    categories:
      - comparison
      - recommendation
      - trends`}</pre>
                  </div>
                  <div className="text-sm text-gray-700">
                    <p>Or use CLI flags:</p>
                    <pre className="bg-gray-50 p-3 rounded mt-2 text-xs overflow-x-auto">{`python main.py run \\
  --enable-auto-gen \\
  --auto-gen-per-brand 5`}</pre>
                  </div>
                </div>
              </div>

              {/* Statistical Analysis */}
              <div className="border border-gray-200 rounded-lg p-5">
                <h3 className="font-medium text-gray-900 mb-4">Statistical Analysis</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Configure confidence levels, anomaly detection thresholds, and run history tracking.
                </p>
                <div className="text-sm text-gray-700">
                  <pre className="bg-gray-50 p-3 rounded text-xs overflow-x-auto">{`tracking:
  statistical_analysis:
    enabled: true
    confidence_level: 95
    track_run_history: true
    min_runs_for_significance: 5
    anomaly_threshold: 2.0`}</pre>
                </div>
              </div>

              {/* Brand Domain */}
              <div className="border border-gray-200 rounded-lg p-5">
                <h3 className="font-medium text-gray-900 mb-4">Brand Domain Configuration</h3>
                <p className="text-sm text-gray-600 mb-4">
                  Add domain metadata to brands for auto-generation and subtopic coverage.
                </p>
                <div className="text-sm text-gray-700">
                  <pre className="bg-gray-50 p-3 rounded text-xs overflow-x-auto">{`# configs/users/brands.yaml
brands:
  - name: "Nike"
    keywords: ["Nike", "Swoosh"]
    domain: "athletic footwear & apparel"
    subtopics:
      - running
      - basketball
      - sustainability
    target_audience:
      - athletes
      - fitness enthusiasts`}</pre>
                </div>
              </div>
            </div>

            {/* Quick reference */}
            <div className="mt-8 border-t pt-6">
              <h3 className="font-medium text-gray-900 mb-3">Quick Reference</h3>
              <div className="grid grid-cols-1 md:grid-cols-2 gap-4 text-sm">
                <div className="bg-gray-50 p-3 rounded">
                  <p className="font-medium text-gray-900 mb-1">Start API server</p>
                  <code className="text-xs">python main.py serve</code>
                </div>
                <div className="bg-gray-50 p-3 rounded">
                  <p className="font-medium text-gray-900 mb-1">Run tracking batch</p>
                  <code className="text-xs">python main.py run</code>
                </div>
                <div className="bg-gray-50 p-3 rounded">
                  <p className="font-medium text-gray-900 mb-1">Export data</p>
                  <code className="text-xs">python main.py export --format csv</code>
                </div>
                <div className="bg-gray-50 p-3 rounded">
                  <p className="font-medium text-gray-900 mb-1">View stats</p>
                  <code className="text-xs">python main.py stats</code>
                </div>
              </div>
            </div>
          </div>
        )}
      </div>
    </main>
  );
}
