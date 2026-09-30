"""Carga idempotente de 20 productos publicados (8 teclados, 8 pantallas, 4 televisores) vía API."""
import io
import os
import sys

import requests
from PIL import Image, ImageDraw

API = os.getenv("API_URL", "http://localhost:8080/api")

TEC = [("Teclado mecánico RGB", "USB", "US", 350), ("Teclado inalámbrico compacto", "Bluetooth", "ES", 220),
       ("Teclado gamer 60%", "USB-C", "US", 480), ("Teclado ergonómico", "USB", "ES", 300),
       ("Teclado slim multidispositivo", "Bluetooth", "US", 260), ("Teclado numérico externo", "USB", "US", 90),
       ("Teclado retroiluminado oficina", "USB", "ES", 180), ("Teclado mecánico TKL", "USB-C", "ES", 520)]
PAN = [("Monitor 24\" Full HD", 24, "1920x1080", 1250), ("Monitor 27\" QHD", 27, "2560x1440", 2100),
       ("Monitor 32\" 4K", 32, "3840x2160", 3400), ("Monitor curvo 34\" UltraWide", 34, "3440x1440", 3900),
       ("Monitor portátil 15.6\"", 15.6, "1920x1080", 1500), ("Monitor 22\" HD+", 22, "1600x900", 780),
       ("Monitor gamer 25\" 240Hz", 25, "1920x1080", 2300), ("Monitor 24\" IPS", 24, "1920x1200", 1450)]
TV = [("Televisor LED 43\"", 43, "1920x1080", 2600), ("Televisor Smart 50\" 4K", 50, "3840x2160", 3800),
      ("Televisor Smart 55\" 4K", 55, "3840x2160", 4500), ("Televisor QLED 65\"", 65, "3840x2160", 7200)]


def lista():
    out = []
    for i, (n, con, dis, pr) in enumerate(TEC, 1):
        out.append((f"LMX-TEC-{i:03d}", n, "Teclados", pr, {"conexion": con, "distribucion": dis}))
    for i, (n, pu, re, pr) in enumerate(PAN, 1):
        out.append((f"LMX-PAN-{i:03d}", n, "Pantallas", pr, {"pulgadas": pu, "resolucion": re}))
    for i, (n, pu, re, pr) in enumerate(TV, 1):
        out.append((f"LMX-TV-{i:03d}", n, "Televisores", pr, {"pulgadas": pu, "resolucion": re}))
    return out


def foto(texto, idx):
    colores = [(30, 90, 160), (20, 120, 90), (150, 60, 40), (90, 60, 140), (170, 110, 20)]
    c = colores[idx % len(colores)]
    img = Image.new("RGB", (1200, 800), c)
    d = ImageDraw.Draw(img)
    for k in range(0, 800, 40):
        d.line([(0, k), (1200, k)], fill=tuple(min(255, v + 25) for v in c))
    d.rectangle([80, 250, 1120, 550], outline="white", width=6)
    d.text((110, 360), texto, fill="white")
    d.text((110, 420), f"Lomax SA - foto de prueba #{idx + 1}", fill="white")
    b = io.BytesIO()
    img.save(b, "JPEG", quality=88)
    return b.getvalue()


def main():
    cats = {c["nombre"]: c["categoria_id"] for c in requests.get(f"{API}/categorias", timeout=30).json()}
    ok = 0
    for i, (cod, nom, cat, precio, attrs) in enumerate(lista()):
        body = {"codigo": cod, "nombre": nom, "descripcion": f"{nom}. Producto tecnológico de la categoría {cat}.",
                "precio": precio, "categoria_id": cats[cat], "atributos": attrs}
        r = requests.post(f"{API}/productos", json=body, timeout=60)
        if r.status_code == 201:
            pid = r.json()["producto_id"]
        elif r.status_code == 409:
            pid, estado = r.json()["producto_id"], r.json()["estado"]
            if estado == "PUBLICADO":
                print(f"= {cod} ya publicado (id {pid})")
                ok += 1
                continue
        else:
            print("ERROR", cod, r.status_code, r.text)
            continue
        r2 = requests.post(f"{API}/productos/{pid}/imagen", files={"imagen": (f"{cod}.jpg", foto(nom, i), "image/jpeg")}, timeout=120)
        print(f"+ {cod} id={pid} imagen -> {r2.status_code} {r2.json().get('estado') or r2.json()}")
        ok += r2.status_code == 200
    print(f"\n{ok}/20 productos publicados")
    sys.exit(0 if ok == 20 else 1)


if __name__ == "__main__":
    main()
