#!/usr/bin/env python3
"""
Download all GitHub Actions artifacts for Phase 5

Downloads artifacts from the last 30 days to artifacts_backup/
Requires: gh CLI tool (GitHub CLI)
Install: brew install gh
"""
import subprocess
import sys
from pathlib import Path
from datetime import datetime


def main():
    print('='*80)
    print('GITHUB ACTIONS ARTIFACT DOWNLOADER')
    print('='*80)
    
    # Check if gh CLI is installed
    try:
        subprocess.run(['gh', '--version'], check=True, capture_output=True)
    except (subprocess.CalledProcessError, FileNotFoundError):
        print('❌ GitHub CLI (gh) not installed')
        print('Install: brew install gh')
        print('Then run: gh auth login')
        return False
    
    # Create backup directory
    backup_dir = Path('artifacts_backup')
    backup_dir.mkdir(exist_ok=True)
    
    timestamp = datetime.now().strftime('%Y%m%d_%H%M%S')
    download_dir = backup_dir / timestamp
    download_dir.mkdir(exist_ok=True)
    
    print(f'\nDownloading artifacts to: {download_dir}')
    
    # Get recent workflow runs
    print('\nFetching recent workflow runs...')
    result = subprocess.run(
        ['gh', 'run', 'list', '--limit', '30', '--json', 'databaseId,conclusion,createdAt'],
        capture_output=True,
        text=True
    )
    
    if result.returncode != 0:
        print(f'❌ Failed to fetch workflow runs: {result.stderr}')
        return False
    
    import json
    runs = json.loads(result.stdout)
    
    print(f'Found {len(runs)} recent workflow runs')
    
    # Download artifacts from each run
    downloaded = 0
    for i, run in enumerate(runs, 1):
        run_id = run['databaseId']
        conclusion = run['conclusion']
        created_at = run['createdAt']
        
        print(f'\n[{i}/{len(runs)}] Run {run_id} ({conclusion}) - {created_at}')
        
        # Download artifacts for this run
        run_dir = download_dir / f'run_{run_id}'
        run_dir.mkdir(exist_ok=True)
        
        result = subprocess.run(
            ['gh', 'run', 'download', str(run_id), '-D', str(run_dir)],
            capture_output=True,
            text=True
        )
        
        if result.returncode == 0:
            print(f'  ✅ Downloaded artifacts')
            downloaded += 1
        else:
            print(f'  ⚠️  No artifacts or download failed')
    
    print(f'\n{'='*80}')
    print(f'✅ DOWNLOAD COMPLETE')
    print(f'{'='*80}')
    print(f'Downloaded artifacts from {downloaded}/{len(runs)} runs')
    print(f'Location: {download_dir}')
    print(f'\nArtifacts include:')
    print(f'  - test-logs/ - Execution logs')
    print(f'  - database-snapshot/ - Database files')
    print(f'  - trading-artifacts/ - Daily JSON/Markdown files')
    
    return True


if __name__ == '__main__':
    success = main()
    sys.exit(0 if success else 1)
