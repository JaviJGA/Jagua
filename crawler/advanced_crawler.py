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

class AdvancedWebCrawler(scrapy.Spider):
    name = "advanced_search_crawler"
    custom_settings = {
        'DEPTH_LIMIT': 3,
        'CONCURRENT_REQUESTS': 100,
        'CONCURRENT_REQUESTS_PER_DOMAIN': 10,
        'REACTOR_THREADPOOL_MAXSIZE': 40,
        'USER_AGENT': 'Mozilla/5.0 (compatible; Jaguar-SearchEngineTFG/3.0; +http://tfgjaguar.com)',
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
            'EOS-SDK/1.17.22-40344262+Switch_13.3.0 (Switch/13.3.0.0) Rocket League/250411.64129.481382'
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
    time.sleep(2)
    print("\n🚀 Iniciando crawler avanzado...")
    
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
        "https://www.genbeta.com", "https://www.hipertextual.com", "https://www.w3schools.com",
        "https://www.tutorialspoint.com", "https://www.geeksforgeeks.org", "https://www.javatpoint.com", "https://www.programiz.com",
        "https://www.freecodecamp.org", "https://www.codecademy.com", "https://www.udacity.com",
    ]
    for en_cat, es_cat in categories.items():
        start_urls.append(f"https://en.wikipedia.org/wiki/Category:{en_cat}")
        start_urls.append(f"https://es.wikipedia.org/wiki/Categoría:{es_cat}")
    
    print(f"🌐 Iniciando con {len(start_urls)} URLs semilla")
    print("⏳ Esto tomará tiempo... Puedes usar la interfaz web mientras se indexa")
    
    process = CrawlerProcess(get_project_settings())
    process.crawl(AdvancedWebCrawler, start_urls=start_urls, db=db)
    process.start()