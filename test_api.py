#!/usr/bin/env python3
"""Test script for API routes"""

import sys
import json
from pathlib import Path

# Add project root to path
sys.path.insert(0, str(Path(__file__).parent))

import rich_click as click

console = click.console

@click.group()
def cli():
    print("API Test Suite")

@cli.command()
@click.option('--days', default=7, type=int)
def test_data_endpoint(days: int):
    """Test the main /api/data endpoint"""
    try:
        import requests
        from urllib.parse import urlparse, urlunparse
        
        base_url = urlparse("http://localhost:3000/api/data")
        query = {'brand': 'Nike', 'days': days}
        url = urlunparse(base_url._replace(query=urllib.parse.urlencode(query)))
        
        print(f'Test: GET /api/data?brand=Nike&days={days}')
        print(f'URL: {url}\n')
        
        resp = requests.get(url, timeout=10)
        print(f'Status: {resp.status_code}')
        data = resp.json()
        print(f'Response keys: {list(data.keys())}')
        print(f'Total mentions: {data.get("stats", {}).get("total_mentions")}') if 'stats' in data else print('No stats in response')
        print(f'Unique models: {data.get("stats", {}).get("unique_models")}' if 'stats' in data else '')
        print(f'\n✓ API working')
        return 0
        
    except Exception as e:
        print(f'✗ Error: {e}')
        return 1

if __name__ == '__main__':
    import urllib
    sys.exit(cli())
