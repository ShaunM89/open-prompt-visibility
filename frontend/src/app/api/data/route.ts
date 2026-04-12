// API route that proxies requests to the Python FastAPI backend.
// The FastAPI server must be running: pvt serve
import { NextResponse } from 'next/server';

const API_BASE = process.env.PVT_API_URL || 'http://localhost:8000';

async function proxyToBackend(path: string): Promise<any> {
  const controller = new AbortController();
  const timeout = setTimeout(() => controller.abort(), 5000);

  try {
    const res = await fetch(`${API_BASE}${path}`, {
      cache: 'no-store',
      signal: controller.signal,
    });
    clearTimeout(timeout);
    if (!res.ok) {
      const text = await res.text();
      throw new Error(`Backend returned ${res.status}: ${text}`);
    }
    return res.json();
  } catch (err: any) {
    clearTimeout(timeout);
    if (err.name === 'AbortError') {
      throw new Error('ECONNREFUSED');
    }
    throw err;
  }
}

export async function GET(request: Request) {
  try {
    const { searchParams } = new URL(request.url);
    const brand = searchParams.get('brand') || 'Nike';
    const days = searchParams.get('days') || '30';
    const endpoint = searchParams.get('endpoint') || 'default';

    const brandParam = encodeURIComponent(brand);
    const daysParam = encodeURIComponent(days);

    switch (endpoint) {
      case 'brands':
        return NextResponse.json(
          await proxyToBackend('/brands')
        );

      case 'visibility-score':
        return NextResponse.json(
          await proxyToBackend(`/visibility-score?brand=${brandParam}&days=${daysParam}`)
        );

      case 'competitors':
        try {
          return NextResponse.json(
            await proxyToBackend(`/competitors?brand=${brandParam}&days=${daysParam}`)
          );
        } catch {
          return NextResponse.json({
            target_brand: brand, target_score: 0,
            competitors: [], all_brands: [], period_days: parseInt(days),
          });
        }

      case 'prompts': {
        const page = searchParams.get('page') || '1';
        const limit = searchParams.get('limit') || '25';
        const model = searchParams.get('model');
        const success = searchParams.get('success');
        let path = `/prompt-list?brand=${brandParam}&days=${daysParam}&page=${encodeURIComponent(page)}&limit=${encodeURIComponent(limit)}`;
        if (model) path += `&model=${encodeURIComponent(model)}`;
        if (success !== null && success !== undefined && success !== '') path += `&success=${success}`;
        return NextResponse.json(await proxyToBackend(path));
      }

      case 'prompt-detail': {
        const recordId = searchParams.get('id') || '0';
        return NextResponse.json(
          await proxyToBackend(`/prompt-detail/${encodeURIComponent(recordId)}`)
        );
      }

      case 'run-history':
        return NextResponse.json(
          await proxyToBackend(`/run-history-detail?days=${daysParam}`)
        );

      case 'statistical-summary':
        return NextResponse.json(
          await proxyToBackend(`/statistical-summary?brand=${brandParam}&days=${daysParam}`)
        );

      case 'convergence-status': {
        const runId = searchParams.get('run_id') || '0';
        return NextResponse.json(
          await proxyToBackend(`/convergence-status?run_id=${encodeURIComponent(runId)}`)
        );
      }

      case 'convergence-live':
        return NextResponse.json(
          await proxyToBackend('/convergence-live')
        );

      case 'model-comparison':
        return NextResponse.json(
          await proxyToBackend(`/models?brand=${brandParam}&days=${daysParam}`)
        );

      case 'sentiment': {
        const runId = searchParams.get('run_id') || '0';
        return NextResponse.json(
          await proxyToBackend(`/sentiment?run_id=${encodeURIComponent(runId)}`)
        );
      }

      case 'sentiment-latest':
        return NextResponse.json(
          await proxyToBackend('/sentiment-latest')
        );

      default:
        return NextResponse.json(
          await proxyToBackend(`/overview?brand=${brandParam}&days=${daysParam}`)
        );
    }
  } catch (error) {
    const message = error instanceof Error ? error.message : 'Unknown error';
    const isBackendDown = message.includes('ECONNREFUSED') || message.includes('fetch failed');
    return NextResponse.json(
      { error: isBackendDown ? 'API server not running. Start it with: pvt serve' : 'Request failed' },
      { status: isBackendDown ? 503 : 500 }
    );
  }
}
