# test_invernadero.py
import pytest
from invernadero import *

def test_sensor():
    sensor = Sensor(1)
    data_generator = sensor.enviar_informacion()
    data = next(data_generator)
    assert isinstance(data, list)
    assert len(data) == 1
    assert isinstance(data[0], tuple)
    assert len(data[0]) == 2
    assert isinstance(data[0][0], str)
    assert isinstance(data[0][1], int)

def test_dueño_invernadero():
    dueño = DueñoInvernadero("John Doe", 1)
    evento = {"timestamp": "2022-01-01 00:00:00", "t": 25}
    result = dueño.actualizar(evento)
    assert result == evento

def test_iot_system():
    system = IoTSystem.obtener_instancia()
    assert system is not None
    assert isinstance(system.suscriptores, list)
    assert isinstance(system.strategy_handlers, list)

def test_strategy_handlers():
    handler = StrategyMeanStdev()
    data = [("2022-01-01 00:00:00", 25), ("2022-01-01 00:01:00", 26), ("2022-01-01 00:02:00", 27)]
    result = handler.handle(data)
    assert result is None or isinstance(result, dict)

    handler = StrategyQuantiles()
    result = handler.handle(data)
    assert result is None or isinstance(result, dict)

    handler = StrategyMaxMin()
    result = handler.handle(data)
    assert result is None or isinstance(result, dict)

def test_temperature_handlers():
    handler = TemperatureThresholdHandler()
    data = [("2022-01-01 00:00:00", 25), ("2022-01-01 00:01:00", 26), ("2022-01-01 00:02:00", 27)]
    result = handler.handle(data, threshold=30)
    assert result is None or isinstance(result, str)

    handler = TemperatureIncreaseHandler()
    result = handler.handle(data)
    assert result is None or isinstance(result, str)

