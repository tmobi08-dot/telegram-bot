import feedparser
import requests
import asyncio
from googletrans import Translator
import logging
import os
import backoff # تثبيت: pip install backoff

# تهيئة المُسجل
logging.basicConfig(level=logging.INFO, format='%(asctime)s - %(levelname)s - %(message)s')

# تهيئة المترجم
translator = Translator()

# قراءة مفاتيح API من متغيرات البيئة
FINNHUB_API_KEY = os.getenv("FINNHUB_API_KEY")
NEWS_API_KEY = os.getenv("NEWS_API_KEY")
GEMINI_API_KEY = os.getenv("GEMINI_API_KEY")

# قائمة بموجزات RSS
RSS_FEEDS = [
    "https://ar.fxstreet.com/rss/analysis",
    "https://www.investing.com/rss/news_301.rss",
    "https://rss.nytimes.com/services/xml/rss/nyt/Business.xml",
    "https://feeds.bloomberg.com/markets/news.rss",
]

# دالة للتحقق مما إذا كان النص باللغة العربية
def is_arabic(text):
    """
    تتحقق مما إذا كان النص يحتوي على أحرف عربية.
    """
    return any('\u0600' <= ch <= 'ۿ' or 'ݐ' <= ch <= 'ݿ' for ch in text)

# دالة لترجمة النص إلى العربية
def translate_to_ar(text):
    """
    تترجم نصًا من الإنجليزية أو أي لغة إلى العربية.
    """
    try:
        if not is_arabic(text):
            return translator.translate(text, dest='ar').text
        return text
    except Exception as e:
        logging.error(f"خطأ في الترجمة: {e}")
        return text

# دالة لإرسال طلب إلى Gemini API
@backoff.on_exception(backoff.expo, (requests.exceptions.RequestException, Exception), max_tries=3)
def gen_gemini_request(prompt):
    """
    ترسل طلبًا إلى Gemini API لإعادة صياغة النص.
    """
    url = f"https://generativelanguage.googleapis.com/v1beta/models/gemini-pro:generateContent?key={GEMINI_API_KEY}"
    payload = {"contents": [{"role": "user", "parts": [{"text": prompt}]}]}
    try:
        resp = requests.post(url, json=payload, timeout=30).json()
        return resp.get("candidates", [{}])[0].get("content", {}).get("parts", [{}])[0].get("text", "").strip()
    except Exception as e:
        logging.error(f"خطأ في Gemini API: {e}")
        return ""

# دالة لإعادة صياغة النص باستخدام Gemini
def rewrite_with_gemini(text):
    """
    تعيد صياغة نص باستخدام Gemini API إذا كان النص بالإنجليزية.
    """
    # لا تعيد صياغة النص إذا كان باللغة العربية بالفعل
    if is_arabic(text):
        return text
    
    prompt = f"أعد صياغة النص التالي بالعربية مع الحفاظ على المعنى:\n\n{text}"
    return gen_gemini_request(prompt) or text

# دالة غير متزامنة لجلب الأخبار من RSS
async def fetch_rss_feed_async(url):
    """
    دالة غير متزامنة لجلب الأخبار من موجز RSS.
    """
    loop = asyncio.get_event_loop()
    try:
        # استخدام run_in_executor لمنع حظر حلقة الأحداث (event loop)
        feed_data = await loop.run_in_executor(None, lambda: feedparser.parse(url))
        news = []
        for e in feed_data.entries:
            title = translate_to_ar(e.title)
            summary = translate_to_ar(e.get("summary", ""))
            news.append({"title": title, "summary": summary, "link": e.link})
        return news
    except Exception as e:
        logging.error(f"خطأ في RSS من {url}: {e}")
        return []

