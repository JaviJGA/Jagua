# 🐾 Jagua 0.0.2.3

![Versión](https://img.shields.io/badge/versión-0.0.2.3-blue?style=flat-square)
![Estado](https://img.shields.io/badge/estado-en%20desarrollo-yellow?style=flat-square)
![Python](https://img.shields.io/badge/python-3.10%2B-blue?style=flat-square)
![Licencia](https://img.shields.io/badge/licencia-WTFPL-green?style=flat-square)

**Est. 2025 — Proyecto TFG para IES Aljada**

Buscador web con capacidad de indexar y hacer crawling de páginas. Si no encuentra lo que buscas, recurre a la API de DuckDuckGo.

---

## ✨ Características

- Indexado directo e inverso en base de datos
- Crawling automático desde 100 enlaces predeterminados (temas variados)
- Si no hay resultados en la base, usa la API de DuckDuckGo y guarda los nuevos enlaces
- Templates básicos para mostrar resultados en navegador

---

## 🚧 Cosas pendientes

- [ ] Permitir cancelar la carga dinámica
- [ ] Poder usar el navegador mientras trabaja la carga dinámica
- [X] Refactorización general del código
- [X] Terminar el "tutorial" de uso
- [X] Crear la base funcional del proyecto
- [X] Mostrar resultados correctamente
- [X] Mejorar los templates
- [ ] No sé xd

---

## 🛠️ Cómo usarlo

1. Instalar dependencias con `pip install -r requisitos.txt`
2. Ejecutar el proyecto con `python main.py`

---

## 🎯 Objetivo

Crear un buscador web que sea capaz de dar resultados lo más cercanos posible a la búsqueda del usuario.  
Queremos desarrollar todo lo que podamos por nuestra cuenta y llegar a tantas páginas como podamos con nuestros propios recursos.

---

## 🙌 Créditos

- Desarrollado por: **Javier Jesús y Fernando Medina**
  
## 🔧 Herramientas y librerías utilizadas

| Librería / Herramienta | Versión     | Descripción breve                                                                 |
|------------------------|-------------|-----------------------------------------------------------------------------------|
| [Scrapy](https://scrapy.org/)            | 2.13.0      | Framework para crawling rápido y escalable de sitios web                          |
| [BeautifulSoup4](https://www.crummy.com/software/BeautifulSoup/) | 4.13.4      | Librería para parsear y navegar documentos HTML de forma sencilla                |
| [DuckDuckGo API](https://duckduckgo.com/api) | -           | API que permite realizar búsquedas web sin rastreo                               |
| [Flask](https://flask.palletsprojects.com/)              | 3.1.1       | Micro-framework web para mostrar los resultados en navegador                     |
| [lxml](https://lxml.de/)                  | 5.4.0       | Analizador XML/HTML muy rápido y eficiente (usado por BeautifulSoup y Scrapy)    |
| [Parsel](https://parsel.readthedocs.io/) | 1.10.0      | Utilidad para extraer datos de HTML/XML (parte de Scrapy)                        |
| [cssselect](https://pypi.org/project/cssselect/)         | 1.3.0       | Permite usar selectores CSS en documentos XML/HTML                               |
| [requests](https://docs.python-requests.org/)            | 2.32.3      | Librería para hacer peticiones HTTP de forma simple                              |
| [Jinja2](https://jinja.palletsprojects.com/)             | 3.1.6       | Motor de plantillas usado en Flask para generar HTML dinámico                    |
| [Werkzeug](https://palletsprojects.com/p/werkzeug/)      | 3.1.3       | Librería WSGI para aplicaciones web en Flask                                     |
| [Twisted](https://twistedmatrix.com/)                    | 24.11.0     | Librería de red usada por Scrapy para manejo de peticiones asíncronas           |
| [w3lib](https://github.com/scrapy/w3lib)                 | 2.3.1       | Utilidades comunes para el scraping web                                          |
| [queuelib](https://github.com/scrapy/queuelib)           | 1.8.0       | Soporte de colas para Scrapy                                                     |
| [service-identity](https://service-identity.readthedocs.io/) | 24.2.0 | Verificación de identidad en conexiones seguras                                  |

---

## 💬 Contacto

Ninguno ✅

---

## 📄 Licencia

Este proyecto está licenciado bajo la Licencia DO WHAT THE FUCK YOU WANT TO PUBLIC LICENSE.
