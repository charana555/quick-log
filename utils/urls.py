import os

ELASTICSEARCH_INTERNAL = "http://elasticsearch:9200"
LOGSTASH_INTERNAL = "http://logstash:9600"
KIBANA_INTERNAL = "http://kibana:5601"


def get_kibana_external():
    host = os.environ.get("QUICK_LOG_HOST", "localhost")
    return f"http://{host}:5601"
