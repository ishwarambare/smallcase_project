# Migration Checklist: Old CSV Import → Django Import-Export

## Overview
This checklist helps you transition from the old custom CSV import system to the new django-import-export system.

## Pre-Migration

### ✅ Backup Current Data
- [ ] Export all stocks to CSV using old system
- [ ] Export all baskets to CSV/JSON
- [ ] Backup database: `python manage.py dumpdata > backup.json`
- [ ] Store backups in safe location with timestamp

### ✅ Verify Installation
- [ ] Package installed: `django-import-export==4.3.1`
- [ ] Added to `INSTALLED_APPS` in settings.py
- [ ] Run `python manage.py check` - no errors
- [ ] `stocks/resources.py` exists
- [ ] `stocks/admin.py` updated with ImportExportModelAdmin

## Testing Phase

### ✅ Test with Sample Data
- [ ] Open admin: `http://localhost:8000/admin/stocks/stock/`
- [ ] Verify "Import" button is visible in top-right
- [ ] Verify "Export" button is visible in top-right
- [ ] Test dry-run import with `stock_import_template.csv`
- [ ] Review preview showing rows to import
- [ ] Confirm no errors in dry-run
- [ ] Test actual import (small dataset)
- [ ] Verify imported stocks appear in database
- [ ] Test export to CSV
- [ ] Test export to XLSX
- [ ] Test export to JSON

### ✅ Test Yahoo Finance Integration
- [ ] Import stock with symbol only (no name/price)
- [ ] Verify name is auto-fetched
- [ ] Verify price is auto-fetched
- [ ] Test with .NS suffix
- [ ] Test without suffix (should add .NS automatically)
- [ ] Test invalid symbol (should show error)

### ✅ Test Update Functionality
- [ ] Import same stock twice
- [ ] Verify second import updates (not duplicates)
- [ ] Check updated price/name

## Migration Steps

### Step 1: Migrate Stock Data

#### Option A: Fresh Import
```bash
# 1. Clear existing stocks (if needed)
python manage.py shell
>>> from stocks.models import Stock
>>> Stock.objects.all().delete()

# 2. Import using new system
# Go to admin → Stocks → Import
# Upload your CSV file
# Review and confirm
```

#### Option B: Update Existing
```bash
# Import will automatically update existing stocks by symbol
# Just upload and import - duplicates will be updated
```

### Step 2: Migrate Basket Data

```bash
# Export baskets from old system
# Create CSV in new format:
# user,name,description,investment_amount

# Import via admin → Baskets → Import
```

### Step 3: Migrate Basket Items

```bash
# Create CSV:
# basket,stock,weight_percentage,allocated_amount,quantity,purchase_price

# Import via admin → Basket items → Import
```

## Validation

### ✅ Data Integrity Check
- [ ] Count old stocks: `Stock.objects.count()`
- [ ] Count imported stocks: should match
- [ ] Verify stock prices are current
- [ ] Check stock names are complete
- [ ] Verify basket counts match
- [ ] Check basket items are correct
- [ ] Test basket calculations (profit/loss)

### ✅ Functionality Check
- [ ] Can view stocks in admin
- [ ] Can create new basket
- [ ] Can add stocks to basket
- [ ] Can export stocks
- [ ] Can import new stocks
- [ ] Basket detail page works
- [ ] Stock prices update correctly

## Clean Up (Optional)

### Remove Old Import System

If new system works perfectly, you can optionally remove old code:

#### Files to Review:
```
stocks/templates/admin/csv_form.html  (old custom import template)
```

#### Code to Review in admin.py:
The old StockAdmin class had custom import methods that are now replaced.

**⚠️ CAUTION**: Only remove after thorough testing!

### Keep for Now:
- Sample CSV files (still useful for reference)
- Old templates (backup purposes)

## Post-Migration

### ✅ Documentation Update
- [ ] Update team documentation
- [ ] Share `DJANGO_IMPORT_EXPORT_GUIDE.md` with team
- [ ] Train team members on new import process
- [ ] Update any import scripts/workflows

### ✅ Schedule Regular Tasks
- [ ] Weekly data backups (export all models)
- [ ] Monthly stock price updates
- [ ] Quarterly data validation

## Rollback Plan

If issues arise, you can rollback:

### Option 1: Restore from Backup
```bash
# Restore database from backup
python manage.py loaddata backup.json
```

### Option 2: Revert Code Changes
```bash
# Revert admin.py to use old custom import
git checkout HEAD stocks/admin.py

# Remove import_export from settings
# Remove from requirements.txt
```

### Option 3: Disable Import-Export
```python
# In settings.py, comment out:
# 'import_export',

# Old custom import will still work via template
```

## Common Issues & Solutions

### Issue: Import button not showing
**Solution**: 
- Clear browser cache
- Verify logged in as admin
- Check `import_export` in INSTALLED_APPS
- Run `python manage.py collectstatic`

### Issue: Yahoo Finance not fetching data
**Solution**:
- Check internet connection
- Verify API not rate-limited
- Manually enter name/price for now
- Retry later when API available

### Issue: Foreign key errors
**Solution**:
- Import parent records first (Users, then Baskets, then BasketItems)
- Use correct identifier (email for Users, symbol for Stocks)
- Verify referenced records exist

### Issue: Duplicate records created
**Solution**:
- Check `import_id_fields` in Resource class
- For Stocks, should be `['symbol']`
- Re-import with correct configuration

## Success Criteria

Migration is successful when:
- ✅ All data migrated without loss
- ✅ Import/export works smoothly
- ✅ Yahoo Finance integration working
- ✅ Team trained on new system
- ✅ No critical bugs or errors
- ✅ Performance is acceptable
- ✅ Backups are in place

## Timeline Estimate

| Phase | Duration | Notes |
|-------|----------|-------|
| Backup & Setup | 30 min | One-time setup |
| Testing | 1-2 hours | Thorough testing |
| Migration | 2-4 hours | Depends on data size |
| Validation | 1 hour | Data integrity checks |
| Training | 1 hour | Team onboarding |
| **Total** | **5-8 hours** | Can be done over days |

## Support Resources

- **Main Guide**: `DJANGO_IMPORT_EXPORT_GUIDE.md`
- **Summary**: `DJANGO_IMPORT_EXPORT_SUMMARY.md`
- **Feature Docs**: `docs/IMPORT_EXPORT_FEATURE.md`
- **Test Script**: `test_import_export.py`
- **Sample Files**: `stock_import_template.csv`, `sample.csv`

## Sign-Off

- [ ] Migration completed successfully
- [ ] Data validated
- [ ] Team trained
- [ ] Documentation updated
- [ ] Backups archived
- [ ] Old system disabled (if applicable)

**Migration Completed By**: ________________  
**Date**: ________________  
**Verified By**: ________________  
**Date**: ________________

---

**Ready to migrate?** Start with the Testing Phase and work through each section systematically. Good luck! 🚀
