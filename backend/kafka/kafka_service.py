from kafka import KafkaProducer, KafkaConsumer
import json
from typing import Any, Dict, List

class KafkaInterface:
    def __init__(self, bootstrap_servers: str = 'localhost:9092'):
        """
        Инициализация интерфейса Kafka
        
        Args:
            bootstrap_servers: адрес Kafka брокера
        """
        self.bootstrap_servers = bootstrap_servers
        self.producer = None
        self.consumer = None
    
    def write_to_topic(self, topic: str, message: int) -> bool:
        """
        Запись сообщения в топик
        
        Args:
            topic: название топика
            message: сообщение для отправки (словарь)
            
        Returns:
            bool: успешность операции
        """
        try:
            if not self.producer:
                self.producer = KafkaProducer(
                    bootstrap_servers=self.bootstrap_servers,
                    value_serializer=lambda v: json.dumps(v).encode('utf-8')
                )
            print(f"Writing message to topic {topic}: {message}")
            future = self.producer.send(topic, message)
            future.get(timeout=10)  # Ждём подтверждения
            self.producer.flush()
            return True
            
        except Exception as e:
            print(f"Ошибка при записи в топик: {e}")
            return False
    
    def read_from_topic(self, topic: str, timeout_ms: int = 5000) -> List[Dict[str, Any]]:
        """
        Чтение сообщений из топика
        
        Args:
            topic: название топика
            timeout_ms: таймаут ожидания сообщений в миллисекундах
            
        Returns:
            List[Dict]: список сообщений
        """
        try:
            self.consumer = KafkaConsumer(
                topic,
                bootstrap_servers=self.bootstrap_servers,
                value_deserializer=lambda x: json.loads(x.decode('utf-8')),
                auto_offset_reset='earliest',  # Changed from 'latest' to 'earliest'
                enable_auto_commit=True,
                group_id='githubxplainer-consumer-group',  # Added consumer group
                consumer_timeout_ms=timeout_ms
            )
            
            messages = []
            for message in self.consumer:
                messages.append(message.value)
            
            return messages
            
        except Exception as e:
            print(f"Ошибка при чтении из топика: {e}")
            return []

    def close(self):
        """Close Kafka connections"""
        if self.producer:
            self.producer.close()
        if self.consumer:
            self.consumer.close()