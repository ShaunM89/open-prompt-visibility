// src/app/api/data/route.ts
// API route to fetch dashboard data
import { NextResponse } from 'next/server';
import { spawnSync } from 'child_process';
import fs from 'fs';
import path from 'path';

function getDbPath(): string {
  // process.cwd() is frontend/, go up one level to project root
  return path.resolve(process.cwd(), '../data/tracks.db');
}

function checkDbExists(): boolean {
  return fs.existsSync(getDbPath());
}

function runPythonQuery(script: string): any {
  const result = spawnSync('python3', ['-c', script], { 
    encoding: 'utf8',
    env: { ...process.env, PVT_DB_PATH: getDbPath() }
  });
  if (result.error) throw result.error;
  if (result.status !== 0) {
    throw new Error(result.stderr || 'Python script failed: ' + result.stdout);
  }
  return JSON.parse(result.stdout);
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const brand = searchParams.get('brand') || 'Nike';
    const days = parseInt(searchParams.get('days') || '30');
    const endpoint = searchParams.get('endpoint') || 'default';

    if (!checkDbExists()) {
      return NextResponse.json({ 
        error: 'Database not found. Run `pvt run` first.',
        stats: null,
        modelStats: [],
        trends: []
      });
    }

    switch (endpoint) {
      case 'visibility-score':
        return handleVisibilityScore(brand, days);
      case 'competitors':
        return handleCompetitors(brand, days);
      case 'prompts':
        const page = parseInt(searchParams.get('page') || '1');
        const limit = parseInt(searchParams.get('limit') || '25');
        const model = searchParams.get('model') || null;
        const successFilter = searchParams.get('success');
        return handlePromptList(brand, days, page, limit, model, 
          successFilter === null ? null : successFilter === 'true');
      case 'prompt-detail':
        const recordId = parseInt(searchParams.get('id') || '0');
        return handlePromptDetail(recordId);
      case 'run-history':
        return handleRunHistory(days);
      case 'statistical-summary':
        return handleStatisticalSummary(brand, days);
      default:
        return handleDefault(brand, days);
    }
  } catch (error) {
    console.error('API error:', error);
    return NextResponse.json(
      { error: error instanceof Error ? error.message : 'Unknown error' },
      { status: 500 }
    );
  }
}

async function handleDefault(brand: string, days: number) {
  const dbPath = getDbPath();
  
  const stats = runPythonQuery(`
import sqlite3, json
conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('SELECT COUNT(*) FROM runs'); total_runs = c.fetchone()[0]
c.execute('SELECT COUNT(*) FROM visibility_records'); total_records = c.fetchone()[0]
c.execute('SELECT COUNT(DISTINCT model_name) FROM visibility_records'); unique_models = c.fetchone()[0]
c.execute("SELECT COUNT(*) FROM visibility_records WHERE mentions_json IS NOT NULL AND mentions_json != '{}'"); total_mentions = c.fetchone()[0]
print(json.dumps({'total_runs': total_runs, 'total_records': total_records, 'unique_models': unique_models, 'total_mentions': total_mentions}))
`);

  const modelStats = runPythonQuery(`
import sqlite3, json
conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('''
  SELECT model_provider, model_name, COUNT(*) as total_runs,
  SUM(CASE WHEN mentions_json LIKE ? THEN 1 ELSE 0 END) as total_mentions,
  ROUND(100.0 * SUM(CASE WHEN mentions_json LIKE ? THEN 1 ELSE 0 END) / COUNT(*), 2) as mention_rate_pct
  FROM visibility_records WHERE detected_at > datetime('now', ?)
  GROUP BY model_provider, model_name ORDER BY total_runs DESC
''', ('%%"{}":%%'.format('${brand}'), '%%"{}":%%'.format('${brand}'), '-{} days'.format(${days})))
print(json.dumps([dict(r) for r in c.fetchall()]))
`);

  const trends = runPythonQuery(`
import sqlite3, json
conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()
c.execute('''
  SELECT DATE(detected_at) as date, model_name, COUNT(*) as total_queries,
  SUM(CASE WHEN mentions_json LIKE ? THEN 1 ELSE 0 END) as mention_count
  FROM visibility_records WHERE detected_at > datetime('now', ?)
  GROUP BY date, model_name ORDER BY date ASC
''', ('%%"{}":%%'.format('${brand}'), '-{} days'.format(${days})))
print(json.dumps([dict(r) for r in c.fetchall()]))
`);

  return NextResponse.json({ stats, modelStats, trends });
}

