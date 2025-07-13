import multiprocessing

workers = multiprocessing.cpu_count() * 2 + 1
timeout = 120  # Increase timeout for heavy operations
keepalive = 5