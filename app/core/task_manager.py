from threading import Lock

global_tasks = {}
global_tasks_lock = Lock()

class TaskManager:
    """Global task manager"""
    
    @staticmethod
    def get_task(task_id):
        """Get task"""
        with global_tasks_lock:
            return global_tasks.get(task_id)
    
    @staticmethod
    def add_task(task_id, task_data):
        """Add task"""
        with global_tasks_lock:
            global_tasks[task_id] = task_data
    
    @staticmethod
    def update_task(task_id, update_data):
        """Update task"""
        with global_tasks_lock:
            if task_id in global_tasks:
                global_tasks[task_id].update(update_data)
    
    @staticmethod
    def remove_task(task_id):
        """Remove task"""
        with global_tasks_lock:
            if task_id in global_tasks:
                del global_tasks[task_id]