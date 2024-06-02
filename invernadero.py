from datetime import datetime
import time
import random

class ValueError(Exception):
    pass

# Definición de la clase Sensor
class Sensor:
    def __init__(self, timestamp: str, temperatura:int):
        self.timestamp = datetime.strptime(timestamp)
        self.temperatura = temperatura

class IoTSystem:
    _instance = None

    def __new__(cls):
        if cls._instance is None:
            cls._instance = super(IoTSystem, cls).__new__(cls)
            cls._instance.data = []
        return cls._instance

    def nuevos_datos(self, data):
        self.data.append(data)
        self.procesamiento_nuevos_datos()

    def procesamiento_nuevos_datos(self):
        # Filtrar los datos de los últimos 60s
        datos_ultimo_minuto = list(filter(lambda x: time.time() - x.timestamp <= 60, self.data))

        temperatura = list(map(lambda x: x.temperatura, datos_ultimo_minuto))

        # Evitamos la posibilidad de que "temperatura" sea una lista vacía
        if len(temperatura) == 0:
            raise ValueError

        temp_media = reduce(lambda a, b: a + b, temperatura) / len(temperatura)
        print(f"Temperatura media de los últimos 60 segundos: {temp_media}")
        
        # Comprobar si la temperatura media es mayor de un límite establecido
        temp_actual = self.data[-1].temperatura
        if temp_actual > 30:
            print(f"Temperatura alta")

        """ 
        Para calcular los datos de los últimos 30 segundos "temperatura" debe tener al menos dos elementos 
        para evitar un error en la comparación de temperaturas.
        """

        if len(temperatura) < 2:
            raise ValueError

        datos_treinta_segundos = list(filter(lambda x: time.time() - x.timestamp <= 30, self.data))
        if len(datos_treinta_segundos) >= 2 and datos_treinta_segundos[-1].temperatura - datos_treinta_segundos[0].temperatura > 10:
            print("La temperatura ha aumentado más de 10 grados en los últimos 30 segundos")

if __name__ == '__main__':
    iot_system = IoTSystem()
    while True:
        data = SensorData(time.time(), random.uniform(20, 40))
        iot_system.receive_data(data)
        time.sleep(5)