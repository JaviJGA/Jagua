from flask import Flask, request, render_template, jsonify, redirect
from database.search_engine_db import SearchEngineDB
from search.dynamic_search import DynamicSearch
from .task_manager import TaskManager
import threading
import time

app = Flask(__name__)
db = SearchEngineDB()
task_manager = TaskManager()
dynamic_searcher = DynamicSearch(db)

@app.route('/')
def index():
    stats = db.get_stats()
    return render_template('search.html', stats=stats)

@app.route('/search')
def search():
    query = request.args.get('q', '')
    results = db.search(query)
    stats = db.get_stats()
    
    if not results and db.should_dynamic_search(query):
        db.record_dynamic_search(query)
        task_id = task_manager.create_task(query)
        
        threading.Thread(
            target=dynamic_search_task, 
            args=(query, task_id)
        ).start()
        
        return redirect(f'/dynamic_search_progress?task_id={task_id}')
    
    return render_template('results.html', query=query, results=results, stats=stats)

@app.route('/dynamic_search_progress')
def dynamic_search_progress():
    task_id = request.args.get('task_id', '')
    task = task_manager.get_task(task_id)
    if not task:
        return "Tarea no encontrada o expirada", 404
    query = task.get('query', 'Búsqueda')
    return render_template('dynamic_search_progress.html', query=query, task_id=task_id)

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

@app.route('/get_task_status')
def get_task_status():
    task_id = request.args.get('task_id')
    task = task_manager.get_task(task_id)
    if not task:
        return jsonify({'error': 'Tarea no encontrada'}), 404
    return jsonify(task)

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
            task_manager.cleanup_task(task_id, delay=300)
    else:
        if task:
            task_manager.update_task(task_id, {
                'status': 'completed',
                'progress': 100,
                'message': 'No se encontraron resultados en DuckDuckGo.'
            })
            task_manager.cleanup_task(task_id, delay=300)