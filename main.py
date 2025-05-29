#celar
import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
import sqlite3
import re
import unicodedata
from flask import Flask, request, render_template, jsonify, redirect
from collections import defaultdict
import threading
import time
import random
from urllib.parse import urlparse, quote
from bs4 import BeautifulSoup
import requests
from datetime import datetime, timedelta

# ========================================
# Base de datos mejorada con manejo de concurrencia
# ========================================
class SearchEngineDB:
    def __init__(self, db_name='search_engine.db'):
        self.db_name = db_name
        self._initialize_db()
        
    def _initialize_db(self):
        conn = self._get_connection()
        try:
            self._create_tables(conn)
            self._create_indexes(conn)
        finally:
            conn.close()
    
    def _get_connection(self):
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 5000")
        return conn
    
    def _create_tables(self, conn):
        cursor = conn.cursor()
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
        conn.commit()
    
    def _create_indexes(self, conn):
        cursor = conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_word ON inverted_index(word)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_domain ON pages(domain)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_query ON dynamic_searches(query)')
        conn.commit()
    
    def insert_page(self, url, domain, title, content):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO pages (url, domain, title, content)
                VALUES (?, ?, ?, ?)
            ''', (url, domain, title, content))
            conn.commit()
            return cursor.lastrowid
        except sqlite3.Error as e:
            print(f"Error inserting page: {e}")
            return None
        finally:
            conn.close()
    
    def insert_inverted_index(self, word, page_id, frequency):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO inverted_index (word, page_id, frequency)
                VALUES (?, ?, ?)
            ''', (word, page_id, frequency))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error inserting inverted index: {e}")
        finally:
            conn.close()
    
    def update_domain(self, domain):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO domains (domain, last_visited)
                VALUES (?, CURRENT_TIMESTAMP)
            ''', (domain,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error updating domain: {e}")
        finally:
            conn.close()
    
    def should_crawl_domain(self, domain):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT last_visited, delay 
                FROM domains 
                WHERE domain = ?
            ''', (domain,))
            row = cursor.fetchone()
            
            if not row:
                return True
            
            last_visited, delay = row
            
            if last_visited is None:
                return True
            
            try:
                dt = datetime.strptime(last_visited, "%Y-%m-%d %H:%M:%S")
                elapsed = time.time() - dt.timestamp()
            except Exception:
                return True
            
            return elapsed > delay
        finally:
            conn.close()
    
    def normalize_word(self, word):
        """Normaliza palabras removiendo acentos y caracteres especiales"""
        # Convertir a minúsculas y remover caracteres no alfabéticos
        word = re.sub(r'[^a-záéíóúüñ]', '', word.lower())
        # Remover acentos
        word = ''.join(c for c in unicodedata.normalize('NFD', word)
                     if unicodedata.category(c) != 'Mn')
        return word
    
    def search(self, query, limit=50):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            # Normalizar y filtrar palabras
            words = [self.normalize_word(word) 
                     for word in re.findall(r'\w+', query) 
                     if len(word) > 2]
            
            if not words:
                return []
            
            # MEJORA: Priorizar páginas con TODAS las palabras
            placeholders = ', '.join(['?'] * len(words))
            
            # Consulta mejorada para priorizar relevancia
            sql = f'''
                SELECT 
                    p.url, 
                    p.title,
                    SUM(ii.frequency) AS total_freq,
                    COUNT(DISTINCT ii.word) AS words_found
                FROM inverted_index ii
                JOIN pages p ON ii.page_id = p.id
                WHERE ii.word IN ({placeholders})
                GROUP BY p.id
                ORDER BY 
                    words_found DESC,  -- Priorizar páginas con más palabras coincidentes
                    total_freq DESC    -- Luego por frecuencia total
                LIMIT ?
            '''
            
            cursor.execute(sql, (*words, limit))
            results = cursor.fetchall()
            
            # MEJORA: Filtrar resultados irrelevantes
            min_words = max(1, len(words) // 2)  # Requerir al menos la mitad de las palabras
            filtered_results = [res for res in results if res[3] >= min_words]
            
            return [(res[0], res[1], res[2]) for res in filtered_results]  # Excluir words_found
        except sqlite3.Error as e:
            print(f"Error en búsqueda: {e}")
            return []
        finally:
            conn.close()
    
    def get_stats(self):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
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
        finally:
            conn.close()

    def should_dynamic_search(self, query):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                SELECT last_searched 
                FROM dynamic_searches 
                WHERE query = ?
            ''', (query,))
            row = cursor.fetchone()
            
            if not row:
                return True

            last_searched_str = row[0]

            try:
                dt = datetime.strptime(last_searched_str, '%Y-%m-%d %H:%M:%S')
                timestamp = dt.timestamp()
            except Exception:
                return True

            elapsed = time.time() - timestamp
            return elapsed > 86400
        finally:
            conn.close()

    def record_dynamic_search(self, query):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            cursor.execute('''
                INSERT OR REPLACE INTO dynamic_searches (query, last_searched)
                VALUES (?, CURRENT_TIMESTAMP)
            ''', (query,))
            conn.commit()
        except sqlite3.Error as e:
            print(f"Error recording dynamic search: {e}")
        finally:
            conn.close()

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
        'USER_AGENT': 'Mozilla/5.0 (compatible; Jaguar-SearchEngineTFG/3.0; +http://tfgjaguar.com)', #dominio inventado
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
            'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'EOS-SDK/1.17.22-40344262+Switch_13.3.0 (Switch/13.3.0.0) Rocket League/250411.64129.481382' #porque no?
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
        if page_id is None:
            self.logger.error(f"Failed to insert page: {url}")
            return
        
        words = re.findall(r'\w+', content.lower())
        word_freq = defaultdict(int)
        for word in words:
            if 3 <= len(word) <= 50:
                # Normalizar palabra antes de indexar
                normalized = self.db.normalize_word(word)
                if normalized:
                    word_freq[normalized] += 1
                
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
    
    def quick_index(self, url, task_id=None):
        """Indexa rápidamente una URL con seguimiento de progreso"""
        try:
            response = requests.get(url, headers=self.headers, timeout=10)
            domain = urlparse(url).netloc
            
            if not self.db.should_crawl_domain(domain):
                return False
                
            # Procesamiento rápido de contenido
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else 'Sin título'
            
            for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
                element.decompose()
            
            content = soup.get_text()
            content = re.sub(r'\s+', ' ', content).strip()[:10000]  # Limitar contenido
            
            if len(content) < 300:
                return False
                
            page_id = self.db.insert_page(url, domain, title, content)
            if page_id is None:
                return False
                
            words = re.findall(r'\w+', content.lower())
            word_freq = defaultdict(int)
            for word in words:
                if 3 <= len(word) <= 50:
                    # Normalizar palabra antes de indexar
                    normalized = self.db.normalize_word(word)
                    if normalized:
                        word_freq[normalized] += 1
            
            for word, freq in word_freq.items():
                self.db.insert_inverted_index(word, page_id, freq)
            
            self.db.update_domain(domain)
            print(f"Quick indexed: {url}")
            return True
            
        except Exception as e:
            print(f"Error indexing {url}: {e}")
            return False

# ========================================
# Interfaz Web mejorada con búsqueda dinámica
# ========================================
app = Flask(__name__)
db = SearchEngineDB()
dynamic_searcher = DynamicSearch(db)
crawler_thread = None

# Almacenamiento de estado de tareas dinámicas
dynamic_tasks = {}

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

@app.route('/dynamic_search_progress')
def dynamic_search_progress():
    task_id = request.args.get('task_id', '')
    task = dynamic_tasks.get(task_id, {})
    query = task.get('query', 'Búsqueda')
    return render_template('dynamic_search_progress.html', query=query, task_id=task_id)

# Nueva ruta para forzar búsqueda dinámica
@app.route('/force_dynamic_search')
def force_dynamic_search():
    query = request.args.get('q', '')
    # Registrar la búsqueda dinámica sin importar el tiempo transcurrido
    db.record_dynamic_search(query)
    
    # Crear un ID único para esta tarea
    task_id = str(time.time()) + "-" + query[:10]
    dynamic_tasks[task_id] = {
        'query': query,
        'status': 'searching',
        'progress': 0,
        'urls_found': 0,
        'urls_indexed': 0,
        'start_time': time.time()
    }
    
    # Iniciar búsqueda dinámica en segundo plano
    threading.Thread(target=dynamic_search_task, args=(query, task_id)).start()
    
    # Redirigir a la página de progreso
    return redirect(f'/dynamic_search_progress?task_id={task_id}')

# Ruta para obtener el estado de la tarea
@app.route('/get_task_status')
def get_task_status():
    task_id = request.args.get('task_id')
    task = dynamic_tasks.get(task_id, {})
    return jsonify(task)

def dynamic_search_task(query, task_id=None):
    """Tarea en segundo plano para búsqueda dinámica con seguimiento de progreso"""
    task = dynamic_tasks.get(task_id) if task_id else {}
    
    if task:
        task['status'] = 'searching'
        task['message'] = 'Buscando en DuckDuckGo...'
        task['progress'] = 5
    
    print(f"Iniciando búsqueda dinámica para: {query}")
    urls = dynamic_searcher.duckduckgo_search(query)
    
    if task:
        task['urls_found'] = len(urls)
        task['status'] = 'indexing'
        task['message'] = f'Encontradas {len(urls)} URLs. Indexando...'
        task['progress'] = 10
    
    print(f"Encontradas {len(urls)} URLs para: {query}")
    
    if urls:
        # Actualizar estado
        if task:
            task['total_urls'] = len(urls)
        
        # Indexar cada URL con seguimiento de progreso
        for i, url in enumerate(urls):
            if task:
                # Actualizar progreso
                progress = 10 + int((i / len(urls)) * 90)
                task['progress'] = progress
                task['current_url'] = url
                task['urls_indexed'] = i
                task['message'] = f'Indexando {i+1}/{len(urls)}: {url[:50]}...'
            
            # Indexar la URL
            success = dynamic_searcher.quick_index(url, task_id)
            
            if task and success:
                # Actualizar contador
                task['urls_indexed'] = i + 1
        
        if task:
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = '¡Indexación completada!'
            # Mantener el resultado por 5 minutos antes de limpiar
            threading.Timer(300, lambda: dynamic_tasks.pop(task_id, None)).start()
        
        print(f"Indexación rápida completada para: {query}")
    else:
        if task:
            task['status'] = 'completed'
            task['progress'] = 100
            task['message'] = 'No se encontraron resultados en DuckDuckGo.'
            threading.Timer(300, lambda: dynamic_tasks.pop(task_id, None)).start()
        
        print(f"No se encontraron resultados en DuckDuckGo para: {query}")

def run_crawler():
    time.sleep(2)
    print("\n🚀 Iniciando crawler avanzado...")
    
    # Lista de URLs semilla por categorías
    categories = {
        'Science': 'Ciencia',
        'Technology': 'Tecnología',
        'History': 'Historia',
        'Art': 'Arte',
        'Mathematics': 'Matemáticas',
        'Geography': 'Geografía'
    }

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
    for en_cat, es_cat in categories.items():
        start_urls.append(f"https://en.wikipedia.org/wiki/Category:{en_cat}")
        start_urls.append(f"https://es.wikipedia.org/wiki/Categoría:{es_cat}")
    
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