async function handleVisibilityScore(brand: string, days: number) {
  const dbPath = getDbPath();
  
  const result = runPythonQuery(`
import sqlite3, json
conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute('''
  SELECT model_name, model_provider, COUNT(*) as total,
  SUM(CASE WHEN mentions_json LIKE ? THEN 1 ELSE 0 END) as mentions
  FROM visibility_records 
  WHERE detected_at > datetime('now', ?)
  GROUP BY model_name, model_provider
''', ('%%"{}":%%'.format('${brand}'), '-{} days'.format(${days})))

rows = c.fetchall()

total_prompts = sum(r['total'] for r in rows)
successful_prompts = sum(r['mentions'] for r in rows)
score = (successful_prompts / total_prompts * 100) if total_prompts > 0 else 0

import math
z = 1.96
n = total_prompts
p = score / 100.0

if n > 0:
  denom = 1 + z**2/n
  center = (p + z**2/(2*n)) / denom
  std_err = (z * math.sqrt((p*(1-p) + z**2/(4*n))/n)) / denom
  ci_low = max(0, (center - std_err)*100)
  ci_high = min(100, (center + std_err)*100)
else:
  ci_low = ci_high = 0

by_model = []
for r in rows:
  m_total = r['total']
  m_mentions = r['mentions']
  m_score = (m_mentions / m_total * 100) if m_total > 0 else 0
  if m_total > 0:
    mdenom = 1 + z**2/m_total
    mcenter = (m_score/100 + z**2/(2*m_total)) / mdenom
    mstd = (z * math.sqrt((m_score/100*(1-m_score/100) + z**2/(4*m_total))/m_total)) / mdenom
    mci = (max(0, (mcenter-mstd)*100), min(100, (mcenter+mstd)*100))
  else:
    mci = None
  by_model.append({
    'model_name': r['model_name'],
    'model_provider': r['model_provider'],
    'score': round(m_score, 2),
    'total_prompts': m_total,
    'successful_prompts': m_mentions,
    'confidence_interval': mci
  })

print(json.dumps({
  'brand': '${brand}',
  'score': round(score, 2),
  'total_prompts': total_prompts,
  'successful_prompts': successful_prompts,
  'by_model': by_model,
  'confidence_interval': (ci_low, ci_high) if n > 0 else None
}))
`);
  
  return NextResponse.json(result || { error: 'No data found' });
}

