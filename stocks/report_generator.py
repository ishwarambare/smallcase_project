import os
import logging
from io import BytesIO
import datetime
import requests
from bs4 import BeautifulSoup
import yfinance as yf
import pandas as pd
import numpy as np

from reportlab.lib.pagesizes import letter
from reportlab.lib import colors
from reportlab.platypus import SimpleDocTemplate, Paragraph, Spacer, Table, TableStyle
from reportlab.lib.styles import getSampleStyleSheet, ParagraphStyle

logger = logging.getLogger(__name__)

def _format_large_number(num):
    """Formats large numbers nicely into Lakhs/Crores for Indian context or Millions/Billions."""
    if num is None or (isinstance(num, float) and np.isnan(num)):
        return "N/A"
    try:
        num = float(num)
        if abs(num) >= 10000000: # 1 Crore = 10 Million
            return f"₹{num / 10000000:.2f} Cr"
        elif abs(num) >= 100000: # 1 Lakh = 100,000
            return f"₹{num / 100000:.2f} L"
        else:
            return f"₹{num:,.2f}"
    except (ValueError, TypeError):
        return str(num)

def _format_pct(val):
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return "N/A"
    try:
        return f"{float(val) * 100:.2f}%" if float(val) < 1.0 else f"{float(val):.2f}%"
    except (ValueError, TypeError):
        return str(val)

def _safe_get(dct, key, default="N/A"):
    val = dct.get(key)
    if val is None or (isinstance(val, float) and np.isnan(val)):
        return default
    return val

def fetch_stock_report_data(symbol: str) -> dict:
    """
    Fetches stock intelligence data from yfinance.
    Returns a structured dictionary ready for PDF compilation.
    """
    data = {
        "symbol": symbol,
        "name": symbol,
        "sector": "N/A",
        "industry": "N/A",
        "description": "No business description available.",
        "website": "N/A",
        "current_price": "N/A",
        "market_cap": "N/A",
        "pe_ratio": "N/A",
        "forward_pe": "N/A",
        "eps": "N/A",
        "dividend_yield": "N/A",
        "beta": "N/A",
        "week_52_high": "N/A",
        "week_52_low": "N/A",
        "price_to_book": "N/A",
        "income_statement": [],
        "balance_sheet": [],
        "cash_flow": [],
        "news": [],
        "generated_at": datetime.datetime.now().strftime("%d %b %Y, %H:%M"),
    }
    
    try:
        ticker = yf.Ticker(symbol)
        info = ticker.info or {}
        
        data["name"] = info.get("longName") or info.get("shortName") or symbol
        data["sector"] = info.get("sector", "N/A")
        data["industry"] = info.get("industry", "N/A")
        data["description"] = info.get("longBusinessSummary") or info.get("description") or "No business description available."
        data["website"] = info.get("website", "N/A")
        
        # Market and Financial ratios
        data["current_price"] = _format_large_number(info.get("currentPrice") or info.get("regularMarketPrice"))
        data["market_cap"] = _format_large_number(info.get("marketCap"))
        data["pe_ratio"] = _safe_get(info, "trailingPE")
        data["forward_pe"] = _safe_get(info, "forwardPE")
        data["eps"] = _safe_get(info, "trailingEps")
        data["dividend_yield"] = _format_pct(info.get("dividendYield"))
        data["beta"] = _safe_get(info, "beta")
        data["week_52_high"] = _format_large_number(info.get("fiftyTwoWeekHigh"))
        data["week_52_low"] = _format_large_number(info.get("fiftyTwoWeekLow"))
        data["price_to_book"] = _safe_get(info, "priceToBook")
        
        # 1. Income Statement
        fin = ticker.financials
        if fin is not None and not fin.empty:
            rows_to_extract = ["Total Revenue", "Gross Profit", "Operating Income", "Net Income", "EBITDA", "Basic EPS"]
            cols = [col.strftime("%Y") if isinstance(col, datetime.datetime) else str(col) for col in fin.columns]
            data["income_statement_years"] = cols
            
            for row in rows_to_extract:
                if row in fin.index:
                    row_vals = []
                    for val in fin.loc[row]:
                        if row == "Basic EPS":
                            row_vals.append(f"{val:.2f}" if pd.notna(val) else "N/A")
                        else:
                            row_vals.append(_format_large_number(val))
                    data["income_statement"].append([row] + row_vals)
        
        # 2. Balance Sheet
        bs = ticker.balance_sheet
        if bs is not None and not bs.empty:
            rows_to_extract = ["Total Assets", "Total Liabilities Net Minority Interest", "Common Stock Equity", "Total Debt"]
            clean_rows = []
            for row in rows_to_extract:
                found_row = next((r for r in bs.index if r.lower().startswith(row.lower()[:15])), None)
                if found_row:
                    clean_rows.append(found_row)
            
            cols = [col.strftime("%Y") if isinstance(col, datetime.datetime) else str(col) for col in bs.columns]
            data["balance_sheet_years"] = cols
            for row in clean_rows:
                row_vals = [_format_large_number(val) for val in bs.loc[row]]
                data["balance_sheet"].append([row] + row_vals)
                
        # 3. Cash Flow
        cf = ticker.cashflow
        if cf is not None and not cf.empty:
            rows_to_extract = ["Operating Cash Flow", "Investing Cash Flow", "Financing Cash Flow", "Free Cash Flow"]
            clean_rows = []
            for row in rows_to_extract:
                found_row = next((r for r in cf.index if r.lower().startswith(row.lower()[:15])), None)
                if found_row:
                    clean_rows.append(found_row)
            
            cols = [col.strftime("%Y") if isinstance(col, datetime.datetime) else str(col) for col in cf.columns]
            data["cash_flow_years"] = cols
            for row in clean_rows:
                row_vals = [_format_large_number(val) for val in cf.loc[row]]
                data["cash_flow"].append([row] + row_vals)

        # 4. News
        news_items = ticker.news or []
        for item in news_items[:8]:
            data["news"].append({
                "title": item.get("title", "No Title"),
                "publisher": item.get("publisher", "Unknown"),
                "link": item.get("link", "#"),
            })
            
    except Exception as e:
        logger.error(f"[ReportGenerator] Error fetching data for {symbol}: {e}")
        
    return data

