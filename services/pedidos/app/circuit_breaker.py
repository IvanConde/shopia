"""Circuit breaker mínimo para proteger llamadas a dependencias externas.

Patrón clásico de tres estados (cerrado → abierto → medio-abierto): tras
`umbral_fallos` fallos consecutivos se corta por `cooldown_s` segundos, evitando
golpear repetidamente a un servicio caído y haciendo que el error sea inmediato.
"""

import time


class CircuitBreaker:
    def __init__(self, umbral_fallos: int = 3, cooldown_s: float = 15.0, nombre: str = "cb"):
        self.umbral_fallos = umbral_fallos
        self.cooldown_s = cooldown_s
        self.nombre = nombre
        self._fallos = 0
        self._abierto_hasta = 0.0

    def permite(self) -> bool:
        return time.monotonic() >= self._abierto_hasta

    def registrar_exito(self) -> None:
        self._fallos = 0
        self._abierto_hasta = 0.0

    def registrar_fallo(self) -> None:
        self._fallos += 1
        if self._fallos >= self.umbral_fallos:
            self._abierto_hasta = time.monotonic() + self.cooldown_s

    @property
    def estado(self) -> str:
        if time.monotonic() < self._abierto_hasta:
            return "abierto"
        return "medio_abierto" if self._fallos else "cerrado"
