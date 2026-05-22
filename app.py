from flask import Flask, redirect, render_template, request, send_file, url_for
from fpdf import FPDF
from random import randint, sample
import json
import os
import re
import secrets
import shutil
import tempfile

app = Flask(__name__)
app.secret_key = os.environ.get("FLASK_SECRET_KEY", "bingo-bg-dev-key-change-in-produccion")

BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

USAR_TEMPORAL = bool(os.environ.get("VERCEL") or os.environ.get("RENDER"))
NOMBRE_BASE_DEFAULT = "cartones_BG"
TODAS_LAS_CELDAS = {(fila, col) for fila in range(5) for col in range(5)}
CENTRO_LIBRE = (2, 2)
NOMBRE_CARTON_LLENO = "cartón lleno"


def resolver_nombre_base(texto_usuario):
    if not texto_usuario or not str(texto_usuario).strip():
        return NOMBRE_BASE_DEFAULT
    nombre = str(texto_usuario).strip()
    for extension in (".pdf", ".txt", ".zip"):
        if nombre.lower().endswith(extension):
            nombre = nombre[: -len(extension)]
    nombre = re.sub(r'[<>:"/\\|?*\x00-\x1f]', "", nombre)
    nombre = nombre.strip().strip(".")
    if not nombre:
        return NOMBRE_BASE_DEFAULT
    return nombre[:80]


def nombre_aleatorio_cartones():
    return f"cartones_BG ({randint(1, 100)})"


def letra_bola(numero):
    if 1 <= numero <= 15:
        return "B"
    if 16 <= numero <= 30:
        return "I"
    if 31 <= numero <= 45:
        return "N"
    if 46 <= numero <= 60:
        return "G"
    if 61 <= numero <= 75:
        return "O"
    return ""


def formato_bola_cantada(numero):
    return f"{letra_bola(numero)}{numero}"


def ruta_estatica(nombre_archivo):
    return os.path.join(STATIC_DIR, nombre_archivo)


def ruta_fuente_arial():
    if not os.path.isdir(FONTS_DIR):
        raise FileNotFoundError(f"No existe la carpeta de fuentes: {FONTS_DIR}")
    for nombre in os.listdir(FONTS_DIR):
        if nombre.lower() == "arialblackitalic.ttf":
            return os.path.join(FONTS_DIR, nombre)
    raise FileNotFoundError("No se encontró ArialBlackItalic en fonts/")


def carpeta_para_guardar():
    if USAR_TEMPORAL:
        return tempfile.gettempdir()
    descargas = os.path.join(os.path.expanduser("~"), "Downloads")
    if os.path.isdir(descargas):
        return descargas
    return os.path.expanduser("~")


def token_seguro(token):
    limpio = re.sub(r"[^a-zA-Z0-9_-]", "", token or "")
    return limpio[:48]


def ruta_pdf_token(token):
    return os.path.join(tempfile.gettempdir(), f"bingo_{token_seguro(token)}.pdf")


def ruta_meta_token(token):
    return os.path.join(tempfile.gettempdir(), f"bingo_{token_seguro(token)}.json")


def guardar_sesion_resultados(token, nombre_base, resumen):
    meta = {
        "nombre_base": nombre_base,
        "resumen": resumen,
    }
    with open(ruta_meta_token(token), "w", encoding="utf-8") as archivo:
        json.dump(meta, archivo, ensure_ascii=False)


def cargar_sesion_resultados(token):
    ruta = ruta_meta_token(token)
    if not os.path.isfile(ruta):
        return None
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def publicar_pdf_temporal(ruta_origen, nombre_base, resumen):
    token = secrets.token_urlsafe(16)
    destino = ruta_pdf_token(token)
    shutil.copy2(ruta_origen, destino)
    guardar_sesion_resultados(token, nombre_base, resumen)
    return token


