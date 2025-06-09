import scrapy
from scrapy.crawler import CrawlerProcess
from scrapy.utils.project import get_project_settings
from urllib.parse import urlparse
import re
import random
import time
from bs4 import BeautifulSoup
from collections import defaultdict
from database.search_engine_db import SearchEngineDB

# esto hace que el crawler sea más avanzado y eficiente, con un enfoque en la indexación de contenido relevante y la gestión de dominios.
# Utiliza Scrapy para rastrear y extraer información de páginas web, optimizando el proceso de indexación y evitando contenido irrelevante.
# Además, implementa un sistema de gestión de dominios para controlar la frecuencia de rastreo y evitar sobrecargas en los servidores.
# No queremos que digitaldot se caiga un viernes por la tarde de nuevo jeje (perdón) 
# jeje pues se cayó un jueves por la mañana y por una ip de metaenlace (nomearrepientodenada)

class AdvancedWebCrawler(scrapy.Spider):
    # nombre del crawler, debe ser único
    name = "advanced_search_crawler"

    # es lo que dice el nombre, son las configuraciones del crawler
    # se puede cambiar el depth limit, el número de peticiones concurrentes, el user agent, etc.
    # también se puede cambiar el delay entre peticiones, el timeout, etc.
    # cuantas veces voy a poner etc?
    custom_settings = {
        'DEPTH_LIMIT': 20, # limita la profundidad del rastreo a 3 niveles
        'CONCURRENT_REQUESTS': 100, # número máximo de peticiones concurrentes
        'CONCURRENT_REQUESTS_PER_DOMAIN': 10, # número máximo de peticiones concurrentes por dominio
        'REACTOR_THREADPOOL_MAXSIZE': 40,
        'USER_AGENT': 'Mozilla/5.0 (compatible; JAGUARCRAWLERDONTBLOCKPLEASE/3.0; +http://tfgjaguar.com)', #dominio de ejemplo, no es real, no hay dinero xd
        'ROBOTSTXT_OBEY': True, # importante para respetar las reglas de los robots.txt
        'AUTOTHROTTLE_ENABLED': True, # habilita el autothrottle para ajustar la velocidad de rastreo
        'AUTOTHROTTLE_START_DELAY': 2, # tiempo de espera inicial entre peticiones
        'AUTOTHROTTLE_MAX_DELAY': 8, # máximo retraso entre peticiones
        'AUTOTHROTTLE_TARGET_CONCURRENCY': 1.5, # ajusta la concurrencia objetivo
        'HTTPCACHE_ENABLED': True, # habilita la caché HTTP para evitar peticiones repetidas
        'RETRY_ENABLED': True, # habilita el reintento de peticiones fallidas
        'RETRY_TIMES': 3, # número de reintentos en caso de fallo
        'DOWNLOAD_TIMEOUT': 15, # tiempo máximo de espera para descargar una página
        'LOG_LEVEL': 'INFO' # nivel de registro, puede ser DEBUG, INFO, WARNING, ERROR o CRITICAL
    }
    
    # lo de abajo es el constructor de la clase, se ejecuta al iniciar el crawler
    # aquí se inicializan las variables del crawler, como las URLs de inicio, la base de datos, etc.
    # o si no como hacemos que se inicialicen las cosas lol
    def __init__(self, start_urls, db, *args, **kwargs):
        super().__init__(*args, **kwargs)
        self.start_urls = start_urls
        self.db = db
        self.visited = set()
        self.indexed_pages = 0
        self.max_pages = 100000
        self.min_content_length = 500
        # los user agents 🔥 importante poner varios para evitar bloqueos
        self.user_agents = [
            'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/605.1.15 (KHTML, like Gecko) Version/14.1.1 Safari/605.1.15',
            'Mozilla/5.0 (X11; Linux x86_64; rv:89.0) Gecko/20100101 Firefox/89.0',
            'EOS-SDK/1.17.22-40344262+Switch_13.3.0 (Switch/13.3.0.0) Rocket League/250411.64129.481382', # por poner una mención a la switch
            'EOS-SDK/1.16.2710-29084362+Switch_16.2.0 (Switch/16.2.0.0) Fortnite/++Fortnite+Release-27.10-CL-29552510',
            'Mozilla/5.0 (Nintendo Switch; WifiWebAuthApplet) AppleWebKit/601.6 (KHTML, like Gecko) NF/4.0.0.8.9 NintendoBrowser/5.1.0.16739',
            'Mozilla/5.0 (Nintendo 3DS; U; Factory Media Production; en) Version/1.7498.US',
            'Mozilla/4.0 (PSP (PlayStation Portable); 2.00)',
            'Mozilla/5.0 (PlayStation Vita 3.75) AppleWebKit/537.73 (KHTML, like Gecko) Silk/3.2 WebOne/0.11.2.0',
        ]
    
    # este método se llama al iniciar el crawler, es donde se definen las URLs de inicio
    # y se envían las primeras peticiones al servidor
    def start_requests(self):
        for url in self.start_urls:
            yield scrapy.Request(url, callback=self.parse, meta={'depth': 0})
    
    # este método se llama para procesar la respuesta de cada petición
    # aquí es donde se extrae el contenido de la página, se limpia, se normaliza y se indexa
    def parse(self, response):
        if self.indexed_pages >= self.max_pages:
            return
            
        url = response.url
        if url in self.visited:
            return
            
        self.visited.add(url)
        domain = urlparse(url).netloc
        
        # comprobamos si el dominio ya ha sido rastreado recientemente
        if not self.db.should_crawl_domain(domain):
            self.logger.info(f"Skipping {url} (domain delay active)")
            return
        
        # extraemos el título de la página y limpiamos el contenido
        title = response.css('title::text').get(default='Sin título').strip()
        soup = BeautifulSoup(response.text, 'html.parser')
        
        for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
            element.decompose()
        
        content = soup.get_text()
        content = re.sub(r'\s+', ' ', content).strip()
        
        # normalizamos el contenido, eliminamos caracteres especiales y convertimos a minúsculas
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

