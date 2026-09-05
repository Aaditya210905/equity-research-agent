from __future__ import annotations

from .models import Company

# Same curated universe as the TypeScript application.
UNIVERSE = [
    Company(ticker="RELIANCE.NS", display="RELIANCE", name="Reliance Industries", market="IN", exchange="NSE", sector="Energy"),
    Company(ticker="TCS.NS", display="TCS", name="Tata Consultancy Services", market="IN", exchange="NSE", sector="IT"),
    Company(ticker="HDFCBANK.NS", display="HDFCBANK", name="HDFC Bank", market="IN", exchange="NSE", sector="Banks"),
    Company(ticker="INFY.NS", display="INFY", name="Infosys", market="IN", exchange="NSE", sector="IT"),
    Company(ticker="ICICIBANK.NS", display="ICICIBANK", name="ICICI Bank", market="IN", exchange="NSE", sector="Banks"),
    Company(ticker="HINDUNILVR.NS", display="HINDUNILVR", name="Hindustan Unilever", market="IN", exchange="NSE", sector="FMCG"),
    Company(ticker="ITC.NS", display="ITC", name="ITC", market="IN", exchange="NSE", sector="FMCG"),
    Company(ticker="SBIN.NS", display="SBIN", name="State Bank of India", market="IN", exchange="NSE", sector="Banks"),
    Company(ticker="BHARTIARTL.NS", display="BHARTIARTL", name="Bharti Airtel", market="IN", exchange="NSE", sector="Telecom"),
    Company(ticker="BAJFINANCE.NS", display="BAJFINANCE", name="Bajaj Finance", market="IN", exchange="NSE", sector="Financials"),
    Company(ticker="KOTAKBANK.NS", display="KOTAKBANK", name="Kotak Mahindra Bank", market="IN", exchange="NSE", sector="Banks"),
    Company(ticker="LT.NS", display="LT", name="Larsen & Toubro", market="IN", exchange="NSE", sector="Industrials"),
    Company(ticker="AXISBANK.NS", display="AXISBANK", name="Axis Bank", market="IN", exchange="NSE", sector="Banks"),
    Company(ticker="ASIANPAINT.NS", display="ASIANPAINT", name="Asian Paints", market="IN", exchange="NSE", sector="Materials"),
    Company(ticker="MARUTI.NS", display="MARUTI", name="Maruti Suzuki", market="IN", exchange="NSE", sector="Auto"),
    Company(ticker="SUNPHARMA.NS", display="SUNPHARMA", name="Sun Pharma", market="IN", exchange="NSE", sector="Healthcare"),
    Company(ticker="TITAN.NS", display="TITAN", name="Titan Company", market="IN", exchange="NSE", sector="Consumer"),
    Company(ticker="ULTRACEMCO.NS", display="ULTRACEMCO", name="UltraTech Cement", market="IN", exchange="NSE", sector="Materials"),
    Company(ticker="WIPRO.NS", display="WIPRO", name="Wipro", market="IN", exchange="NSE", sector="IT"),
    Company(ticker="HCLTECH.NS", display="HCLTECH", name="HCL Technologies", market="IN", exchange="NSE", sector="IT"),
    Company(ticker="TATAMOTORS.NS", display="TATAMOTORS", name="Tata Motors", market="IN", exchange="NSE", sector="Auto"),
    Company(ticker="M&M.NS", display="M&M", name="Mahindra & Mahindra", market="IN", exchange="NSE", sector="Auto"),
    Company(ticker="ADANIENT.NS", display="ADANIENT", name="Adani Enterprises", market="IN", exchange="NSE", sector="Conglomerate"),
    Company(ticker="NTPC.NS", display="NTPC", name="NTPC", market="IN", exchange="NSE", sector="Utilities"),
    Company(ticker="ONGC.NS", display="ONGC", name="ONGC", market="IN", exchange="NSE", sector="Energy"),
    Company(ticker="JSWSTEEL.NS", display="JSWSTEEL", name="JSW Steel", market="IN", exchange="NSE", sector="Materials"),
    Company(ticker="NESTLEIND.NS", display="NESTLEIND", name="Nestle India", market="IN", exchange="NSE", sector="FMCG"),
    Company(ticker="POWERGRID.NS", display="POWERGRID", name="Power Grid", market="IN", exchange="NSE", sector="Utilities"),
]

for ticker, name, exchange, sector in [
    ("AAPL", "Apple", "NASDAQ", "Technology"), ("MSFT", "Microsoft", "NASDAQ", "Technology"),
    ("NVDA", "NVIDIA", "NASDAQ", "Technology"), ("AMZN", "Amazon", "NASDAQ", "Consumer"),
    ("GOOGL", "Alphabet", "NASDAQ", "Technology"), ("META", "Meta Platforms", "NASDAQ", "Technology"),
    ("TSLA", "Tesla", "NASDAQ", "Auto"), ("AVGO", "Broadcom", "NASDAQ", "Technology"),
    ("JPM", "JPMorgan Chase", "NYSE", "Banks"), ("V", "Visa", "NYSE", "Financials"),
    ("UNH", "UnitedHealth", "NYSE", "Healthcare"), ("XOM", "Exxon Mobil", "NYSE", "Energy"),
    ("JNJ", "Johnson & Johnson", "NYSE", "Healthcare"), ("WMT", "Walmart", "NYSE", "Consumer"),
    ("MA", "Mastercard", "NYSE", "Financials"), ("PG", "Procter & Gamble", "NYSE", "FMCG"),
    ("COST", "Costco", "NASDAQ", "Consumer"), ("NFLX", "Netflix", "NASDAQ", "Media"),
    ("BAC", "Bank of America", "NYSE", "Banks"), ("KO", "Coca-Cola", "NYSE", "FMCG"),
    ("AMD", "AMD", "NASDAQ", "Technology"), ("ORCL", "Oracle", "NYSE", "Technology"),
    ("LLY", "Eli Lilly", "NYSE", "Healthcare"), ("HD", "Home Depot", "NYSE", "Consumer"),
    ("CRM", "Salesforce", "NYSE", "Technology"), ("DIS", "Walt Disney", "NYSE", "Media"),
]:
    UNIVERSE.append(Company(ticker=ticker, display=ticker, name=name, market="US", exchange=exchange, sector=sector))


def find_company(ticker: str) -> Company | None:
    key = ticker.strip().upper()
    return next((company for company in UNIVERSE if company.ticker.upper() == key or company.display.upper() == key), None)


def infer_market(ticker: str, exchange: str | None = None) -> str:
    ticker_upper = ticker.upper()
    exchange_upper = (exchange or "").upper()
    if ticker_upper.endswith((".NS", ".BO")) or any(x in exchange_upper for x in ("NSE", "NSI", "BSE")):
        return "IN"
    if any(x in exchange_upper for x in ("NASDAQ", "NYSE", "NMS", "NYQ", "PCX")):
        return "US"
    if ticker_upper.isascii() and ticker_upper.replace(".", "").isalpha() and len(ticker_upper) <= 6 and "." not in ticker_upper:
        return "US"
    return "OTHER"
