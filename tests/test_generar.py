"""Pruebas: verifican que las configs generadas cumplen la ficha de la variante A.

Ejecutar con:  python -m pytest -q
"""
import sys
from pathlib import Path

import pytest

RAIZ = Path(__file__).resolve().parent.parent
sys.path.insert(0, str(RAIZ))
import generar  # noqa: E402

FICHA = RAIZ / "datos" / "ficha_variante_a.yaml"


@pytest.fixture(scope="module", params=["topologia_packet_tracer.yaml", "topologia_laboratorio.yaml"])
def cfg(request, tmp_path_factory):
    salida = tmp_path_factory.mktemp("configs")
    archivos = generar.generar(FICHA, RAIZ / "datos" / request.param, salida)
    return {a.stem: a.read_text() for a in archivos}


def test_seis_equipos(cfg):
    assert sorted(cfg) == ["AS1", "AS2", "DS1", "DS2", "R1", "R2"]


def test_hsrp_activo_segun_ficha(cfg):
    # R1 activo en 10, 20, 99; R2 activo en 30, 40 (prioridad 150 + preempt)
    for grupo in (10, 1010, 20, 1020, 99):
        assert f"standby {grupo} priority 150" in cfg["R1"]
        assert f"standby {grupo} priority 150" not in cfg["R2"]
    for grupo in (30, 1030, 40, 1040):
        assert f"standby {grupo} priority 150" in cfg["R2"]
        assert f"standby {grupo} priority 150" not in cfg["R1"]


def test_dhcp_rangos_sin_traslape(cfg):
    assert "ip dhcp excluded-address 192.168.10.131 192.168.10.254" in cfg["R1"]
    assert "ip dhcp excluded-address 192.168.10.1 192.168.10.20" in cfg["R1"]
    assert "ip dhcp excluded-address 192.168.10.1 192.168.10.130" in cfg["R2"]
    assert "default-router 192.168.10.3" in cfg["R1"]
    assert "default-router 192.168.10.3" in cfg["R2"]


def test_dhcpv6_pools_distintos(cfg):
    assert "address prefix 2001:A:B:10:1::/80" in cfg["R1"]
    assert "address prefix 2001:A:B:10:2::/80" in cfg["R2"]


def test_raiz_stp_alineada_con_hsrp(cfg):
    assert "spanning-tree vlan 10,20,99 root primary" in cfg["DS1"]
    assert "spanning-tree vlan 30,40 root primary" in cfg["DS2"]
    for sw in ("DS1", "DS2", "AS1", "AS2"):
        assert "spanning-tree mode rapid-pvst" in cfg[sw]


def test_vlans_solo_en_un_servidor(cfg):
    assert "name VENTAS" in cfg["DS1"]
    for sw in ("DS2", "AS1", "AS2"):
        assert "name VENTAS" not in cfg[sw]


def test_etherchannel_modos(cfg):
    assert "channel-group 1 mode active" in cfg["DS1"]
    assert "channel-group 1 mode passive" in cfg["AS2"]
    assert "channel-group 2 mode desirable" in cfg["DS2"]
    assert "channel-group 2 mode auto" in cfg["AS1"]


def test_ip_gestion(cfg):
    for sw, ip in {"DS1": 11, "DS2": 12, "AS1": 13, "AS2": 14}.items():
        assert f"ip address 192.168.99.{ip} 255.255.255.0" in cfg[sw]
        assert "ip default-gateway 192.168.99.3" in cfg[sw]


def test_serial_reloj_solo_en_r1(cfg):
    assert "clock rate 128000" in cfg["R1"]
    assert "clock rate" not in cfg["R2"]