# دالة غير متزامنة لجلب الأخبار من Finnhub
async def fetch_finnhub_async():
    """
    دالة غير متزامنة لجلب الأخبار من Finnhub API.
    """
    if not FINNHUB_API_KEY:
        logging.error("Finnhub API key is not set.")
        return []

    url = f"https://finnhub.io/api/v1/news?category=general&token={FINNHUB_API_KEY}"
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: requests.get(url, timeout=10))
        response.raise_for_status()  # يرفع استثناء للأخطاء 4xx/5xx

        # تحقق من أن الاستجابة هي JSON قبل التحليل
        if 'application/json' not in response.headers.get('Content-Type', ''):
            logging.error(f"استجابة Finnhub ليست JSON. المحتوى الخام: {response.text}")
            return []

        data = response.json()
        if not isinstance(data, list):
            logging.error("Finnhub API returned an unexpected format. Expected a list.")
            return []

        news = []
        for i in data:
            title = translate_to_ar(i.get("headline", ""))
            summary = translate_to_ar(i.get("summary", ""))
            news.append({"title": title, "summary": summary, "link": i.get("url", "")})
        return news
    except requests.exceptions.RequestException as e:
        logging.error(f"خطأ في Finnhub: {e}")
        return []

# دالة غير متزامنة لجلب الأخبار من NewsAPI
async def fetch_newsapi_async():
    """
    دالة غير متزامنة لجلب الأخبار من NewsAPI.
    """
    url = "https://newsapi.org/v2/everything"
    params = {
        "q": "forex OR currency AND (major OR significant OR impact OR critical OR breaking OR analysis OR outlook)",
        "language": "ar",
        "sortBy": "publishedAt",
        "pageSize": 5,
        "apiKey": NEWS_API_KEY
    }
    loop = asyncio.get_event_loop()
    try:
        response = await loop.run_in_executor(None, lambda: requests.get(url, params=params, timeout=10))
        response.raise_for_status()

        if 'application/json' not in response.headers.get('Content-Type', ''):
            logging.error(f"استجابة NewsAPI ليست JSON. المحتوى الخام: {response.text}")
            return []

        data = response.json()
        articles = data.get("articles", [])
        news = []
        for a in articles:
            title = a.get("title", "")
            summary = a.get("description", "")
            news.append({"title": title, "summary": summary, "link": a.get("url", "")})
        return news
    except requests.exceptions.RequestException as e:
        logging.error(f"خطأ في NewsAPI: {e}")
        return []
    except Exception as e:
        logging.error(f"خطأ غير متوقع في NewsAPI: {e}")
        return []

# دالة رئيسية لجلب جميع الأخبار بشكل متزامن
async def get_all_news_async():
    """
    تجمع الأخبار من جميع المصادر (RSS, Finnhub, NewsAPI) بشكل متزامن.
    """
    # جلب الأخبار من RSS
    rss_tasks = [fetch_rss_feed_async(url) for url in RSS_FEEDS]
    rss_results = await asyncio.gather(*rss_tasks, return_exceptions=True)
    rss_news = []
    for result in rss_results:
        if isinstance(result, list):
            rss_news.extend(result)
        else:
            logging.error(f"فشل في جلب بعض أخبار RSS: {result}")
    
    # جلب الأخبار من Finnhub و NewsAPI بشكل متزامن
    finnhub_task = fetch_finnhub_async()
    newsapi_task = fetch_newsapi_async()
    
    finnhub_result, newsapi_result = await asyncio.gather(finnhub_task, newsapi_task, return_exceptions=True)

    finnhub_news = finnhub_result if isinstance(finnhub_result, list) else []
    if not isinstance(finnhub_result, list):
        logging.error(f"فشل في جلب أخبار Finnhub: {finnhub_result}")

    newsapi_news = newsapi_result if isinstance(newsapi_result, list) else []
    if not isinstance(newsapi_result, list):
        logging.error(f"فشل في جلب أخبار NewsAPI: {newsapi_result}")

    # تجميع كل الأخبار في قائمة واحدة
    all_news = rss_news + finnhub_news + newsapi_news
    
    # إزالة الأخبار المكررة بناءً على الرابط
    unique_news = {item['link']: item for item in all_news}.values()
    
    return list(unique_news)

