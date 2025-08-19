import yfinance as yf
import requests
import logging
import os

# إعداد تسجيل الأخطاء والمعلومات
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# --- إعداد أزواج العملات (الفوركس) ---
FOREX_PAIRS = {
    "EUR/USD": "EURUSD=X",
    "GBP/USD": "GBPUSD=X",
    "USD/JPY": "USDJPY=X",
    "AUD/USD": "AUDUSD=X",
    "USD/CAD": "USDCAD=X",
    "USD/CHF": "USDCHF=X",
    "NZD/USD": "NZDUSD=X"
}

def fetch_forex_prices():
    """
    جلب أسعار أزواج الفوركس من Yahoo Finance.
    """
    prices = {}
    for pair, ticker in FOREX_PAIRS.items():
        try:
            df = yf.Ticker(ticker).history(period="1d", interval="1h")
            if not df.empty:
                price = df["Close"].iloc[-1]
                prices[pair] = price
            else:
                prices[pair] = None
                print(f"لم يتم العثور على بيانات سعرية لـ {pair} في الفترة الزمنية المحددة.")
        except Exception as e:
            print(f"خطأ في جلب السعر لـ {pair}: {e}")
            prices[pair] = None
    return prices

def fetch_oil_price():
    """
    جلب سعر النفط (خام برنت) من Yahoo Finance.
    """
    try:
        df = yf.Ticker("BZ=F").history(period="1d", interval="1h")
        if not df.empty:
            return df["Close"].iloc[-1]
        else:
            print("لم يتم العثور على بيانات سعرية للنفط.")
            return None
    except Exception as e:
        print(f"خطأ في جلب سعر النفط: {e}")
        return None

def fetch_silver_price():
    """
    جلب سعر الفضة من Yahoo Finance.
    """
    try:
        df = yf.Ticker("SI=F").history(period="1d", interval="1h")
        if not df.empty:
            return df["Close"].iloc[-1]
        else:
            print("لم يتم العثور على بيانات سعرية للفضة.")
            return None
    except Exception as e:
        print(f"خطأ في جلب سعر الفضة: {e}")
        return None

# -------- مثال على طباعة الأسعار --------
if __name__ == "__main__":
    forex = fetch_forex_prices()
    print("أسعار أزواج العملات:")
    for pair, price in forex.items():
        if price is not None:
            print(f"{pair}: {price:.5f}")
        else:
            print(f"{pair}: ❌ (لا توجد بيانات)")

    oil = fetch_oil_price()
    print(f"\nسعر النفط (برنت): {oil if oil is not None else '❌'}")

    silver = fetch_silver_price()
    print(f"سعر الفضة: {silver if silver is not None else '❌'}")