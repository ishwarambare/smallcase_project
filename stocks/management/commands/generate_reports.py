from django.core.management.base import BaseCommand
from stocks.models import Stock
from stocks.report_generator import auto_generate_and_save_report

class Command(BaseCommand):
    help = 'Generate and index financial report PDFs for all stocks or a specific symbol'

    def add_arguments(self, parser):
        parser.add_argument('--all', action='store_true', help='Generate reports for all stocks')
        parser.add_argument('--symbol', type=str, help='Generate report for a specific stock symbol')

    def handle(self, *args, **options):
        if options['all']:
            stocks = Stock.objects.all()
            self.stdout.write(f"Generating reports for {stocks.count()} stocks...")
            for stock in stocks:
                self.stdout.write(f"Processing {stock.symbol}...")
                success, msg = auto_generate_and_save_report(stock)
                status = "SUCCESS" if success else "FAILED"
                self.stdout.write(f"[{status}] {stock.symbol}: {msg}")
        elif options['symbol']:
            symbol = options['symbol']
            try:
                stock = Stock.objects.get(symbol=symbol)
                self.stdout.write(f"Processing {stock.symbol}...")
                success, msg = auto_generate_and_save_report(stock)
                status = "SUCCESS" if success else "FAILED"
                self.stdout.write(f"[{status}] {stock.symbol}: {msg}")
            except Stock.DoesNotExist:
                self.stderr.write(f"Stock with symbol {symbol} does not exist.")
        else:
            self.stderr.write("Please specify either --all or --symbol <symbol>.")