def generar_numeros_bingo():
    bingo_carton = {"B": [], "I": [], "N": [], "G": [], "O": []}
    columnas = {
        "B": range(1, 16),
        "I": range(16, 31),
        "N": range(31, 46),
        "G": range(46, 61),
        "O": range(61, 76),
    }
    for letra in bingo_carton:
        if letra == "N":
            bingo_carton[letra] = sample(columnas[letra], 4)
            bingo_carton[letra].insert(2, "LOGO")
        else:
            bingo_carton[letra] = sample(columnas[letra], 5)
    return bingo_carton


def hex_a_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def generar_secuencia_cartones(cantidad_paginas):
    cartones = []
    for pagina in range(int(cantidad_paginas)):
        for indice in range(6):
            cartones.append(
                {
                    "numero": pagina * 6 + indice + 1,
                    "numeros": generar_numeros_bingo(),
                }
            )
    return cartones


def parsear_secuencia_numeros(texto):
    if not texto or not str(texto).strip():
        raise ValueError(
            "Debes ingresar la secuencia de números cantados (ejemplo: 1, 2, 3, 4)."
        )
    partes = [p.strip() for p in str(texto).replace(";", ",").split(",") if p.strip()]
    if not partes:
        raise ValueError("La secuencia está vacía. Usa el formato: 1, 2, 3, 4")
    numeros = []
    for parte in partes:
        try:
            numero = int(parte)
        except ValueError:
            raise ValueError(f"Valor inválido en la secuencia: '{parte}'.")
        if numero < 1 or numero > 75:
            raise ValueError(f"El número {numero} debe estar entre 1 y 75.")
        numeros.append(numero)
    return numeros


def parsear_patron_celdas(texto):
    if not texto or not str(texto).strip():
        return set()
    celdas = set()
    for par in str(texto).split(";"):
        par = par.strip()
        if not par:
            continue
        trozos = [t.strip() for t in par.split(",")]
        if len(trozos) != 2:
            raise ValueError(f"Formato de patrón inválido: '{par}'.")
        try:
            fila, col = int(trozos[0]), int(trozos[1])
        except ValueError:
            raise ValueError(f"Coordenadas inválidas: '{par}'.")
        if fila < 0 or fila > 4 or col < 0 or col > 4:
            raise ValueError(f"La celda ({fila}, {col}) está fuera del cartón 5x5.")
        celdas.add((fila, col))
    return celdas


def validar_configuracion_ganadores(secuencia_texto, patron1, nombre1, patron2, nombre2):
    secuencia = parsear_secuencia_numeros(secuencia_texto)
    modos_personalizados = []

    if patron1:
        if not nombre1:
            raise ValueError(
                "La cuadrícula 1 tiene casillas marcadas: escribe un nombre para esa forma de ganar."
            )
        modos_personalizados.append({"nombre": nombre1, "celdas": patron1})
    elif nombre1:
        raise ValueError(
            "Escribiste un nombre en la cuadrícula 1 pero no marcaste casillas."
        )

    if patron2:
        if not nombre2:
            raise ValueError(
                "La cuadrícula 2 tiene casillas marcadas: escribe un nombre para esa forma de ganar."
            )
        modos_personalizados.append({"nombre": nombre2, "celdas": patron2})
    elif nombre2:
        raise ValueError(
            "Escribiste un nombre en la cuadrícula 2 pero no marcaste casillas."
        )

    modos = modos_personalizados + [
        {"nombre": NOMBRE_CARTON_LLENO, "celdas": TODAS_LAS_CELDAS}
    ]
    return secuencia, modos


def marcar_numero_en_carton(marcadas, numeros_carton, numero):
    for fila in range(5):
        for col, letra in enumerate("BINGO"):
            if numeros_carton[letra][fila] == numero:
                marcadas.add((fila, col))


def patron_cumplido(marcadas, celdas_patron):
    return all(celda in marcadas for celda in celdas_patron)


