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

# El dueño del invernadero será la persona que se subscriba al sistema IoT para obtener la información de su invernadero en tiempo real.
class DueñoInvernadero(Suscriptor):
    def __init__(self, nombre, id):
        self.nombre = nombre
        self.id = id
        

    def actualizar(self, evento):
        print(f"Último reporte de temperatura: {evento}")
        return evento
    

# Definición de la clase Sensor que funcionará como Productor en Kafka ya que es
# la clase que genera/simula los distintos eventos(temperaturas) que se captan dentro del invernadero.
class Sensor:
    def __init__(self, id:int):
        self._id = id                      
        self.temp_history = []
        self.producer = Producer({'bootstrap.servers': 'localhost:9092'}) # Atributo donde instanciamos la clase Producer
    

# Este método nos permite simular la generación de datos captados por el sensor en el invernadero.
    def enviar_informacion(self):
        while True:
            time.sleep(5) # CON ESTO CONSEGUIMOS SIMULAR EL ENVÍO DE DATOS CADA 5 SEGUNDOS 
            timestamp = time.strftime("%Y-%m-%d %H:%M:%S", time.localtime())
            t = random.randint(15,35)
            data = (timestamp, t)
            self.producer.produce('Temperaturas', value=json.dumps(data)) # SIMULACIÓN DEL ENVÍO DE DATOS AL SERVIDOR DE KAFKA AL TÓPICO DE TEMPERATURAS
            self.temp_history.append(data)
            if len(self.temp_history) > 30: # ESTE CONDICIONAL NOS PERMITE IR ELIMINANDO 
                                            #LOS EVENTOS QUE YA HEMOS PROCESADO Y MOSTRADO A LOS SUBSCRIPTORES(UNA VEZ PASADO LOS DOS MINUTOS Y MEDIO, SE ELIMINA)
                self.temp_history.pop(0)
            yield self.temp_history

# 1) CHAIN OF RESPONSIBILITY:
class Handler(ABC):
    def __init__(self):
        self.next_handler = None
        
    # MÉTODO PARA PODER FIJAR EL ATRIBUTO next_handler con la instanciación de la clase manejadora concreta
    # este atributo nos permitirá seguir el orden marcado por la cadena de responsabilidad, eslabón a eslabón.
    def set_next(self, handler):
        self.next_handler = handler
        return handler

    # MÉTODO CLAVE QUE NOS PERMITIRÁ PROCESAR LOS DATOS
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
# HEMOS TENIDO VARIOS PROBLEMAS CON EL FORMATO DE LAS FECHAS PARA QUE EL CÓDIGO FUNCIONE BIEN,
# PARA CORREGIRLO, DEFINIMOS ESTE MÉTODO ESTÁTICO QUE NOS PERMITE CONVERTIR UN STRING CON UN FORMATO CONCRETO
# A UN OBJETO datetime USANDO DICHO FORMATO ESPECIFICADO.

# 2) STRATEGY(empleamos el patrón Strategy para ofrecer el cálculo de distintos estadísticos en el paso 1 de la cadena de responsabilidad):
# Es decir, aplicamos un Strategy dentro del Chain of Responsability para ofrecer la funcionalidad comentada.

class StrategyHandler(Handler):
    
    def handle(self, data_sensor):
        pass

    def is_valid_date(date_string):
        if len(date_string) != 19:  # The length of a datetime string in the format '%Y-%m-%d %H:%M:%S' is 19
            return False
        return True

# IMPORTANTE A TENER EN CUENTA, RECORDAR QUE SENSOR GENERA DATOS EN EL SIGUIENTE FORMATO: tuple(datetime, temperature)
# POR TANTO, CUANDO UTILIZAMOS x[0] accedemos al atributo fecha del evento y con x[1] accedemos al atributo temperatura.

