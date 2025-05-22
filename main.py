#celar
import scrapy
import json

class FakeJobsSpider(scrapy.Spider):
    name = "fake_jobs"
    def __init__(self, start_urls=None, *args, **kwargs):
        super().__init__(*args, **kwargs)
        if start_urls:
            if isinstance(start_urls, str):
                # Permitir pasar varias URLs separadas por coma
                self.start_urls = [url.strip() for url in start_urls.split(',')]
            else:
                self.start_urls = list(start_urls)
        else:
            self.start_urls = [
                "https://forocoches.com/foro/forumdisplay.php?f=2",
                "https://en.wikipedia.org/wiki/Battle_of_Boquer%C3%B3n_(1932)"
            ]
    custom_settings = {
        'DEPTH_LIMIT': 1,
    }

    def parse(self, response):
        # Extrae todos los enlaces (href) de la página
        urls = [response.urljoin(href) for href in response.css('a::attr(href)').getall()]
        data = {
            'url': response.url,
            'urls': urls
        }

        # Sobrescribe el archivo resultados.json en cada llamada
        with open('resultados.json', 'w', encoding='utf-8') as f:
            json.dump(data, f, ensure_ascii=False, indent=2)

        # Sigue cada enlace encontrados
        for url in urls:
            yield scrapy.Request(url, callback=self.parse)
