from irrigation_controller_server.config import get_settings

settings = get_settings()

broker_url = settings.broker.url
result_backend = settings.broker.result_backend
beat_dburi = settings.broker.beat_dburi