async function handleCompetitors(brand: string, days: number) {
  const dbPath = getDbPath();
  const configPath = path.resolve(process.cwd(), '../configs/default.yaml');
  
  const result = runPythonQuery(`
import sqlite3, json
import yaml
from pathlib import Path

conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()

config_file = Path('${configPath.replace(/'/g, "\\'")}')
brands_config = []
if config_file.exists():
  with open(config_file, 'r') as f:
    config = yaml.safe_load(f)
  if 'tool' in config and 'users' in config:
    users_path = config_file.parent / config['users'].lstrip('/')
    brands_file = users_path / 'brands.yaml'
    if brands_file.exists():
      with open(brands_file, 'r') as bf:
        user_config = yaml.safe_load(bf)
        brands_config = user_config.get('brands', [])

target_brand = '${brand}'
competitors = []
for b in brands_config:
  if b['name'] == target_brand:
    for comp in b.get('competitors', []):
      competitors.append(comp['name'])
    break

def get_mention_rate(bname, dval):
  c.execute('''
    SELECT COUNT(*) as total,
    SUM(CASE WHEN mentions_json LIKE ? THEN 1 ELSE 0 END) as mentions
    FROM visibility_records 
    WHERE detected_at > datetime('now', ?)
  ''', ('%%"{}":%%'.format(bname), '-{} days'.format(dval)))
  r = c.fetchone()
  total = r['total']
  mentions = r['mentions']
  score = (mentions / total * 100) if total > 0 else 0
  return {'name': bname, 'score': round(score, 2), 'total_prompts': total, 'successful_prompts': mentions}

target_data = get_mention_rate(target_brand, ${days})
comp_data = [get_mention_rate(c, ${days}) for c in competitors]

all_brands = [target_data] + comp_data
all_brands.sort(key=lambda x: x['score'], reverse=True)
for br in all_brands:
  br['is_target'] = (br['name'] == target_brand)

print(json.dumps({
  'target_brand': target_brand,
  'target_score': target_data['score'],
  'competitors': comp_data,
  'all_brands': all_brands,
  'period_days': ${days}
}))
`);
  
  return NextResponse.json(result || { error: 'No data found' });
}

async function handlePromptList(brand: string, days: number, page: number, limit: number, 
  model: string | null, successFilter: boolean | null) {
  const dbPath = getDbPath();
  
  const result = runPythonQuery(`
import sqlite3, json
from datetime import datetime, timedelta

conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()

cutoff = datetime.utcnow() - timedelta(days=${days})
cutoff_str = cutoff.strftime('%Y-%m-%d %H:%M:%S')

query = """
  SELECT id, run_id, model_provider, model_name, prompt, 
         response_text, mentions_json, detected_at
  FROM visibility_records
  WHERE detected_at > ?
  AND mentions_json LIKE ?
"""
params = [cutoff_str, '%"${brand}":%']

${model ? "params.append('${model}'); query += ' AND model_name = ?'" : ''}

${successFilter !== null ? `if ${successFilter ? 'True' : 'False'}:
  query += " AND (LENGTH(mentions_json) > 2 AND mentions_json != ?)"
  params.append('{"${brand}": 1}')
else:
  query += " AND (mentions_json = '{}' OR mentions_json = ? OR mentions_json LIKE ?)"
  params.append('{"${brand}": 1}')
  params.append('%"${brand}":%')` : ''}

count_query = query.split(' ORDER BY')[0].replace('SELECT id, run_id', 'SELECT COUNT(*)')
c.execute(count_query, params[:query.count('?')])
total = c.fetchone()[0]

offset = (${page} - 1) * ${limit}
query += " ORDER BY detected_at DESC LIMIT ? OFFSET ?"
params.extend([${limit}, offset])

c.execute(query, params)
rows = c.fetchall()

prompts = []
for row in rows:
  mentions = json.loads(row['mentions_json'] or '{}')
  is_success = len(mentions) > 0
  prompts.append({
    'id': row['id'],
    'run_id': row['run_id'],
    'model_provider': row['model_provider'],
    'model_name': row['model_name'],
    'prompt': row['prompt'],
    'response_text': (row['response_text'] or '')[:500],
    'mentions': mentions,
    'detected_at': str(row['detected_at']),
    'is_success': is_success
  })

print(json.dumps({
  'prompts': prompts,
  'pagination': {
    'page': ${page},
    'limit': ${limit},
    'total': total,
    'total_pages': (total + ${limit} - 1) // ${limit} if total > 0 else 0
  },
  'filters': {
    'brand': '${brand}',
    'model': ${model ? `'${model}'` : 'None'},
    'days': ${days},
    'success_filter': ${successFilter !== null ? (successFilter ? 'True' : 'False') : 'None'}
  }
}))
`);
  
  return NextResponse.json(result || { error: 'No data found' });
}

