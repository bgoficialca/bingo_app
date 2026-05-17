from flask import Flask, render_template, request, send_file

from fpdf import FPDF

from random import sample

import io

import os

import tempfile

import zipfile



app = Flask(__name__)



# Carpeta base del proyecto (funciona igual en local y en la nube)

BASE_DIR = os.path.dirname(os.path.abspath(__file__))

STATIC_DIR = os.path.join(BASE_DIR, "static")

FONTS_DIR = os.path.join(BASE_DIR, "fonts")



# En Vercel/Render el disco es efímero; el PDF se guarda en carpeta temporal

USAR_TEMPORAL = bool(os.environ.get("VERCEL") or os.environ.get("RENDER"))



# Todas las celdas del cartón 5x5 (columnas B-I-N-G-O, filas 0-4)

TODAS_LAS_CELDAS = {(fila, col) for fila in range(5) for col in range(5)}

CENTRO_LIBRE = (2, 2)

NOMBRE_CARTON_LLENO = "cartón lleno"





def ruta_estatica(nombre_archivo):

    """Devuelve ruta absoluta a un archivo dentro de static/."""

    return os.path.join(STATIC_DIR, nombre_archivo)





def ruta_fuente_arial():

    """

    Localiza ArialBlackItalic sin importar mayúsculas.

    En Linux (Render) 'archivo.TTF' y 'archivo.ttf' no son el mismo archivo.

    """

    if not os.path.isdir(FONTS_DIR):

        raise FileNotFoundError(f"No existe la carpeta de fuentes: {FONTS_DIR}")

    for nombre in os.listdir(FONTS_DIR):

        if nombre.lower() == "arialblackitalic.ttf":

            return os.path.join(FONTS_DIR, nombre)

    raise FileNotFoundError("No se encontró ArialBlackItalic en fonts/")





def carpeta_para_guardar():

    """Carpeta donde se escribe el PDF según el entorno (local o nube)."""

    if USAR_TEMPORAL:

        return tempfile.gettempdir()

    descargas = os.path.join(os.path.expanduser("~"), "Downloads")

    if os.path.isdir(descargas):

        return descargas

    return os.path.expanduser("~")





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

    """Genera todos los cartones de una sola vez (misma tirada para PDF y TXT)."""

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





def carton_a_bloque_txt(numero_carton, numeros_carton):

    """Arma el bloque de texto de un cartón a partir de los mismos números que el PDF."""

    bloque = (

        "---\n\n*Cartón {}*\n| B  | I  | N  | G  | O  |\n|----|----|----|----|----|\n".format(

            numero_carton

        )

    )

    for fila in range(5):

        for letra in "BINGO":

            numero = numeros_carton[letra][fila]

            if numero == "LOGO":

                bloque += "|(BG)"

            else:

                bloque += "| {:<2} ".format(numero)

        bloque += "|\n"

    return bloque





def parsear_secuencia_numeros(texto):

    """Convierte '1, 2, 3, 4' en lista de enteros; valida formato y rango 1-75."""

    if not texto or not str(texto).strip():

        raise ValueError(

            "Debes ingresar la secuencia de números cantados (ejemplo: 1, 2, 3, 4)."

        )



    partes = [p.strip() for p in str(texto).replace(";", ",").split(",") if p.strip()]

    if not partes:

        raise ValueError(

            "La secuencia de números está vacía. Usa el formato: 1, 2, 3, 4"

        )



    numeros = []

    for parte in partes:

        try:

            numero = int(parte)

        except ValueError:

            raise ValueError(f"Valor inválido en la secuencia: '{parte}'. Solo números enteros.")

        if numero < 1 or numero > 75:

            raise ValueError(

                f"El número {numero} está fuera del rango permitido (1 a 75)."

            )

        numeros.append(numero)



    return numeros





def parsear_patron_celdas(texto):

    """

    Convierte '0,0;1,2;2,2' en conjunto de (fila, columna).

    Misma orientación que el cartón: columnas B-I-N-G-O, filas de arriba a abajo.

    """

    if not texto or not str(texto).strip():

        return set()



    celdas = set()

    for par in str(texto).split(";"):

        par = par.strip()

        if not par:

            continue

        trozos = [t.strip() for t in par.split(",")]

        if len(trozos) != 2:

            raise ValueError(

                f"Formato de patrón inválido en '{par}'. Use fila,columna separadas por punto y coma."

            )

        try:

            fila, col = int(trozos[0]), int(trozos[1])

        except ValueError:

            raise ValueError(f"Coordenadas inválidas en el patrón: '{par}'.")

        if fila < 0 or fila > 4 or col < 0 or col > 4:

            raise ValueError(

                f"La celda ({fila}, {col}) está fuera del cartón 5x5 (filas y columnas 0 a 4)."

            )

        celdas.add((fila, col))



    return celdas





def validar_configuracion_ganadores(secuencia_texto, patron1, nombre1, patron2, nombre2):

    """

    Valida secuencia, nombres obligatorios si hay patrón activo,

    y que exista al menos una forma de ganar.

    """

    secuencia = parsear_secuencia_numeros(secuencia_texto)



    modos_personalizados = []



    if patron1:

        if not nombre1:

            raise ValueError(

                "La cuadrícula 1 tiene casillas marcadas: debes escribir un nombre para esa forma de ganar."

            )

        modos_personalizados.append({"nombre": nombre1, "celdas": patron1})

    elif nombre1:

        raise ValueError(

            "Escribiste un nombre en la cuadrícula 1 pero no marcaste ninguna casilla. "

            "Marca el patrón o borra el nombre."

        )



    if patron2:

        if not nombre2:

            raise ValueError(

                "La cuadrícula 2 tiene casillas marcadas: debes escribir un nombre para esa forma de ganar."

            )

        modos_personalizados.append({"nombre": nombre2, "celdas": patron2})

    elif nombre2:

        raise ValueError(

            "Escribiste un nombre en la cuadrícula 2 pero no marcaste ninguna casilla. "

            "Marca el patrón o borra el nombre."

        )



    # Siempre se evalúa cartón lleno cuando se usa el modo txt con ganadores

    modos = modos_personalizados + [

        {"nombre": NOMBRE_CARTON_LLENO, "celdas": TODAS_LAS_CELDAS, "es_lleno": True}

    ]



    return secuencia, modos





