# Automatización — Práctica integradora Redes II (Variante A · ViajaYa)

Bono de automatización: un script en Python lee un YAML con los datos de la ficha
y genera con plantillas Jinja2 la configuración de los 6 equipos (R1, R2, DS1, DS2, AS1, AS2).

**Equipo:** Sarah Raygoza Alfaro · Mariana Hernández Guzmán · Samuel López González · Kevin Guadalupe Díaz Rubio

## Estructura

```
viajaya-automatizacion/
├── generar.py                       # Script principal
├── datos/
│   ├── ficha_variante_a.yaml        # Datos de la ficha (VLANs, IPs, HSRP, DHCP, VTP, SSH...)
│   ├── topologia_packet_tracer.yaml # Interfaces de la imagen (2960 + ISR4321)
│   └── topologia_laboratorio.yaml   # Interfaces del equipo físico (C9200L + C8200L)
├── plantillas/
│   ├── base.j2                      # Pasos 1 y 9 (comunes a los 6 equipos)
│   ├── router.j2                    # Pasos 6 y 7 (subinterfaces, HSRPv2, serial, DHCPv4/v6)
│   └── switch.j2                    # Pasos 2-5, 8 y 10 (EtherChannel, troncales, VTP, VLANs, STP, port-security)
├── configs/                         # Salida generada (una carpeta por topología)
└── tests/test_generar.py            # Verifica que la salida cumple la ficha
```

La **ficha** solo tiene los datos de la variante; el script calcula todo lo demás:

- 1.ª/2.ª IP utilizable para R1/R2 y la 3.ª para la IP virtual HSRP.
- Rangos `ip dhcp excluded-address` para que cada router solo entregue su rango (R1 .21–.130, R2 .131–.254).
- Pools DHCPv6 que no se traslapan: R1 entrega `2001:A:B:<vlan>:1::/80` y R2 `2001:A:B:<vlan>:2::/80`.
- Raíz de Rapid PVST+: el switch de distribución conectado al router HSRP activo de cada VLAN es primario, el otro secundario.
- Grupo HSRP IPv6 = VLAN + 1000, prioridad 150 y `preempt` solo en el router activo.

La **topología** solo tiene nombres de interfaces. Así la misma ficha genera la config
para Packet Tracer o para el equipo físico sin tocar las plantillas.

## Uso

```bash
pip install -r requirements.txt

# Configuración para Packet Tracer (por defecto)
python generar.py

# Configuración para el equipo físico del laboratorio
python generar.py --topologia datos/topologia_laboratorio.yaml

# Pruebas
python -m pytest -q
```

Los archivos quedan en `configs/packet_tracer/` y `configs/laboratorio/`.

## Cómo cargarlo en Packet Tracer

Peguen cada archivo en la pestaña **CLI** del equipo, en este orden:

1. **DS1** primero: es el servidor VTP que crea las VLANs.
2. **DS2**, luego **AS1** y **AS2** (aprenden las VLANs por VTP).
3. **R1** y **R2**.

Para la demostración: `show etherchannel summary`, `show interfaces trunk`, `show vlan brief`,
`show standby brief`, `show spanning-tree vlan 10`, `show ip dhcp binding`, `show ipv6 dhcp binding`.

## Notas

- Las contraseñas de `credenciales` en la ficha son de ejemplo (≥ 10 caracteres). Cámbienlas por las suyas.
- Verifiquen el nombre del puerto serial (`Serial0/1/0`) en su `.pkt` y en el router físico.
- Packet Tracer no acepta `enable algorithm-type scrypt`; por eso la topología de PT usa `enable secret`.