def detectar_ganadores(secuencia_cartones, secuencia_llamados, modos):
    estados = []
    for carton in secuencia_cartones:
        estados.append(
            {
                "numero": carton["numero"],
                "numeros": carton["numeros"],
                "marcadas": {CENTRO_LIBRE},
            }
        )

    ya_registrado = set()
    modos_con_resultado = set()
    resultados_por_modo = {}

    for indice_bola, numero in enumerate(secuencia_llamados, start=1):
        ganadores_en_bola = {}
        for estado in estados:
            marcar_numero_en_carton(estado["marcadas"], estado["numeros"], numero)
            for modo in modos:
                nombre = modo["nombre"]
                if nombre in modos_con_resultado:
                    continue
                clave = (estado["numero"], nombre)
                if clave in ya_registrado:
                    continue
                if patron_cumplido(estado["marcadas"], modo["celdas"]):
                    ganadores_en_bola.setdefault(nombre, []).append(estado["numero"])
                    ya_registrado.add(clave)

        for nombre, cartones in ganadores_en_bola.items():
            if nombre not in modos_con_resultado:
                resultados_por_modo[nombre] = {
                    "bola": indice_bola,
                    "numero_cantado": numero,
                    "cartones": cartones,
                }
                modos_con_resultado.add(nombre)

    ganadores = []
    for modo in modos:
        nombre = modo["nombre"]
        if nombre not in resultados_por_modo:
            continue
        r = resultados_por_modo[nombre]
        for carton in r["cartones"]:
            ganadores.append(
                {
                    "nombre_modo": nombre,
                    "numero_carton": carton,
                    "bola": r["bola"],
                    "numero_cantado": r["numero_cantado"],
                }
            )
    return ganadores


def preparar_resumen_ganadores(modos, ganadores):
    por_patron = {}
    for g in ganadores:
        nombre = g["nombre_modo"]
        if nombre not in por_patron:
            por_patron[nombre] = {
                "bola": g["bola"],
                "numero_cantado": g["numero_cantado"],
                "cartones": [],
            }
        por_patron[nombre]["cartones"].append(g["numero_carton"])

    patrones = []
    for modo in modos:
        nombre = modo["nombre"]
        if nombre in por_patron:
            info = por_patron[nombre]
            cartones = sorted(set(info["cartones"]))
            patrones.append(
                {
                    "nombre": nombre,
                    "tiene_ganador": True,
                    "bola_etiqueta": formato_bola_cantada(info["numero_cantado"]),
                    "bola_posicion": info["bola"],
                    "cartones": cartones,
                    "un_carton": len(cartones) == 1,
                }
            )
        else:
            patrones.append(
                {
                    "nombre": nombre,
                    "tiene_ganador": False,
                }
            )

    return {
        "patrones": patrones,
        "hay_ganadores": any(p["tiene_ganador"] for p in patrones),
    }