def marcar_numero_en_carton(marcadas, numeros_carton, numero):

    """Marca en el cartón todas las celdas que contienen ese número cantado."""

    for fila in range(5):

        for col, letra in enumerate("BINGO"):

            if numeros_carton[letra][fila] == numero:

                marcadas.add((fila, col))





def patron_cumplido(marcadas, celdas_patron):

    """True si todas las celdas requeridas del patrón están marcadas."""

    return all(celda in marcadas for celda in celdas_patron)





def detectar_ganadores(secuencia_cartones, secuencia_llamados, modos):

    """

    Por cada patrón por separado: primera bola en que ese patrón tiene ganador

    y todos los cartones que ganaron ese patrón en esa misma bola.

    """

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

                    if nombre not in ganadores_en_bola:

                        ganadores_en_bola[nombre] = []

                    ganadores_en_bola[nombre].append(estado["numero"])

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





def formatear_reporte_ganadores(secuencia_llamados, modos, ganadores):

    """Un mensaje por patrón, cada uno con su propia bola de victoria."""

    lineas = ["", "========== GANADORES =========="]

    if not ganadores:

        lineas.append("No hubo ganadores con esta secuencia de números.")

        lineas.append("")

        return "\n".join(lineas)

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

    for modo in modos:

        nombre = modo["nombre"]

        if nombre not in por_patron:

            lineas.append(f"{nombre}: sin ganador en esta secuencia.")

            continue

        info = por_patron[nombre]

        bola = info["bola"]

        num = info["numero_cantado"]

        cartones_unicos = sorted(set(info["cartones"]))

        if len(cartones_unicos) == 1:

            lineas.append(

                f"{nombre} ganador cartón {cartones_unicos[0]} (bola #{bola}: {num})"

            )

        else:

            lista = ", ".join(f"cartón {c}" for c in cartones_unicos)

            lineas.append(f"{nombre} ganador {lista} (bola #{bola}: {num})")

    lineas.append("")

    return "\n".join(lineas)





def generar_pdf_personalizado(

    color_carton_hex,

    color_bingo_hex,

    color_enumeracion_hex,

    cantidad_paginas,

    version,

    text_bg,

    secuencia_cartones=None,

    bloque_ganadores="",

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



    contenido_txt = ""

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



            contenido_txt += carton_a_bloque_txt(numero_carton, numeros_carton)



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



    txt_path = None

    if text_bg == "on":

        contenido_txt += bloque_ganadores

        txt_path = os.path.join(carpeta_para_guardar(), "cartones_BG.txt")

        with open(txt_path, mode="w", encoding="utf-8") as f:

            f.write(contenido_txt)



    pdf_output = os.path.join(carpeta_para_guardar(), "cartones_BG.pdf")

    pdf.output(pdf_output)

    return pdf_output, txt_path





def crear_zip_descarga(pdf_path, txt_path):

    """Empaqueta PDF y TXT de la misma generación (misma secuencia de cartones)."""

    buffer = io.BytesIO()

    with zipfile.ZipFile(buffer, "w", zipfile.ZIP_DEFLATED) as archivo_zip:

        archivo_zip.write(pdf_path, "cartones_BG.pdf")

        archivo_zip.write(txt_path, "cartones_BG.txt")

    buffer.seek(0)

    return buffer





def _form_a_dict():

    """Guarda los valores del formulario para rellenar la plantilla si hay error."""

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

        "text_bg_checked": request.form.get("text-bg") == "on",

    }





@app.route("/", methods=["GET", "POST"])

def index():

    if request.method == "POST":

        color_carton = request.form.get("color_carton", "#fe630b")

        color_bingo = request.form.get("color_bingo", "#000000")

        color_enumeracion = request.form.get("color_enumeracion", "#000000")

        cantidad_paginas = request.form.get("cantidad_paginas", "1")

        version = request.form.get("version", "1.0")

        text_bg = request.form.get("text-bg", "off")



        secuencia_cartones = None

        bloque_ganadores = ""



        if text_bg == "on":

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

                bloque_ganadores = formatear_reporte_ganadores(

                    secuencia_llamados, modos, ganadores

                )

            except ValueError as error:

                return render_template(

                    "index.html",

                    error=str(error),

                    form=_form_a_dict(),

                )



        pdf_path, txt_path = generar_pdf_personalizado(

            color_carton,

            color_bingo,

            color_enumeracion,

            cantidad_paginas,

            version,

            text_bg,

            secuencia_cartones=secuencia_cartones,

            bloque_ganadores=bloque_ganadores,

        )



        if txt_path and os.path.isfile(txt_path):

            zip_buffer = crear_zip_descarga(pdf_path, txt_path)

            return send_file(

                zip_buffer,

                mimetype="application/zip",

                as_attachment=True,

                download_name="cartones_BG.zip",

            )



        return send_file(pdf_path, as_attachment=True, download_name="cartones_BG.pdf")



    return render_template("index.html")





if __name__ == "__main__":

    puerto = int(os.environ.get("PORT", 5001))

    debug = os.environ.get("FLASK_DEBUG", "1") == "1"

    app.run(debug=debug, host="0.0.0.0", port=puerto)


