from flask import Flask, render_template, request, send_file
from fpdf import FPDF
from random import sample
import os
import tempfile

app = Flask(__name__)

# Carpeta base del proyecto (funciona igual en local y en la nube)
BASE_DIR = os.path.dirname(os.path.abspath(__file__))
STATIC_DIR = os.path.join(BASE_DIR, "static")
FONTS_DIR = os.path.join(BASE_DIR, "fonts")

# En Vercel/Render el disco es efímero; el PDF se guarda en carpeta temporal
USAR_TEMPORAL = bool(os.environ.get("VERCEL") or os.environ.get("RENDER"))


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
    # En Windows la carpeta Descargas suele llamarse Downloads
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
            bingo_carton[letra].insert(2, "LOGO")  # Logo en la casilla central
        else:
            bingo_carton[letra] = sample(columnas[letra], 5)

    return bingo_carton


def hex_a_rgb(hex_color):
    hex_color = hex_color.lstrip("#")
    return tuple(int(hex_color[i : i + 2], 16) for i in (0, 2, 4))


def generar_pdf_personalizado(
    color_carton_hex, color_bingo_hex, color_enumeracion_hex, cantidad_paginas, version, text_bg
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
    file = ""

    for pagina in range(int(cantidad_paginas)):
        pdf.add_page()
        pdf.image(watermark_path, 0, 0, 210, 297)

        for i in range(6):
            x, y = posiciones_cartones[i]
            numeros_carton = generar_numeros_bingo()

            file += "---\n\n*Cartón {}*\n| B  | I  | N  | G  | O  |\n|----|----|----|----|----|\n".format(
                pagina * 6 + i + 1
            )

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
                        file += "|(BG)"
                    else:
                        pdf.set_font("ArialBlackItalic", "", 20)
                        pdf.cell(15, 12, str(numero), 1, 0, "C", fill=True)
                        file += "| {:<2} ".format(numero)
                file += "|\n"

            pdf.set_xy(x, y + alto_carton - 10)
            pdf.set_font("ArialBlackItalic", "", 14)
            pdf.set_text_color(*color_enumeracion)
            pdf.cell(ancho_carton, 10, f"Cartón {pagina * 6 + i + 1}", 0, 1, "C", fill=False)

    if text_bg == "on":
        txt_path = os.path.join(carpeta_para_guardar(), "cartones_BG.txt")
        with open(txt_path, mode="w", encoding="utf-8") as f:
            f.write(file)

    pdf_output = os.path.join(carpeta_para_guardar(), "cartones_BG.pdf")
    pdf.output(pdf_output)
    return pdf_output


@app.route("/", methods=["GET", "POST"])
def index():
    if request.method == "POST":
        color_carton = request.form.get("color_carton", "#fe630b")
        color_bingo = request.form.get("color_bingo", "#000000")
        color_enumeracion = request.form.get("color_enumeracion", "#000000")
        cantidad_paginas = request.form.get("cantidad_paginas", "1")
        version = request.form.get("version", "1.0")
        text_bg = request.form.get("text-bg", "off")

        pdf_path = generar_pdf_personalizado(
            color_carton, color_bingo, color_enumeracion, cantidad_paginas, version, text_bg
        )
        return send_file(pdf_path, as_attachment=True, download_name="cartones_BG.pdf")

    return render_template("index.html")


if __name__ == "__main__":
    puerto = int(os.environ.get("PORT", 5001))
    debug = os.environ.get("FLASK_DEBUG", "1") == "1"
    app.run(debug=debug, host="0.0.0.0", port=puerto)
