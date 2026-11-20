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
│   ├── topologia_laboratorio.yaml   # Interfaces del equipo físico (C9200L-24 + C8200L) — por defecto
│   └── topologia_packet_tracer.yaml # Interfaces de la imagen de la práctica (opcional)
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

La **topología** solo tiene nombres de interfaces, tomados de `show cdp neighbors` y
`show etherchannel summary` del equipo físico:

| Equipo | Hacia router | Troncales | EtherChannel |
|---|---|---|---|
| DS1 | Gi1/0/2 → R1 Gi0/0/0 | Gi1/0/1 → AS1, Gi1/0/3 → DS2 | Po1 (Gi1/0/4-5) → AS2 |
| DS2 | Gi1/0/2 → R2 Gi0/0/0 | Gi1/0/1 → AS2, Gi1/0/3 → DS1 | Po2 (Gi1/0/4-5) → AS1 |
| AS1 | — | Gi1/0/1 → DS1 | Po2 (Gi1/0/2-3) → DS2 |
| AS2 | — | Gi1/0/1 → DS2 | Po1 (Gi1/0/2-3) → DS1 |

Como la topología está separada de la ficha, la misma ficha también genera la config
para la topología de la imagen (`topologia_packet_tracer.yaml`) sin tocar las plantillas.

## Uso

```bash
pip install -r requirements.txt

# Configuración para el equipo físico del laboratorio (por defecto)
python generar.py

# Opcional: topología de la imagen de la práctica
python generar.py --topologia datos/topologia_packet_tracer.yaml

# Pruebas
python -m pytest -q
```

Los archivos quedan en `configs/laboratorio/` (y `configs/packet_tracer/` si generan esa).

## Cómo cargarlo en el equipo físico

1. Partan de equipos limpios (`write erase`, `delete flash:vlan.dat` en los switches y `reload`).
2. Conéctense por consola (PuTTY / Tera Term) y peguen cada archivo de `configs/laboratorio/` en este orden:
   1. **DS1** primero: es el servidor VTP que crea las VLANs.
   2. **DS2**, luego **AS1** y **AS2** (aprenden las VLANs por VTP).
   3. **R1** y **R2**.
3. Peguen por bloques (cada sección `! ===== Paso ... =====`) o configuren un retardo entre líneas
   en la terminal: por consola a 9600 baudios, un pegado muy largo puede perder caracteres.

Para la demostración: `show etherchannel summary`, `show interfaces trunk`, `show vlan brief`,
`show standby brief`, `show spanning-tree vlan 10`, `show ip dhcp binding`, `show ipv6 dhcp binding`.

## Notas

- Las contraseñas de `credenciales` deben tener 10 caracteres o más: el script se detiene con un error si alguna es más corta.
- Verifiquen el nombre del puerto serial (`Serial0/1/0`) con `show ip interface brief` en R1 y R2.
- Si el equipo ya tiene llaves RSA, `crypto key generate rsa` pregunta si reemplazarlas: respondan `yes`.
- Si su versión de IOS XE no acepta llaves de 1024 bits, cambien `ssh.modulo_rsa` a 2048 en la ficha y regeneren.
