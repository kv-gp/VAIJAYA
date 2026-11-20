#!/usr/bin/env python3
"""Genera la configuración de los 6 equipos de la práctica integradora (Redes II).

Lee la ficha de la variante (YAML) y una topología (YAML con los nombres de
interfaces), calcula el direccionamiento y renderiza las plantillas Jinja2.

Uso:
    python generar.py                                   # Equipo fisico del laboratorio
    python generar.py --topologia datos/topologia_packet_tracer.yaml
"""
import argparse
import ipaddress
from pathlib import Path

import yaml
from jinja2 import Environment, FileSystemLoader, StrictUndefined

RAIZ = Path(__file__).parent


def cargar_yaml(ruta):
    with open(ruta, encoding="utf-8") as f:
        return yaml.safe_load(f)


def ip_n(red, n):
    """n-ésima IP utilizable de una red IPv4 (1 = primera)."""
    return str(red.network_address + n)


def rangos_excluidos(red, inicio, fin):
    """Todo lo que NO es el rango [inicio, fin] del router queda excluido."""
    excl = []
    if inicio > 1:
        excl.append((ip_n(red, 1), ip_n(red, inicio - 1)))
    ultima = red.num_addresses - 2
    if fin < ultima:
        excl.append((ip_n(red, fin + 1), ip_n(red, ultima)))
    return excl


def preparar_vlans(ficha):
    """Agrega a cada VLAN las IPs calculadas que usan las plantillas."""
    hsrp = ficha["hsrp"]
    vlans = []
    for v in ficha["vlans"]:
        red4 = ipaddress.ip_network(v["ipv4"])
        red6 = ipaddress.ip_network(v["ipv6"]) if v.get("ipv6") else None
        vlan = dict(v)
        vlan["red4"] = str(red4.network_address)
        vlan["mascara"] = str(red4.netmask)
        vlan["virtual4"] = ip_n(red4, hsrp["ip_virtual_indice"])
        vlan["grupo4"] = v["id"]
        vlan["grupo6"] = v["id"] + hsrp["offset_grupo_ipv6"]
        vlan["es_usuarios"] = not v.get("gestion", False)
        vlan["por_router"] = {}
        for nombre, r in ficha["routers"].items():
            datos = {"ipv4": ip_n(red4, r["indice"])}
            if red6:
                datos["ipv6"] = f"{red6.network_address + r['indice']}/{red6.prefixlen}".upper()
                # Cada router entrega un /80 distinto dentro del /64: nunca se repite una dirección
                base = int(red6.network_address) + (r["dhcp_v6_subred"] << 48)
                datos["pool6"] = f"{ipaddress.IPv6Address(base)}/80".upper()
            if vlan["es_usuarios"]:
                ini, fin = r["dhcp_v4"]
                datos["excluidas"] = rangos_excluidos(red4, ini, fin)
            vlan["por_router"][nombre] = datos
        vlans.append(vlan)
    return vlans


def rango_interfaz(prefijo, inicio, fin):
    return f"{prefijo}{inicio} - {fin}"


def contexto_router(nombre, ficha, topo, vlans):
    r = ficha["routers"][nombre]
    t = topo["routers"][nombre]
    serial4 = ipaddress.ip_network(ficha["serial"]["ipv4"])
    serial6 = ipaddress.ip_network(ficha["serial"]["ipv6"])
    return {
        "hostname": nombre,
        "tipo": "router",
        "lan": t["lan"],
        "vty": t["vty"],
        "link_local": r["link_local"],
        "vlans": vlans,
        "serial": {
            "interfaz": t["serial"],
            "ipv4": ip_n(serial4, r["indice"]),
            "mascara": str(serial4.netmask),
            "ipv6": f"{serial6.network_address + r['indice']}/{serial6.prefixlen}".upper(),
            "clock_rate": ficha["serial"]["clock_rate"] if ficha["serial"]["dce"] == nombre else None,
        },
    }