def compile_pdf_report(data: dict) -> bytes:
    """
    Compiles report data into a beautiful, styled PDF document.
    Returns the PDF as a byte string.
    """
    buffer = BytesIO()
    doc = SimpleDocTemplate(
        buffer,
        pagesize=letter,
        rightMargin=40,
        leftMargin=40,
        topMargin=40,
        bottomMargin=40
    )
    
    styles = getSampleStyleSheet()
    
    primary_color = colors.HexColor("#1e3a8a") # Deep Blue
    secondary_color = colors.HexColor("#3b82f6") # Bright Blue
    text_color = colors.HexColor("#334155") # Dark slate
    light_bg = colors.HexColor("#f8fafc") # Slate 50
    border_color = colors.HexColor("#e2e8f0") # Slate 200
    
    title_style = ParagraphStyle(
        'DocTitle',
        parent=styles['Heading1'],
        fontName='Helvetica-Bold',
        fontSize=24,
        leading=28,
        textColor=primary_color,
        spaceAfter=6
    )
    
    subtitle_style = ParagraphStyle(
        'DocSubTitle',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=10,
        leading=14,
        textColor=colors.HexColor("#64748b"),
        spaceAfter=15
    )
    
    section_heading = ParagraphStyle(
        'SectionHeading',
        parent=styles['Heading2'],
        fontName='Helvetica-Bold',
        fontSize=14,
        leading=18,
        textColor=primary_color,
        spaceBefore=15,
        spaceAfter=8,
        keepWithNext=True
    )
    
    body_style = ParagraphStyle(
        'Body',
        parent=styles['BodyText'],
        fontName='Helvetica',
        fontSize=9.5,
        leading=14,
        textColor=text_color,
        spaceAfter=8
    )
    
    table_cell_style = ParagraphStyle(
        'TableCell',
        parent=styles['Normal'],
        fontName='Helvetica',
        fontSize=8.5,
        leading=11,
        textColor=text_color
    )
    
    table_header_style = ParagraphStyle(
        'TableHeader',
        parent=styles['Normal'],
        fontName='Helvetica-Bold',
        fontSize=9,
        leading=12,
        textColor=colors.white
    )
    
    story = []
    
    story.append(Paragraph(f"{data['name']} ({data['symbol']})", title_style))
    story.append(Paragraph(f"Annual Report & Financial Analysis Report · Generated on {data['generated_at']}", subtitle_style))
    
    story.append(Paragraph("Company Profile", section_heading))
    profile_text = f"<b>Sector:</b> {data['sector']} | <b>Industry:</b> {data['industry']} | <b>Website:</b> {data['website']}"
    story.append(Paragraph(profile_text, body_style))
    story.append(Paragraph(data['description'], body_style))
    story.append(Spacer(1, 10))
    
    story.append(Paragraph("Key Financial Metrics", section_heading))
    metrics_data = [
        [
            Paragraph("<b>Current Price:</b>", table_cell_style), Paragraph(str(data["current_price"]), table_cell_style),
            Paragraph("<b>Market Capitalization:</b>", table_cell_style), Paragraph(str(data["market_cap"]), table_cell_style)
        ],
        [
            Paragraph("<b>P/E Ratio (Trailing):</b>", table_cell_style), Paragraph(str(data["pe_ratio"]), table_cell_style),
            Paragraph("<b>Forward P/E:</b>", table_cell_style), Paragraph(str(data["forward_pe"]), table_cell_style)
        ],
        [
            Paragraph("<b>Earnings Per Share (EPS):</b>", table_cell_style), Paragraph(str(data["eps"]), table_cell_style),
            Paragraph("<b>Dividend Yield:</b>", table_cell_style), Paragraph(str(data["dividend_yield"]), table_cell_style)
        ],
        [
            Paragraph("<b>Beta (Volatility):</b>", table_cell_style), Paragraph(str(data["beta"]), table_cell_style),
            Paragraph("<b>Price to Book (P/B):</b>", table_cell_style), Paragraph(str(data["price_to_book"]), table_cell_style)
        ],
        [
            Paragraph("<b>52-Week High:</b>", table_cell_style), Paragraph(str(data["week_52_high"]), table_cell_style),
            Paragraph("<b>52-Week Low:</b>", table_cell_style), Paragraph(str(data["week_52_low"]), table_cell_style)
        ]
    ]
    
    metrics_table = Table(metrics_data, colWidths=[130, 130, 130, 130])
    metrics_table.setStyle(TableStyle([
        ('BACKGROUND', (0,0), (-1,-1), light_bg),
        ('BOX', (0,0), (-1,-1), 0.5, border_color),
        ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
        ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
        ('TOPPADDING', (0,0), (-1,-1), 6),
        ('BOTTOMPADDING', (0,0), (-1,-1), 6),
        ('LEFTPADDING', (0,0), (-1,-1), 8),
        ('RIGHTPADDING', (0,0), (-1,-1), 8),
    ]))
    story.append(metrics_table)
    story.append(Spacer(1, 15))
    
    if data["income_statement"]:
        story.append(Paragraph("Income Statement Highlights", section_heading))
        headers = [Paragraph("Metric", table_header_style)] + [Paragraph(year, table_header_style) for year in data["income_statement_years"]]
        table_rows = [headers]
        for row in data["income_statement"]:
            row_p = [Paragraph(f"<b>{row[0]}</b>" if i == 0 else row[i], table_cell_style) for i in range(len(row))]
            table_rows.append(row_p)
            
        is_table = Table(table_rows, colWidths=[180] + [85] * (len(headers) - 1))
        is_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(is_table)
        story.append(Spacer(1, 15))
        
    if data["balance_sheet"]:
        story.append(Paragraph("Balance Sheet Highlights", section_heading))
        headers = [Paragraph("Metric", table_header_style)] + [Paragraph(year, table_header_style) for year in data["balance_sheet_years"]]
        table_rows = [headers]
        for row in data["balance_sheet"]:
            row_p = [Paragraph(f"<b>{row[0]}</b>" if i == 0 else row[i], table_cell_style) for i in range(len(row))]
            table_rows.append(row_p)
            
        bs_table = Table(table_rows, colWidths=[180] + [85] * (len(headers) - 1))
        bs_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), secondary_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(bs_table)
        story.append(Spacer(1, 15))
        
    if data["cash_flow"]:
        story.append(Paragraph("Cash Flow Highlights", section_heading))
        headers = [Paragraph("Metric", table_header_style)] + [Paragraph(year, table_header_style) for year in data["cash_flow_years"]]
        table_rows = [headers]
        for row in data["cash_flow"]:
            row_p = [Paragraph(f"<b>{row[0]}</b>" if i == 0 else row[i], table_cell_style) for i in range(len(row))]
            table_rows.append(row_p)
            
        cf_table = Table(table_rows, colWidths=[180] + [85] * (len(headers) - 1))
        cf_table.setStyle(TableStyle([
            ('BACKGROUND', (0,0), (-1,0), primary_color),
            ('ROWBACKGROUNDS', (0,1), (-1,-1), [colors.white, light_bg]),
            ('BOX', (0,0), (-1,-1), 0.5, border_color),
            ('INNERGRID', (0,0), (-1,-1), 0.5, border_color),
            ('VALIGN', (0,0), (-1,-1), 'MIDDLE'),
            ('TOPPADDING', (0,0), (-1,-1), 5),
            ('BOTTOMPADDING', (0,0), (-1,-1), 5),
        ]))
        story.append(cf_table)
        story.append(Spacer(1, 15))

    if data["news"]:
        story.append(Paragraph("Recent News & Developments", section_heading))
        for item in data["news"]:
            title_p = Paragraph(f"• <b>{item['title']}</b> ({item['publisher']})", table_cell_style)
            story.append(title_p)
            story.append(Spacer(1, 4))
            
    doc.build(story)
    pdf_bytes = buffer.getvalue()
    buffer.close()
    return pdf_bytes

