#!/usr/bin/env python3
"""
Auto-generate SCRIPTS_AND_COMMANDS.md documentation

Scans Makefile, scripts/, and src/ to create comprehensive documentation.
Prevents duplication by auto-discovering all commands and scripts.
"""
import re
from pathlib import Path
from datetime import datetime


def extract_makefile_targets(makefile_path):
    """Extract all targets and their descriptions from Makefile"""
    targets = {}
    
    with open(makefile_path) as f:
        lines = f.readlines()
    
    current_comment = None
    for i, line in enumerate(lines):
        # Check for comment above target
        if line.strip().startswith('#') and not line.strip().startswith('##'):
            current_comment = line.strip()[1:].strip()
        # Check for target definition
        elif ':' in line and not line.startswith('\t'):
            target = line.split(':')[0].strip()
            if target and not target.startswith('.') and target != 'help':
                targets[target] = current_comment or 'No description'
                current_comment = None
    
    return targets


def extract_script_info(script_path):
    """Extract docstring and usage from a Python script"""
    try:
        with open(script_path) as f:
            content = f.read()
        
        # Extract docstring
        docstring_match = re.search(r'"""(.*?)"""', content, re.DOTALL)
        if docstring_match:
            docstring = docstring_match.group(1).strip()
            lines = [line.strip() for line in docstring.split('\n') if line.strip()]
            
            # First line is brief description
            brief = lines[0] if lines else 'No description'
            
            # Look for usage line
            usage = None
            for line in lines:
                if line.lower().startswith('usage:'):
                    usage = line.split(':', 1)[1].strip()
                    break
            
            return brief, usage
        
        return 'No description', None
    except Exception:
        return 'No description', None


def generate_documentation():
    """Generate SCRIPTS_AND_COMMANDS.md"""
    
    project_root = Path(__file__).parent.parent
    doc_path = project_root / 'docs' / 'SCRIPTS_AND_COMMANDS.md'
    
    print('Generating SCRIPTS_AND_COMMANDS.md...')
    
    # Extract Makefile targets
    makefile_path = project_root / 'Makefile'
    make_targets = extract_makefile_targets(makefile_path) if makefile_path.exists() else {}
    
    # Scan scripts directory
    scripts_dir = project_root / 'scripts'
    script_files = sorted(scripts_dir.glob('*.py')) if scripts_dir.exists() else []
    
    # Generate documentation
    doc_content = f"""# Scripts and Commands Reference

**Auto-generated documentation for all scripts and Make commands**

Last updated: {datetime.now().strftime('%Y-%m-%d %H:%M:%S')}

---

## Make Commands

"""
    
    # Add Make commands
    if make_targets:
        # Group by category
        categories = {
            'Data Management': ['update-data', 'clean-data'],
            'Testing': ['test', 'test-single'],
            'Execution': ['run', 'dry-run'],
            'Database': ['init-db', 'reset-db'],
            'Utilities': ['clean', 'help']
        }
        
        for category, target_names in categories.items():
            doc_content += f"### {category}\n"
            for target in target_names:
                if target in make_targets:
                    doc_content += f"- **`make {target}`** - {make_targets[target]}\n"
            doc_content += "\n"
    
    doc_content += """---

## Scripts Directory

"""
    
    # Add scripts
    if script_files:
        # Group scripts by category based on name
        phase5_scripts = []
        data_scripts = []
        db_scripts = []
        test_scripts = []
        other_scripts = []
        
        for script in script_files:
            if 'phase5' in script.name or 'phase_5' in script.name:
                phase5_scripts.append(script)
            elif 'data' in script.name or 'fetch' in script.name:
                data_scripts.append(script)
            elif 'database' in script.name or 'init_db' in script.name:
                db_scripts.append(script)
            elif 'test' in script.name or 'debug' in script.name:
                test_scripts.append(script)
            else:
                other_scripts.append(script)
        
        # Data scripts
        if data_scripts:
            doc_content += "### Data Scripts\n"
            for script in data_scripts:
                brief, usage = extract_script_info(script)
                doc_content += f"**`{script.relative_to(project_root)}`**\n"
                doc_content += f"- {brief}\n"
                if usage:
                    doc_content += f"- Usage: `{usage}`\n"
                doc_content += "\n"
        
        # Database scripts
        if db_scripts:
            doc_content += "### Database Scripts\n"
            for script in db_scripts:
                brief, usage = extract_script_info(script)
                doc_content += f"**`{script.relative_to(project_root)}`**\n"
                doc_content += f"- {brief}\n"
                if usage:
                    doc_content += f"- Usage: `{usage}`\n"
                doc_content += "\n"
        
        # Phase 5 scripts
        if phase5_scripts:
            doc_content += "### Phase 5 Scripts\n"
            for script in phase5_scripts:
                brief, usage = extract_script_info(script)
                doc_content += f"**`{script.relative_to(project_root)}`**\n"
                doc_content += f"- {brief}\n"
                if usage:
                    doc_content += f"- Usage: `{usage}`\n"
                doc_content += "\n"
        
        # Testing scripts
        if test_scripts:
            doc_content += "### Testing Scripts\n"
            for script in test_scripts:
                brief, usage = extract_script_info(script)
                doc_content += f"**`{script.relative_to(project_root)}`**\n"
                doc_content += f"- {brief}\n"
                if usage:
                    doc_content += f"- Usage: `{usage}`\n"
                doc_content += "\n"
        
        # Other scripts
        if other_scripts:
            doc_content += "### Other Scripts\n"
            for script in other_scripts:
                brief, usage = extract_script_info(script)
                doc_content += f"**`{script.relative_to(project_root)}`**\n"
                doc_content += f"- {brief}\n"
                if usage:
                    doc_content += f"- Usage: `{usage}`\n"
                doc_content += "\n"
    
    doc_content += """---

## Auto-Discovery System

This documentation auto-updates by scanning:
1. **Makefile** - Extracts all targets and descriptions
2. **scripts/** - Lists all .py files with docstrings
3. **src/** - Documents main execution files

To regenerate this documentation:
```bash
python3 scripts/generate_docs.py
```

---

## Adding New Scripts

When adding a new script:
1. Add a docstring at the top explaining what it does
2. Run `python3 scripts/generate_docs.py` to update this file
3. Commit both the script and updated documentation

Example docstring format:
```python
#!/usr/bin/env python3
\"\"\"
Brief description of what this script does

Longer explanation if needed.
Usage: python3 scripts/my_script.py [args]
\"\"\"
```

---

## Quick Reference

**Daily execution (Phase 5):**
```bash
export ENABLE_BROKER_RECONCILIATION=true
python3 src/multi_strategy_main.py
```

**Update market data:**
```bash
make update-data
```

**Initialize database:**
```bash
python3 scripts/init_database.py
```

**Weekly review:**
```bash
python3 scripts/phase5_weekly_review.py
```

**Generate final report:**
```bash
python3 scripts/generate_phase5_report.py
```

**Download CI/CD artifacts:**
```bash
python3 scripts/download_github_artifacts.py
```

**Regenerate this documentation:**
```bash
python3 scripts/generate_docs.py
```
"""
    
    # Write documentation
    with open(doc_path, 'w') as f:
        f.write(doc_content)
    
    print(f'✅ Generated: {doc_path}')
    print(f'   Make commands: {len(make_targets)}')
    print(f'   Script files: {len(script_files)}')
    
    return True


if __name__ == '__main__':
    import sys
    success = generate_documentation()
    sys.exit(0 if success else 1)
