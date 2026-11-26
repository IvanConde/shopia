"""Circuit breaker mínimo para proteger llamadas a dependencias externas.

Patrón clásico de tres estados:
  * **cerrado**: las llamadas pasan; se cuentan los fallos consecutivos.
  * **abierto**: tras `umbral_fallos` fallos seguidos, se corta por `cooldown_s`
    segundos (las llamadas no se intentan: se degrada de inmediato al respaldo).
  * **medio-abierto**: vencido el cooldown, se permite una llamada de prueba; si
    tiene éxito el circuito se cierra, si falla vuelve a abrirse.

Evita golpear repetidamente a un servicio caído (p. ej. el LLM sin cuota) y hace
que la degradación sea inmediata en vez de acumular timeouts.
"""

import time


class CircuitBreaker:
    def __init__(self, umbral_fallos: int = 3, cooldown_s: float = 30.0, nombre: str = "cb"):
        self.umbral_fallos = umbral_fallos
        self.cooldown_s = cooldown_s
        self.nombre = nombre
        self._fallos = 0
        self._abierto_hasta = 0.0  # instante (monotónico) hasta el que sigue abierto

    def permite(self) -> bool:
        """True si se puede intentar la llamada (cerrado o medio-abierto)."""
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
