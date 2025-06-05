import requests
import re
import threading
import time
from urllib.parse import urlparse

class SafeSearch:
    def __init__(self, hosts_url):
        self.hosts_url = hosts_url
        self.blocked_domains = set()
        self.lock = threading.Lock()
        self.last_update = 0
        self.update_interval = 86400  # Actualizar cada 24 horas
        self.load_blocked_domains()
        
        # Iniciar hilo para actualizaciones periódicas
        self.update_thread = threading.Thread(target=self.periodic_update, daemon=True)
        self.update_thread.start()
    
    def load_blocked_domains(self):
        try:
            print(f"Descargando lista de dominios bloqueados de {self.hosts_url}")
            response = requests.get(self.hosts_url)
            if response.status_code == 200:
                new_blocked = set()
                for line in response.text.splitlines():
                    if not line.strip() or line.startswith('#'):
                        continue
                    parts = line.split()
                    if len(parts) >= 2:
                        domain = parts[1].strip()
                        clean_domain = self.normalize_domain(domain)
                        if clean_domain:
                            new_blocked.add(clean_domain)
                
                with self.lock:
                    self.blocked_domains = new_blocked
                    self.last_update = time.time()
                    print(f"Lista de dominios bloqueados actualizada. {len(self.blocked_domains)} dominios bloqueados.")
            else:
                print(f"Error al descargar lista bloqueada: Código {response.status_code}")
        except Exception as e:
            print(f"Error al cargar dominios bloqueados: {e}")
    
    def normalize_domain(self, domain):
        # Eliminar cualquier prefijo www
        if domain.startswith('www.'):
            domain = domain[4:]
        # Eliminar cualquier puerto especificado
        if ':' in domain:
            domain = domain.split(':')[0]
        # Validar que sea un dominio válido
        if re.match(r'^[a-z0-9.-]+\.[a-z]{2,}$', domain, re.IGNORECASE):
            return domain.lower()
        return None

    def periodic_update(self):
        while True:
            time.sleep(self.update_interval)
            self.load_blocked_domains()

    def is_domain_blocked(self, url_or_domain):
        try:
            # Si es una URL, extrae el dominio
            if '://' in url_or_domain:
                domain = urlparse(url_or_domain).netloc
            else:
                domain = url_or_domain
            # Elimina posibles credenciales en la URL
            if '@' in domain:
                domain = domain.split('@')[-1]
            clean_domain = self.normalize_domain(domain)
            if not clean_domain:
                return False
            with self.lock:
                # Verifica el dominio completo
                if clean_domain in self.blocked_domains:
                    return True
                # Verifica el dominio base (por ejemplo, example.com de sub.example.com)
                parts = clean_domain.split('.')
                if len(parts) > 2:
                    base_domain = '.'.join(parts[-2:])
                    if base_domain in self.blocked_domains:
                        return True
            return False
        except Exception as e:
            print(f"Error en is_domain_blocked: {e}")
            return False
    
    def filter_results(self, results):
        safe_results = []
        for result in results:
            url = result[0]
            if not self.is_domain_blocked(url):
                safe_results.append(result)
        return safe_results