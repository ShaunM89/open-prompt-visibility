'use client';

import { useEffect, useState } from 'react';
import { LineChart, Line, XAxis, YAxis, CartesianGrid, Tooltip, Legend, ResponsiveContainer, BarChart, Bar, RadarChart, PolarGrid, PolarAngleAxis, PolarRadiusAxis, Radar } from 'recharts';
import { fetchData, fetchVisibilityScore, fetchCompetitorComparison, fetchPromptList, fetchPromptDetail, fetchRunHistory, fetchStatisticalSummary, VisibilityScoreData, CompetitorComparison, PromptListData, StatisticalSummary, RunHistoryEntry } from '../lib/api';

type Tab = 'overview' | 'competitors' | 'prompts' | 'history' | 'stats';

export default function Home() {
  const [activeTab, setActiveTab] = useState<Tab>('overview');
  const [loading, setLoading] = useState(true);
  const [brand, setBrand] = useState('Nike');
  const [days, setDays] = useState(30);
  
  // Overview data
  const [overview, setOverview] = useState<any>(null);
  const [visibilityScore, setVisibilityScore] = useState<VisibilityScoreData | null>(null);
  
  // Competitor data
  const [competitorData, setCompetitorData] = useState<CompetitorComparison | null>(null);
  
  // Prompt list data
  const [promptList, setPromptList] = useState<PromptListData | null>(null);
  const [promptPage, setPromptPage] = useState(1);
  const [selectedPrompt, setSelectedPrompt] = useState<any>(null);
  const [successFilter, setSuccessFilter] = useState<boolean | null>(null);
  
  // Run history
  const [runHistory, setRunHistory] = useState<RunHistoryEntry[]>([]);
  
  // Statistical summary
  const [statSummary, setStatSummary] = useState<StatisticalSummary | null>(null);

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
      } else if (activeTab === 'prompts') {
        const promptsData = await fetchPromptList(brand, days, promptPage, 25, null, successFilter);
        setPromptList(promptsData);
      } else if (activeTab === 'history') {
        const historyData = await fetchRunHistory(days);
        setRunHistory(historyData);
      } else if (activeTab === 'stats') {
        const summary = await fetchStatisticalSummary(brand, days);
        setStatSummary(summary);
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

  const radarData = visibilityScore?.by_model?.map(m => ({
    model: m.model_name,
    score: m.score
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
            className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border"
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
            className="rounded-md border-gray-300 shadow-sm focus:border-indigo-500 focus:ring-indigo-500 p-2 border"
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
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              All
            </button>
            <button
              onClick={() => setSuccessFilter(true)}
              className={`px-3 py-1 rounded text-sm ${
                successFilter === true 
                  ? 'bg-green-600 text-white' 
                  : 'bg-gray-200 text-gray-700'
              }`}
            >
              Success only
            </button>
            <button
              onClick={() => setSuccessFilter(false)}
              className={`px-3 py-1 rounded text-sm ${
                successFilter === false 
                  ? 'bg-red-600 text-white' 
                  : 'bg-gray-200 text-gray-700'
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
              { id: 'competitors', label: 'Competitors' },
              { id: 'prompts', label: 'Prompt Details' },
              { id: 'history', label: 'Run History' },
              { id: 'stats', label: 'Statistics' }
            ].map((tab) => (
              <button
                key={tab.id}
                onClick={() => { setActiveTab(tab.id as Tab); setSelectedPrompt(null); }}
                className={`py-4 px-1 border-b-2 font-medium text-sm ${
                  activeTab === tab.id
                    ? 'border-indigo-500 text-indigo-600'
                    : 'border-transparent text-gray-500 hover:text-gray-700 hover:border-gray-300'
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
                  <dt className="text-sm font-medium text-gray-500 truncate">Visibility Score</dt>
                  <dd className={`mt-2 text-4xl font-bold ${
                    visibilityScore.score >= 70 ? 'text-green-600' : 
                    visibilityScore.score >= 40 ? 'text-yellow-600' : 'text-red-600'
                  }`}>
                    {visibilityScore.score}%
                  </dd>
                  {visibilityScore.confidence_interval && (
                    <dd className="mt-1 text-xs text-gray-500">
                      95% CI: [{visibilityScore.confidence_interval[0].toFixed(1)} - {visibilityScore.confidence_interval[1].toFixed(1)}]%
                    </dd>
                  )}
                </div>
                
                <div className="bg-white overflow-hidden shadow rounded-lg p-5">
                  <dt className="text-sm font-medium text-gray-500 truncate">Successful Prompts</dt>
                  <dd className="mt-2 text-3xl font-semibold text-gray-900">
                    {visibilityScore.successful_prompts}
                  </dd>
                  <dd className="mt-1 text-xs text-gray-500">
                    of {visibilityScore.total_prompts} total
                  </dd>
                </div>

                <div className="bg-white overflow-hidden shadow rounded-lg p-5">
                  <dt className="text-sm font-medium text-gray-500 truncate">Total Runs</dt>
                  <dd className="mt-1 text-3xl font-semibold text-gray-900">{overview.stats?.total_runs}</dd>
                </div>
                
                <div className="bg-white overflow-hidden shadow rounded-lg p-5">
                  <dt className="text-sm font-medium text-gray-500 truncate">Total Queries</dt>
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
                      {Object.keys(chartData[0] || {}).filter((k: string) => k !== 'date').map((model: string, i: number) => (
                        <Line key={model} type="monotone" dataKey={model} stroke={`hsl(${i * 60}, 70%, 50%)`} />
                      ))}
                    </LineChart>
                  </ResponsiveContainer>
                ) : (
                  <p className="text-gray-500 text-center py-8">No trend data available</p>
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
                  <p className="text-gray-500 text-center py-8">No model data available</p>
                )}
              </div>
            </div>

            {/* Model Comparison Table */}
            <div className="bg-white shadow rounded-lg p-6">
              <h2 className="text-lg font-medium text-gray-900 mb-4">Model Comparison</h2>
              {overview.modelStats.length > 0 ? (
                <table className="min-w-full divide-y divide-gray-200">
                  <thead className="bg-gray-50">
                    <tr>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Query Count</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mention Rate</th>
                      <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">95% CI</th>
                    </tr>
                  </thead>
                  <tbody className="bg-white divide-y divide-gray-200">
                    {overview.modelStats.map((row: any) => (
                      <tr key={row.model_name}>
                        <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                          {row.model_name}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                          {row.total_runs}
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-900">
                          {row.mention_rate_pct}%
                        </td>
                        <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
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
                <p className="text-gray-500 text-center py-8">No model comparison data available</p>
              )}
            </div>
          </>
        )}

        {!loading && activeTab === 'competitors' && competitorData && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">
              Competitor Comparison ({brand} vs competitors)
            </h2>
            
            <div className="mb-6">
              <p className="text-sm text-gray-600 mb-2">
                All brands sorted by mention rate ({days} days)
              </p>
              <div className="space-y-3">
                {competitorData.all_brands.map((br, idx) => (
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
                    <div className="w-48 text-xs text-gray-500 text-right pl-4">
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
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Brand</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Type</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Query Count</th>
                  <th className="px-6 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mention Rate</th>
                </tr>
              </thead>
              <tbody className="bg-white divide-y divide-gray-200">
                {competitorData.all_brands.map((br) => (
                  <tr key={br.name}>
                    <td className="px-6 py-4 whitespace-nowrap text-sm font-medium text-gray-900">
                      {br.name}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
                      {br.is_target ? 'Target' : 'Competitor'}
                    </td>
                    <td className="px-6 py-4 whitespace-nowrap text-sm text-gray-500">
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
                    className="text-gray-500 hover:text-gray-700"
                  >
                    ✕
                  </button>
                </div>
                
                <div className="mb-4">
                  <p className="text-sm text-gray-600 mb-2">Prompt:</p>
                  <div className="bg-white p-3 rounded border text-sm font-mono">
                    {selectedPrompt.prompt}
                  </div>
                </div>
                
                {selectedPrompt.highlighted_response ? (
                  <div>
                    <p className="text-sm text-gray-600 mb-2">Response (highlighted):</p>
                    <div 
                      className="bg-white p-3 rounded border text-sm prose max-w-none"
                      dangerouslySetInnerHTML={{ __html: selectedPrompt.highlighted_response }}
                    />
                  </div>
                ) : (
                  <div>
                    <p className="text-sm text-gray-600 mb-2">Response:</p>
                    <div className="bg-white p-3 rounded border text-sm whitespace-pre-wrap">
                      {selectedPrompt.response_text}
                    </div>
                  </div>
                )}
                
                <div className="mt-3 flex gap-4 text-sm text-gray-600">
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
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Status</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Prompt</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Model</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Mentions</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
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
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {prompt.model_name}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {Object.keys(prompt.mentions).join(', ') || 'None'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
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
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded disabled:opacity-50"
                >
                  Previous
                </button>
                <span className="text-sm text-gray-600">
                  Page {promptPage} of {promptList.pagination.total_pages}
                </span>
                <button
                  onClick={() => setPromptPage(p => Math.min(promptList.pagination.total_pages, p + 1))}
                  disabled={promptPage === promptList.pagination.total_pages}
                  className="px-4 py-2 bg-gray-200 text-gray-700 rounded disabled:opacity-50"
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
            
            <div className="overflow-x-auto">
              <table className="min-w-full divide-y divide-gray-200">
                <thead className="bg-gray-50">
                  <tr>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Run ID</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Date</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Duration</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Queries</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Success Rate</th>
                    <th className="px-4 py-3 text-left text-xs font-medium text-gray-500 uppercase">Models</th>
                  </tr>
                </thead>
                <tbody className="bg-white divide-y divide-gray-200">
                  {runHistory.map((run) => (
                    <tr key={run.run_id}>
                      <td className="px-4 py-3 whitespace-nowrap text-sm font-medium text-gray-900">
                        #{run.run_id}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {new Date(run.started_at).toLocaleString()}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {run.duration || 'N/A'}
                      </td>
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
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
                      <td className="px-4 py-3 whitespace-nowrap text-sm text-gray-500">
                        {run.models_used.join(', ')}
                      </td>
                    </tr>
                  ))}
                </tbody>
              </table>
            </div>
          
            {!runHistory.length && (
              <p className="text-gray-500 text-center py-8">No runs found in this period</p>
            )}
          </div>
        )}

        {!loading && activeTab === 'stats' && statSummary && (
          <div className="bg-white shadow rounded-lg p-6">
            <h2 className="text-lg font-medium text-gray-900 mb-4">Statistical Summary ({statSummary.brand})</h2>
            
            <div className="grid grid-cols-1 md:grid-cols-2 gap-6 mb-6">
              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900 mb-3">Key Metrics</h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Analysis Period:</dt>
                    <dd className="font-medium">{statSummary.period_days} days</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Number of Runs:</dt>
                    <dd className="font-medium">{statSummary.n_runs}</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Mean Mention Rate:</dt>
                    <dd className="font-medium">{statSummary.mean_mention_rate}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Std Deviation:</dt>
                    <dd className="font-medium">{statSummary.std_deviation.toFixed(2)}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Std Error:</dt>
                    <dd className="font-medium">{statSummary.std_error.toFixed(2)}%</dd>
                  </div>
                </dl>
              </div>

              <div className="bg-gray-50 p-4 rounded-lg">
                <h3 className="font-medium text-gray-900 mb-3">Confidence Analysis</h3>
                <dl className="space-y-2 text-sm">
                  <div className="flex justify-between">
                    <dt className="text-gray-500">95% Confidence Interval:</dt>
                    <dd className="font-medium">
                      {statSummary.confidence_interval_95 
                        ? `[${statSummary.confidence_interval_95[0].toFixed(1)} - ${statSummary.confidence_interval_95[1].toFixed(1)}]%`
                        : 'N/A'
                      }
                    </dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Coefficient of Variation:</dt>
                    <dd className="font-medium">{statSummary.coefficient_of_variation.toFixed(1)}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Min Rate:</dt>
                    <dd className="font-medium">{statSummary.min_rate}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Max Rate:</dt>
                    <dd className="font-medium">{statSummary.max_rate}%</dd>
                  </div>
                  <div className="flex justify-between">
                    <dt className="text-gray-500">Range:</dt>
                    <dd className="font-medium">{statSummary.rate_range.toFixed(1)}%</dd>
                  </div>
                </dl>
              </div>
            </div>

            <div className="bg-blue-50 border border-blue-200 rounded-lg p-4 mb-6">
              <h3 className="font-medium text-blue-900 mb-2">Interpretation</h3>
              <p className="text-sm text-blue-800">{statSummary.interpretation}</p>
            </div>

            {statSummary.anomalies.length > 0 && (
              <div className="bg-yellow-50 border border-yellow-200 rounded-lg p-4">
                <h3 className="font-medium text-yellow-900 mb-3">Anomalies Detected ({statSummary.anomalies.length})</h3>
                <p className="text-sm text-yellow-800 mb-2">
                  These runs show mention rates {'>'}2 standard deviations from the mean:
                </p>
                <ul className="text-sm text-yellow-800 space-y-1">
                  {statSummary.anomalies.map((anom) => (
                    <li key={anom.run_id}>
                      Run #{anom.run_id}: {anom.rate}% (deviation: {anom.deviation.toFixed(2)}σ)
                    </li>
                  ))}
                </ul>
              </div>
            )}
          </div>
        )}
      </div>
    </main>
  );
}
