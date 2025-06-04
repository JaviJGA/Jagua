import requests
from bs4 import BeautifulSoup
from urllib.parse import urlparse, quote, unquote, parse_qs
import time
import random
import re
from collections import defaultdict
from database.search_engine_db import SearchEngineDB

# DynamicSearch: Clase para realizar búsquedas dinámicas en DuckDuckGo y extraer enlaces de páginas web.
# no tenemos el dinero para hacer scraping de Google, así que usamos DuckDuckGo. (soy pobre)
class DynamicSearch:
    def __init__(self, db):
        self.db = db
        self.headers = {
            'User-Agent': 'Mozilla/5.0 (Windows NT 10.0; Win64; x64) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
            'Accept': 'text/html,application/xhtml+xml,application/xml;q=0.9,image/webp,*/*;q=0.8',
            'Accept-Language': 'es-ES,en;q=0.5',
            'DNT': '1',
            'Connection': 'keep-alive',
            'Upgrade-Insecure-Requests': '1'
        }
    
    # duckduckgo_search: Realiza una búsqueda en DuckDuckGo y devuelve los enlaces de los resultados.
    # Parámetros:
    # - query: La consulta de búsqueda.
    # - num_results: Número máximo de resultados a devolver (por defecto 15).
    # Devuelve una lista de URLs encontradas o una lista vacía si ocurre un error.
    # Si no se encuentran resultados, devuelve una lista vacía.
    def duckduckgo_search(self, query, num_results=15):
        try:
            search_url = f"https://html.duckduckgo.com/html/?q={quote(query)}"
            response = requests.get(search_url, headers=self.headers)
            soup = BeautifulSoup(response.text, 'html.parser')
            
            results = []
            for result in soup.select('.result__url'):
                url = result.get('href')
                if url and url.startswith('http'):
                    if url.startswith('//duckduckgo.com/l/?uddg='):
                        url = self.extract_real_url(url)
                    results.append(url)
                    if len(results) >= num_results:
                        break
            return results[:num_results]
        except Exception as e:
            print(f"Error en DuckDuckGo: {e}")
            return []
    
    # extract_real_url: Extrae la URL real de un enlace de DuckDuckGo.
    # Parámetros:
    # - ddg_url: La URL de DuckDuckGo que contiene el enlace real.
    # Devuelve la URL real extraída o la URL original si no se puede extraer.
    # Si ocurre un error, devuelve la URL original.
    def extract_real_url(self, ddg_url):
        try:
            parsed = urlparse(ddg_url)
            query = parse_qs(parsed.query)
            if 'uddg' in query:
                return unquote(query['uddg'][0])
            return ddg_url
        except:
            return ddg_url
    
    # quick_index: Indexa una página web dada su URL y extrae enlaces relacionados.
    # Parámetros:
    # - url: La URL de la página a indexar.
    # - extract_links: Si es True, extrae enlaces relacionados de la página (por defecto True).
    # Devuelve una lista de enlaces relacionados o una lista vacía si ocurre un error.
    # Si la página no tiene contenido suficiente, también devuelve una lista vacía.
    def quick_index(self, url, extract_links=True):
        try:
            response = None
            for attempt in range(3):
                try:
                    response = requests.get(url, headers=self.headers, timeout=10)
                    break
                except Exception as e:
                    if attempt < 2:
                        time.sleep(1)
                        continue
                    raise e
            
            domain = urlparse(url).netloc
            
            if not self.db.should_crawl_domain(domain):
                return []
                
            soup = BeautifulSoup(response.text, 'html.parser')
            title = soup.title.string.strip() if soup.title else 'Sin título'
            
            for element in soup(['script', 'style', 'header', 'footer', 'nav', 'aside']):
                element.decompose()
            
            content = soup.get_text()
            content = re.sub(r'\s+', ' ', content).strip()[:10000]
            
            if len(content) < 300:
                return []
                
            page_id = None
            for attempt in range(3):
                page_id = self.db.insert_page(url, domain, title, content)
                if page_id is not None:
                    break
                time.sleep(0.5)
                
            if page_id is None:
                return []
                
            words = re.findall(r'\w+', content.lower())
            word_freq = defaultdict(int)
            for word in words:
                if 3 <= len(word) <= 50:
                    normalized = self.db.normalize_word(word)
                    if normalized:
                        word_freq[normalized] += 1
            
            # esto no me acuerdo que era, pero lo dejé por si acaso
            # ah ya me acuerdo, era para evitar que se indexen palabras muy comunes
            for word, freq in word_freq.items():
                inserted = False
                for attempt in range(3):
                    try:
                        self.db.insert_inverted_index(word, page_id, freq)
                        inserted = True
                        break
                    except:
                        time.sleep(0.2 * (attempt + 1))
                if not inserted:
                    print(f"Failed to insert word: {word} for page: {url}")
            
            for attempt in range(3):
                try:
                    self.db.update_domain(domain)
                    break
                except:
                    time.sleep(0.3)
            
            # esto era para evitar pdf, imágenes y otros archivos pesados
            related_links = []
            if extract_links:
                for link in soup.find_all('a', href=True):
                    href = link.get('href')
                    if href and href.startswith(('http://', 'https://')):
                        parsed = urlparse(href)
                        if (
                            not parsed.fragment and
                            not any(ext in parsed.path.lower() for ext in ['.pdf', '.jpg', '.png', '.gif', '.zip', '.exe', '.mp3', '.mp4']) and
                            len(href) < 250
                        ):
                            related_links.append(href)
                
                if len(related_links) > 5:
                    related_links = random.sample(related_links, 5)
            
            return related_links
        
        # Si ocurre un error al indexar la página, se captura la excepción y se imprime un mensaje.
        except Exception as e:
            print(f"Error indexando {url}: {e}")
            return []