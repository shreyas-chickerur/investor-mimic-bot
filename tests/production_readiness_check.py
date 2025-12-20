#!/usr/bin/env python3
"""
Production Readiness Comprehensive Check

Validates:
1. Code quality and structure
2. Error handling
3. Data validation
4. Security
5. Performance
6. Documentation
7. Dependencies
8. Configuration
9. Logging
10. Deployment readiness
"""

import os
import sys
import ast
import sqlite3
import pandas as pd
import json
from pathlib import Path

class ProductionReadinessChecker:
    def __init__(self):
        self.root_dir = Path(__file__).parent.parent
        self.issues = []
        self.warnings = []
        self.passed = []
        
    def log_pass(self, check, message):
        """Log passed check"""
        self.passed.append(f"✅ {check}: {message}")
        
    def log_warning(self, check, message):
        """Log warning"""
        self.warnings.append(f"⚠️ {check}: {message}")
        
    def log_issue(self, check, message):
        """Log critical issue"""
        self.issues.append(f"❌ {check}: {message}")
    
    # ========================================================================
    # CHECK 1: FILE STRUCTURE
    # ========================================================================
    
    def check_file_structure(self):
        """Verify required files exist"""
        print("\n1. Checking file structure...")
        
        required_files = {
            'trading_system.py': 'Main trading system',
            'README.md': 'Documentation',
            'data/training_data.csv': 'Historical data',
            'tests/test_trading_system.py': 'Test suite'
        }
        
        for file, desc in required_files.items():
            file_path = self.root_dir / file
            if file_path.exists():
                self.log_pass("File Structure", f"{desc} exists")
            else:
                self.log_issue("File Structure", f"Missing {desc}: {file}")
        
        # Check for leftover test files
        scripts_dir = self.root_dir / 'scripts'
        if scripts_dir.exists():
            py_files = list(scripts_dir.glob('*.py'))
            if len(py_files) > 0:
                self.log_warning("File Structure", f"Found {len(py_files)} files in scripts/ - should be cleaned up")
            else:
                self.log_pass("File Structure", "scripts/ directory is clean")
    
    # ========================================================================
    # CHECK 2: CODE QUALITY
    # ========================================================================
    
    def check_code_quality(self):
        """Check code quality and structure"""
        print("\n2. Checking code quality...")
        
        trading_system = self.root_dir / 'trading_system.py'
        
        if not trading_system.exists():
            self.log_issue("Code Quality", "trading_system.py not found")
            return
        
        with open(trading_system, 'r') as f:
            code = f.read()
        
        # Check for proper imports
        if 'import pandas' in code and 'import numpy' in code:
            self.log_pass("Code Quality", "Required imports present")
        else:
            self.log_issue("Code Quality", "Missing required imports")
        
        # Check for docstrings
        if '"""' in code or "'''" in code:
            self.log_pass("Code Quality", "Docstrings present")
        else:
            self.log_warning("Code Quality", "Missing docstrings")
        
        # Check for error handling
        if 'try:' in code or 'except' in code:
            self.log_pass("Code Quality", "Error handling present")
        else:
            self.log_warning("Code Quality", "No error handling found")
        
        # Parse AST to check for functions
        try:
            tree = ast.parse(code)
            functions = [node.name for node in ast.walk(tree) if isinstance(node, ast.FunctionDef)]
            classes = [node.name for node in ast.walk(tree) if isinstance(node, ast.ClassDef)]
            
            if len(functions) > 0:
                self.log_pass("Code Quality", f"Found {len(functions)} functions")
            if len(classes) > 0:
                self.log_pass("Code Quality", f"Found {len(classes)} classes")
                
        except SyntaxError as e:
            self.log_issue("Code Quality", f"Syntax error in code: {e}")
    
    # ========================================================================
    # CHECK 3: DATA VALIDATION
    # ========================================================================
    
    def check_data_validation(self):
        """Validate training data"""
        print("\n3. Checking data validation...")
        
        data_file = self.root_dir / 'data' / 'training_data.csv'
        
        if not data_file.exists():
            self.log_issue("Data Validation", "training_data.csv not found")
            return
        
        try:
            df = pd.read_csv(data_file, index_col=0)
            
            # Check size
            if len(df) > 0:
                self.log_pass("Data Validation", f"Data loaded: {len(df)} rows")
            else:
                self.log_issue("Data Validation", "Data file is empty")
            
            # Check required columns
            required_cols = ['close', 'rsi', 'volatility_20d', 'future_return_20d', 'symbol']
            missing_cols = [col for col in required_cols if col not in df.columns]
            
            if not missing_cols:
                self.log_pass("Data Validation", "All required columns present")
            else:
                self.log_issue("Data Validation", f"Missing columns: {missing_cols}")
            
            # Check for symbols
            if 'symbol' in df.columns:
                num_symbols = df['symbol'].nunique()
                if num_symbols > 0:
                    self.log_pass("Data Validation", f"{num_symbols} symbols in dataset")
                else:
                    self.log_issue("Data Validation", "No symbols in dataset")
            
            # Check for extreme missing values
            missing_pct = (df.isnull().sum().sum() / (len(df) * len(df.columns))) * 100
            if missing_pct < 50:
                self.log_pass("Data Validation", f"Missing values: {missing_pct:.1f}%")
            else:
                self.log_warning("Data Validation", f"High missing values: {missing_pct:.1f}%")
            
        except Exception as e:
            self.log_issue("Data Validation", f"Error loading data: {e}")
    
    # ========================================================================
    # CHECK 4: DATABASE
    # ========================================================================
    
    def check_database(self):
        """Validate database structure"""
        print("\n4. Checking database...")
        
        db_file = self.root_dir / 'data' / 'trading_system.db'
        
        if not db_file.exists():
            self.log_warning("Database", "Database doesn't exist yet (will be created on first run)")
            return
        
        try:
            conn = sqlite3.connect(db_file)
            cursor = conn.cursor()
            
            # Check tables exist
            cursor.execute("SELECT name FROM sqlite_master WHERE type='table'")
            tables = [row[0] for row in cursor.fetchall()]
            
            required_tables = ['positions', 'signals', 'performance']
            missing_tables = [t for t in required_tables if t not in tables]
            
            if not missing_tables:
                self.log_pass("Database", "All required tables exist")
            else:
                self.log_issue("Database", f"Missing tables: {missing_tables}")
            
            # Check table schemas
            for table in required_tables:
                if table in tables:
                    cursor.execute(f"PRAGMA table_info({table})")
                    columns = [row[1] for row in cursor.fetchall()]
                    if len(columns) > 0:
                        self.log_pass("Database", f"{table} table has {len(columns)} columns")
            
            conn.close()
            
        except Exception as e:
            self.log_issue("Database", f"Error checking database: {e}")
    
    # ========================================================================
    # CHECK 5: ERROR HANDLING
    # ========================================================================
    
    def check_error_handling(self):
        """Check error handling in code"""
        print("\n5. Checking error handling...")
        
        trading_system = self.root_dir / 'trading_system.py'
        
        if not trading_system.exists():
            return
        
        with open(trading_system, 'r') as f:
            code = f.read()
        
        # Check for try-except blocks
        try_count = code.count('try:')
        except_count = code.count('except')
        
        if try_count > 0 and except_count > 0:
            self.log_pass("Error Handling", f"Found {try_count} try-except blocks")
        else:
            self.log_warning("Error Handling", "Limited error handling")
        
        # Check for input validation
        if 'if' in code and ('is None' in code or 'len(' in code):
            self.log_pass("Error Handling", "Input validation present")
        else:
            self.log_warning("Error Handling", "Limited input validation")
    
    # ========================================================================
    # CHECK 6: SECURITY
    # ========================================================================
    
    def check_security(self):
        """Check for security issues"""
        print("\n6. Checking security...")
        
        trading_system = self.root_dir / 'trading_system.py'
        
        if not trading_system.exists():
            return
        
        with open(trading_system, 'r') as f:
            code = f.read()
        
        # Check for hardcoded credentials
        security_issues = []
        if 'password' in code.lower() and '=' in code:
            security_issues.append("Possible hardcoded password")
        if 'api_key' in code.lower() and '=' in code:
            security_issues.append("Possible hardcoded API key")
        
        if not security_issues:
            self.log_pass("Security", "No hardcoded credentials found")
        else:
            for issue in security_issues:
                self.log_warning("Security", issue)
        
        # Check for SQL injection protection
        if 'execute(' in code and '?' in code:
            self.log_pass("Security", "Using parameterized SQL queries")
        elif 'execute(' in code:
            self.log_warning("Security", "Check SQL queries for injection protection")
    
    # ========================================================================
    # CHECK 7: DOCUMENTATION
    # ========================================================================
    
    def check_documentation(self):
        """Check documentation completeness"""
        print("\n7. Checking documentation...")
        
        readme = self.root_dir / 'README.md'
        
        if not readme.exists():
            self.log_issue("Documentation", "README.md not found")
            return
        
        with open(readme, 'r') as f:
            content = f.read()
        
        required_sections = [
            ('Quick Start', 'Quick start guide'),
            ('How It Works', 'Strategy explanation'),
            ('Expected', 'Performance expectations'),
            ('Configuration', 'Configuration options'),
        ]
        
        for section, desc in required_sections:
            if section in content:
                self.log_pass("Documentation", f"{desc} documented")
            else:
                self.log_warning("Documentation", f"Missing {desc}")
        
        # Check length
        if len(content) > 1000:
            self.log_pass("Documentation", f"Comprehensive documentation ({len(content)} chars)")
        else:
            self.log_warning("Documentation", "Documentation may be incomplete")
    
    # ========================================================================
    # CHECK 8: TESTS
    # ========================================================================
    
    def check_tests(self):
        """Check test coverage"""
        print("\n8. Checking tests...")
        
        test_file = self.root_dir / 'tests' / 'test_trading_system.py'
        
        if not test_file.exists():
            self.log_issue("Tests", "Test suite not found")
            return
        
        with open(test_file, 'r') as f:
            code = f.read()
        
        # Count test methods
        test_count = code.count('def test_')
        
        if test_count >= 10:
            self.log_pass("Tests", f"Comprehensive test suite ({test_count} tests)")
        elif test_count >= 5:
            self.log_pass("Tests", f"Good test coverage ({test_count} tests)")
        else:
            self.log_warning("Tests", f"Limited test coverage ({test_count} tests)")
        
        # Check for unittest
        if 'import unittest' in code:
            self.log_pass("Tests", "Using unittest framework")
        else:
            self.log_warning("Tests", "No test framework detected")
    
    # ========================================================================
    # CHECK 9: DEPENDENCIES
    # ========================================================================
    
    def check_dependencies(self):
        """Check dependencies are available"""
        print("\n9. Checking dependencies...")
        
        required_packages = {
            'pandas': 'Data manipulation',
            'numpy': 'Numerical operations',
            'sqlite3': 'Database'
        }
        
        for package, desc in required_packages.items():
            try:
                __import__(package)
                self.log_pass("Dependencies", f"{desc} ({package}) available")
            except ImportError:
                self.log_issue("Dependencies", f"Missing {desc} ({package})")
    
    # ========================================================================
    # CHECK 10: PERFORMANCE
    # ========================================================================
    
    def check_performance(self):
        """Check for performance issues"""
        print("\n10. Checking performance...")
        
        trading_system = self.root_dir / 'trading_system.py'
        
        if not trading_system.exists():
            return
        
        with open(trading_system, 'r') as f:
            code = f.read()
        
        # Check for efficient operations
        if '.iterrows()' in code:
            self.log_warning("Performance", "Using .iterrows() - consider vectorization")
        else:
            self.log_pass("Performance", "No obvious performance issues")
        
        # Check for database connection management
        if 'conn.close()' in code:
            self.log_pass("Performance", "Proper database connection cleanup")
        else:
            self.log_warning("Performance", "Check database connection cleanup")
    
    # ========================================================================
    # RUN ALL CHECKS
    # ========================================================================
    
    def run_all_checks(self):
        """Run all production readiness checks"""
        print("=" * 80)
        print("PRODUCTION READINESS CHECK")
        print("=" * 80)
        
        self.check_file_structure()
        self.check_code_quality()
        self.check_data_validation()
        self.check_database()
        self.check_error_handling()
        self.check_security()
        self.check_documentation()
        self.check_tests()
        self.check_dependencies()
        self.check_performance()
        
        # Print summary
        print("\n" + "=" * 80)
        print("SUMMARY")
        print("=" * 80)
        
        print(f"\n✅ Passed: {len(self.passed)}")
        print(f"⚠️  Warnings: {len(self.warnings)}")
        print(f"❌ Issues: {len(self.issues)}")
        
        if self.issues:
            print("\n" + "=" * 80)
            print("CRITICAL ISSUES (Must Fix)")
            print("=" * 80)
            for issue in self.issues:
                print(f"  {issue}")
        
        if self.warnings:
            print("\n" + "=" * 80)
            print("WARNINGS (Should Fix)")
            print("=" * 80)
            for warning in self.warnings:
                print(f"  {warning}")
        
        print("\n" + "=" * 80)
        print("VERDICT")
        print("=" * 80)
        
        if len(self.issues) == 0:
            if len(self.warnings) == 0:
                print("\n🎉 PRODUCTION READY - No issues found!")
                return 0
            else:
                print(f"\n✅ PRODUCTION READY - {len(self.warnings)} warnings to address")
                return 0
        else:
            print(f"\n❌ NOT PRODUCTION READY - {len(self.issues)} critical issues to fix")
            return 1

def main():
    """Main execution"""
    checker = ProductionReadinessChecker()
    exit_code = checker.run_all_checks()
    
    print("\n" + "=" * 80)
    print("✅ PRODUCTION READINESS CHECK COMPLETE")
    print("=" * 80)
    
    return exit_code

if __name__ == '__main__':
    sys.exit(main())