def scrape_and_index_bse_nse_documents(stock, limit=3) -> int:
    """
    Scrapes Screener.in for BSE/NSE annual reports & concall transcripts.
    Downloads and indexes up to `limit` documents.
    Returns the count of successfully indexed documents.
    """
    from .models import StockDocument
    from .pgvector_rag_service import pgvector_rag_service
    from django.core.files.base import ContentFile
    
    clean_symbol = stock.symbol.replace('.NS', '').replace('.BO', '').strip()
    url = f"https://www.screener.in/company/{clean_symbol}/"
    headers = {
        'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/120.0.0.0 Safari/537.36'
    }
    
    try:
        r = requests.get(url, headers=headers, timeout=15)
        if r.status_code != 200:
            logger.warning(f"[Scraper] Screener returned status {r.status_code} for {clean_symbol}")
            return 0
            
        soup = BeautifulSoup(r.text, 'html.parser')
        documents_to_download = []
        
        # 1. Parse Concalls (Transcripts, PPTs)
        cc_div = soup.find('div', class_='concalls')
        if cc_div:
            for li in cc_div.find_all('li'):
                date_div = li.find('div')
                period = date_div.text.strip() if date_div else "N/A"
                for a in li.find_all('a'):
                    href = a.get('href')
                    if href and '.pdf' in href.lower():
                        text = a.text.strip()
                        doc_type = 'other'
                        if 'transcript' in text.lower():
                            doc_type = 'earnings_call'
                        elif 'ppt' in text.lower() or 'presentation' in text.lower():
                            doc_type = 'investor_presentation'
                            
                        if doc_type in ['earnings_call', 'investor_presentation']:
                            documents_to_download.append({
                                'title': f"{stock.symbol} Concall {text} ({period})",
                                'doc_type': doc_type,
                                'period': period,
                                'url': href
                            })
                            
        # 2. Parse Annual Reports
        ar_div = soup.find('div', class_='annual-reports')
        if ar_div:
            for a in ar_div.find_all('a'):
                href = a.get('href')
                if href and '.pdf' in href.lower():
                    period = a.text.strip().replace('\n', ' ').strip()
                    period_clean = period.replace("Financial Year ", "FY")
                    documents_to_download.append({
                        'title': f"{stock.symbol} Annual Report ({period_clean})",
                        'doc_type': 'annual_report',
                        'period': period_clean,
                        'url': href
                    })

        # Process and download (prioritize most recent)
        indexed_count = 0
        for doc_info in documents_to_download[:limit]:
            title = doc_info['title']
            # Check if already exists
            if StockDocument.objects.filter(stock=stock, title=title).exists():
                logger.info(f"[Scraper] Document already exists: {title}. Skipping.")
                continue
                
            # Download PDF
            try:
                doc_resp = requests.get(doc_info['url'], headers=headers, timeout=20)
                if doc_resp.status_code == 200 and doc_resp.content.startswith(b'%PDF'):
                    doc = StockDocument.objects.create(
                        stock=stock,
                        title=title,
                        document_type=doc_info['doc_type'],
                        fiscal_year=doc_info['period'],
                        is_indexed=False,
                        notes=f"Source URL: {doc_info['url']}"
                    )
                    
                    filename = f"{stock.symbol}_{doc_info['doc_type']}_{doc_info['period']}.pdf".replace(" ", "_")
                    doc.file.save(filename, ContentFile(doc_resp.content))
                    
                    # Index via RAG
                    result = pgvector_rag_service.ingest_document(
                        symbol=stock.symbol,
                        document_id=doc.id,
                        file_path='',
                        doc_title=title,
                        doc_type=doc_info['doc_type']
                    )
                    if result['success']:
                        indexed_count += 1
                        logger.info(f"[Scraper] Successfully indexed: {title}")
                    else:
                        logger.warning(f"[Scraper] Failed to index: {title} - {result.get('error')}")
                else:
                    logger.info(f"[Scraper] Download failed or invalid PDF for URL (status {doc_resp.status_code}): {doc_info['url']}")
            except Exception as download_err:
                logger.debug(f"[Scraper] Download error for {doc_info['url']}: {download_err}")

                
        return indexed_count
    except Exception as e:
        logger.error(f"[Scraper] Error scraping Screener.in for {stock.symbol}: {e}")
        return 0

