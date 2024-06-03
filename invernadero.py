from datetime import datetime
from functools import reduce
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


class DueñoInvernadero(Suscriptor):

    def __init__(self, nombre, id):
        self.nombre = nombre
        self.id = id                   # HABRÍA QUE DEFINIRLO COMO CONSUMER DE KAFKA

    def actualizar(self, evento):
        print(f"Último reporte de temperatura: {evento}")
        return evento
    

# Definición de la clase Sensor
class Sensor:
    def __init__(self, id:int):
        self._id = id                      # AQUÍ PERFECTO, DEFINIMOS COMO PRODUCTOR PERO NO EXACTAMENTE HEREDA DE SUSCRIPTOR PK NO TIENE SENTIDO QUE TENGA EL MÉTODO ACTUALIZAR
        self.temperatura = None
        self.producer = Producer({'bootstrap.servers': 'localhost:9092'})

    def enviar_informacion(self, timestamp:str, t:int):
        time.sleep(5) # CON ESTO CONSEGUIMOS SIMULAR EL ENVÍO DE DATOS CADA 5 SEGUNDOS 
        timestamp = datetime.strptime(timestamp)    # Convierte un str en un fecha que pueda procesar
        self.temperatura = t
        data = (timestamp, t)
        self.producer.produce('Temperaturas', value=json.dumps(data)) # SIMULAICÓN DEL ENVÍO DE DATOS AL SERVIDOR DE KAFKA
        return data



# IMPORTANTE: LOS DISTINTOS MANEJADORES RECIBEN LA NUEVA INFORMACIÓN CAPTURADA POR EL SENSOR, TUPLA (FECHA, T) PERO:
# ¿CÓMO HACEMOS PARA QUE TRATEN CON EL HISTORIAL DE TEMPERATURAS?

# 1) CHAIN OF RESPONSABILITY:
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


# 2) STRATEGY:
class StrategyHandler(Handler):
    def __init__(self, strategy):
        self.current_strategy = strategy

    def set_strategy(self, strategy):
        self.current_strategy = strategy
    
    def handle(self, data_sensor):
        pass

class StrategyMeanStdev(StrategyHandler):
    def handle(self, data_sensor):
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, data_sensor))

        temperaturas = [x.t for x in datos_ultimo_minuto]

        temp_media =  mean(temperaturas)
        temp_desviacion_tipica = stdev(temperaturas)

        print(f"Temperatura media: {temp_media}\n Desviación Típica: {temp_desviacion_tipica}")
        return super().handle(data_sensor)

class StrategyQuantiles(StrategyHandler):
    def handle(self, data_sensor):
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, data_sensor))

        temperaturas = [x.t for x in datos_ultimo_minuto]

        quantiles =  [quantiles(temperaturas, [0.25, 0.5, 0.75])]

        print(f"Quantil 1: {quantiles[0]}\n Mediana: {quantiles[1]}\n Quantil 3: {quantiles[-1]}")
        return super().handle(data_sensor)


class StrategyMaxMin(StrategyHandler):
    def handle(self, data_sensor):
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, data_sensor))

        temperaturas = [x.t for x in datos_ultimo_minuto]
        print(f"En el último minuto se ha resgistrado una temperatura mínima de {min(temperaturas)} ºC y una temperatura máxima de {max(temperaturas)} ºC")
        return super().handle(data_sensor)

# FIN 2)




class TemperatureThresholdHandler(Handler):
    def handle(self, data_sensor):
        temp_max = reduce(lambda t1, t2: t1 if t1 > t2 else t2, data_sensor) # Podemos emplear también la función max() predefinida
        if temp_max > 30:
            print(f"¡¡¡Alerta!!!: Temperatura máxima supera el umbral: {temp_max}ºC")
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        return None

class TemperatureIncreaseHandler(Handler):
    def handle(self, data_sensor):
        sorted_data = sorted(data_sensor, key=lambda x: x[0])
        for i in range(1, len(sorted_data)):
            if sorted_data[i][0] - sorted_data[i-1][0] <= 30 and sorted_data[i][1] - sorted_data[i-1][1] > 10:
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
            'group.id': 'iot_system',                # ¿CONSUMER EL SISTEMA IOT?
            'auto.offset.reset': 'earliest'
        })
        self.consumer.subscribe(['Temperaturas'])

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

    def nuevos_datos(self, data):
        self.data.append(data)  
        self.procesamiento_nuevos_datos()

    def procesamiento_nuevos_datos(self): # MÉTODO MORADO
        for handler in self.strategy_handlers:   # NO SOLO HAY QUE TENER EN CUENTA LOS STRATEGY DEL PRIMER PASO, HABRÍA QUE TENER EN CUENTA EL PASO 2 Y PASO 3 DEFINIDOS COMO MANEJADORES
            handler.handle(self.data)

            # NOS HARÁ UN RETURN CON EL EVENTO A PASARLE A LOS DUEÑOS DEL INVERNADERO

    def notificar_suscriptores(self):
        for suscriptor in self.suscriptores:
            suscriptor.actualizar(self.sensor.temperatura) # LE PASAREMOS TODOS LOS DATOS PREPROCESADOS EN EL STRATEGY Y LA CAD.RESP

