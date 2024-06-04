from datetime import datetime
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
import matplotlib.pyplot as plt

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
        self._id = id                      # AQUÍ PERFECTO, DEFINIMOS COMO PRODUCTOR PERO NO EXACTAMENTE HEREDA DE SUSCRIPTOR PK NO TIENE SENTIDO QUE TENGA EL MÉTODO ACTUALIZAR
        self.temperatura = None
        self.producer = Producer({'bootstrap.servers': 'localhost:9092'})
    

    def enviar_informacion(self):
        while True:
            time.sleep(5) # CON ESTO CONSEGUIMOS SIMULAR EL ENVÍO DE DATOS CADA 5 SEGUNDOS 
            timestamp = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            t = random.randint(15,35)
            data = (timestamp, t)
            self.producer.produce('Temperaturas', value=json.dumps(data)) # SIMULACIÓN DEL ENVÍO DE DATOS AL SERVIDOR DE KAFKA AL TÓPICO DE TEMPERATURAS
            return data



# IMPORTANTE: LOS DISTINTOS MANEJADORES RECIBEN LA NUEVA INFORMACIÓN CAPTURADA POR EL SENSOR, TUPLA (FECHA, T) PERO:
# ¿CÓMO HACEMOS PARA QUE TRATEN CON EL HISTORIAL DE TEMPERATURAS?

# 1) CHAIN OF RESPONSIBILITY:
class Handler(ABC):
    def __init__(self):
        self.next_handler = None
        self.temp_history = []

    def set_next(self, handler):
        self.next_handler = handler
        return handler

    @ abstractmethod
    def handle(self, data_sensor):
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        return None

    def update_temperature_history(self, timestamp, t):
        self.temp_history.append((timestamp, t))
        if len(self.temp_history) > 30:
            self.temp_history.pop(0)

    def get_temperature_history(self):
        return self.temp_history


    


# 2) STRATEGY:
class StrategyHandler(Handler):
    
    def handle(self, data_sensor):
        pass

class StrategyMeanStdev(StrategyHandler):
    def handle(self, data_sensor):
        datos_ultimo_minuto = list(filter(lambda x: time.mktime(datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S").timetuple()) - time.time() <= 60, data_sensor))

        temperaturas = [x[1] for x in datos_ultimo_minuto]

        temp_media =  mean(temperaturas)
        temp_desviacion_tipica = stdev(temperaturas)

        print(f"Temperatura media: {temp_media}\n Desviación Típica: {temp_desviacion_tipica}")
        return super().handle(data_sensor)

class StrategyQuantiles(StrategyHandler):
    def handle(self, data_sensor):
        datos_ultimo_minuto = list(filter(lambda x: time.mktime(datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S").timetuple()) - time.time() <= 60, data_sensor))

        temperaturas = [x[1] for x in datos_ultimo_minuto]

        # Convertir la lista a una serie de Pandas para que pueda usar la función "quantile"
        temperaturas_series = pd.Series(temperaturas)

        quantiles = temperaturas_series.quantile([0.25, 0.5, 0.75])

        print(f"Quantil 1: {quantiles[0.25]}\n Mediana: {quantiles[0.5]}\n Quantil 3: {quantiles[0.75]}")
        return super().handle(data_sensor)


class StrategyMaxMin(StrategyHandler):
    def handle(self, data_sensor):
        datos_ultimo_minuto = list(filter(lambda x: time.mktime(datetime.strptime(x[0], "%Y-%m-%d %H:%M:%S").timetuple()) - time.time() <= 60, data_sensor))

        temperaturas = [x[1] for x in datos_ultimo_minuto]
        print(f"En el último minuto se ha resgistrado una temperatura mínima de {min(temperaturas)} ºC y una temperatura máxima de {max(temperaturas)} ºC")
        return super().handle(data_sensor)

# FIN 2)

class TemperatureThresholdHandler(Handler):
    def handle(self, data_sensor, threshold:int):
        current_temp = data_sensor[-1][1]
        if current_temp > threshold:
            print(f"¡¡¡Alerta!!! Temperatura supera el umbral: {current_temp}ºC")
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        return None

class TemperatureIncreaseHandler(Handler):
    def handle(self, data_sensor):
        sorted_data = sorted(data_sensor, key=lambda x: x[0])
        for i in range(1, len(sorted_data)):
            time_diff = datetime.strptime(sorted_data[i][0], "%Y-%m-%d %H:%M:%S") - datetime.strptime(sorted_data[i-1][0], "%Y-%m-%d %H:%M:%S")
            temp_diff = sorted_data[i][1] - sorted_data[i-1][1]
            if time_diff.total_seconds() <= 30 and temp_diff > 10:
                print(f"¡¡¡Alerta!!!: La temperatura ha aumentado más de 10 grados en los últimos 30 segundos: {sorted_data[i][1]}")
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        return None   

# FIN 1)

class IoTSystem:
    # 3) SINGLETON:
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
        self.consumer.subscribe(['Temperaturas'])  # Suscripción al tópico
        
        # Inicializar los manejadores de temperatura
        self.strategy_handler = StrategyHandler()
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


    def dar_de_alta(self, id, nombre):
        self.suscriptores.append(DueñoInvernadero(nombre, id))
        print(f"{nombre} con id: {id} fue dado de alta en el sistema.")

    def dar_de_baja(self, id, nombre):
        for s in self.suscriptores:
            if s.id == id:
                self.suscriptores.remove(s)
                print(f"{nombre} con id: {id} fue dado de bajo en el sistema.")
            else: # EXCEPCIÓN?
                print(f"No se ha encontrado al suscriptor con id: {id} en el sistema.")

    def procesamiento_de_datos(self, data):
        for handler in self.strategy_handlers:
            handler.handle(data)

        temp_theshold_handler = TemperatureThresholdHandler()
        temp_increase_handler = TemperatureIncreaseHandler()

        temp_threshold_result = temp_theshold_handler.handle(data, threshold=30)
        temp_increase_result = temp_increase_handler.handle(data)

        evento = {
            data[-1][0]: data[-1][-1],
            'Cálculos estadísticos': [handler.current_strategy for handler in self.strategy_handlers],
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
    dueño_invernadero = DueñoInvernadero('Nombre del dueño', 'ID del dueño')
    sistema.dar_de_alta(dueño_invernadero)

    # Añadir algunos datos de sensores
    data_sensor = [('2022-01-01 00:00:00', 25), ('2022-01-01 00:01:00', 26), ('2022-01-01 00:02:00', 27)]

    # Procesar los datos
    evento = sistema.procesamiento_de_datos(data_sensor)

    # Notificar a los suscriptores
    sistema.notificar_suscriptores(evento)

    # Eliminar un suscriptor del sistema
    sistema.eliminar_suscriptor(dueño_invernadero)

    # Intentar notificar a los suscriptores de nuevo (no debería haber ninguno)
    sistema.notificar_suscriptores(evento)