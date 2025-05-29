#celar
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import sqlite3
import re
from flask import Flask, request, render_template, jsonify
from collections import defaultdict
import threading
import time
import random
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta

# ========================================
# Base de datos mejorada
# ========================================
class SearchEngineDB:
    def __init__(self, db_name='search_engine.db'):
        self.conn = sqlite3.connect(db_name, check_same_thread=False)
        self.create_tables()
        self.create_indexes()
        
    def create_tables(self):
        cursor = self.conn.cursor()
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS pages (
                id INTEGER PRIMARY KEY,
                url TEXT UNIQUE,
                domain TEXT,
                title TEXT,
                content TEXT,
                last_crawled TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS inverted_index (
                word TEXT,
                page_id INTEGER,
                frequency INTEGER,
                PRIMARY KEY(word, page_id)
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS domains (
                domain TEXT PRIMARY KEY,
                last_visited TIMESTAMP,
                delay INTEGER DEFAULT 5
            )
        ''')
        cursor.execute('''
            CREATE TABLE IF NOT EXISTS dynamic_searches (
                query TEXT PRIMARY KEY,
                last_searched TIMESTAMP
            )
        ''')
        self.conn.commit()
    
    def create_indexes(self):
        cursor = self.conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_word ON inverted_index(word)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_domain ON pages(domain)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_query ON dynamic_searches(query)')
        self.conn.commit()
    
    def insert_page(self, url, domain, title, content):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO pages (url, domain, title, content)
            VALUES (?, ?, ?, ?)
        ''', (url, domain, title, content))
        self.conn.commit()
        return cursor.lastrowid
    
    def insert_inverted_index(self, word, page_id, frequency):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO inverted_index (word, page_id, frequency)
            VALUES (?, ?, ?)
        ''', (word, page_id, frequency))
    
    def update_domain(self, domain):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO domains (domain, last_visited)
            VALUES (?, CURRENT_TIMESTAMP)
        ''', (domain,))
        self.conn.commit()
    
    def should_crawl_domain(self, domain):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT last_visited, delay 
            FROM domains 
            WHERE domain = ?
        ''', (domain,))
        row = cursor.fetchone()
        
        if not row:
            return True
        
        last_visited, delay = row
        elapsed = time.time() - (last_visited if isinstance(last_visited, float) else time.mktime(last_visited.timetuple()))
        return elapsed > delay
    
    def search(self, query, limit=50):
        cursor = self.conn.cursor()
        words = [word.lower() for word in re.findall(r'\w+', query) if len(word) > 2]
        
        if not words:
            return []
        
        placeholders = ', '.join(['?'] * len(words))
        sql = f'''
            SELECT p.url, p.title, SUM(ii.frequency) AS total_freq
            FROM inverted_index ii
            JOIN pages p ON ii.page_id = p.id
            WHERE ii.word IN ({placeholders})
            GROUP BY p.id
            ORDER BY total_freq DESC
            LIMIT ?
        '''
        
        cursor.execute(sql, (*words, limit))
        return cursor.fetchall()
    
    def get_stats(self):
        cursor = self.conn.cursor()
        cursor.execute('SELECT COUNT(*) FROM pages')
        page_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(DISTINCT word) FROM inverted_index')
        word_count = cursor.fetchone()[0]
        cursor.execute('SELECT COUNT(DISTINCT domain) FROM pages')
        domain_count = cursor.fetchone()[0]
        return {
            'pages': page_count,
            'words': word_count,
            'domains': domain_count
        }
    
    def should_dynamic_search(self, query):
        cursor = self.conn.cursor()
        cursor.execute('''
            SELECT last_searched 
            FROM dynamic_searches 
            WHERE query = ?
        ''', (query,))
        row = cursor.fetchone()
        
        if not row:
            return True
        
        last_searched = row[0]
        elapsed = time.time() - (last_searched if isinstance(last_searched, float) else time.mktime(last_searched.timetuple()))
        return elapsed > 86400  # 24 horas
    
    def record_dynamic_search(self, query):
        cursor = self.conn.cursor()
        cursor.execute('''
            INSERT OR REPLACE INTO dynamic_searches (query, last_searched)
            VALUES (?, CURRENT_TIMESTAMP)
        ''', (query,))
        self.conn.commit()

# ========================================
# Crawler mejorado para gran escala
# ========================================
class AdvancedWebCrawler(scrapy.Spider):
    name = "advanced_search_crawler"
    custom_settings = {
        'DEPTH_LIMIT': 3,
        'CONCURRENT_REQUESTS': 100,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 10,
        'REACTOR_THREADPOOL_MAXSIZE': 40,
        'USER_AGENT': 'Mozilla/5.0 (compatible; TFG-SearchEngine/3.0; +http://tfg.example.com)',
        'ROBOTSTXT_OBEY': True,
        'AUTOTHROTTLE_ENABLED': True,
        'AUTOTHROTTLE_START_DELAY': 1,
        'AUTOTHROTTLE_MAX_DELAY': 5,
        'HTTPCACHE_ENABLED': True,
        'RETRY_ENABLED': True,
        'RETRY_TIMES': 2,
        'DOWNLOAD_TIMEOUT': 15,
        'LOG_LEVEL': 'INFO'
    }
    
    def __init__(self, start_urls, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls
        self.db = db
        self.visited = set()
        self.indexed_pages = 0
        self.max_pages = 100000
        self.min_content_length = 500
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0'
        ]
    
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, meta={'depth': 0})
    
    def parse(self, response):
        if self.indexed_pages >= self.max_pages:
            return
            
        url = response.url
        if url in self.visited:
            return
            
        self.visited.add(url)
        domain = urlparse(url).netloc
        
        if not self.db.should_crawl_domain(domain):
            self.logger.info(f"Skipping {url} (domain delay active)")
            return
        
        # Procesar contenido
        title = response.css('title::text').get(default='Sin título').strip()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
            element.decompose()
        
        content = soup.get_text()
        content = re.sub(r'\s+', ' ', content).strip()
        
        if len(content) < self.min_content_length:
            self.logger.info(f"Skipping {url} (content too short: {len(content)} chars)")
            return
        
        page_id = self.db.insert_page(url, domain, title, content[:50000])
        
        words = re.findall(r'\w+', content.lower())
        word_freq = defaultdict(int)
        for word in words:
            if 3 <= len(word) <= 50:
                word_freq[word] += 1
                
        for word, freq in word_freq.items():
            self.db.insert_inverted_index(word, page_id, freq)
        
        self.db.update_domain(domain)
        self.indexed_pages += 1
        
        if self.indexed_pages % 100 == 0:
            stats = self.db.get_stats()
            self.logger.info(f"Indexed: {self.indexed_pages} pages | {stats['words']} words | {stats['domains']} domains")
        
        if response.meta.get('depth', 0) < 3 and self.indexed_pages < self.max_pages:
            for link in response.css('a::attr(href)').getall():
                absolute_url = response.urljoin(link)
                parsed = urlparse(absolute_url)
                
                if (
                    absolute_url.startswith(('http://', 'https://')) and
                    not parsed.fragment and
                    not any(ext in parsed.path.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.zip', '.exe', '.mp3', '.mp4']) and
                    len(absolute_url) < 250
                ):
                    headers = {'User-Agent': random.choice(self.user_agents)}
                    yield scrapy.Request(
                        absolute_url, 
                        callback=self.parse, 
                        headers=headers,
                        meta={'depth': response.meta['depth'] + 1}
                    )

# ========================================
# Módulo de búsqueda dinámica con DuckDuckGo
# ========================================
class DynamicSearch:
    def __init__(self, db):
        self.db = db
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'en-US,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    def duckduckgo_search(self, query, num_results=10):
        """Busca en DuckDuckGo y devuelve URLs de resultados"""
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            response = requests.get(search_url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            for result in soup.select('.result__url'):
                url = result.get('href')
                if url and url.startswith('http'):
                    # DuckDuckGo usa redirecciones, extraemos la URL real
                    if url.startswith('//duckduckgo.com/l/?uddg='):
                        url = self.extract_real_url(url)
                    results.append(url)
                    if len(results) >= num_results:
                        break
            
            return results[:num_results]
        except Exception as e:
            print(f"Error en DuckDuckGo: {e}")
            return []
    
    def extract_real_url(self, ddg_url):
        """Extrae la URL real de la redirección de DuckDuckGo"""
        from urllib.parse import unquote, urlparse, parse_qs
        try:
            parsed = urlparse(ddg_url)
            query = parse_qs(parsed.query)
            if 'uddg' in query:
                return unquote(query['uddg'][0])
            return ddg_url
        except:
            return ddg_url
    
    def quick_index(self, urls):
        """Indexa rápidamente las URLs encontradas"""
        for url in urls:
            try:
                response = requests.get(url, headers=self.headers, timeout=10)
                domain = urlparse(url).netloc
                
                if not self.db.should_crawl_domain(domain):
                    continue
                
                # Procesamiento rápido de contenido
                soup = BeautifulSoup(response.text, 'html.parser')
                title = soup.title.string.strip() if soup.title else 'Sin título'
                
                for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
                    element.decompose()
                
                content = soup.get_text()
                content = re.sub(r'\s+', ' ', content).strip()[:10000]  # Limitar contenido
                
                if len(content) < 300:
                    continue
                
                page_id = self.db.insert_page(url, domain, title, content)
                
                words = re.findall(r'\w+', content.lower())
                word_freq = defaultdict(int)
                for word in words:
                    if 3 <= len(word) <= 50:
                        word_freq[word] += 1
                
                for word, freq in word_freq.items():
                    self.db.insert_inverted_index(word, page_id, freq)
                
                self.db.update_domain(domain)
                print(f"Quick indexed: {url}")
                
            except Exception as e:
                print(f"Error indexing {url}: {e}")

# ========================================
# Interfaz Web mejorada con búsqueda dinámica
# ========================================
app = Flask(__name__)
db = SearchEngineDB()
dynamic_searcher = DynamicSearch(db)
crawler_thread = None

@app.route('/')
def index():
    stats = db.get_stats()
    return render_template('search.html', stats=stats)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    results = db.search(query)
    stats = db.get_stats()
    
    # Comprobar si necesitamos búsqueda dinámica
    if not results and db.should_dynamic_search(query):
        db.record_dynamic_search(query)
        
        # Iniciar búsqueda dinámica en segundo plano
        threading.Thread(target=dynamic_search_task, args=(query,)).start()
        
        return render_template('dynamic_search.html', query=query)
    
    return render_template('results.html', query=query, results=results, stats=stats)

@app.route('/dynamic_search_status')
def dynamic_search_status():
    query = request.args.get('q', '')
    return render_template('dynamic_search_progress.html', query=query)

def dynamic_search_task(query):
    """Tarea en segundo plano para búsqueda dinámica"""
    print(f"Iniciando búsqueda dinámica para: {query}")
    urls = dynamic_searcher.duckduckgo_search(query)
    print(f"Encontradas {len(urls)} URLs para: {query}")
    
    if urls:
        dynamic_searcher.quick_index(urls)
        print(f"Indexación rápida completada para: {query}")
    else:
        print(f"No se encontraron resultados en DuckDuckGo para: {query}")

def run_crawler():
    time.sleep(2)
    print("\n🚀 Iniciando crawler avanzado...")
    
    # Lista ampliada de URLs semilla
    start_urls = [
        "https://www.nytimes.com", "https://www.bbc.com", "https://www.theguardian.com",
        "https://www.reuters.com", "https://apnews.com", "https://www.cnn.com",
        "https://www.washingtonpost.com", "https://www.nbcnews.com", "https://www.aljazeera.com",
        "https://techcrunch.com", "https://www.wired.com", "https://www.theverge.com",
        "https://arstechnica.com", "https://www.cnet.com", "https://www.engadget.com",
        "https://www.gsmarena.com", "https://www.tomsguide.com", "https://www.digitaltrends.com",
        "https://www.wikipedia.org", "https://www.khanacademy.org", "https://www.coursera.org",
        "https://www.edx.org", "https://www.ted.com", "https://www.udemy.com",
        "https://www.nature.com", "https://www.sciencemag.org", "https://www.sciencedaily.com",
        "https://www.space.com", "https://www.nationalgeographic.com", "https://www.livescience.com",
        "https://stackoverflow.com", "https://github.com", "https://gitlab.com",
        "https://developer.mozilla.org", "https://www.w3schools.com", "https://dev.to",
        "https://css-tricks.com", "https://www.freecodecamp.org", "https://leetcode.com",
        "https://www.reddit.com", "https://www.quora.com", "https://www.imdb.com",
        "https://www.amazon.com", "https://www.ebay.com", "https://www.etsy.com",
        "https://www.booking.com", "https://www.tripadvisor.com", "https://www.yelp.com",
        "https://www.healthline.com", "https://www.webmd.com", "https://www.mayoclinic.org",
        "https://www.elpais.com", "https://www.elmundo.es", "https://www.abc.es",
        "https://www.lavanguardia.com", "https://www.elperiodico.com", "https://www.20minutos.es",
        "https://www.marca.com", "https://www.as.com", "https://www.xataka.com",
        "https://www.genbeta.com", "https://www.hipertextual.com"
    ]
    
    # Añadir categorías de Wikipedia
    for category in ['Science', 'Technology', 'History', 'Art', 'Mathematics', 'Geography']:
        start_urls.append(f"https://en.wikipedia.org/wiki/Category:{category}")
        start_urls.append(f"https://es.wikipedia.org/wiki/Categoría:{category}")
    
    print(f"🌐 Iniciando con {len(start_urls)} URLs semilla")
    print("⏳ Esto tomará tiempo... Puedes usar la interfaz web mientras se indexa")
    
    process = CrawlerProcess(get_project_settings())
    process.crawl(AdvancedWebCrawler, start_urls=start_urls, db=db)
    process.start()

# ========================================
# Inicio de la aplicación
# ========================================
if __name__ == '__main__':
    crawler_thread = threading.Thread(target=run_crawler, daemon=True)
    crawler_thread.start()
    app.run(port=5000, debug=True, use_reloader=False)