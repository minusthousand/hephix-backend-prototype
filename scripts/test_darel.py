import json
from services import darel_store

if __name__ == '__main__':
    res = darel_store.darel_search('hammer', results_per_page=5)
    print(type(res))
    print(len(res))
    print(json.dumps(res[:5], indent=2, ensure_ascii=False))