async function handlePromptDetail(recordId: number) {
  const dbPath = getDbPath();
  const configPath = path.resolve(process.cwd(), '../configs/default.yaml');
  
  const result = runPythonQuery(`
import sqlite3, json
import yaml
from pathlib import Path
import re

conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()

c.execute("""
  SELECT id, run_id, model_provider, model_name, prompt, 
         response_text, mentions_json, detected_at
  FROM visibility_records
  WHERE id = ?
""", (${recordId},))

row = c.fetchone()
if not row:
  print(json.dumps(None))
  exit(0)

mentions = json.loads(row['mentions_json'] or '{}')

config_path = Path('${configPath.replace(/'/g, "\\'")}')
brands = {}
if config_path.exists():
  with open(config_path, 'r') as f:
    config = yaml.safe_load(f)
  if 'tool' in config and 'users' in config:
    users_path = config_path.parent / config['users'].lstrip('/')
    brands_file = users_path / 'brands.yaml'
    if brands_file.exists():
      with open(brands_file, 'r') as bf:
        user_config = yaml.safe_load(bf)
        for br in user_config.get('brands', []):
          brands[br['name']] = {
            'keywords': br.get('keywords', []),
            'is_target': False
          }
          for comp in br.get('competitors', []):
            brands[comp['name']] = {
              'keywords': comp.get('keywords', [comp['name']]),
              'is_target': False
            }

target_brand = list(mentions.keys())[0] if mentions else ''

text = row['response_text'] or ''
for brand_name, config in brands.items():
  is_target = brand_name == target_brand
  for keyword in config.get('keywords', []):
    is_mentioned = brand_name in mentions
    if is_mentioned:
      color = 'green' if is_target else '#f59e0b'
      replacement = f'<mark style="background-color: {color}33; color: {color}; font-weight: bold;">{keyword}</mark>'
    else:
      replacement = keyword
    text = re.sub(rf'\\b{re.escape(keyword)}\\b', replacement, text, flags=re.IGNORECASE)

print(json.dumps({
  'id': row['id'],
  'run_id': row['run_id'],
  'model_provider': row['model_provider'],
  'model_name': row['model_name'],
  'prompt': row['prompt'],
  'response_text': row['response_text'],
  'highlighted_response': text,
  'mentions': mentions,
  'detected_at': str(row['detected_at']),
  'target_brand': target_brand
}))
`);
  
  return NextResponse.json(result || { error: 'Record not found' });
}

async function handleRunHistory(days: number) {
  const dbPath = getDbPath();
  
  const result = runPythonQuery(`
import sqlite3, json
from datetime import datetime, timedelta
from collections import defaultdict

conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()

cutoff = datetime.utcnow() - timedelta(days=${days})

c.execute("""
  SELECT id, started_at, completed_at
  FROM runs
  WHERE started_at > ?
  ORDER BY started_at DESC
  LIMIT 20
""", (cutoff,))

runs = c.fetchall()

run_history = []
for run in runs:
  c.execute("SELECT * FROM visibility_records WHERE run_id = ?", (run['id'],))
  records = c.fetchall()
  
  total = len(records)
  successful = sum(1 for r in records if r['mentions_json'] and r['mentions_json'] != '{}')
  models = list(set(r['model_name'] for r in records))
  
  all_mentions = defaultdict(int)
  for r in records:
    mentions = json.loads(r['mentions_json'] or '{}')
    for brand, count in mentions.items():
      all_mentions[brand] += count
  
  duration = None
  if run['completed_at'] and run['started_at']:
    try:
      fmt = '%Y-%m-%d %H:%M:%S.%f' if '.' in str(run['started_at']) else '%Y-%m-%d %H:%M:%S'
      start = datetime.strptime(str(run['started_at']), fmt)
      end = datetime.strptime(str(run['completed_at']), fmt)
      duration = str(end - start)
    except (ValueError, TypeError):
      duration = None
  
  run_history.append({
    'run_id': run['id'],
    'started_at': str(run['started_at']),
    'completed_at': str(run['completed_at']),
    'duration': duration,
    'total_queries': total,
    'successful_queries': successful,
    'success_rate': round(successful/total*100, 2) if total > 0 else 0,
    'models_used': models,
    'all_mentions': dict(all_mentions)
  })

print(json.dumps(run_history))
`);
  
  return NextResponse.json(result || []);
}

