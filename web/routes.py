from flask import Flask, request, render_template, jsonify, redirect
from database.search_engine_db import SearchEngineDB
from search.dynamic_search import DynamicSearch
from security.safe_search import SafeSearch
from .task_manager import TaskManager
import threading
import time

safe_search = SafeSearch("https://raw.githubusercontent.com/StevenBlack/hosts/master/alternates/fakenews-gambling-porn/hosts")

# aqui ya empezzam las cosas interesantes
# usamos flask para crear una aplicación web sencilla
# y manejar las búsquedas dinámicas con DuckDuckGo.
app = Flask(__name__)
db = SearchEngineDB()
task_manager = TaskManager()
dynamic_searcher = DynamicSearch(db)

# la ruta / es la página principal que muestra las estadísticas del motor de búsqueda
# y un formulario de búsqueda.
@app.route('/')
def index():
    stats = db.get_stats()
    # Contar tareas activas en segundo plano
    active_tasks = [task for task in task_manager.tasks.values() 
                   if task['status'] != 'completed']
    background_tasks = len(active_tasks)
    return render_template('search.html', stats=stats, background_tasks=background_tasks)

# la ruta /search maneja las búsquedas del usuario.	
@app.route('/search')
def search():
    query = request.args.get('q', '')
    safe_mode = request.args.get('safe', 'off') == 'on'
    results = db.search(query)
    stats = db.get_stats()

    if safe_mode:
        original_count = len(results)
        results = safe_search.filter_results(results)
        safe_count = len(results)
        print(f"Modo seguro activado. Filtrados {original_count - safe_count} resultados")
    
    # Contar tareas activas en segundo plano
    active_tasks = [task for task in task_manager.tasks.values() 
                   if task['status'] != 'completed']
    background_tasks = len(active_tasks)
    
    # Si hay resultados o no se requiere búsqueda dinámica, mostrar resultados
    if results or not db.should_dynamic_search(query):
        return render_template('results.html', query=query, results=results, stats=stats, background_tasks=background_tasks, safe_mode=safe_mode)
    
    # Registrar búsqueda dinámica e iniciar tarea
    db.record_dynamic_search(query)
    task_id = task_manager.create_task(query)
    
    threading.Thread(
        target=dynamic_search_task, 
        args=(query, task_id)
    ).start()
    
    return redirect(f'/dynamic_search_progress?task_id={task_id}')

# la ruta /dynamic_search_progress muestra el progreso de una búsqueda dinámica.
# Si la tarea no existe o ha expirado, muestra un mensaje de error.
@app.route('/dynamic_search_progress')
def dynamic_search_progress():
    task_id = request.args.get('task_id', '')
    task = task_manager.get_task(task_id)
    if not task:
        return "Tarea no encontrada o expirada", 404
    query = task.get('query', 'Búsqueda')
    return render_template('dynamic_search_progress.html', query=query, task_id=task_id)

# la ruta /force_dynamic_search permite forzar una búsqueda dinámica
# y crear una tarea para indexar los resultados.
@app.route('/force_dynamic_search')
def force_dynamic_search():
    query = request.args.get('q', '')
    db.record_dynamic_search(query)
    task_id = task_manager.create_task(query)
    
    threading.Thread(
        target=dynamic_search_task, 
        args=(query, task_id)
    ).start()
    
    return redirect(f'/dynamic_search_progress?task_id={task_id}')

# la ruta /get_task_status permite consultar el estado de una tarea dinámica.
# Devuelve un JSON con el estado, progreso y mensajes de la tarea.
# viva json muerte a xml (no me gusta xml)
@app.route('/get_task_status')
def get_task_status():
    task_id = request.args.get('task_id')
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    return jsonify(task)

@app.route('/check_domain')
def check_domain():
    domain = request.args.get('d', '')
    is_blocked = safe_search.is_domain_blocked(domain)
    #print_blocked_domains(safe_search)
    return jsonify({
        'domain': domain,
        'blocked': is_blocked,
        'blocked_domains_count': len(safe_search.blocked_domains),
        'last_update': safe_search.last_update
    })

# dynamic_search_task es la función que se ejecuta en un hilo separado
# para realizar la búsqueda dinámica y la indexación de resultados.
# es bastanet larga, pero básicamente sigue estos pasos:
# 1. Actualiza el estado de la tarea a "buscando" y realiza una búsqueda en DuckDuckGo.
# 2. Si se encuentran URLs, actualiza el estado a "indexando" y comienza a indexar cada URL.
# 3. Para cada URL, extrae enlaces relacionados y los indexa también.
# 4. Actualiza el estado de la tarea a "completada" al finalizar.
# Si no se encuentran resultados, actualiza el estado a "completada" con un mensaje adecuado.
def dynamic_search_task(query, task_id):
    task = task_manager.get_task(task_id)
    total_steps = 100  # Progreso total
    
    # Paso 1: Búsqueda inicial (10%)
    task_manager.update_task(task_id, {
        'status': 'searching',
        'progress': 10,
        'message': 'Buscando en DuckDuckGo...'
    })
    
    urls = dynamic_searcher.duckduckgo_search(query, num_results=15)
    
    if not urls:
        task_manager.update_task(task_id, {
            'status': 'completed',
            'progress': 100,
            'message': 'No se encontraron resultados'
        })
        return

    # Paso 2: Indexación principal (40%)
    task_manager.update_task(task_id, {
        'status': 'indexing',
        'progress': 20,
        'total_urls': len(urls),
        'message': f'Indexando {len(urls)} URLs principales...'
    })
    
    related_urls = []
    for i, url in enumerate(urls):
        # Calcular progreso (20-60%)
        progress = 20 + int((i / len(urls)) * 40)
        
        task_manager.update_task(task_id, {
            'progress': progress,
            'current_url': url,
            'urls_indexed': i + 1,
            'message': f'Indexando URL {i+1}/{len(urls)}'
        })
        
        found_related = dynamic_searcher.quick_index(url)
        related_urls.extend(found_related)

    # Paso 3: Indexación de relacionados (30%)
    unique_related = list(set(related_urls))
    if unique_related:
        task_manager.update_task(task_id, {
            'status': 'indexing_related',
            'progress': 60,
            'total_related': len(unique_related),
            'message': f'Indexando {len(unique_related)} enlaces relacionados...'
        })
        
        for j, rel_url in enumerate(unique_related):
            # Calcular progreso (60-90%)
            progress = 60 + int((j / len(unique_related)) * 30)
            
            task_manager.update_task(task_id, {
                'progress': progress,
                'current_url': rel_url,
                'related_indexed': j + 1,
                'message': f'Indexando relacionado {j+1}/{len(unique_related)}'
            })
            
            dynamic_searcher.quick_index(rel_url, extract_links=False)

    # Paso 4: Finalización (100%), le meti que redirija a los resultados antes no iba creo lol
    task_manager.update_task(task_id, {
        'status': 'completed',
        'progress': 100,
        'message': '¡Indexación completada!',
        'redirect_url': f'/search?q={query}'
    })

def print_blocked_domains(self):
    print("Dominios bloqueados actualmente:")
    for d in self.blocked_domains:
        print(d)