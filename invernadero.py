from datetime import datetime, timedelta
from functools import reduce
import time
import random
from statistics import *
from abc import abstractmethod, ABC
from confluent_kafka import Producer, Consumer, KafkaException
import json
import pandas as pd
import pytest
import random

class ValueError(Exception):
    pass

class Suscriptor(ABC):
    
    @abstractmethod
    def actualizar(self, evento):
        pass


class DueñoInvernadero(Suscriptor):

    def __init__(self, nombre, id):
        self.nombre = nombre
        self.id = id
        

    def actualizar(self, evento):
        print(f"Último reporte de temperatura: {evento}")
        return evento
    

# Definición de la clase Sensor
class Sensor:
    def __init__(self, id:int):
        self._id = id                      
        self.temp_history = []
        self.producer = Producer({'bootstrap.servers': 'localhost:9092'})
    

    def enviar_informacion(self):
        while True:
            time.sleep(5) # CON ESTO CONSEGUIMOS SIMULAR EL ENVÍO DE DATOS CADA 5 SEGUNDOS 
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            t = random.randint(15,35)
            data = (timestamp, t)
            self.producer.produce('Temperaturas', value=json.dumps(data)) # SIMULACIÓN DEL ENVÍO DE DATOS AL SERVIDOR DE KAFKA AL TÓPICO DE TEMPERATURAS
            print(data)
            self.temp_history.append(data)
            if len(self.temp_history) > 30:
                self.temp_history.pop(0)
            yield self.temp_history

# 1) CHAIN OF RESPONSIBILITY:
class Handler(ABC):
    def __init__(self):
        self.next_handler = None
        

    def set_next(self, handler):
        self.next_handler = handler
        return handler

    @ abstractmethod
    def handle(self, data_sensor):
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        return None

    @staticmethod
    def convert_to_datetime(date_string):
        try:
            return datetime.strptime(date_string, "%Y-%m-%d %H:%M:%S")
        except ValueError:
            print(f"Cannot convert '{date_string}' to datetime. Invalid format.")
            return None


# 2) STRATEGY:
class StrategyHandler(Handler):
    
    def handle(self, data_sensor):
        pass

    def is_valid_date(date_string):
        if len(date_string) != 19:  # The length of a datetime string in the format '%Y-%m-%d %H:%M:%S' is 19
            return False
        return True


class StrategyMeanStdev(StrategyHandler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]

        datos_ultimo_minuto = list(filter(lambda x: StrategyHandler.is_valid_date(x[0]) and time.time() - time.mktime(time.strptime(x[0], "%Y-%m-%d %H:%M:%S")) <= 60, data_sensor))

        temperaturas = [x[1] for x in datos_ultimo_minuto]
        
        if len(temperaturas) < 2:
            return None

        temp_media =  mean(temperaturas)
        temp_desviacion_tipica = stdev(temperaturas)

        return f"Temperatura media: {temp_media}, Desviación Típica: {temp_desviacion_tipica}"
        

class StrategyQuantiles(StrategyHandler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]

        datos_ultimo_minuto = list(filter(lambda x: StrategyHandler.is_valid_date(x[0]) and time.time() - time.mktime(time.strptime(x[0], "%Y-%m-%d %H:%M:%S")) <= 60, data_sensor))

        temperaturas = [x[1] for x in datos_ultimo_minuto]

        if len(temperaturas) < 2:
            return None

        # Convertir la lista a una serie de Pandas para que pueda usar la función "quantile"
        temperaturas_series = pd.Series(temperaturas)

        quantiles = temperaturas_series.quantile([0.25, 0.5, 0.75])

        return f"Quantil 1: {quantiles[0.25]}, Mediana: {quantiles[0.5]}, Quantil 3: {quantiles[0.75]}"


class StrategyMaxMin(StrategyHandler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]
        

        datos_ultimo_minuto = list(filter(lambda x: StrategyHandler.is_valid_date(x[0]) and time.time() - time.mktime(time.strptime(x[0], "%Y-%m-%d %H:%M:%S")) <= 60, data_sensor))
            
        temperaturas = [x[1] for x in datos_ultimo_minuto]
        
        if len(temperaturas) < 2:
            return None

        return f"En el último minuto se ha resgistrado una temperatura mínima de {min(temperaturas)} ºC y una temperatura máxima de {max(temperaturas)} ºC"

# FIN 2)

class TemperatureThresholdHandler(Handler):
    def handle(self, data_sensor, threshold:int):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]
        current_temp = data_sensor[-1][1]
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        return f"¡¡¡Alerta!!! Temperatura supera el umbral: {current_temp}ºC" if current_temp > threshold else "Temperatura normal"

