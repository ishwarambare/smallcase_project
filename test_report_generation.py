import os
import django
import sys

# Setup Django Environment
os.environ.setdefault('DJANGO_SETTINGS_MODULE', 'smallcase_project.settings')
django.setup()

from stocks.models import Stock, StockDocument
from stocks.report_generator import fetch_stock_report_data, compile_pdf_report, auto_generate_and_save_report

def run_tests():
    test_symbol = "INFY.NS"
    print(f"--- 1. Testing yfinance Data Fetching for {test_symbol} ---")
    try:
        data = fetch_stock_report_data(test_symbol)
        assert data is not None, "Data fetched should not be None"
        assert data["symbol"] == test_symbol, "Symbol mismatch in fetched data"
        assert len(data["name"]) > 0, "Stock name should not be empty"
        print("[SUCCESS] yfinance data fetched successfully.")
        print(f"Name: {data['name']}, Sector: {data['sector']}, Industry: {data['industry']}")
    except Exception as e:
        print(f"[FAIL] yfinance fetching failed: {e}")
        sys.exit(1)

    print(f"\n--- 2. Testing reportlab PDF Compilation ---")
    try:
        pdf_bytes = compile_pdf_report(data)
        assert pdf_bytes is not None, "Generated PDF bytes should not be None"
        assert len(pdf_bytes) > 0, "PDF bytes should not be empty"
        print("[SUCCESS] PDF compiled successfully using reportlab.")
        print(f"Generated PDF Size: {len(pdf_bytes)} bytes")
    except Exception as e:
        print(f"[FAIL] PDF compilation failed: {e}")
        sys.exit(1)

    print(f"\n--- 3. Testing Full RAG Saving & Indexing Pipeline ---")
    try:
        stock = Stock.objects.filter(symbol=test_symbol).first()
        if not stock:
            # Create a temporary stock object for testing
            print(f"Creating temporary Stock model for {test_symbol}...")
            stock = Stock.objects.create(symbol=test_symbol, name="Infosys Limited")
            created_temp_stock = True
        else:
            created_temp_stock = False

        # Generate and save report
        success, msg = auto_generate_and_save_report(stock)
        print(f"Result: {msg}")
        assert success is True, f"Report generation failed: {msg}"

        # Verify Document exists in DB and is indexed
        doc = StockDocument.objects.filter(stock=stock, is_indexed=True).first()
        assert doc is not None, "Document should be saved and marked as indexed in DB"
        assert doc.chunk_count > 0, "Indexed document should have chunks in DB"
        print("[SUCCESS] Document saved and indexed successfully into Django DB / RAG.")

        # Cleanup
        print("\n--- 4. Cleaning up Test Data ---")
        # Delete file from storage and db
        if doc.file:
            doc.file.delete(save=False)
        doc.delete()
        
        if created_temp_stock:
            stock.delete()
            print("Temporary stock deleted.")

        print("[SUCCESS] Cleanup completed. Tests passed successfully!")

    except Exception as e:
        print(f"[FAIL] Full pipeline verification failed: {e}")
        # Make sure to clean up even if tests fail
        try:
            if 'doc' in locals() and doc:
                if doc.file:
                    doc.file.delete(save=False)
                doc.delete()
            if 'created_temp_stock' in locals() and created_temp_stock and stock:
                stock.delete()
        except Exception:
            pass
        sys.exit(1)

if __name__ == "__main__":
    run_tests()