def contexto_switch(nombre, ficha, topo, vlans):
    t = topo["switches"][nombre]
    es_dist = t["rol"] == "distribucion"
    gestion = next(v for v in vlans if not v["es_usuarios"])
    red_gestion = ipaddress.ip_network(gestion["ipv4"])

    # EtherChannel: grupo, protocolo y modo salen de la ficha; puertos, de la topología
    ec = None
    for canal in ficha["etherchannel"]:
        for lado in ("distribucion", "acceso"):
            if canal[lado]["equipo"] == nombre:
                ec = {"grupo": canal["grupo"], "protocolo": canal["protocolo"],
                      "modo": canal[lado]["modo"], "puertos": " , ".join(t["puertos_etherchannel"])}

    # Rapid PVST+: raíz primaria = el DS conectado al router HSRP activo de la VLAN
    raiz_primaria, raiz_secundaria = [], []
    if es_dist:
        for v in vlans:
            (raiz_primaria if v["hsrp_activo"] == t["router"] else raiz_secundaria).append(str(v["id"]))

    troncales = list(t["troncales"])
    if es_dist:
        troncales.append(t["hacia_router"])

    puertos_acceso = []
    if not es_dist:
        for v in vlans:
            if v["es_usuarios"]:
                ini, fin = v["puertos_acceso"]
                puertos_acceso.append({"vlan": v["id"], "nombre": v["nombre"],
                                       "rango": rango_interfaz(t["prefijo_acceso"], ini, fin)})

    return {
        "hostname": nombre,
        "tipo": "switch",
        "rol": t["rol"],
        "vty": t["vty"],
        "vtp_modo": "server" if nombre in ficha["vtp"]["servidores"] else "client",
        "crea_vlans": ficha["vtp"]["crea_vlans"] == nombre,
        "vlans": vlans,
        "etherchannel": ec,
        "troncales": troncales,
        "vlans_permitidas": ",".join([str(v["id"]) for v in vlans] + [str(ficha["vlan_nativa"]["id"])]),
        "raiz_primaria": ",".join(raiz_primaria),
        "raiz_secundaria": ",".join(raiz_secundaria),
        "puertos_acceso": puertos_acceso,
        "sin_uso": t["sin_uso"],
        "gestion": {
            "vlan": gestion["id"],
            "ip": ip_n(red_gestion, ficha["ip_gestion_switches"][nombre]),
            "mascara": gestion["mascara"],
            "gateway": gestion["virtual4"],
        },
    }


def generar(ruta_ficha, ruta_topologia, carpeta_salida):
    ficha = cargar_yaml(ruta_ficha)
    topo = cargar_yaml(ruta_topologia)
    vlans = preparar_vlans(ficha)

    env = Environment(loader=FileSystemLoader(RAIZ / "plantillas"), undefined=StrictUndefined,
                      trim_blocks=True, lstrip_blocks=True, keep_trailing_newline=True)

    salida = Path(carpeta_salida) / topo["nombre"]
    salida.mkdir(parents=True, exist_ok=True)

    equipos = [contexto_router(n, ficha, topo, vlans) for n in topo["routers"]]
    equipos += [contexto_switch(n, ficha, topo, vlans) for n in topo["switches"]]

    archivos = []
    for eq in equipos:
        plantilla = env.get_template(f"{eq['tipo']}.j2")
        texto = plantilla.render(f=ficha, topo=topo, eq=eq)
        archivo = salida / f"{eq['hostname']}.txt"
        archivo.write_text(texto, encoding="utf-8")
        archivos.append(archivo)
        print(f"  {archivo}")
    return archivos


def main():
    p = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    p.add_argument("--ficha", default=RAIZ / "datos" / "ficha_variante_a.yaml")
    p.add_argument("--topologia", default=RAIZ / "datos" / "topologia_laboratorio.yaml")
    p.add_argument("--salida", default=RAIZ / "configs")
    args = p.parse_args()
    print("Configuraciones generadas:")
    generar(args.ficha, args.topologia, args.salida)


if __name__ == "__main__":
    main()