def generar_pdf_personalizado(
    color_carton_hex,
    color_bingo_hex,
    color_enumeracion_hex,
    cantidad_paginas,
    version,
    secuencia_cartones=None,
    nombre_base=NOMBRE_BASE_DEFAULT,
):
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_font("ArialBlackItalic", "", ruta_fuente_arial())

    if version == "1.0":
        logo_path = ruta_estatica("logo_v1.png")
        watermark_path = ruta_estatica("watermark_v1.png")
    elif version == "navidad 1.0":
        logo_path = ruta_estatica("logo_v1.png")
        watermark_path = ruta_estatica("navidad_v1.png")
    elif version == "navidad 2.0":
        logo_path = ruta_estatica("logo_v2.png")
        watermark_path = ruta_estatica("navidad_v2.png")
    elif version == "halloween 1.0":
        logo_path = ruta_estatica("logo_v1.png")
        watermark_path = ruta_estatica("halloween_v1.png")
    elif version == "halloween 2.0":
        logo_path = ruta_estatica("logo_v2.png")
        watermark_path = ruta_estatica("halloween_v2.png")
    elif version == "1":
        logo_path = ruta_estatica("logo_personalizado.png")
        watermark_path = ruta_estatica("1.png")
    elif version == "2":
        logo_path = ruta_estatica("logo_personalizado.png")
        watermark_path = ruta_estatica("2.png")
    elif version == "3":
        logo_path = ruta_estatica("logo_personalizado.png")
        watermark_path = ruta_estatica("3.png")
    elif version == "4":
        logo_path = ruta_estatica("logo_personalizado.png")
        watermark_path = ruta_estatica("4.png")
    else:
        logo_path = ruta_estatica("logo_v2.png")
        watermark_path = ruta_estatica("watermark_v2.png")

    ancho_carton = 75
    alto_carton = 87
    margen_x = 20
    margen_y = 10
    espacio_vertical = 6
    espacio_horizontal = 20
    posiciones_cartones = [
        (margen_x, margen_y),
        (margen_x + ancho_carton + espacio_horizontal, margen_y),
        (margen_x, margen_y + alto_carton + espacio_vertical),
        (margen_x + ancho_carton + espacio_horizontal, margen_y + alto_carton + espacio_vertical),
        (margen_x, margen_y + 2 * (alto_carton + espacio_vertical)),
        (margen_x + ancho_carton + espacio_horizontal, margen_y + 2 * (alto_carton + espacio_vertical)),
    ]

    color_carton = hex_a_rgb(color_carton_hex)
    color_bingo = hex_a_rgb(color_bingo_hex)
    color_enumeracion = hex_a_rgb(color_enumeracion_hex)

    if secuencia_cartones is None:
        secuencia_cartones = generar_secuencia_cartones(cantidad_paginas)

    indice_carton = 0
    for pagina in range(int(cantidad_paginas)):
        pdf.add_page()
        pdf.image(watermark_path, 0, 0, 210, 297)
        for i in range(6):
            carton = secuencia_cartones[indice_carton]
            indice_carton += 1
            x, y = posiciones_cartones[i]
            numeros_carton = carton["numeros"]
            numero_carton = carton["numero"]

            pdf.set_fill_color(*color_carton)
            pdf.rect(x - 1, y - 1, ancho_carton + 2, alto_carton + 2, style="F")
            pdf.set_draw_color(*color_carton)
            pdf.set_line_width(1.5)
            pdf.set_xy(x, y + 2)
            pdf.set_font("ArialBlackItalic", "", 24)
            pdf.set_text_color(*color_bingo)
            for idx, letra in enumerate("BINGO"):
                pdf.set_xy(x + idx * 15, y + 7)
                pdf.cell(15, 10, letra, 0, 0, "C", fill=False)

            pdf.set_fill_color(255, 255, 255)
            pdf.set_text_color(0, 0, 0)
            pdf.set_draw_color(*color_carton)
            pdf.set_line_width(0.5)
            for fila in range(5):
                pdf.set_xy(x, y + 18 + fila * 12)
                for idx, letra in enumerate("BINGO"):
                    numero = numeros_carton[letra][fila]
                    if numero == "LOGO":
                        pdf.set_fill_color(255, 255, 255)
                        pdf.cell(15, 12, "", 1, 0, "C", fill=True)
                        logo_x = x + idx * 15 + 1
                        logo_y = y + 18 + fila * 12 + 1
                        pdf.image(logo_path, logo_x, logo_y, 13, 10)
                    else:
                        pdf.set_font("ArialBlackItalic", "", 20)
                        pdf.cell(15, 12, str(numero), 1, 0, "C", fill=True)

            pdf.set_xy(x, y + alto_carton - 10)
            pdf.set_font("ArialBlackItalic", "", 14)
            pdf.set_text_color(*color_enumeracion)
            pdf.cell(ancho_carton, 10, f"Cartón {numero_carton}", 0, 1, "C", fill=False)

    pdf_output = os.path.join(carpeta_para_guardar(), f"{nombre_base}.pdf")
    pdf.output(pdf_output)
    return pdf_output, nombre_base, len(secuencia_cartones)


