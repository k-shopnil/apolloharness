"""Run heavy engine calls one at a time.

On a 512 MB host one global-terrain request peaks near 400 MB (measured). FastAPI
runs plain `def` routes in a thread pool, so two such requests at once could
exceed the memory limit and crash the server. Requests wait their turn instead;
each takes about 0.5-3.5 s.
"""
import threading

ENGINE_GATE = threading.BoundedSemaphore(1)