class StrategyMeanStdev(StrategyHandler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]
        # Filtra los datos del último minuto de data_sensor
        # Solo se incluyen los datos cuya fecha es válida y ha ocurrido en el último minuto
        datos_ultimo_minuto = list(filter(lambda x: StrategyHandler.is_valid_date(x[0]) and time.time() - time.mktime(time.strptime(x[0], "%Y-%m-%d %H:%M:%S")) <= 60, data_sensor))
        # Nos quedamos solo con las temperaturas
        temperaturas = [x[1] for x in datos_ultimo_minuto]
        
        if len(temperaturas) < 2:
            return None
        # CÁLCULOS ESTADÍSTICOS CONCRETOS DE ESTA ESTRATEGIA:
        temp_media =  mean(temperaturas)
        temp_desviacion_tipica = stdev(temperaturas)

        return f"Temperatura media: {temp_media}, Desviación Típica: {temp_desviacion_tipica}"
        


class StrategyQuantiles(StrategyHandler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]

        # Filtra los datos del último minuto de data_sensor
        # Solo se incluyen los datos cuya fecha es válida y ha ocurrido en el último minuto
        datos_ultimo_minuto = list(filter(lambda x: StrategyHandler.is_valid_date(x[0]) and time.time() - time.mktime(time.strptime(x[0], "%Y-%m-%d %H:%M:%S")) <= 60, data_sensor))

        # Nos quedamos solo con las temperaturas
        temperaturas = [x[1] for x in datos_ultimo_minuto]

        if len(temperaturas) < 2:
            return None

        # Convertir la lista a una serie de Pandas para que pueda usar la función "quantile"
        temperaturas_series = pd.Series(temperaturas)
        # CÁLCULOS ESTADÍSTICOS CONCRETOS DE ESTA ESTRATEGIA:
        quantiles = temperaturas_series.quantile([0.25, 0.5, 0.75])

        return f"Quantil 1: {quantiles[0.25]}, Mediana: {quantiles[0.5]}, Quantil 3: {quantiles[0.75]}"


class StrategyMaxMin(StrategyHandler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]
        
        # Filtra los datos del último minuto de data_sensor
        # Solo se incluyen los datos cuya fecha es válida y ha ocurrido en el último minuto
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
        # Obtenemos la temperatura actual del último elemento de data_sensor, última temperatura registrada
        current_temp = data_sensor[-1][1]
          # Si hay un siguiente manejador en la cadena de responsabilidad, delegamos la petición a él
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        # Si no hay un siguiente manejador, comprobamos si la temperatura actual supera el umbral
        # Si la supera, devolvemos una alerta, si no, indicamos que la temperatura es normal
        return f"¡¡¡Alerta!!! Temperatura supera el umbral: {current_temp}ºC" if current_temp > threshold else "Temperatura normal"


class TemperatureIncreaseHandler(Handler):
    def handle(self, data_sensor):
        # Convertir data_sensor a una lista de una sola tupla si no es una lista
        if not isinstance(data_sensor, list):
            data_sensor = [data_sensor]
        # Ordenamos los datos del sensor por tiempo
        sorted_data = sorted(data_sensor, key=lambda x: x[0])
        if len(sorted_data) < 2:
            return None
        
        # Recorremos los datos ordenados
        for i in range(1, len(sorted_data)):
            # Convertimos las marcas de tiempo a segundos desde la época:
            time_i = time.mktime(time.strptime(sorted_data[i][0], "%Y-%m-%d %H:%M:%S"))
            time_i_minus_1 = time.mktime(time.strptime(sorted_data[i-1][0], "%Y-%m-%d %H:%M:%S"))
            # Cálculamos las diferencias de tiempo y temperatura:
            time_diff = time_i - time_i_minus_1
            temp_diff = sorted_data[i][1] - sorted_data[i-1][1]
            # Si la temperatura ha aumentado más de 10 grados en los últimos 30 segundos, retornamos una alerta
            if time_diff <= 30 and temp_diff >= 10:
                return f"¡¡¡Alerta!!!: La temperatura ha aumentado más de 10 grados en los últimos 30 segundos: {sorted_data[i][1]}"
        # Si hay un siguiente manejador en la cadena de responsabilidad, delegamos la petición a él:
        if self.next_handler:
            return self.next_handler.handle(data_sensor)
        # Si no hay un siguiente manejador, indicamos que la temperatura es estable
        return 'Temperatura estable'

# FIN 1)

