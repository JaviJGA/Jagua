import threading
import time

# esto maneja las tareas de búsqueda dinámica
# y el progreso de las mismas. Permite crear, actualizar y limpiar tareas.
class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()
        # Hilo para limpieza automática
        self.cleanup_thread = threading.Thread(target=self.auto_cleanup, daemon=True)
        self.cleanup_thread.start()
    
    def create_task(self, query):
        task_id = f"{time.time()}-{query[:10]}"
        with self.lock:
            self.tasks[task_id] = {
                'id': task_id,
                'query': query,
                'status': 'searching',
                'progress': 0,
                'urls_found': 0,
                'urls_indexed': 0,
                'related_found': 0,
                'related_indexed': 0,
                'start_time': time.time(),
                'completed': False  # Nuevo campo para identificar tareas completadas
            }
        return task_id
    
    def update_task(self, task_id, updates):
       if task_id in self.tasks:
           self.tasks[task_id].update(updates)
    
    def get_task(self, task_id):
        with self.lock:
            return self.tasks.get(task_id, {}).copy()
    
    # esto limpia las tareas completadas que han expirado
    # y las elimina después de 5 minutos.
    def auto_cleanup(self):
        while True:
            time.sleep(60)
            current_time = time.time()
            with self.lock:
                to_remove = [
                    task_id for task_id, task in self.tasks.items()
                    if task.get('completed') and (current_time - task.get('start_time', 0)) > 300
                ]
                for task_id in to_remove:
                    del self.tasks[task_id]

# a donde vas