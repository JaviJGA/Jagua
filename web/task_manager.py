import threading
import time

class TaskManager:
    def __init__(self):
        self.tasks = {}
        self.lock = threading.Lock()
    
    def create_task(self, query):
        task_id = f"{time.time()}-{query[:10]}"
        with self.lock:
            self.tasks[task_id] = {
                'query': query,
                'status': 'searching',
                'progress': 0,
                'urls_found': 0,
                'urls_indexed': 0,
                'related_found': 0,
                'related_indexed': 0,
                'start_time': time.time()
            }
        return task_id
    
    def update_task(self, task_id, updates):
        with self.lock:
            if task_id in self.tasks:
                self.tasks[task_id].update(updates)
    
    def get_task(self, task_id):
        with self.lock:
            return self.tasks.get(task_id, {}).copy()
    
    def cleanup_task(self, task_id, delay=300):
        def cleanup():
            time.sleep(delay)
            with self.lock:
                if task_id in self.tasks:
                    del self.tasks[task_id]
        threading.Thread(target=cleanup).start()