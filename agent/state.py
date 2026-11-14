"""Working memory interface."""
_memory = {}

def save(thread_id, name, obj):
    _memory.setdefault(thread_id, {})[name] = obj

def load(thread_id, name):
    return _memory[thread_id][name]