def generate_and_save_yfinance_overview(stock) -> tuple[bool, str]:
    """Generates yfinance overview report and saves/indexes it."""
    from .models import StockDocument
    from .pgvector_rag_service import pgvector_rag_service
    from django.core.files.base import ContentFile
    
    data = fetch_stock_report_data(stock.symbol)
    try:
        pdf_bytes = compile_pdf_report(data)
        title = f"{stock.symbol} Annual Report & Financial Analysis (FY2025)"
        
        # Check if overview already exists
        if StockDocument.objects.filter(stock=stock, title=title).exists():
            return True, "Overview report already exists."
            
        doc = StockDocument.objects.create(
            stock=stock,
            title=title,
            document_type='annual_report',
            fiscal_year='FY2025',
            is_indexed=False,
            notes="Automatically generated from Yahoo Finance API"
        )
        
        filename = f"{stock.symbol}_AnnualReport_2025.pdf"
        doc.file.save(filename, ContentFile(pdf_bytes))
        
        result = pgvector_rag_service.ingest_document(
            symbol=stock.symbol,
            document_id=doc.id,
            file_path='',
            doc_title=title,
            doc_type='annual_report'
        )
        
        if result['success']:
            return True, "Overview report generated and indexed."
        else:
            return False, f"Overview report saved but indexing failed: {result.get('error')}"
    except Exception as e:
        return False, str(e)

def auto_generate_and_save_report(stock) -> tuple[bool, str]:
    """
    Scrapes Screener.in for BSE/NSE annual reports/transcripts,
    and generates a yfinance detailed overview PDF.
    Returns: (success_bool, message_str)
    """
    # 1. Scrape concalls / annual reports from Screener.in
    scraped_count = scrape_and_index_bse_nse_documents(stock, limit=3)
    
    # 2. Generate yfinance detailed overview PDF
    overview_success, overview_msg = generate_and_save_yfinance_overview(stock)
    
    if scraped_count > 0 or overview_success:
        msg = f"Generated yfinance overview report. Scraped and indexed {scraped_count} documents from BSE/NSE."
        return True, msg
    else:
        return False, f"Failed to generate reports: {overview_msg}"
