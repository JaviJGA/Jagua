import sqlite3
import re
import unicodedata
import time
from datetime import datetime
import threading

# esto sirve para crear una base de datos SQLite para el motor de búsqueda.
# la base de datos almacena páginas web, un índice invertido para las palabras clave,
# dominios visitados y búsquedas dinámicas.
class SearchEngineDB:
    # inicializa la base de datos y crea las tablas necesarias.
    # utiliza un bloqueo para asegurar que las operaciones de escritura sean seguras en un entorno multihilo.
    # si no sabes lo que es multihilo, yo tampoco, lo acabo de aprender.
    # pero básicamente es para que el crawler y la aplicación web puedan funcionar al mismo tiempo sin problemas.
    def __init__(self, db_name='search_engine.db'):
        self.db_name = db_name
        self._initialize_db()
        self.lock = threading.Lock()
        
    # inicializa la base de datos, creando las tablas y los índices necesarios.
    def _initialize_db(self):
        conn = self._get_connection()
        try:
            self._create_tables(conn)
            self._create_indexes(conn)
        finally:
            conn.close()
    
    # obtiene una conexión a la base de datos SQLite.
    def _get_connection(self):
        conn = sqlite3.connect(self.db_name, check_same_thread=False)
        conn.execute("PRAGMA journal_mode=WAL")
        conn.execute("PRAGMA busy_timeout = 10000")
        return conn
    
    # crea las tablas necesarias en la base de datos.
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
    
    # crea índices para mejorar el rendimiento de las consultas en la base de datos.
    def _create_indexes(self, conn):
        cursor = conn.cursor()
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_word ON inverted_index(word)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_domain ON pages(domain)')
        cursor.execute('CREATE INDEX IF NOT EXISTS idx_query ON dynamic_searches(query)')
        conn.commit()
    
    # inserta o actualiza una página en la base de datos.
    def insert_page(self, url, domain, title, content):
        with self.lock:
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
    
    # inserta o actualiza un índice invertido para una palabra clave en una página.
    def insert_inverted_index(self, word, page_id, frequency):
        with self.lock:
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
    
    # actualiza el dominio en la base de datos, registrando la última visita.
    def update_domain(self, domain):
        with self.lock:
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
    
    # verifica si se debe rastrear un dominio, basado en el tiempo transcurrido desde la última visita y el retraso configurado.
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
    
    # normaliza una palabra eliminando caracteres no alfabéticos y convirtiéndola a minúsculas.
    def normalize_word(self, word):
        word = re.sub(r'[^a-záéíóúüñ]', '', word.lower())
        word = ''.join(c for c in unicodedata.normalize('NFD', word)
                     if unicodedata.category(c) != 'Mn')
        return word
    
    # busca páginas en la base de datos que contengan las palabras clave especificadas en la consulta.
    def search(self, query, limit=50):
        conn = self._get_connection()
        try:
            cursor = conn.cursor()
            words = [self.normalize_word(word) 
                     for word in re.findall(r'\w+', query) 
                     if len(word) > 2]
            
            if not words:
                return []
            
            placeholders = ', '.join(['?'] * len(words))
            
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
                    words_found DESC,
                    total_freq DESC
                LIMIT ?
            '''
            
            cursor.execute(sql, (*words, limit))
            results = cursor.fetchall()
            
            min_words = max(1, len(words) // 2)
            filtered_results = [res for res in results if res[3] >= min_words]
            
            return [(res[0], res[1], res[2]) for res in filtered_results]
        except sqlite3.Error as e:
            print(f"Error en búsqueda: {e}")
            return []
        finally:
            conn.close()
    
    # obtiene estadísticas de la base de datos, como el número de páginas, palabras y dominios.
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

    # verifica si una búsqueda dinámica debe realizarse, basada en el tiempo transcurrido desde la última búsqueda.
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

    # registra una búsqueda dinámica, actualizando la última vez que se buscó la consulta.
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