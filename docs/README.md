# Documentation

Comprehensive documentation for the Multi-Strategy Trading System.

## Directory Structure

### 📚 **guides/** - How-To Guides
Practical guides for setup, operation, and daily use.

- `GUIDE.md` - Complete system guide and overview
- `AUTOMATION_GUIDE.md` - Setup automated trading workflows
- `ADD_GITHUB_SECRETS.md` - Configure GitHub secrets for CI/CD
- `MAKEFILE_GUIDE.md` - Makefile commands reference
- `MARKET_OPEN_CHECKLIST.md` - Pre-market checklist
- `MARKET_OPEN_QUICK_START.md` - Quick start for market open
- `SCRIPTS_AND_COMMANDS.md` - Scripts directory reference

---

### 📖 **reference/** - Technical Reference
Technical documentation, schemas, and system architecture.

- `TRADING_DB_SCHEMA.md` - Complete database schema
- `DATABASE_PERSISTENCE.md` - Database persistence layer
- `STRATEGY_FLOWCHARTS.md` - Strategy execution flowcharts
- `EMAIL_NOTIFICATIONS.md` - Email notification system
- `SECURITY_PY_EXPLANATION.md` - Security module documentation
- `KNOWN_LIMITATIONS.md` - System limitations and constraints

---

### 📊 **reports/** - Current Reports
Active reports and system documentation.

- `ALGORITHM_SPECIFICATION.md` - Algorithm specifications
- `COMPLETE_SYSTEM_DOCUMENTATION.md` - Complete system documentation
- `EMPIRICAL_VALIDATION_REPORT.md` - Empirical validation results
- `VERIFICATION_REPORT.md` - System verification
- `FINAL_IMPLEMENTATION_REPORT.md` - Final implementation details
- `EXPERT_FEEDBACK_ROUND2.md` - Expert feedback and improvements
- `IMPROVEMENT_TRACKER.md` - Improvement tracking
- `SYSTEM_UPDATE_FOR_REVIEW.md` - System updates
- `QUICK_START.md` - Quick start guide

---

### 📦 **history/** - Historical Documentation
Archived phase-specific and historical documentation.

**implementation/** - Implementation history and phase reports
- Phase 5 implementation documentation
- Phase 4 completion summary
- Operational validation procedures
- GitHub Actions setup and configuration
- Workflow explanations

**development/** - Development notes and handoffs
- ChatGPT handoff documentation
- Development status updates
- Windsurf IDE workflow notes

**reviews/** - Code reviews and fixes
- Code consolidation plans
- Code review findings
- Fixes applied during development

---

## Quick Navigation

### Getting Started
1. Read `guides/GUIDE.md` for system overview
2. Follow `guides/ADD_GITHUB_SECRETS.md` for setup
3. Review `guides/MARKET_OPEN_CHECKLIST.md` before trading

### Daily Operations
- **Pre-market:** `guides/MARKET_OPEN_CHECKLIST.md`
- **Monitor:** Use `make dashboard` or `make view`
- **Troubleshoot:** Check `reference/KNOWN_LIMITATIONS.md`

### Development
- **Commands:** `guides/MAKEFILE_GUIDE.md`
- **Scripts:** `guides/SCRIPTS_AND_COMMANDS.md`
- **Database:** `reference/TRADING_DB_SCHEMA.md`

### System Understanding
- **Algorithm:** `reports/ALGORITHM_SPECIFICATION.md`
- **Validation:** `reports/EMPIRICAL_VALIDATION_REPORT.md`
- **Architecture:** `reports/COMPLETE_SYSTEM_DOCUMENTATION.md`

### Historical Context
- Browse `history/` for project history and archived documentation
- Implementation details in `history/implementation/`
- Development notes in `history/development/`

---

## Documentation Standards

### File Organization
- **guides/** = How to do something (operational)
- **reference/** = Technical specifications (informational)
- **reports/** = Current system reports and documentation
- **history/** = Archived historical documentation

### File Naming
- Use descriptive names: `MARKET_OPEN_CHECKLIST.md` not `CHECKLIST.md`
- Use UPPERCASE with underscores for consistency
- Avoid phase-specific naming (use functional names)

### Maintenance
- Keep guides up-to-date with code changes
- Archive outdated docs to `history/` instead of deleting
- Update this README when adding new categories
- Use functional categories, not phase-based organization

---

## Contributing

When adding new documentation:
1. Choose the appropriate subfolder based on function
2. Use descriptive, generic file names (not phase-specific)
3. Update this README if creating new categories
4. Cross-reference related documents
5. Archive old versions to `history/` rather than deleting

---

## Support

For questions or issues:
- Check `reference/KNOWN_LIMITATIONS.md` first
- Review relevant guides in `guides/`
- Consult system reports in `reports/`
- See historical context in `history/` if needed
- Run `make help` for available commands