def _form_a_dict():
    return {
        "color_carton": request.form.get("color_carton", "#fe630b"),
        "color_bingo": request.form.get("color_bingo", "#000000"),
        "color_enumeracion": request.form.get("color_enumeracion", "#000000"),
        "cantidad_paginas": request.form.get("cantidad_paginas", "1"),
        "version": request.form.get("version", "1.0"),
        "secuencia_numeros": request.form.get("secuencia_numeros", ""),
        "nombre_patron1": request.form.get("nombre_patron1", ""),
        "nombre_patron2": request.form.get("nombre_patron2", ""),
        "patron1_celdas": request.form.get("patron1_celdas", ""),
        "patron2_celdas": request.form.get("patron2_celdas", ""),
        "detectar_ganadores_checked": request.form.get("detectar-ganadores") == "on",
        "nombre_archivo": request.form.get("nombre_archivo", ""),
    }


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        color_carton = request.form.get("color_carton", "#fe630b")
        color_bingo = request.form.get("color_bingo", "#000000")
        color_enumeracion = request.form.get("color_enumeracion", "#000000")
        cantidad_paginas = request.form.get("cantidad_paginas", "1")
        version = request.form.get("version", "1.0")
        detectar_ganadores_modo = request.form.get("detectar-ganadores") == "on"
        nombre_base = resolver_nombre_base(request.form.get("nombre_archivo", ""))

        secuencia_cartones = None

        if detectar_ganadores_modo:
            try:
                patron1 = parsear_patron_celdas(request.form.get("patron1_celdas", ""))
                patron2 = parsear_patron_celdas(request.form.get("patron2_celdas", ""))
                nombre1 = request.form.get("nombre_patron1", "").strip()
                nombre2 = request.form.get("nombre_patron2", "").strip()

                secuencia_llamados, modos = validar_configuracion_ganadores(
                    request.form.get("secuencia_numeros", ""),
                    patron1,
                    nombre1,
                    patron2,
                    nombre2,
                )

                secuencia_cartones = generar_secuencia_cartones(cantidad_paginas)
                ganadores = detectar_ganadores(secuencia_cartones, secuencia_llamados, modos)
                resumen = preparar_resumen_ganadores(modos, ganadores)

                pdf_path, nombre_base, total_cartones = generar_pdf_personalizado(
                    color_carton,
                    color_bingo,
                    color_enumeracion,
                    cantidad_paginas,
                    version,
                    secuencia_cartones=secuencia_cartones,
                    nombre_base=nombre_base,
                )

                resumen["total_cartones"] = total_cartones
                resumen["secuencia_texto"] = ", ".join(str(n) for n in secuencia_llamados)

                token = publicar_pdf_temporal(pdf_path, nombre_base, resumen)
                return redirect(url_for("resultados", token=token))

            except ValueError as error:
                return render_template(
                    "index.html",
                    error=str(error),
                    form=_form_a_dict(),
                )

        pdf_path, nombre_base, _ = generar_pdf_personalizado(
            color_carton,
            color_bingo,
            color_enumeracion,
            cantidad_paginas,
            version,
            secuencia_cartones=secuencia_cartones,
            nombre_base=nombre_base,
        )
        return send_file(pdf_path, as_attachment=True, download_name=f"{nombre_base}.pdf")

    return render_template("index.html")


@app.route("/resultados/<token>")
def resultados(token):
    datos = cargar_sesion_resultados(token)
    if not datos:
        return render_template(
            "index.html",
            error="La sesión de resultados expiró. Genera los cartones de nuevo.",
        )
    return render_template(
        "resultados.html",
        token=token_seguro(token),
        nombre_base=datos["nombre_base"],
        resumen=datos["resumen"],
    )


@app.route("/descargar/<token>")
def descargar(token):
    token = token_seguro(token)
    ruta_pdf = ruta_pdf_token(token)
    datos = cargar_sesion_resultados(token)
    if not os.path.isfile(ruta_pdf) or not datos:
        return render_template(
            "index.html",
            error="El PDF ya no está disponible. Genera los cartones de nuevo.",
        )
    return send_file(
        ruta_pdf,
        as_attachment=True,
        download_name=f"{datos['nombre_base']}.pdf",
    )


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=puerto)
