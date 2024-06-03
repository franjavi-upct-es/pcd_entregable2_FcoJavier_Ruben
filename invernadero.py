from datetime import datetime
import time
import random
from statistics import *
from abc import abstractmethod, ABC

class ValueError(Exception):
    pass


class Suscriptor(ABC):
    
    @abstractmethod
    def actualizar(self, evento):
        pass

class DueñoInvernadero(Suscriptor):
    def __init__(self, nombre, id):
        self.nombre = nombre
        self._id = id

    def actualizar(self, evento):
        return evento
    

# Definición de la clase Sensor
class Sensor:
    def __init__(self, id:int):
        self._id = id

    def enviar_informacion(self, timestamp:str, t:int):
        time.sleep(5)
        timestamp = datetime.strptime(timestamp)    # Convierte un str en un fecha que pueda procesar
        return (timestamp, t)
        
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

"""
def procesamiento_nuevos_datos(self):
        # Filtrar los datos de los últimos 60s
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, self.data))

        temperaturas = list(map(lambda x: x.t, datos_ultimo_minuto))

        # Evitamos la posibilidad de que "temperatura" sea una lista vacía
        if len(temperaturas) == 0:
            raise ValueError

        temp_media = mean(temperaturas)
        print(f"Temperatura media de los últimos 60 segundos: {temp_media}")
        
        # Comprobar si la temperatura media es mayor de un límite establecido
        temp_actual = self.data[-1].t
        if temp_actual > 30:
            print(f"Temperatura alta")

        desviacion_tipica = stdev(temperatura)

        datos_treinta_segundos = list(filter(lambda x: time.time() - x.timestamp <= 30, self.data))
        if len(datos_treinta_segundos) >= 2 and datos_treinta_segundos[-1].t - datos_treinta_segundos[0].t > 10:
            print("La temperatura ha aumentado más de 10 grados en los últimos 30 segundos")
"""

class IoTSystem:
    
    _instance = None

    def __init__(self):
        self.suscriptores = []

    @classmethod
    def obtener_instancia(cls):
        if not cls._instance:
            cls._instance = cls()
            cls._instance.data = []
        return cls._instance

    def nuevos_datos(self, data):
        self.data.append(data)
        self.procesamiento_nuevos_datos()