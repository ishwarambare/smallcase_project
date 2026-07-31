"""
Quick Test Script for Django Import-Export Integration

This script demonstrates how to programmatically test the import functionality.
Run this after starting Django shell: python manage.py shell
"""

from stocks.resources import StockResource
from io import BytesIO

# Sample CSV data
sample_csv = """symbol,name,current_price
RELIANCE.NS,Reliance Industries,
TCS.NS,Tata Consultancy Services,
INFY.NS,Infosys,
"""

def test_import():
    """Test importing stocks from CSV data"""
    
    # Create resource instance
    stock_resource = StockResource()
    
    # Create dataset from CSV string
    dataset = stock_resource.import_data(
        dataset=sample_csv,
        dry_run=True,  # Test mode - don't actually save
        format='csv',
        raise_errors=False
    )
    
    # Print results
    print("=" * 50)
    print("IMPORT TEST RESULTS")
    print("=" * 50)
    print(f"Total rows: {dataset.totals['new'] + dataset.totals['update']}")
    print(f"New records: {dataset.totals['new']}")
    print(f"Updated records: {dataset.totals['update']}")
    print(f"Skipped records: {dataset.totals['skip']}")
    print(f"Errors: {dataset.totals['error']}")
    print("=" * 50)
    
    if dataset.has_errors():
        print("\nERRORS FOUND:")
        for row in dataset.invalid_rows:
            print(f"Row {row.number}: {row.error}")
    else:
        print("\n✅ Import test successful! No errors found.")
        print("\nTo actually import the data, run with dry_run=False")
    
    return dataset


def test_export():
    """Test exporting stocks to CSV"""
    from stocks.models import Stock
    
    stock_resource = StockResource()
    dataset = stock_resource.export()
    
    # Get CSV export
    csv_export = dataset.csv
    
    print("=" * 50)
    print("EXPORT TEST RESULTS")
    print("=" * 50)
    print(f"Total stocks exported: {len(dataset)}")
    print("\nFirst few rows of CSV export:")
    print("-" * 50)
    print("\n".join(csv_export.split('\n')[:5]))
    print("=" * 50)
    
    return csv_export


if __name__ == "__main__":
    print("Django Import-Export Test Script")
    print("\nTo run these tests:")
    print("1. python manage.py shell")
    print("2. exec(open('test_import_export.py').read())")
    print("3. test_import()")
    print("4. test_export()")
