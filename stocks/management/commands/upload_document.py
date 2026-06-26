import os
from django.core.management.base import BaseCommand, CommandError
from django.core.files import File
from stocks.models import Stock, StockDocument
from stocks.pgvector_rag_service import pgvector_rag_service

class Command(BaseCommand):
    help = 'Upload and index a local PDF document for a stock'

    def add_arguments(self, parser):
        parser.add_argument('--symbol', type=str, required=True, help='Stock symbol (e.g. TCS)')
        parser.add_argument('--file', type=str, required=True, help='Path to the local PDF file')
        parser.add_argument('--title', type=str, help='Title of the document (defaults to filename)')
        parser.add_argument(
            '--type', 
            type=str, 
            default='other', 
            choices=['annual_report', 'earnings_call', 'investor_presentation', 'research_report', 'other'],
            help='Document type'
        )
        parser.add_argument('--fy', type=str, default='', help='Fiscal year (e.g. FY2025 or Q3-2025)')
        parser.add_argument('--notes', type=str, default='', help='Additional notes')

    def handle(self, *args, **options):
        symbol = options['symbol'].upper()
        file_path = options['file']
        title = options['title']
        doc_type = options['type']
        fy = options['fy']
        notes = options['notes']

        # Verify stock exists
        try:
            stock = Stock.objects.get(symbol=symbol)
        except Stock.DoesNotExist:
            raise CommandError(f"Stock with symbol {symbol} does not exist in the database.")

        # Verify file exists locally
        if not os.path.exists(file_path):
            raise CommandError(f"Local file not found: {file_path}")
        
        if not file_path.lower().endswith('.pdf'):
            raise CommandError("Only PDF files are supported for ingestion.")

        # Set default title if not provided
        filename = os.path.basename(file_path)
        if not title:
            title = os.path.splitext(filename)[0].replace('_', ' ').replace('-', ' ').title()

        self.stdout.write(f"Uploading {filename} for {symbol}...")

        try:
            # 1. Create StockDocument record
            doc = StockDocument.objects.create(
                stock=stock,
                title=title,
                document_type=doc_type,
                fiscal_year=fy,
                is_indexed=False,
                notes=notes
            )

            # 2. Save file to storage
            with open(file_path, 'rb') as f:
                doc.file.save(filename, File(f))
            
            self.stdout.write(self.style.SUCCESS(f"Saved document '{title}' to storage."))

            # 3. Index/Ingest document in RAG
            self.stdout.write("Extracting and indexing text chunks...")
            result = pgvector_rag_service.ingest_document(
                symbol=symbol,
                document_id=doc.id,
                file_path='',  # The service will load it from storage via document_id
                doc_title=title,
                doc_type=doc_type
            )

            if result['success']:
                self.stdout.write(
                    self.style.SUCCESS(
                        f"Successfully indexed '{title}' into RAG with {result['chunk_count']} chunks."
                    )
                )
            else:
                doc.delete()  # Clean up database and storage if indexing fails
                raise CommandError(f"Failed to index document: {result.get('error')}")

        except Exception as e:
            self.stdout.write(self.style.ERROR(f"Error during upload/ingest: {e}"))
            raise CommandError(e)