async function handleStatisticalSummary(brand: string, days: number) {
  const dbPath = getDbPath();
  
  const result = runPythonQuery(`
import sqlite3, json
from datetime import datetime, timedelta
from collections import defaultdict
import math

conn = sqlite3.connect('${dbPath}')
conn.row_factory = sqlite3.Row
c = conn.cursor()

cutoff = datetime.utcnow() - timedelta(days=${days})

c.execute("""
  SELECT id, started_at, completed_at
  FROM runs
  WHERE started_at > ?
  ORDER BY started_at DESC
""", (cutoff,))

runs = c.fetchall()

if not runs:
  print(json.dumps({
    'brand': '${brand}',
    'period_days': ${days},
    'n_runs': 0,
    'message': 'No runs found'
  }))
  exit(0)

run_rates = []
for run in runs:
  c.execute("SELECT * FROM visibility_records WHERE run_id = ?", (run['id'],))
  records = c.fetchall()
  
  mentions = sum(1 for r in records 
       if '${brand}' in (json.loads(r['mentions_json'] or '{}') if r['mentions_json'] else {}))
  total = len(records)
  rate = (mentions / total * 100) if total > 0 else 0
  run_rates.append(rate)

if not run_rates:
  print(json.dumps({
    'brand': '${brand}',
    'period_days': ${days},
    'n_runs': len(runs),
    'message': 'No data for brand'
  }))
  exit(0)

n = len(run_rates)
mean_rate = sum(run_rates) / n
variance = sum((r - mean_rate) ** 2 for r in run_rates) / (n - 1) if n > 1 else 0
std_dev = math.sqrt(variance)
std_error = std_dev / math.sqrt(n) if n > 0 else 0

p = mean_rate / 100.0
z = 1.96
if n > 0:
  denom = 1 + z**2/n
  center = (p + z**2/(2*n)) / denom
  std_err_calc = (z * math.sqrt((p*(1-p) + z**2/(4*n))/n)) / denom
  ci_low = max(0, (center - std_err_calc)*100)
  ci_high = min(100, (center + std_err_calc)*100)
  ci = (ci_low, ci_high)
else:
  ci = None

cv = (std_dev / mean_rate * 100) if mean_rate > 0 else 0

anomalies = []
for i, rate in enumerate(run_rates):
  if std_dev > 0 and abs(rate - mean_rate) > 2 * std_dev:
    anomalies.append({
      'run_index': i,
      'run_id': runs[i]['id'],
      'rate': round(rate, 2),
      'deviation': round((rate - mean_rate) / std_dev, 2)
    })

interpretation = 'Stable' if cv < 20 else 'Moderate variation' if cv < 30 else 'High variation'

print(json.dumps({
  'brand': '${brand}',
  'period_days': ${days},
  'n_runs': n,
  'mean_mention_rate': round(mean_rate, 2),
  'std_deviation': round(std_dev, 2),
  'std_error': round(std_error, 2),
  'confidence_interval_95': ci,
  'coefficient_of_variation': round(cv, 2),
  'min_rate': round(min(run_rates), 2),
  'max_rate': round(max(run_rates), 2),
  'rate_range': round(max(run_rates) - min(run_rates), 2),
  'anomalies': anomalies,
  'interpretation': interpretation
}))
`);
  
  return NextResponse.json(result || { error: 'No data found' });
}