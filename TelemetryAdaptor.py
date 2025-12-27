import redis


class TelemetryAdaptor:
    def __init__(self, config):
        self.ip = config["ip"]  # ip of the Redis instance
        self.port = config["port"]  # port of the Redis instance
        self.topic_id = config["topic_id"]  # topic where telemetry is pushed
        self.redis_client = None
        self._connect()

    def _connect(self):
        self.redis_client = redis.Redis(host=self.ip, port=self.port, retry_on_timeout=True)

    def write_to_redis(self, data_json):
        try:
            self.redis_client.publish(self.topic_id, data_json)
            return
        except redis.exceptions.TimeoutError:
            print("Reconnecting to Redis Instance...")
            try:
                self._connect()
            except:
                raise ConnectionError
            try:
                self.redis_client.publish(self.topic_id, data_json)
                return
            except:
                raise ConnectionError
        except redis.exceptions.ConnectionError:
            raise ConnectionError

    def __del__(self):
        self.redis_client.connection_pool.disconnect()