def run_crawler(db):
    time.sleep(2) #muy pro esto, nivel belda
    print("\n Crawler encendiendose... 🚀\n")
    
    # esto es para wikipedia
    categories = {
        'Science': 'Ciencia',
        'Technology': 'Tecnología',
        'History': 'Historia',
        'Art': 'Arte',
        'Mathematics': 'Matemáticas',
        'Geography': 'Geografía',
        'Philosophy': 'Filosofía',
        'Politics': 'Política',
        'Economics': 'Economía',
        'Literature': 'Literatura',
        'Music': 'Música',
        'Architecture': 'Arquitectura',
        'Biology': 'Biología',
        'Chemistry': 'Química',
        'Physics': 'Física',
        'Astronomy': 'Astronomía',
        'Medicine': 'Medicina',
        'Education': 'Educación',
        'Engineering': 'Ingeniería',
        'Religion': 'Religión',
        'Linguistics': 'Lingüística',
        'Psychology': 'Psicología',
        'Sociology': 'Sociología',
        'Anthropology': 'Antropología',
        'Law': 'Derecho',
        'Cinema': 'Cine',
        'Theatre': 'Teatro',
        'Sports': 'Deportes',
        'Cuisine': 'Gastronomía',
        'Transportation': 'Transporte',
        'Environment': 'Medio ambiente',
        'Military': 'Militar',
        'Computing': 'Informática',
        'Mythology': 'Mitología'
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
        "https://www.genbeta.com", "https://www.hipertextual.com", "https://www.w3schools.com",
        "https://www.tutorialspoint.com", "https://www.geeksforgeeks.org", "https://www.javatpoint.com", "https://www.programiz.com",
        "https://www.freecodecamp.org", "https://www.codecademy.com", "https://www.udacity.com", "https://www.digitaldot.es/"
    ]
    # lo que decía de antes, se usan las categorías y por cada categoría se añaden las URLs de Wikipedia en inglés y español
    # esto es para que el crawler pueda indexar contenido relevante de Wikipedia en ambos idiomas (bilingüe)
    for en_cat, es_cat in categories.items():
        start_urls.append(f"https://en.wikipedia.org/wiki/Category:{en_cat}")
        start_urls.append(f"https://es.wikipedia.org/wiki/Categoría:{es_cat}")
    
    print(f"Iniciando con {len(start_urls)} URLs semilla")
    print("Esto tomará tiempo... Puedes usar la interfaz web mientras se indexa")
    
    process = CrawlerProcess(get_project_settings())
    process.crawl(AdvancedWebCrawler, start_urls=start_urls, db=db)
    process.start()