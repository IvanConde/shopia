-- Inicialización de la base del prototipo (patrón "base de datos por servicio",
-- resuelto en una única instancia PostgreSQL con un ESQUEMA por microservicio).
-- Cada servicio es dueño exclusivo de su esquema; las referencias entre servicios
-- son lógicas (por ID), sin FK que cruce el límite del servicio. La consistencia
-- entre esquemas se mantiene por eventos (RabbitMQ), no por integridad referencial.
--
-- Este script solo crea los esquemas vacíos. Las tablas de cada servicio las
-- creará el propio servicio (vía SQLAlchemy / migraciones) cuando se implemente.
-- Corre una única vez, al inicializar el volumen de datos por primera vez.

CREATE SCHEMA IF NOT EXISTS usuarios;       -- Servicio Usuarios  (USUARIO)
CREATE SCHEMA IF NOT EXISTS catalogo;       -- Servicio Catálogo  (CATEGORIA, PRODUCTO)
CREATE SCHEMA IF NOT EXISTS stock;          -- Servicio Stock     (STOCK)
CREATE SCHEMA IF NOT EXISTS pedidos;        -- Servicio Pedidos   (PEDIDO, ITEM_PEDIDO)
CREATE SCHEMA IF NOT EXISTS pagos;          -- Servicio Pagos     (PAGO)
CREATE SCHEMA IF NOT EXISTS anomalias;      -- IA anomalías       (ALERTA_FRAUDE)
CREATE SCHEMA IF NOT EXISTS notificaciones; -- Motor notif.       (NOTIFICACION)
