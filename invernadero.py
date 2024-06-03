from datetime import datetime
import time
import random
from statistics import *
from abc import abstractmethod, ABC
from confluent_kafka import Producer, Consumer, KafkaException
import json

class ValueError(Exception):
    pass



class Suscriptor(ABC):
    
    @abstractmethod
    def actualizar(self, evento):
        pass

# Definición de la clase Sensor
class Sensor:
    def __init__(self, id:int):
        self._id = id
        self.temperatura = None
        self.producer = Producer({'bootstrap.servers': 'localhost:9092'})

    def enviar_informacion(self, timestamp:str, t:int):
        time.sleep(5)
        timestamp = datetime.strptime(timestamp)    # Convierte un str en un fecha que pueda procesar
        self.temperatura = t
        data = (timestamp, t)
        self.producer.produce('Temperaturas', value=json.dumps(data))
        return data
        
class Handler(ABC):
    def __init__(self):
        self.next_handler = None

    def set_next(self, handler):
        self.next_handler = handler
        return handler

    @ abstractmethod
    def handle(self, solicitud):
        if self.next_handler:
            return self.next_handler.handle(solicitud)
        return None

class StrategyHandler(Handler):
    def __init__(self, strategy):
        self.current_strategy = strategy

    def set_strategy(self, strategy):
        self.current_strategy = strategy
    
    def handle(self, data):
        pass

class StrategyMeanStdev(StrategyHandler):
    def handle(self, data):
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, data))

        temperaturas = [x.t for x in datos_ultimo_minuto]

        temp_media =  mean(temperaturas)
        temp_desviacion_tipica = stdev(temperaturas)

        print(f"Temperatura media: {temp_media}\n Desviación Típica: {temp_desviacion_tipica}")
        return super().handle(solicitud)

class StrategyQuantiles(StrategyHandler):
    def handle(self, data):
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, data))

        temperaturas = [x.t for x in datos_ultimo_minuto]

        quantiles =  [quantiles(temperaturas, [0.25, 0.5, 0.75])]

        print(f"Quantil 1: {quantiles[0]}\n Mediana: {quantiles[1]}\n Quantil 3: {quantiles[-1]}")
        return super().handle(solicitud)

class StrategyMaxMin(StrategyHandler):
    def handle(self, data):
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, data))

        temperaturas = [x.t for x in datos_ultimo_minuto]

        return max(temperaturas), min(temperaturas)

class TemperatureThresholdHandler(Handler):
    def handle(self, data):
        temp_max = max(data, key = lambda x: x[1])[1]
        if temp_max > 30:
            print(f"Alerta: Temperatura máxima supera el umbral: {temp_max}")
        if self.next_handler:
            return self.next_handler.handle(data)
        return None

class TemperatureIncreaseHandler(Handler):
    def handle(self, data):
        sorted_data = sorted(data, key=lambda x: x[0])
        for i in range(1, len(sorted_data)):
            if sorted_data[i][0] - sorted_data[i-1][0] <= 30 and sorted_data[i][1] - sorted_data[i-1][1] > 10:
                print(f"Alerta: La temperatura ha aumentado más de 10 grados en los últimos 30 segundos: {sorted_data[i][1]}")
        if self.next_handler:
            return self.next_handler.handle(data)
        return None   


class IoTSystem:
    
    _instance = None

    def __init__(self):
        self.strategy_handlers = [StrategyMeanStdev(), StrategyQuantiles(), StrategyMaxMin()]
        for i in range(len(self.strategy_handlers) - 1):
            self.strategy_handlers[i].set_next(self.strategy_handlers[i + 1])
        self.suscriptores = []
        self.consumer = Consumer({
            'bootstrap.servers': 'localhost:9092',
            'group.id': 'iot_system',
            'auto.offset.reset': 'earliest'
        })
        self.consumer.subscribe(['Temperaturas'])

    @classmethod
    def obtener_instancia(cls):
        if not cls._instance:
            cls._instance = cls()
            cls._instance.data = []
        return cls._instance

    def nuevos_datos(self, data):
        self.data.append(data)
        self.procesamiento_nuevos_datos()

    def procesamiento_nuevos_datos(self):
        for handler in self.strategy_handlers:
            handler.handle(self.data)

    def notificar_suscriptores(self):
        for suscriptor in self.suscriptores:
            suscriptor.actualizar(self.sensor.temperatura)

class DueñoInvernadero(Suscriptor):

    def __init__(self, nombre, id):
        self.nombre = nombre
        self._id = id

    def actualizar(self, evento):
        print(f"Último reporte de temperatura: {evento}")
        return evento