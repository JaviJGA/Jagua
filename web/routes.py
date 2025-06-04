from flask import Flask, request, render_template, jsonify, redirect
from database.search_engine_db import SearchEngineDB
from search.dynamic_search import DynamicSearch
from .task_manager import TaskManager
import threading
import time

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
    results = db.search(query)
    stats = db.get_stats()
    
    # Contar tareas activas en segundo plano
    active_tasks = [task for task in task_manager.tasks.values() 
                   if task['status'] != 'completed']
    background_tasks = len(active_tasks)
    
    # Si hay resultados o no se requiere búsqueda dinámica, mostrar resultados
    if results or not db.should_dynamic_search(query):
        return render_template('results.html', query=query, results=results, stats=stats, background_tasks=background_tasks)
    
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
    
    if task:
        task_manager.update_task(task_id, {
            'status': 'searching',
            'message': 'Buscando en DuckDuckGo...',
            'progress': 5
        })
    
    urls = dynamic_searcher.duckduckgo_search(query, num_results=15)
    
    if task:
        task_manager.update_task(task_id, {
            'urls_found': len(urls),
            'status': 'indexing',
            'message': f'Encontradas {len(urls)} URLs. Indexando...',
            'progress': 10
        })
    
    if urls:
        if task:
            task_manager.update_task(task_id, {'total_urls': len(urls)})
        
        related_urls = []
        
        for i, url in enumerate(urls):
            if task:
                progress = 10 + int((i / len(urls)) * 50)
                task_manager.update_task(task_id, {
                    'progress': progress,
                    'current_url': url,
                    'urls_indexed': i,
                    'message': f'Indexando {i+1}/{len(urls)}: {url[:50]}...'
                })
            
            found_related = dynamic_searcher.quick_index(url)
            related_urls.extend(found_related)
            
            if task and found_related:
                task_manager.update_task(task_id, {'related_found': len(related_urls)})
            
            if task:
                task_manager.update_task(task_id, {'urls_indexed': i + 1})
        
        if related_urls:
            if task:
                task_manager.update_task(task_id, {
                    'status': 'indexing_related',
                    'message': f'Indexando {len(related_urls)} enlaces relacionados...',
                    'progress': 60
                })
            
            unique_related = list(set(related_urls))
            
            if task:
                task_manager.update_task(task_id, {'related_found': len(unique_related)})
            
            for j, rel_url in enumerate(unique_related):
                if task:
                    progress = 60 + int((j / len(unique_related))) * 40
                    task_manager.update_task(task_id, {
                        'progress': progress,
                        'current_url': rel_url,
                        'related_indexed': j,
                        'message': f'Indexando relacionado {j+1}/{len(unique_related)}: {rel_url[:50]}...'
                    })
                
                dynamic_searcher.quick_index(rel_url, extract_links=False)
                
                if task:
                    task_manager.update_task(task_id, {'related_indexed': j + 1})
        
        if task:
            task_manager.update_task(task_id, {
                'status': 'completed',
                'progress': 100,
                'message': '¡Indexación completada!'
            })
            # No eliminar la tarea inmediatamente, solo marcarla como completada
            # La limpieza se hará más tarde automáticamente
    else:
        if task:
            task_manager.update_task(task_id, {
                'status': 'completed',
                'progress': 100,
                'message': 'No se encontraron resultados en DuckDuckGo.'
            })