class TemperatureIncreaseHandler(Handler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]
        sorted_data = sorted(data_sensor, key=lambda x: x[0])
        if len(sorted_data) < 2:
            return None
        for i in range(1, len(sorted_data)):
            time_i = time.mktime(time.strptime(sorted_data[i][0], "%Y-%m-%d %H:%M:%S"))
            time_i_minus_1 = time.mktime(time.strptime(sorted_data[i-1][0], "%Y-%m-%d %H:%M:%S"))
            time_diff = time_i - time_i_minus_1
            temp_diff = sorted_data[i][1] - sorted_data[i-1][1]
            if time_diff <= 30 and temp_diff >= 10:
                return f"¡¡¡Alerta!!!: La temperatura ha aumentado más de 10 grados en los últimos 30 segundos: {sorted_data[i][1]}"
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        return 'Temperatura estable'

# FIN 1)

class IoTSystem:
    # 3) SINGLETON:
    _instance = None

    def __init__(self):
        self.strategy_handlers = [StrategyMeanStdev(), StrategyQuantiles(), StrategyMaxMin()]
        # for i in range(len(self.strategy_handlers) - 1):
        #     self.strategy_handlers[i].set_next(self.strategy_handlers[i + 1])
        self.suscriptores = []
        self.consumer = Consumer({
            'bootstrap.servers': 'localhost:9092',
            'group.id': 'iot_system',
            'auto.offset.reset': 'earliest'
        })
        self.consumer.subscribe(['Temperaturas'])  # Suscripción al tópico
        
        # Inicializar los manejadores de temperatura
        self.strategy_handler = StrategyMeanStdev()
        self.temperature_threshold_handler = TemperatureThresholdHandler()
        self.temperature_increase_handler = TemperatureIncreaseHandler()

        self.strategy_handler.set_next(self.temperature_threshold_handler)
        self.temperature_threshold_handler.set_next(self.temperature_increase_handler)

    @classmethod
    def obtener_instancia(cls):
        if not cls._instance:
            cls._instance = cls()
            cls._instance.data = []
        return cls._instance
    # FIN 3)


    def dar_de_alta(self, suscriptor):
        self.suscriptores.append(suscriptor)
        print(f"{suscriptor.nombre} con id: {suscriptor.id} fue dado de alta en el sistema.")

    def dar_de_baja(self, id):
        for s in self.suscriptores:
            if s.id == id:
                self.suscriptores.remove(s)
                print(f"{nombre} con id: {id} fue dado de bajo en el sistema.")
            else: # EXCEPCIÓN?
                print(f"No se ha encontrado al suscriptor con id: {id} en el sistema.")

    def procesamiento_de_datos(self, data):
        if not isinstance(data, list):
            data = [data]

        strategy_results = {}
        for handler in self.strategy_handlers:
            result = handler.handle(data)
            strategy_results[type(handler).__name__] = result

        temp_theshold_handler = TemperatureThresholdHandler()
        temp_increase_handler = TemperatureIncreaseHandler()

        temp_threshold_result = temp_theshold_handler.handle(data, threshold=30)
        temp_increase_result = temp_increase_handler.handle(data)

        evento = {
            'Fecha': data[-1][0], 
            'Temperatura': data[-1][-1],
            'Cálculos estadísticos': strategy_results,
            'Comprobación de la temperatura actual': temp_threshold_result,
            'Comprobación de la temperatura en los últimos 30 segundos': temp_increase_result
        }

        return evento
            

    def notificar_suscriptores(self, evento):
        for suscriptor in self.suscriptores:
            suscriptor.actualizar(evento) # LE PASAREMOS TODOS LOS DATOS PREPROCESADOS EN EL STRATEGY Y LA CAD.RESP


if __name__ == '__main__':
    # Crear una instancia del sistema IoT
    sistema = IoTSystem.obtener_instancia()

    # Añadir un suscriptor al sistema
    dueño_invernadero = DueñoInvernadero('Modesto Mercader', '26649110E')
    sistema.dar_de_alta(dueño_invernadero)

    # Añadir algunos datos de sensores
    sensor = Sensor(1)
    data_sensor = sensor.enviar_informacion()

    # Procesar los datos
    for data in data_sensor:
        evento = sistema.procesamiento_de_datos(data)
        # Notificar a los suscriptores
        sistema.notificar_suscriptores(evento)

    # Eliminar un suscriptor del sistema
    sistema.dar_de_baja(dueño_invernadero)

    # Intentar notificar a los suscriptores de nuevo (no debería haber ninguno)
    sistema.notificar_suscriptores(evento)