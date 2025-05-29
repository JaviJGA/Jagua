#celar
from crawler.advanced_crawler import run_crawler
from database.search_engine_db import SearchEngineDB
from web.routes import app
import threading

def main():
    db = SearchEngineDB()
    
    crawler_thread = threading.Thread(
        target=run_crawler, 
        args=(db,),
        daemon=True
    )
    crawler_thread.start()
    
    app.run(port=5000, debug=True, use_reloader=False, threaded=True)

if __name__ == '__main__':
    main()