# AQUÍ DEFINIMOS LA CLASE GESTORA PRINCIPAL, EN ELLA EMPLEAMOS EL PATRÓN SINGLETON PARA QUE NO
# SE PUEDA INSTACIAR MÁS DE UN OBJETO DE ESTA CLASE, QUEREMOS QUE SEA ÚNICO Y ADEMÁS HEMOS IMPLEMENTADO LO SIGUIENTE:
# POR UN LADO, EL PATRÓN OBSERVER DONDE, EL SISTEMA IOT ES EL OBSERVABLE Y EL DUEÑO DEL INVERNADERO ES EL OBSERVADOR QUE
# SE SUBSCRIBE PARA RECIBIR LAS ALERTAS QUE ENVÍA EL SISTEMA A TRAVÉS DEL MÉTODO notificar_subscriptores.
# Y POR OTRO LADO, HEMOS IMPLEMENTADO/SIMULADO UN CONSUMIDOR DENTRO DEL SISTEMA QUE RECIBIRÍA DEL SERVIDOR DE KAFKA, LOS 
# EVENTOS QUE PRODUCE EL PRODUCTOR YA IMPLEMENTADO, EL SENSOR.

class IoTSystem:
    # 3) SINGLETON:
    _instance = None

    def __init__(self):
        self.strategy_handlers = [StrategyMeanStdev(), StrategyQuantiles(), StrategyMaxMin()]
        self.suscriptores = []
        self.consumer = Consumer({
            'bootstrap.servers': 'localhost:9092',
            'group.id': 'iot_system',
            'auto.offset.reset': 'earliest'
        })
        self.consumer.subscribe(['Temperaturas'])  # Suscripción del sistema al tópico(Temperaturas) donde el Sensor escribe los eventos que ocurren en el invernadero
        
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
                print(f"{s.nombre} con id: {id} fue dado de bajo en el sistema.")
            else: 
                print(f"No se ha encontrado al suscriptor con id: {id} en el sistema.")
    
    # CON ESTE MÉTODO PROCESAMOS TODOS LOS DATOS QUE NOS ENVÍA EL SENSOR Y NOS PERMITE MOSTRARLA AL SUBSCRIPTOR COMO UN EVENTO 
    # CADA VEZ QUE EL SENSOR GENERA UN DATO NUEVO:
    def procesamiento_de_datos(self, data):
        if not isinstance(data, list):
            data = [data]
        # Aplicamos cada uno de los manejadores de estrategia a los datos y almacenamos los resultados:
        strategy_results = {}
        for handler in self.strategy_handlers:
            result = handler.handle(data)
            strategy_results[type(handler).__name__] = result
        # Creamos los manejadores de la cadena de responsabilidad:
        temp_theshold_handler = TemperatureThresholdHandler()
        temp_increase_handler = TemperatureIncreaseHandler()
        # Aplicamos los manejadores de la cadena de responsabilidad a los datos:
        temp_threshold_result = temp_theshold_handler.handle(data, threshold=30)
        temp_increase_result = temp_increase_handler.handle(data)
        # Creamos un diccionario con los resultados de las estrategias y de la cadena de responsabilidad,
        # esto nos permite reunir toda la información para mostrarla como un evento cada vez que el sensor genera un dato nuevo:
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
            suscriptor.actualizar(evento) # LE PASAREMOS TODOS LOS DATOS PREPROCESADOS MEDIANTE EL MÉTODO procesamiento_de_datos()


if __name__ == '__main__':
    # Crear una instancia del sistema IoT:
    sistema = IoTSystem.obtener_instancia()

    # Añadir un suscriptor al sistema:
    dueño_invernadero = DueñoInvernadero('Modesto Mercader', '26649110E')
    sistema.dar_de_alta(dueño_invernadero)

    # Añadir algunos datos de sensores:
    sensor = Sensor(1)
    data_sensor = sensor.enviar_informacion()

    # Procesar los datos:
    for data in data_sensor:
        evento = sistema.procesamiento_de_datos(data)
        # Notificar a los suscriptores:
        sistema.notificar_suscriptores(evento)

    # Eliminar un suscriptor del sistema:
    sistema.dar_de_baja(dueño_invernadero)

    # Intentar notificar a los suscriptores de nuevo: (no debería haber ninguno)
    sistema.notificar_suscriptores(evento)