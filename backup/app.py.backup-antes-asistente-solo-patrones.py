from flask import Flask, redirect, render_template, request, send_file, url_for, jsonify
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
RANGOS_COLUMNA = {
    "B": list(range(1, 16)),
    "I": list(range(16, 31)),
    "N": list(range(31, 46)),
    "G": list(range(46, 61)),
    "O": list(range(61, 76)),
}
CANTIDAD_POR_COLUMNA = {"B": 5, "I": 5, "N": 4, "G": 5, "O": 5}
TIPO_PATRON_CUADRO = "cuadro"
TIPO_PATRON_LINEA = "linea"
TIPO_PATRON_LLENO = "lleno"
ORDEN_TIPOS_PATRON = {
    TIPO_PATRON_CUADRO: 0,
    TIPO_PATRON_LINEA: 1,
    TIPO_PATRON_LLENO: 2,
}


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


def resolver_recursos_version(version):
    """Devuelve rutas de logo y marca de agua según la versión del diseño (PDF y vista previa)."""
    if version == "1.0":
        return ruta_estatica("logo_v1.png"), ruta_estatica("watermark_v1.png")
    if version == "navidad 1.0":
        return ruta_estatica("logo_v1.png"), ruta_estatica("navidad_v1.png")
    if version == "navidad 2.0":
        return ruta_estatica("logo_v2.png"), ruta_estatica("navidad_v2.png")
    if version == "halloween 1.0":
        return ruta_estatica("logo_v1.png"), ruta_estatica("halloween_v1.png")
    if version == "halloween 2.0":
        return ruta_estatica("logo_v2.png"), ruta_estatica("halloween_v2.png")
    if version == "1":
        return ruta_estatica("logo_personalizado.png"), ruta_estatica("1.png")
    if version == "2":
        return ruta_estatica("logo_personalizado.png"), ruta_estatica("2.png")
    if version == "3":
        return ruta_estatica("logo_personalizado.png"), ruta_estatica("3.png")
    if version == "4":
        return ruta_estatica("logo_personalizado.png"), ruta_estatica("4.png")
    if version == "2.0":
        return ruta_estatica("logo_v2.png"), ruta_estatica("watermark_v2.png")
    return ruta_estatica("logo_v2.png"), ruta_estatica("watermark_v2.png")


def recursos_version_para_web(version):
    """Rutas relativas de assets para la plantilla HTML."""
    logo_path, watermark_path = resolver_recursos_version(version)
    return {
        "logo": "static/" + os.path.basename(logo_path),
        "watermark": "static/" + os.path.basename(watermark_path),
    }


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


def guardar_sesion_resultados(token, nombre_base, resumen, regenerar=None):
    meta = {
        "nombre_base": nombre_base,
        "resumen": resumen,
    }
    if regenerar:
        meta["regenerar"] = regenerar
    with open(ruta_meta_token(token), "w", encoding="utf-8") as archivo:
        json.dump(meta, archivo, ensure_ascii=False)


def cargar_sesion_resultados(token):
    ruta = ruta_meta_token(token)
    if not os.path.isfile(ruta):
        return None
    with open(ruta, "r", encoding="utf-8") as archivo:
        return json.load(archivo)


def publicar_pdf_temporal(ruta_origen, nombre_base, resumen, regenerar=None):
    token = secrets.token_urlsafe(16)
    destino = ruta_pdf_token(token)
    shutil.copy2(ruta_origen, destino)
    guardar_sesion_resultados(token, nombre_base, resumen, regenerar=regenerar)
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


def generar_secuencia_cartones_total(total_cartones):
    """Genera una lista exacta de cartones (sin rellenar la última página con extras)."""
    total = int(total_cartones)
    if total < 1:
        raise ValueError("Debes generar al menos 1 cartón.")
    return [
        {"numero": indice + 1, "numeros": generar_numeros_bingo()}
        for indice in range(total)
    ]


def columna_de_numero(numero):
    """Devuelve la columna B-I-N-G-O a la que pertenece un número."""
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
    return None


def numeros_en_carton(numeros_carton):
    """Lista los números reales de un cartón (sin el centro LOGO)."""
    resultado = []
    for letra in "BINGO":
        for valor in numeros_carton[letra]:
            if valor != "LOGO":
                resultado.append(valor)
    return resultado


def construir_estructura_carton(mapa_columnas):
    """Arma el diccionario BINGO ordenado e inserta LOGO en la columna N."""
    numeros = {}
    for letra in "BINGO":
        columna = sorted(mapa_columnas[letra])
        if letra == "N":
            columna.insert(2, "LOGO")
        numeros[letra] = columna
    return numeros


def conteo_columnas_factible(conjunto_numeros):
    """Verifica si un conjunto de 24 números puede distribuirse en las columnas del bingo."""
    conteo = {letra: 0 for letra in "BINGO"}
    for numero in conjunto_numeros:
        letra = columna_de_numero(numero)
        if letra is None:
            return False
        conteo[letra] += 1
    return all(conteo[letra] == CANTIDAD_POR_COLUMNA[letra] for letra in "BINGO")


def asignar_numeros_a_columnas(conjunto_numeros):
    """
    Distribuye exactamente 24 números en columnas válidas mediante backtracking.
    Retorna la estructura del cartón o None si no hay forma válida.
    """
    numeros_ordenados = sorted(conjunto_numeros)
    mapa = {letra: [] for letra in "BINGO"}

    def backtrack(indice):
        if indice == len(numeros_ordenados):
            for letra in "BINGO":
                if len(mapa[letra]) != CANTIDAD_POR_COLUMNA[letra]:
                    return None
            return construir_estructura_carton(mapa)

        numero = numeros_ordenados[indice]
        letra = columna_de_numero(numero)
        if len(mapa[letra]) >= CANTIDAD_POR_COLUMNA[letra]:
            return None
        mapa[letra].append(numero)
        resultado = backtrack(indice + 1)
        if resultado is not None:
            return resultado
        mapa[letra].pop()
        return None

    return backtrack(0)


def asignacion_desde_carton(numeros_carton):
    """Mapa (fila, col) → número a partir de un cartón ya construido."""
    asignacion = {}
    for fila in range(5):
        for col in range(5):
            if (fila, col) == CENTRO_LIBRE:
                continue
            asignacion[(fila, col)] = numero_en_celda(numeros_carton, fila, col)
    return asignacion


def carton_respeta_fijas(numeros_carton, fijas):
    """True si el cartón mantiene intactas las casillas ya fijadas en fases anteriores."""
    for (fila, col), numero in fijas.items():
        if numero_en_celda(numeros_carton, fila, col) != numero:
            return False
    return True


def simular_bola_patron_desde_asignacion(asignacion, secuencia, celdas_patron):
    """
    Simula en qué bola se completa el patrón usando solo las casillas ya asignadas
    (asistente: el resto del cartón sigue en blanco hasta la generación del PDF).
    """
    if celdas_patron == TODAS_LAS_CELDAS:
        celdas_lista = [
            (fila, col)
            for fila in range(5)
            for col in range(5)
            if (fila, col) != CENTRO_LIBRE
        ]
    else:
        celdas_lista = celdas_patron_sin_centro(celdas_patron)

    if not all(celda in asignacion for celda in celdas_lista):
        return None, None

    numeros_map = {asignacion[celda]: celda for celda in celdas_lista}
    marcadas = {CENTRO_LIBRE}

    for indice, numero in enumerate(secuencia, start=1):
        if numero in numeros_map:
            marcadas.add(numeros_map[numero])
        if patron_cumplido(marcadas, celdas_patron):
            return indice, numero
    return None, None


def celdas_a_congelar_de_plan(plan):
    """Casillas que fija una modalidad ganadora (solo el patrón, no todo el cartón)."""
    if plan["celdas_patron"] == TODAS_LAS_CELDAS:
        return [
            (fila, col)
            for fila in range(5)
            for col in range(5)
            if (fila, col) != CENTRO_LIBRE
        ]
    return celdas_patron_sin_centro(plan["celdas_patron"])


def generar_asignacion_patron_con_fijas(
    secuencia, bola_ganadora, celdas_patron, fijas, intentos=300, solo_casillas_patron=False
):
    """
    Asigna números a las casillas del patrón respetando celdas ya fijadas
    en fases previas (mismo cartón, otra modalidad).
    solo_casillas_patron=True: no exige rellenar el cartón (solo asistente).
    """
    if celdas_patron == TODAS_LAS_CELDAS:
        return generar_asignacion_lleno_con_fijas(
            secuencia, bola_ganadora, fijas, intentos, solo_casillas_patron=solo_casillas_patron
        )

    celdas = celdas_patron_sin_centro(celdas_patron)
    prefijo = secuencia[:bola_ganadora]
    numero_cierre = secuencia[bola_ganadora - 1]
    posiciones = primera_posicion_en_prefijo(prefijo)
    if numero_cierre not in posiciones:
        return None

    posicion_cierre = posiciones[numero_cierre]
    pool = [numero for numero, pos in posiciones.items() if pos <= posicion_cierre]
    letra_cierre = columna_de_numero(numero_cierre)
    celdas_cierre = [
        celda
        for celda in celdas
        if letra_de_celda(celda[0], celda[1]) == letra_cierre
    ]
    if not celdas_cierre:
        return None

    for _ in range(intentos):
        asignacion = dict(fijas)
        celda_cierre = sample(celdas_cierre, 1)[0]
        if celda_cierre in asignacion:
            if asignacion[celda_cierre] != numero_cierre:
                continue
        else:
            asignacion[celda_cierre] = numero_cierre

        otras = [c for c in celdas if c != celda_cierre]
        pendientes = []
        valido = True
        for celda in otras:
            if celda in asignacion:
                if (
                    asignacion[celda] not in pool
                    or posiciones[asignacion[celda]] > posicion_cierre
                ):
                    valido = False
                    break
            else:
                pendientes.append(celda)
        if not valido:
            continue

        if pendientes and not asignar_celdas_patron_recursivo(
            pendientes, pool, asignacion, posiciones, posicion_cierre
        ):
            continue

        if solo_casillas_patron:
            bola_real, _ = simular_bola_patron_desde_asignacion(
                asignacion, secuencia, celdas_patron
            )
            if bola_real == bola_ganadora:
                return asignacion
            continue

        carton = completar_carton_desde_asignacion(asignacion)
        if carton is None:
            continue
        if ultima_bola_patron(carton, secuencia, celdas_patron, bola_ganadora) != bola_ganadora:
            continue
        return asignacion

    return None


def generar_asignacion_lleno_con_fijas(
    secuencia, bola_ganadora, fijas, intentos=300, solo_casillas_patron=False
):
    """Completa cartón lleno en la bola indicada respetando casillas congeladas."""
    prefijo = secuencia[:bola_ganadora]
    numero_cierre = secuencia[bola_ganadora - 1]
    posiciones = primera_posicion_en_prefijo(prefijo)
    if numero_cierre not in posiciones:
        return None

    posicion_cierre = posiciones[numero_cierre]
    pool = [numero for numero, pos in posiciones.items() if pos <= posicion_cierre]
    letra_cierre = columna_de_numero(numero_cierre)
    todas = [
        (fila, col)
        for fila in range(5)
        for col in range(5)
        if (fila, col) != CENTRO_LIBRE
    ]

    for _ in range(intentos):
        asignacion = dict(fijas)
        usados = set(asignacion.values())

        if any(
            asignacion.get(celda) == numero_cierre
            for celda in asignacion
            if letra_de_celda(celda[0], celda[1]) == letra_cierre
        ):
            celda_cierre = next(
                celda
                for celda in asignacion
                if asignacion[celda] == numero_cierre
                and letra_de_celda(celda[0], celda[1]) == letra_cierre
            )
        else:
            libres_cierre = [
                celda
                for celda in todas
                if celda not in asignacion
                and letra_de_celda(celda[0], celda[1]) == letra_cierre
            ]
            if not libres_cierre:
                continue
            celda_cierre = sample(libres_cierre, 1)[0]
            asignacion[celda_cierre] = numero_cierre
            usados.add(numero_cierre)

        libres = [celda for celda in todas if celda not in asignacion]
        for celda in libres:
            letra = letra_de_celda(celda[0], celda[1])
            opciones = [
                n
                for n in pool
                if n not in usados
                and columna_de_numero(n) == letra
            ]
            if not opciones:
                break
            numero = sample(opciones, 1)[0]
            asignacion[celda] = numero
            usados.add(numero)
        else:
            if solo_casillas_patron:
                bola_real, _ = simular_bola_patron_desde_asignacion(
                    asignacion, secuencia, TODAS_LAS_CELDAS
                )
                if bola_real == bola_ganadora:
                    return asignacion
                continue
            carton = completar_carton_desde_asignacion(asignacion)
            if carton is None:
                continue
            if (
                ultima_bola_patron(carton, secuencia, TODAS_LAS_CELDAS, bola_ganadora)
                == bola_ganadora
            ):
                return asignacion

    return None


def fijas_de_planes_anteriores(carton_actual, planes_previos):
    """
    Casillas que no deben cambiar: solo las que pertenecen a modalidades ya acordadas.
    El resto del cartón puede reorganizarse en fases posteriores.
    """
    celdas_congeladas = set()
    for plan in planes_previos:
        if plan["celdas_patron"] == TODAS_LAS_CELDAS:
            for fila in range(5):
                for col in range(5):
                    if (fila, col) != CENTRO_LIBRE:
                        celdas_congeladas.add((fila, col))
        else:
            celdas_congeladas.update(celdas_patron_sin_centro(plan["celdas_patron"]))

    asignacion = asignacion_desde_carton(carton_actual)
    return {celda: asignacion[celda] for celda in celdas_congeladas if celda in asignacion}


def extender_carton_para_patron(
    secuencia,
    carton_actual,
    plan,
    planes_carton,
    ganadores_config,
    intentos_globales=80,
    intentos_patron=200,
):
    """
    Añade una modalidad ganadora a un cartón ya iniciado en fases anteriores.
    Solo congelan las casillas de patrones previos; el relleno puede reorganizarse.
    """
    planes_previos = [
        p
        for p in planes_carton
        if ORDEN_TIPOS_PATRON[p["tipo_patron"]] < ORDEN_TIPOS_PATRON[plan["tipo_patron"]]
    ]
    fijas = fijas_de_planes_anteriores(carton_actual, planes_previos)
    ultimo_error = None

    for _ in range(intentos_globales):
        try:
            if plan["celdas_patron"] == TODAS_LAS_CELDAS:
                asignacion = generar_asignacion_lleno_con_fijas(
                    secuencia, plan["bola"], fijas, intentos=intentos_patron
                )
                if not asignacion:
                    continue
                carton = completar_carton_desde_asignacion(asignacion)
                if carton is None:
                    continue
            else:
                asignacion = generar_asignacion_patron_con_fijas(
                    secuencia,
                    plan["bola"],
                    plan["celdas_patron"],
                    fijas,
                    intentos=intentos_patron,
                )
                if not asignacion:
                    continue
                carton = completar_carton_desde_asignacion(asignacion)
                if carton is None:
                    continue

            if not carton_cumple_planes_ganador(secuencia, carton, planes_carton):
                continue

            restricciones = restricciones_para_carton(
                ganadores_config, plan["numero_carton"]
            )
            if not carton_valido_como_perdedor(carton, secuencia, restricciones):
                continue
            return carton
        except ValueError as error:
            ultimo_error = error

    mensaje = (
        f"No se pudo ampliar el cartón {plan['numero_carton']} "
        f"para {plan['nombre_patron']} en la bola {plan['bola']} "
        "sin romper las modalidades anteriores."
    )
    if ultimo_error:
        mensaje += f" Detalle: {ultimo_error}"
    raise ValueError(mensaje)


def construir_carton_ganador_secuencial(
    secuencia,
    numero_carton,
    planes_carton,
    ganadores_config,
    intentos_globales=80,
    intentos_patron=200,
):
    """
    Construye un cartón ganador fase por fase: Patrón 1 → Patrón 2 → lleno.
    Cada fase fija casillas; las siguientes solo amplían sin tocar lo ya acordado.
    """
    planes = ordenar_ganadores_dirigidos(planes_carton)
    carton = None
    acumulados = []

    for plan in planes:
        acumulados.append(plan)
        if carton is None:
            carton = generar_carton_ganador_dirigido(
                secuencia,
                plan,
                ganadores_config,
                intentos_globales=intentos_globales,
                intentos_patron=intentos_patron,
            )
        else:
            carton = extender_carton_para_patron(
                secuencia,
                carton,
                plan,
                acumulados,
                ganadores_config,
                intentos_globales=intentos_globales,
                intentos_patron=intentos_patron,
            )
    return carton


def celdas_patron_sin_centro(celdas_patron):
    """Casillas del patrón que requieren un número (excluye el centro libre)."""
    return [celda for celda in celdas_patron if celda != CENTRO_LIBRE]


def primera_posicion_en_prefijo(prefijo):
    """Mapa número → índice de su primera aparición en el prefijo de la secuencia."""
    posiciones = {}
    for indice, numero in enumerate(prefijo):
        if numero not in posiciones:
            posiciones[numero] = indice
    return posiciones


def letra_de_celda(fila, col):
    return "BINGO"[col]


def numero_en_celda(numeros_carton, fila, col):
    return numeros_carton[letra_de_celda(fila, col)][fila]


def asignar_celdas_patron_recursivo(
    celdas_pendientes, pool, asignacion, posiciones, posicion_maxima
):
    """Backtracking: asigna números del pool a celdas del patrón respetando columnas."""
    if not celdas_pendientes:
        return True

    fila, col = celdas_pendientes[0]
    letra = letra_de_celda(fila, col)
    usados = set(asignacion.values())
    candidatos = [
        numero
        for numero in pool
        if numero not in usados
        and columna_de_numero(numero) == letra
        and posiciones[numero] <= posicion_maxima
    ]

    for numero in sample(candidatos, len(candidatos)):
        asignacion[(fila, col)] = numero
        if asignar_celdas_patron_recursivo(
            celdas_pendientes[1:], pool, asignacion, posiciones, posicion_maxima
        ):
            return True
        del asignacion[(fila, col)]
    return False


def completar_carton_desde_asignacion(asignacion_celdas):
    """
    Completa un cartón válido a partir de celdas ya asignadas (patrón ganador).
    asignacion_celdas: dict (fila, col) → número
    """
    mapa = {letra: [] for letra in "BINGO"}
    for (fila, col), numero in asignacion_celdas.items():
        mapa[letra_de_celda(fila, col)].append(numero)

    for letra in "BINGO":
        faltantes = CANTIDAD_POR_COLUMNA[letra] - len(mapa[letra])
        if faltantes < 0:
            return None
        if faltantes == 0:
            continue
        usados = set(mapa[letra])
        disponibles = [n for n in RANGOS_COLUMNA[letra] if n not in usados]
        if len(disponibles) < faltantes:
            return None
        mapa[letra].extend(sample(disponibles, faltantes))

    return construir_estructura_carton(mapa)


def ultima_bola_patron(numeros_carton, secuencia, celdas_patron, limite_bola):
    """Última bola (≤ limite) en que se marca alguna casilla del patrón."""
    numeros_patron = set()
    for fila, col in celdas_patron:
        if (fila, col) == CENTRO_LIBRE:
            continue
        numeros_patron.add(numero_en_celda(numeros_carton, fila, col))

    ultima = 0
    for indice, numero in enumerate(secuencia[:limite_bola], start=1):
        if numero in numeros_patron:
            ultima = indice
    return ultima


def generar_carton_ganador_patron(secuencia, bola_ganadora, celdas_patron, intentos=3000):
    """
    Construye un cartón que completa el patrón indicado exactamente en la bola pedida.
    Funciona para cuadro, línea o cartón lleno.
    """
    celdas = celdas_patron_sin_centro(celdas_patron)
    minimo_bolas = len(celdas)
    if celdas_patron == TODAS_LAS_CELDAS:
        minimo_bolas = 24

    if bola_ganadora < minimo_bolas:
        raise ValueError(
            f"El patrón necesita al menos {minimo_bolas} bolas; indicaste la bola {bola_ganadora}."
        )
    if bola_ganadora > len(secuencia):
        raise ValueError(
            f"La bola {bola_ganadora} supera la longitud de la secuencia ({len(secuencia)})."
        )

    prefijo = secuencia[:bola_ganadora]
    numero_cierre = secuencia[bola_ganadora - 1]
    posiciones = primera_posicion_en_prefijo(prefijo)

    if numero_cierre not in posiciones:
        raise ValueError(
            f"El número de cierre {numero_cierre} no aparece antes de la bola {bola_ganadora}."
        )

    posicion_cierre = posiciones[numero_cierre]
    pool = [numero for numero, pos in posiciones.items() if pos <= posicion_cierre]
    letra_cierre = columna_de_numero(numero_cierre)

    celdas_cierre = [
        celda
        for celda in celdas
        if letra_de_celda(celda[0], celda[1]) == letra_cierre
    ]
    if not celdas_cierre:
        raise ValueError(
            f"En la bola {bola_ganadora} sale el {numero_cierre} (columna {letra_cierre}), "
            "pero ninguna casilla del patrón pertenece a esa columna."
        )

    if celdas_patron == TODAS_LAS_CELDAS:
        for _ in range(intentos):
            elegidos = sample([n for n in pool if n != numero_cierre], 23) + [numero_cierre]
            if not conteo_columnas_factible(elegidos):
                continue
            carton = asignar_numeros_a_columnas(elegidos)
            if carton is None:
                continue
            if ultima_bola_patron(carton, secuencia, celdas_patron, bola_ganadora) == bola_ganadora:
                return carton
        raise ValueError(
            f"No se pudo generar cartón lleno ganador en la bola {bola_ganadora}. "
            "Prueba otra posición o ajusta la secuencia."
        )

    for _ in range(intentos):
        celda_cierre = sample(celdas_cierre, 1)[0]
        otras = [c for c in celdas if c != celda_cierre]
        asignacion = {celda_cierre: numero_cierre}

        if not asignar_celdas_patron_recursivo(
            otras, pool, asignacion, posiciones, posicion_cierre
        ):
            continue

        carton = completar_carton_desde_asignacion(asignacion)
        if carton is None:
            continue

        if ultima_bola_patron(carton, secuencia, celdas_patron, bola_ganadora) != bola_ganadora:
            continue

        marcadas = {CENTRO_LIBRE}
        for indice, numero in enumerate(secuencia[:bola_ganadora], start=1):
            marcar_numero_en_carton(marcadas, carton, numero)
            if indice == bola_ganadora and patron_cumplido(marcadas, celdas_patron):
                return carton

    raise ValueError(
        f"No se pudo generar ganador del patrón en la bola {bola_ganadora}. "
        "Prueba otra posición o ajusta la secuencia."
    )


def generar_carton_perdedor(numeros_bloqueo, intentos=400):
    """
    Genera un cartón perdedor que incluye al menos un número de bloqueo
    (números que aún no salieron cuando gana el cartón principal).
    """
    if not numeros_bloqueo:
        raise ValueError(
            "No quedan números de bloqueo en la cola de la secuencia para los cartones perdedores."
        )

    lista_bloqueo = list(numeros_bloqueo)
    for _ in range(intentos):
        numero_bloque = sample(lista_bloqueo, 1)[0]
        letra_bloque = columna_de_numero(numero_bloque)
        mapa = {letra: [] for letra in "BINGO"}
        mapa[letra_bloque].append(numero_bloque)

        valido = True
        for letra in "BINGO":
            faltantes = CANTIDAD_POR_COLUMNA[letra] - len(mapa[letra])
            if faltantes < 0:
                valido = False
                break
            if faltantes == 0:
                continue
            disponibles = [
                n
                for n in RANGOS_COLUMNA[letra]
                if n not in mapa[letra] and n not in numeros_bloqueo
            ]
            if len(disponibles) < faltantes:
                valido = False
                break
            mapa[letra].extend(sample(disponibles, faltantes))

        if not valido:
            continue

        carton = construir_estructura_carton(mapa)
        if any(n in numeros_bloqueo for n in numeros_en_carton(carton)):
            return carton

    raise ValueError(
        "No se pudo generar un cartón perdedor con los números de bloqueo disponibles."
    )


def validar_secuencia_modo_dirigido(secuencia):
    """Exige una secuencia completa de 75 números únicos entre 1 y 75."""
    if len(secuencia) != 75:
        raise ValueError(
            f"El modo dirigido requiere una secuencia completa de 75 bolas; recibiste {len(secuencia)}."
        )
    if len(set(secuencia)) != 75:
        raise ValueError(
            "La secuencia debe tener 75 números distintos (sin repetidos) del 1 al 75."
        )
    return secuencia


def validar_bolas_compartidas_por_patron(ganadores):
    """Exige que todos los ganadores del mismo patrón usen la misma bola."""
    etiquetas = {
        TIPO_PATRON_CUADRO: "Patrón 1",
        TIPO_PATRON_LINEA: "Patrón 2",
        TIPO_PATRON_LLENO: "cartón lleno",
    }
    bolas_por_tipo = {}
    for ganador in ganadores:
        tipo = ganador["tipo_patron"]
        bolas_por_tipo.setdefault(tipo, set()).add(ganador["bola"])
    for tipo, bolas in bolas_por_tipo.items():
        if len(bolas) > 1:
            raise ValueError(
                f"En {etiquetas.get(tipo, tipo)}, todos los cartones ganadores deben "
                "compartir la misma bola de la secuencia."
            )


def validar_orden_bolas_patrones(ganadores):
    """
    Regla del modo dirigido: Patrón 1 gana antes que Patrón 2,
    y ambos antes que cartón lleno (bolas estrictamente crecientes).
    """
    etiquetas = {
        TIPO_PATRON_CUADRO: "Patrón 1",
        TIPO_PATRON_LINEA: "Patrón 2",
        TIPO_PATRON_LLENO: "cartón lleno",
    }
    bolas_por_tipo = {}
    for ganador in ganadores:
        bolas_por_tipo[ganador["tipo_patron"]] = ganador["bola"]

    secuencia_tipos = (
        TIPO_PATRON_CUADRO,
        TIPO_PATRON_LINEA,
        TIPO_PATRON_LLENO,
    )
    activos = [tipo for tipo in secuencia_tipos if tipo in bolas_por_tipo]
    for indice in range(len(activos) - 1):
        tipo_actual = activos[indice]
        tipo_siguiente = activos[indice + 1]
        bola_actual = bolas_por_tipo[tipo_actual]
        bola_siguiente = bolas_por_tipo[tipo_siguiente]
        if bola_actual >= bola_siguiente:
            raise ValueError(
                f"{etiquetas[tipo_actual]} debe ganar en una bola anterior a "
                f"{etiquetas[tipo_siguiente]} (tienes {bola_actual} y {bola_siguiente}). "
                "Usa bolas estrictamente crecientes: Patrón 1 → Patrón 2 → cartón lleno."
            )


def bolas_compatibles_con_patron(secuencia, celdas_patron, min_bola=1, max_bola=75, limite=15):
    """
    Lista bolas donde el número cantado cae en una columna válida del patrón
    (requisito para poder construir el cartón ganador).
    """
    if celdas_patron == TODAS_LAS_CELDAS:
        return list(range(max(min_bola, 24), min(max_bola, len(secuencia)) + 1))[:limite]

    columnas_patron = {
        letra_de_celda(fila, col)
        for fila, col in celdas_patron
        if (fila, col) != CENTRO_LIBRE
    }
    compatibles = []
    for bola in range(min_bola, min(max_bola, len(secuencia)) + 1):
        numero = secuencia[bola - 1]
        if columna_de_numero(numero) in columnas_patron:
            compatibles.append(bola)
        if len(compatibles) >= limite:
            break
    return compatibles


# --- Asistente modo dirigido (ingeniería inversa guiada) ---

MAPA_CLAVE_TIPO_DIRIGIDO = {
    "cuadro": TIPO_PATRON_CUADRO,
    "linea": TIPO_PATRON_LINEA,
    "lleno": TIPO_PATRON_LLENO,
}

ETIQUETAS_PASO_DIRIGIDO = {
    TIPO_PATRON_CUADRO: "Patrón 1",
    TIPO_PATRON_LINEA: "Patrón 2",
    TIPO_PATRON_LLENO: "Cartón lleno",
}


def pasos_dirigido_activos(activo_cuadro, activo_linea, activo_lleno):
    """Orden fijo de pasos del asistente según patrones activados."""
    pasos = []
    if activo_cuadro:
        pasos.append(TIPO_PATRON_CUADRO)
    if activo_linea:
        pasos.append(TIPO_PATRON_LINEA)
    if activo_lleno:
        pasos.append(TIPO_PATRON_LLENO)
    return pasos


def datos_patron_dirigido(tipo_patron, patron1, nombre1, patron2, nombre2):
    """Devuelve celdas y nombre visible para un paso del asistente."""
    if tipo_patron == TIPO_PATRON_CUADRO:
        return patron2, (nombre2 or "Patrón 1").strip()
    if tipo_patron == TIPO_PATRON_LINEA:
        return patron1, (nombre1 or "Patrón 2").strip()
    return TODAS_LAS_CELDAS, NOMBRE_CARTON_LLENO


def clave_desde_tipo_patron(tipo_patron):
    for clave, tipo in MAPA_CLAVE_TIPO_DIRIGIDO.items():
        if tipo == tipo_patron:
            return clave
    return None


def cartones_probar_para_bolas(ganadores_previos, total_cartones):
    """
    Mínimo de cartones para saber si una bola sirve: los ya elegidos (reutilización)
    más uno distinto; no hace falta probar todos.
    """
    previos = sorted({g["numero_carton"] for g in ganadores_previos})
    frescos = [
        n for n in cartones_candidatos_dirigido(total_cartones) if n not in previos
    ]
    probes = list(previos)
    if frescos:
        probes.append(frescos[0])
    return probes if probes else [1]


def cartones_candidatos_dirigido(total_cartones):
    """Todos los números de cartón del PDF."""
    return list(range(1, int(total_cartones) + 1))


def ganancias_previas_por_carton(ganadores_previos):
    """Mapa cartón → nombres de patrones ya ganados en pasos anteriores del asistente."""
    mapa = {}
    for ganador in ganadores_previos:
        numero = ganador["numero_carton"]
        mapa.setdefault(numero, []).append(ganador["nombre_patron"])
    return mapa


def planes_carton_dirigido(ganadores_previos, plan_nuevo=None):
    """Planes de un cartón: victorias previas más el patrón que se está evaluando."""
    numero = plan_nuevo["numero_carton"] if plan_nuevo else None
    planes = [
        g for g in ganadores_previos
        if plan_nuevo is None or g["numero_carton"] == numero
    ]
    if plan_nuevo:
        claves = {(p["tipo_patron"], p["bola"]) for p in planes}
        clave_nueva = (plan_nuevo["tipo_patron"], plan_nuevo["bola"])
        if clave_nueva not in claves:
            planes.append(plan_nuevo)
    return ordenar_ganadores_dirigidos(planes)


def plan_ganador_dirigido(numero_carton, bola, tipo_patron, celdas, nombre_patron):
    """Arma un plan de ganador para pruebas de viabilidad del asistente."""
    return {
        "numero_carton": numero_carton,
        "bola": int(bola),
        "tipo_patron": tipo_patron,
        "celdas_patron": celdas,
        "nombre_patron": nombre_patron,
    }


def carton_cumple_planes_ganador(secuencia, numeros_carton, planes_carton):
    """True si el cartón cierra cada patrón exactamente en la bola planificada."""
    for plan in planes_carton:
        bola_real, _ = simular_bola_patron_en_carton(
            numeros_carton, secuencia, plan["celdas_patron"]
        )
        if bola_real != plan["bola"]:
            return False
    return True


def generar_carton_multimodal_dirigido(
    secuencia,
    numero_carton,
    planes_carton,
    ganadores_config,
    intentos_globales=80,
    intentos_patron=200,
):
    """
    Genera un cartón que gana todos los patrones asignados a ese número
    (misma carta en Patrón 1, Patrón 2 y/o lleno cuando la secuencia lo permite).
    """
    if not planes_carton:
        raise ValueError(f"No hay patrones planificados para el cartón {numero_carton}.")

    todos_ganadores = list(ganadores_config)
    vistos = {(g["numero_carton"], g["tipo_patron"]) for g in todos_ganadores}
    for plan in planes_carton:
        clave = (plan["numero_carton"], plan["tipo_patron"])
        if clave not in vistos:
            todos_ganadores.append(plan)
            vistos.add(clave)

    restricciones = restricciones_para_carton(todos_ganadores, numero_carton)
    planes_ordenados = ordenar_ganadores_dirigidos(planes_carton)
    ultimo_error = None

    # Probar generar desde cada patrón como ancla (el más restrictivo suele ser el lleno).
    anclas = list(reversed(planes_ordenados)) + planes_ordenados

    for plan_primario in anclas:
        for _ in range(intentos_globales // max(len(anclas), 1)):
            try:
                carton = generar_carton_ganador_patron(
                    secuencia,
                    plan_primario["bola"],
                    plan_primario["celdas_patron"],
                    intentos=intentos_patron,
                )
                if not carton_cumple_planes_ganador(secuencia, carton, planes_carton):
                    continue
                if carton_valido_como_perdedor(carton, secuencia, restricciones):
                    return carton
            except ValueError as error:
                ultimo_error = error

    nombres = ", ".join(p["nombre_patron"] for p in planes_ordenados)
    mensaje = (
        f"No se pudo generar el cartón {numero_carton} ganando {nombres}. "
        "Prueba otras bolas o cartones; la combinación debe ser matemáticamente viable."
    )
    if ultimo_error:
        mensaje += f" Detalle: {ultimo_error}"
    raise ValueError(mensaje)


def probar_plan_dirigido_rapido(
    secuencia, plan, ganadores_previos, intentos=15, exploracion=False
):
    """
    Prueba viabilidad de un cartón para el patrón actual.
    exploracion=True: menos intentos (listado de bolas/cartones en el asistente).
    """
    planes = planes_carton_dirigido(ganadores_previos, plan)
    es_lleno = plan["tipo_patron"] == TIPO_PATRON_LLENO
    if exploracion:
        if es_lleno:
            intentos_globales = 8
            intentos_patron = 40
        elif len(planes) == 1:
            intentos_globales = 5
            intentos_patron = 35
        else:
            intentos_globales = 8
            intentos_patron = 35
    else:
        intentos_globales = max(intentos, 40 if len(planes) > 1 else intentos)
        intentos_patron = 200

    if len(planes) == 1:
        try:
            generar_carton_ganador_dirigido(
                secuencia,
                plan,
                ganadores_previos,
                intentos_globales=intentos_globales,
                intentos_patron=intentos_patron,
            )
            return True
        except ValueError:
            return False

    try:
        construir_carton_ganador_secuencial(
            secuencia,
            plan["numero_carton"],
            planes,
            ganadores_previos,
            intentos_globales=intentos_globales,
            intentos_patron=intentos_patron,
        )
        return True
    except ValueError:
        return False


def ganadores_previos_desde_seleccion(seleccion, patron1, nombre1, patron2, nombre2):
    """
    Convierte las elecciones del asistente (pasos ya confirmados) en planes parciales
    para calcular restricciones de los pasos siguientes.
    """
    ganadores = []
    for clave in ("cuadro", "linea", "lleno"):
        paso = seleccion.get(clave)
        if not paso or not paso.get("cartones"):
            continue
        tipo = MAPA_CLAVE_TIPO_DIRIGIDO[clave]
        celdas, nombre = datos_patron_dirigido(tipo, patron1, nombre1, patron2, nombre2)
        bola = int(paso["bola"])
        for numero in paso["cartones"]:
            ganadores.append(plan_ganador_dirigido(numero, bola, tipo, celdas, nombre))
    return ganadores


def bola_minima_paso_dirigido(tipo_patron, celdas, ganadores_previos):
    """Bola mínima permitida para este paso según el patrón y pasos previos."""
    if tipo_patron == TIPO_PATRON_LLENO:
        minimo = 24
    else:
        minimo = max(4, len(celdas_patron_sin_centro(celdas)))
    if ganadores_previos:
        minimo = max(minimo, max(g["bola"] for g in ganadores_previos) + 1)
    return minimo


def listar_bolas_viables_asistente(
    secuencia,
    tipo_patron,
    celdas,
    nombre_patron,
    ganadores_previos,
    total_cartones,
    limite=50,
):
    """
    Bolas de la secuencia donde al menos un cartón puede ganar este patrón,
    respetando lo ya elegido en pasos anteriores (incluye cartones repetidos).
    """
    min_bola = bola_minima_paso_dirigido(tipo_patron, celdas, ganadores_previos)
    probes = cartones_probar_para_bolas(ganadores_previos, total_cartones)
    if not probes:
        return []
    columnas_patron = None
    if tipo_patron != TIPO_PATRON_LLENO:
        columnas_patron = {
            letra_de_celda(fila, col)
            for fila, col in celdas
            if (fila, col) != CENTRO_LIBRE
        }

    resultado = []
    max_bola = min(len(secuencia), 75)
    iter_bolas = range(min_bola, max_bola + 1)

    for bola in iter_bolas:
        numero_bola = secuencia[bola - 1]
        letra = columna_de_numero(numero_bola)
        if columnas_patron is not None and letra not in columnas_patron:
            continue
        viable_alguno = False
        for num_carton in probes:
            plan = plan_ganador_dirigido(
                num_carton, bola, tipo_patron, celdas, nombre_patron
            )
            if probar_plan_dirigido_rapido(
                secuencia, plan, ganadores_previos, exploracion=True
            ):
                viable_alguno = True
                break
        if viable_alguno:
            resultado.append(
                {
                    "bola": bola,
                    "numero": numero_bola,
                    "columna": letra,
                    "etiqueta": f"Bola {bola}: {numero_bola} ({letra})",
                }
            )
        if len(resultado) >= limite:
            break
    return resultado


def listar_cartones_viables_asistente(
    secuencia,
    tipo_patron,
    celdas,
    nombre_patron,
    bola,
    ganadores_previos,
    total_cartones,
):
    """
    Cartones que pueden ganar el patrón en la bola elegida.
    Solo devuelve los viables (incluye repetir el mismo cartón de un paso anterior).
    """
    previas = ganancias_previas_por_carton(ganadores_previos)
    items = []
    for numero in cartones_candidatos_dirigido(total_cartones):
        plan = plan_ganador_dirigido(numero, bola, tipo_patron, celdas, nombre_patron)
        if not probar_plan_dirigido_rapido(
            secuencia, plan, ganadores_previos, exploracion=True
        ):
            continue
        items.append(
            {
                "numero": numero,
                "viable": True,
                "ganancias_previas": previas.get(numero, []),
            }
        )
    return items


def seleccion_asistente_a_config(seleccion, activo_cuadro, activo_linea, activo_lleno):
    """Convierte las elecciones del asistente al JSON que usa parsear_config_dirigido."""
    config = {
        "cuadro": {"activo": False, "bola": None, "ganadores": []},
        "linea": {"activo": False, "bola": None, "ganadores": []},
        "lleno": {"activo": False, "bola": None, "ganadores": []},
    }
    flags = {
        "cuadro": activo_cuadro,
        "linea": activo_linea,
        "lleno": activo_lleno,
    }
    for clave, activo in flags.items():
        if not activo:
            continue
        paso = seleccion.get(clave)
        if not paso or not paso.get("cartones"):
            raise ValueError(f"Falta completar el paso «{clave}» en el asistente.")
        bola = int(paso["bola"])
        config[clave] = {
            "activo": True,
            "bola": bola,
            "ganadores": [{"carton": int(c), "bola": bola} for c in paso["cartones"]],
        }
    return config


def validar_setup_asistente_dirigido(
    secuencia_texto, activo_cuadro, activo_linea, activo_lleno, patron1, patron2, nombre1, nombre2
):
    """Valida secuencia, patrones y que haya al menos un paso activo."""
    secuencia = parsear_secuencia_numeros(secuencia_texto)
    secuencia = validar_secuencia_modo_dirigido(secuencia)
    pasos = pasos_dirigido_activos(activo_cuadro, activo_linea, activo_lleno)
    if not pasos:
        raise ValueError("Activa al menos un patrón ganador (Patrón 1, Patrón 2 o cartón lleno).")
    if activo_cuadro and not patron2:
        raise ValueError("Activaste Patrón 1: marca su forma en la cuadrícula.")
    if activo_linea and not patron1:
        raise ValueError("Activaste Patrón 2: marca su forma en la cuadrícula.")
    if activo_cuadro and not nombre2:
        raise ValueError("Escribe un nombre para Patrón 1.")
    if activo_linea and not nombre1:
        raise ValueError("Escribe un nombre para Patrón 2.")
    return secuencia, pasos


def parsear_config_dirigido(
    texto_json, total_cartones, patron1, nombre1, patron2, nombre2
):
    """
    Lee la configuración por patrón del modo dirigido.
    Formato: { cuadro|linea|lleno: { activo, ganadores: [{carton, bola}] } }
    """
    if not texto_json or not str(texto_json).strip():
        raise ValueError("Debes configurar al menos un patrón ganador en el modo dirigido.")
    try:
        datos = json.loads(texto_json)
    except json.JSONDecodeError:
        raise ValueError("La configuración del modo dirigido no es válida.")

    if not isinstance(datos, dict):
        raise ValueError("La configuración del modo dirigido debe ser un objeto JSON.")

    mapa_bloques = [
        (TIPO_PATRON_CUADRO, patron2, nombre2, "Patrón 1"),
        (TIPO_PATRON_LINEA, patron1, nombre1, "Patrón 2"),
        (TIPO_PATRON_LLENO, TODAS_LAS_CELDAS, NOMBRE_CARTON_LLENO, "cartón lleno"),
    ]

    ganadores = []
    vistos = set()
    hubo_activo = False

    for tipo_patron, celdas, nombre_patron, etiqueta in mapa_bloques:
        bloque = datos.get(tipo_patron, {})
        if not isinstance(bloque, dict):
            raise ValueError(f"Configuración inválida para el patrón '{tipo_patron}'.")

        activo = bool(bloque.get("activo"))
        lista = bloque.get("ganadores", [])
        if not activo:
            continue

        hubo_activo = True
        if not isinstance(lista, list) or not lista:
            raise ValueError(
                f"Activaste '{etiqueta}' pero no indicaste cartones ganadores."
            )

        if tipo_patron != TIPO_PATRON_LLENO and not celdas:
            raise ValueError(
                f"Activaste {etiqueta}: marca las casillas en la cuadrícula correspondiente."
            )
        if tipo_patron != TIPO_PATRON_LLENO and not nombre_patron:
            raise ValueError(
                f"Activaste {etiqueta}: escribe un nombre para ese patrón."
            )

        minimo_bolas = len(celdas_patron_sin_centro(celdas))
        if tipo_patron == TIPO_PATRON_LLENO:
            minimo_bolas = 24

        # Bola compartida: todos los ganadores del mismo patrón deben usar la misma bolita
        bola_bloque = bloque.get("bola")
        bolas_vistas = set()

        for indice, item in enumerate(lista, start=1):
            if not isinstance(item, dict):
                raise ValueError(f"Entrada inválida en ganador #{indice} de {etiqueta}.")
            try:
                numero_carton = int(item.get("carton"))
            except (TypeError, ValueError):
                raise ValueError(
                    f"{etiqueta}, ganador #{indice}: el número de cartón debe ser un entero."
                )

            if bola_bloque is not None:
                bola = int(bola_bloque)
            else:
                try:
                    bola = int(item.get("bola"))
                except (TypeError, ValueError):
                    raise ValueError(
                        f"{etiqueta}, ganador #{indice}: indica la bola ganadora."
                    )

            bolas_vistas.add(bola)

            if numero_carton < 1 or numero_carton > int(total_cartones):
                raise ValueError(
                    f"{etiqueta}, ganador #{indice}: el cartón {numero_carton} "
                    f"debe estar entre 1 y {total_cartones}."
                )
            if bola < minimo_bolas or bola > 75:
                raise ValueError(
                    f"{etiqueta}, ganador #{indice}: la bola debe estar "
                    f"entre {minimo_bolas} y 75."
                )

            clave = (numero_carton, tipo_patron)
            if clave in vistos:
                raise ValueError(
                    f"El cartón {numero_carton} está repetido en el patrón '{tipo_patron}'."
                )
            vistos.add(clave)

            ganadores.append(
                {
                    "numero_carton": numero_carton,
                    "bola": bola,
                    "tipo_patron": tipo_patron,
                    "nombre_patron": nombre_patron,
                    "celdas_patron": celdas,
                }
            )

        if len(bolas_vistas) > 1:
            raise ValueError(
                f"En {etiqueta}, todos los cartones ganadores deben compartir "
                "la misma bola de la secuencia."
            )

    if not hubo_activo:
        raise ValueError("Activa al menos un patrón con cartones ganadores.")

    validar_bolas_compartidas_por_patron(ganadores)
    validar_orden_bolas_patrones(ganadores)
    return ganadores


def parsear_ganadores_dirigidos(
    texto_json, total_cartones, cantidad_ganadores, patron1, nombre1, patron2, nombre2
):
    """Compatibilidad con el formato anterior (lista plana de ganadores)."""
    if not texto_json or not str(texto_json).strip():
        raise ValueError("Debes indicar qué cartones serán ganadores.")
    try:
        datos = json.loads(texto_json)
    except json.JSONDecodeError:
        raise ValueError("La configuración de ganadores no es válida.")

    if isinstance(datos, dict):
        return parsear_config_dirigido(
            texto_json, total_cartones, patron1, nombre1, patron2, nombre2
        )

    if not isinstance(datos, list):
        raise ValueError("La configuración de ganadores debe ser una lista u objeto.")

    if len(datos) != int(cantidad_ganadores):
        raise ValueError(
            f"Indicaste {cantidad_ganadores} ganador(es), pero la configuración tiene {len(datos)}."
        )

    mapa_patrones = {
        TIPO_PATRON_CUADRO: {"celdas": patron2, "nombre": nombre2, "etiqueta": "cuadro"},
        TIPO_PATRON_LINEA: {"celdas": patron1, "nombre": nombre1, "etiqueta": "línea"},
        TIPO_PATRON_LLENO: {
            "celdas": TODAS_LAS_CELDAS,
            "nombre": NOMBRE_CARTON_LLENO,
            "etiqueta": "cartón lleno",
        },
    }

    vistos = set()
    ganadores = []
    for indice, item in enumerate(datos, start=1):
        if not isinstance(item, dict):
            raise ValueError(f"Entrada inválida en ganador #{indice}.")

        try:
            numero_carton = int(item.get("carton"))
            bola = int(item.get("bola"))
        except (TypeError, ValueError):
            raise ValueError(f"Ganador #{indice}: cartón y bola deben ser números enteros.")

        tipo_patron = str(item.get("patron", TIPO_PATRON_LLENO)).strip().lower()
        if tipo_patron not in mapa_patrones:
            raise ValueError(
                f"Ganador #{indice}: patrón inválido '{tipo_patron}'. "
                "Usa cuadro, linea o lleno."
            )

        info_patron = mapa_patrones[tipo_patron]
        celdas = info_patron["celdas"]
        nombre_patron = info_patron["nombre"]

        if tipo_patron != TIPO_PATRON_LLENO and not celdas:
            raise ValueError(
                f"Ganador #{indice}: marcaste patrón '{tipo_patron}' pero la cuadrícula "
                f"{'2 (cuadro)' if tipo_patron == TIPO_PATRON_CUADRO else '1 (línea)'} está vacía."
            )
        if tipo_patron != TIPO_PATRON_LLENO and not nombre_patron:
            raise ValueError(
                f"Ganador #{indice}: escribe el nombre del patrón "
                f"{'cuadrícula 2' if tipo_patron == TIPO_PATRON_CUADRO else 'cuadrícula 1'}."
            )

        minimo_bolas = len(celdas_patron_sin_centro(celdas))
        if tipo_patron == TIPO_PATRON_LLENO:
            minimo_bolas = 24

        if numero_carton < 1 or numero_carton > int(total_cartones):
            raise ValueError(
                f"Ganador #{indice}: el cartón {numero_carton} debe estar entre 1 y {total_cartones}."
            )
        if bola < minimo_bolas or bola > 75:
            raise ValueError(
                f"Ganador #{indice}: para {info_patron['etiqueta']} la bola debe estar "
                f"entre {minimo_bolas} y 75."
            )

        clave = (numero_carton, tipo_patron)
        if clave in vistos:
            raise ValueError(
                f"El cartón {numero_carton} está repetido con el mismo patrón '{tipo_patron}'."
            )
        vistos.add(clave)

        ganadores.append(
            {
                "numero_carton": numero_carton,
                "bola": bola,
                "tipo_patron": tipo_patron,
                "nombre_patron": nombre_patron,
                "celdas_patron": celdas,
            }
        )

    validar_bolas_compartidas_por_patron(ganadores)
    validar_orden_bolas_patrones(ganadores)
    return ganadores


def ordenar_ganadores_dirigidos(ganadores_config):
    """
    Orden de construcción: cuadro → línea → cartón lleno; dentro de cada tipo, por bola.
    """
    return sorted(
        ganadores_config,
        key=lambda g: (ORDEN_TIPOS_PATRON[g["tipo_patron"]], g["bola"]),
    )


def restricciones_perdedores_desde_ganadores(ganadores_config):
    """
    Reglas para cartones no designados ganadores: no completar un patrón activo
    antes de la bola oficial de ese patrón (pueden completarlo después).
    """
    restricciones = []
    for tipo in (TIPO_PATRON_CUADRO, TIPO_PATRON_LINEA, TIPO_PATRON_LLENO):
        del_tipo = [g for g in ganadores_config if g["tipo_patron"] == tipo]
        if not del_tipo:
            continue
        bola_oficial = min(g["bola"] for g in del_tipo)
        celdas = del_tipo[0]["celdas_patron"]
        restricciones.append(
            {
                "tipo_patron": tipo,
                "nombre_patron": del_tipo[0]["nombre_patron"],
                "celdas": celdas,
                "min_bola_ganador": bola_oficial,
            }
        )
    return restricciones


def carton_valido_como_perdedor(numeros_carton, secuencia, restricciones):
    """
    True si el cartón no completa ningún patrón activo antes de la bola acordada.
    Completarlo en o después de esa bola es válido (solo cuentan los ganadores designados).
    """
    for regla in restricciones:
        bola_real, _ = simular_bola_patron_en_carton(
            numeros_carton, secuencia, regla["celdas"]
        )
        if bola_real is not None and bola_real < regla["min_bola_ganador"]:
            return False
    return True


def restricciones_para_carton(ganadores_config, numero_carton):
    """
    Patrones que este cartón no debe completar antes de tiempo.
    Excluye todos los patrones que este cartón gana (puede ser más de uno).
    """
    tipos_ganados = {
        g["tipo_patron"]
        for g in ganadores_config
        if g["numero_carton"] == numero_carton
    }
    todas = restricciones_perdedores_desde_ganadores(ganadores_config)
    return [regla for regla in todas if regla["tipo_patron"] not in tipos_ganados]


def generar_carton_ganador_dirigido(
    secuencia, config, ganadores_config, intentos_globales=80, intentos_patron=200
):
    """
    Genera un cartón ganador de una modalidad sin completar otros patrones antes de su bola.
    """
    restricciones = restricciones_para_carton(ganadores_config, config["numero_carton"])
    ultimo_error = None

    for _ in range(intentos_globales):
        try:
            carton = generar_carton_ganador_patron(
                secuencia,
                config["bola"],
                config["celdas_patron"],
                intentos=intentos_patron,
            )
            if carton_valido_como_perdedor(carton, secuencia, restricciones):
                return carton
        except ValueError as error:
            ultimo_error = error

    mensaje = (
        f"No se pudo generar el cartón {config['numero_carton']} "
        f"({config['nombre_patron']}) en la bola {config['bola']}. "
        "Prueba otra bola compatible o ajusta la secuencia."
    )
    if ultimo_error:
        mensaje += f" Detalle: {ultimo_error}"
    raise ValueError(mensaje)


def generar_carton_perdedor_dirigido(secuencia, restricciones, intentos=500):
    """Cartón perdedor: relleno al azar sin ganar patrones antes de lo acordado."""
    for _ in range(intentos):
        carton = generar_numeros_bingo()
        if carton_valido_como_perdedor(carton, secuencia, restricciones):
            return carton

    raise ValueError(
        "No se pudo generar cartones perdedores que respeten las bolas ganadoras. "
        "Prueba con menos cartones o ajusta las bolas."
    )


def validar_ganadores_con_secuencia(ganadores_config, secuencia):
    """
    Valida que en cada bola ganadora el número cantado caiga en una columna
    compatible con el patrón (requisito para construir el cartón).
    """
    tipos_revisados = set()
    for plan in ganadores_config:
        tipo = plan["tipo_patron"]
        if tipo in tipos_revisados or tipo == TIPO_PATRON_LLENO:
            continue
        tipos_revisados.add(tipo)

        minimo = len(celdas_patron_sin_centro(plan["celdas_patron"]))
        numero_bola = secuencia[plan["bola"] - 1]
        letra_bola = columna_de_numero(numero_bola)
        columnas_patron = {
            letra_de_celda(fila, col)
            for fila, col in plan["celdas_patron"]
            if (fila, col) != CENTRO_LIBRE
        }
        if letra_bola not in columnas_patron:
            sugeridas = bolas_compatibles_con_patron(
                secuencia, plan["celdas_patron"], min_bola=minimo
            )
            texto_sugeridas = (
                ", ".join(str(b) for b in sugeridas)
                if sugeridas
                else "ninguna con esta secuencia"
            )
            raise ValueError(
                f"{plan['nombre_patron']}: en la bola {plan['bola']} sale el {numero_bola} "
                f"(columna {letra_bola}), pero el patrón no tiene casillas en esa columna. "
                f"Bolas compatibles (ejemplos): {texto_sugeridas}."
            )


def generar_cartones_modo_dirigido(secuencia, ganadores_config, total_cartones, reintentos_globales=10):
    """
    Genera cartones en orden: primero los ganadores diseñados, luego los perdedores
    con al menos un número de bloqueo en la cola de la secuencia.
    Reintenta la construcción si alguna secuencia puntual no admite solución.
    """
    secuencia = validar_secuencia_modo_dirigido(secuencia)
    validar_ganadores_con_secuencia(ganadores_config, secuencia)
    total = int(total_cartones)
    cartones_ganadores = {g["numero_carton"] for g in ganadores_config}
    if total < len(cartones_ganadores):
        raise ValueError(
            "La cantidad de cartones debe ser mayor o igual al número de cartones "
            f"ganadores ({len(cartones_ganadores)} distintos)."
        )

    ultimo_error = None
    for _ in range(reintentos_globales):
        try:
            return _construir_cartones_modo_dirigido(
                secuencia, ganadores_config, total
            )
        except ValueError as error:
            ultimo_error = error
    raise ultimo_error


def _agrupar_planes_por_carton(ganadores_config):
    """Agrupa todos los patrones ganadores por número de cartón."""
    grupos = {}
    for config in ordenar_ganadores_dirigidos(ganadores_config):
        grupos.setdefault(config["numero_carton"], []).append(config)
    return grupos


def _construir_cartones_modo_dirigido(secuencia, ganadores_config, total):
    """
    Pipeline por fases: fija ganadores P1 → P2 → lleno (ampliando el mismo cartón si aplica),
    luego rellena perdedores al azar sin ganar patrones antes de lo acordado.
    """
    restricciones = restricciones_perdedores_desde_ganadores(ganadores_config)
    cartones_por_numero = {}
    procesados = set()

    for tipo in (TIPO_PATRON_CUADRO, TIPO_PATRON_LINEA, TIPO_PATRON_LLENO):
        for config in ordenar_ganadores_dirigidos(
            [g for g in ganadores_config if g["tipo_patron"] == tipo]
        ):
            clave = (config["numero_carton"], config["tipo_patron"])
            if clave in procesados:
                continue
            procesados.add(clave)

            numero = config["numero_carton"]
            planes_carton = [
                g for g in ganadores_config if g["numero_carton"] == numero
            ]

            if numero not in cartones_por_numero:
                cartones_por_numero[numero] = generar_carton_ganador_dirigido(
                    secuencia, config, ganadores_config
                )
            else:
                cartones_por_numero[numero] = extender_carton_para_patron(
                    secuencia,
                    cartones_por_numero[numero],
                    config,
                    [p for p in planes_carton if ORDEN_TIPOS_PATRON[p["tipo_patron"]] <= ORDEN_TIPOS_PATRON[config["tipo_patron"]]],
                    ganadores_config,
                )

    for numero in range(1, total + 1):
        if numero in cartones_por_numero:
            continue
        cartones_por_numero[numero] = generar_carton_perdedor_dirigido(
            secuencia, restricciones
        )

    return [
        {"numero": numero, "numeros": cartones_por_numero[numero]}
        for numero in range(1, total + 1)
    ]


def simular_bola_patron_en_carton(numeros_carton, secuencia, celdas_patron):
    """
    Simula una partida para un solo cartón y devuelve en qué bola se completa el patrón.
    Si nunca se completa, retorna (None, None).
    """
    marcadas = {CENTRO_LIBRE}
    for indice_bola, numero in enumerate(secuencia, start=1):
        marcar_numero_en_carton(marcadas, numeros_carton, numero)
        if patron_cumplido(marcadas, celdas_patron):
            return indice_bola, numero
    return None, None


def verificar_ganadores_planeados(ganadores_config, secuencia_cartones, secuencia):
    """
    Verifica cartón por cartón que cada ganador planeado cierre su patrón en la bola indicada.
    """
    cartones_por_numero = {c["numero"]: c for c in secuencia_cartones}
    resultados = []
    todos_ok = True

    for plan in ganadores_config:
        carton = cartones_por_numero.get(plan["numero_carton"])
        if carton is None:
            todos_ok = False
            resultados.append(
                {
                    "carton": plan["numero_carton"],
                    "nombre_patron": plan["nombre_patron"],
                    "tipo_patron": plan["tipo_patron"],
                    "bola_esperada": plan["bola"],
                    "ok": False,
                    "bola_real": None,
                    "numero_real": None,
                }
            )
            continue

        bola_real, numero_real = simular_bola_patron_en_carton(
            carton["numeros"], secuencia, plan["celdas_patron"]
        )
        ok = bola_real == plan["bola"]
        if not ok:
            todos_ok = False

        resultados.append(
            {
                "carton": plan["numero_carton"],
                "nombre_patron": plan["nombre_patron"],
                "tipo_patron": plan["tipo_patron"],
                "bola_esperada": plan["bola"],
                "ok": ok,
                "bola_real": bola_real,
                "numero_real": numero_real,
            }
        )

    return {"todos_ok": todos_ok, "detalle": resultados}


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
                "Patrón 2 tiene casillas marcadas: escribe un nombre para esa forma de ganar."
            )
        modos_personalizados.append({"nombre": nombre1, "celdas": patron1})
    elif nombre1:
        raise ValueError(
            "Escribiste un nombre en Patrón 2 pero no marcaste casillas."
        )

    if patron2:
        if not nombre2:
            raise ValueError(
                "Patrón 1 tiene casillas marcadas: escribe un nombre para esa forma de ganar."
            )
        modos_personalizados.append({"nombre": nombre2, "celdas": patron2})
    elif nombre2:
        raise ValueError(
            "Escribiste un nombre en Patrón 1 pero no marcaste casillas."
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
    version,
    secuencia_cartones=None,
    total_cartones=6,
    nombre_base=NOMBRE_BASE_DEFAULT,
):
    pdf = FPDF("P", "mm", "A4")
    pdf.set_auto_page_break(auto=True, margin=10)
    pdf.add_font("ArialBlackItalic", "", ruta_fuente_arial())

    logo_path, watermark_path = resolver_recursos_version(version)

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
        secuencia_cartones = generar_secuencia_cartones_total(total_cartones)

    total_cartones = len(secuencia_cartones)
    paginas_necesarias = max(1, (total_cartones + 5) // 6)

    indice_carton = 0
    for pagina in range(paginas_necesarias):
        pdf.add_page()
        pdf.image(watermark_path, 0, 0, 210, 297)
        cartones_restantes = total_cartones - indice_carton
        en_esta_pagina = min(6, cartones_restantes)
        for i in range(en_esta_pagina):
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


def _config_regenerar_detectar(form):
    """Guarda los datos necesarios para regenerar cartones en modo detectar."""
    return {
        "modo": "detectar",
        "color_carton": form.get("color_carton", "#fe630b"),
        "color_bingo": form.get("color_bingo", "#000000"),
        "color_enumeracion": form.get("color_enumeracion", "#000000"),
        "version": form.get("version", "1.0"),
        "total_cartones": form.get("total_cartones", "6"),
        "secuencia_numeros": form.get("secuencia_numeros", ""),
        "nombre_patron1": form.get("nombre_patron1", ""),
        "nombre_patron2": form.get("nombre_patron2", ""),
        "patron1_celdas": form.get("patron1_celdas", ""),
        "patron2_celdas": form.get("patron2_celdas", ""),
        "nombre_archivo": form.get("nombre_archivo", ""),
    }


def _ejecutar_modo_detectar(config):
    """Genera cartones al azar y detecta ganadores con la secuencia guardada."""
    color_carton = config["color_carton"]
    color_bingo = config["color_bingo"]
    color_enumeracion = config["color_enumeracion"]
    version = config["version"]
    total_cartones = int(config.get("total_cartones", "6"))
    if total_cartones < 1:
        raise ValueError("Debes generar al menos 1 cartón.")

    patron1 = parsear_patron_celdas(config.get("patron1_celdas", ""))
    patron2 = parsear_patron_celdas(config.get("patron2_celdas", ""))
    nombre1 = config.get("nombre_patron1", "").strip()
    nombre2 = config.get("nombre_patron2", "").strip()

    secuencia_llamados, modos = validar_configuracion_ganadores(
        config.get("secuencia_numeros", ""),
        patron1,
        nombre1,
        patron2,
        nombre2,
    )

    secuencia_cartones = generar_secuencia_cartones_total(total_cartones)
    ganadores = detectar_ganadores(secuencia_cartones, secuencia_llamados, modos)
    resumen = preparar_resumen_ganadores(modos, ganadores)

    nombre_base = resolver_nombre_base(config.get("nombre_archivo", ""))
    pdf_path, nombre_base, total_generados = generar_pdf_personalizado(
        color_carton,
        color_bingo,
        color_enumeracion,
        version,
        secuencia_cartones=secuencia_cartones,
        total_cartones=total_cartones,
        nombre_base=nombre_base,
    )

    resumen["total_cartones"] = total_generados
    resumen["secuencia_texto"] = ", ".join(str(n) for n in secuencia_llamados)
    return pdf_path, nombre_base, resumen


def _form_a_dict():
    return {
        "color_carton": request.form.get("color_carton", "#fe630b"),
        "color_bingo": request.form.get("color_bingo", "#000000"),
        "color_enumeracion": request.form.get("color_enumeracion", "#000000"),
        "total_cartones": request.form.get("total_cartones", "6"),
        "version": request.form.get("version", "1.0"),
        "modo_operacion": request.form.get("modo_operacion", "normal"),
        "secuencia_numeros": request.form.get("secuencia_numeros", ""),
        "secuencia_dirigida": request.form.get("secuencia_dirigida", ""),
        "config_dirigido_json": request.form.get("config_dirigido_json", ""),
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
        total_cartones = int(request.form.get("total_cartones", "6"))
        version = request.form.get("version", "1.0")
        detectar_ganadores_modo = request.form.get("detectar-ganadores") == "on"
        modo_operacion = request.form.get("modo_operacion", "normal")
        if modo_operacion == "detectar":
            detectar_ganadores_modo = True
        nombre_base = resolver_nombre_base(request.form.get("nombre_archivo", ""))

        if total_cartones < 1:
            return render_template(
                "index.html",
                error="Debes generar al menos 1 cartón.",
                form=_form_a_dict(),
            )

        secuencia_cartones = None

        if modo_operacion == "dirigido":
            try:
                secuencia_llamados = parsear_secuencia_numeros(
                    request.form.get("secuencia_dirigida", "")
                )
                validar_secuencia_modo_dirigido(secuencia_llamados)

                patron1 = parsear_patron_celdas(request.form.get("patron1_celdas", ""))
                patron2 = parsear_patron_celdas(request.form.get("patron2_celdas", ""))
                nombre1 = request.form.get("nombre_patron1", "").strip()
                nombre2 = request.form.get("nombre_patron2", "").strip()

                config_json = request.form.get("config_dirigido_json", "")
                if not config_json:
                    config_json = request.form.get("ganadores_dirigido_json", "")

                ganadores_config = parsear_config_dirigido(
                    config_json,
                    total_cartones,
                    patron1,
                    nombre1,
                    patron2,
                    nombre2,
                )

                _, modos = validar_configuracion_ganadores(
                    request.form.get("secuencia_dirigida", ""),
                    patron1,
                    nombre1,
                    patron2,
                    nombre2,
                )

                secuencia_cartones = generar_cartones_modo_dirigido(
                    secuencia_llamados,
                    ganadores_config,
                    total_cartones,
                )

                ganadores = detectar_ganadores(
                    secuencia_cartones, secuencia_llamados, modos
                )
                resumen = preparar_resumen_ganadores(modos, ganadores)

                for plan in ganadores_config:
                    plan["numero_cantado"] = secuencia_llamados[plan["bola"] - 1]

                verificacion = verificar_ganadores_planeados(
                    ganadores_config, secuencia_cartones, secuencia_llamados
                )
                resumen["verificacion_dirigida"] = verificacion
                resumen["modo_dirigido"] = True

                pdf_path, nombre_base, total_generados = generar_pdf_personalizado(
                    color_carton,
                    color_bingo,
                    color_enumeracion,
                    version,
                    secuencia_cartones=secuencia_cartones,
                    total_cartones=total_cartones,
                    nombre_base=nombre_base,
                )

                resumen["total_cartones"] = total_generados
                resumen["secuencia_texto"] = ", ".join(str(n) for n in secuencia_llamados)

                token = publicar_pdf_temporal(pdf_path, nombre_base, resumen)
                return redirect(url_for("resultados", token=token))

            except ValueError as error:
                return render_template(
                    "index.html",
                    error=str(error),
                    form=_form_a_dict(),
                )

        if detectar_ganadores_modo:
            try:
                pdf_path, nombre_base, resumen = _ejecutar_modo_detectar(
                    _config_regenerar_detectar(request.form)
                )
                token = publicar_pdf_temporal(
                    pdf_path,
                    nombre_base,
                    resumen,
                    regenerar=_config_regenerar_detectar(request.form),
                )
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
            version,
            secuencia_cartones=secuencia_cartones,
            total_cartones=total_cartones,
            nombre_base=nombre_base,
        )
        return send_file(pdf_path, as_attachment=True, download_name=f"{nombre_base}.pdf")

    return render_template("index.html")


@app.route("/api/dirigido/opciones", methods=["POST"])
def api_dirigido_opciones():
    """
    Asistente: devuelve bolas o cartones viables para el paso actual.
    Body JSON: secuencia, paso (cuadro|linea|lleno), seleccion previa, total_cartones,
    patrones, activos, bola (opcional, si ya se eligió bola).
    """
    datos = request.get_json(silent=True) or {}
    try:
        secuencia, _ = validar_setup_asistente_dirigido(
            datos.get("secuencia", ""),
            bool(datos.get("activo_cuadro")),
            bool(datos.get("activo_linea")),
            bool(datos.get("activo_lleno")),
            parsear_patron_celdas(datos.get("patron1_celdas", "")),
            parsear_patron_celdas(datos.get("patron2_celdas", "")),
            str(datos.get("nombre_patron1", "")).strip(),
            str(datos.get("nombre_patron2", "")).strip(),
        )
        paso_clave = str(datos.get("paso", "")).strip().lower()
        if paso_clave not in MAPA_CLAVE_TIPO_DIRIGIDO:
            raise ValueError("Paso del asistente inválido.")

        tipo_patron = MAPA_CLAVE_TIPO_DIRIGIDO[paso_clave]
        patron1 = parsear_patron_celdas(datos.get("patron1_celdas", ""))
        patron2 = parsear_patron_celdas(datos.get("patron2_celdas", ""))
        nombre1 = str(datos.get("nombre_patron1", "")).strip()
        nombre2 = str(datos.get("nombre_patron2", "")).strip()
        total_cartones = int(datos.get("total_cartones", 6))
        seleccion = datos.get("seleccion") or {}

        celdas, nombre_patron = datos_patron_dirigido(
            tipo_patron, patron1, nombre1, patron2, nombre2
        )
        ganadores_previos = ganadores_previos_desde_seleccion(
            seleccion, patron1, nombre1, patron2, nombre2
        )

        bola = datos.get("bola")
        if bola is None or str(bola).strip() == "":
            bolas = listar_bolas_viables_asistente(
                secuencia,
                tipo_patron,
                celdas,
                nombre_patron,
                ganadores_previos,
                total_cartones,
            )
            return jsonify(
                {
                    "paso": paso_clave,
                    "nombre_patron": nombre_patron,
                    "bolas": bolas,
                    "sin_opciones": not bolas,
                    "mensaje": (
                        "No hay bolas viables con la configuración actual. "
                        "Usa «Empezar de nuevo» o cambia la secuencia."
                        if not bolas
                        else None
                    ),
                }
            )

        cartones = listar_cartones_viables_asistente(
            secuencia,
            tipo_patron,
            celdas,
            nombre_patron,
            int(bola),
            ganadores_previos,
            total_cartones,
        )
        viables = [c["numero"] for c in cartones if c["viable"]]
        return jsonify(
            {
                "paso": paso_clave,
                "nombre_patron": nombre_patron,
                "bola": int(bola),
                "cartones": cartones,
                "cartones_viables": viables,
                "total_cartones": total_cartones,
                "sin_opciones": not viables,
                "mensaje": (
                    "Ningún cartón puede ganar en esa bola con la configuración actual. "
                    "Elige otra bola."
                    if not viables
                    else (
                        "Puedes marcar cartones nuevos o repetir uno que ya ganó "
                        "en un paso anterior, si aparece disponible."
                    )
                ),
            }
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@app.route("/api/dirigido/pasos", methods=["POST"])
def api_dirigido_pasos():
    """Devuelve la lista ordenada de pasos activos del asistente."""
    datos = request.get_json(silent=True) or {}
    try:
        _, pasos = validar_setup_asistente_dirigido(
            datos.get("secuencia", ""),
            bool(datos.get("activo_cuadro")),
            bool(datos.get("activo_linea")),
            bool(datos.get("activo_lleno")),
            parsear_patron_celdas(datos.get("patron1_celdas", "")),
            parsear_patron_celdas(datos.get("patron2_celdas", "")),
            str(datos.get("nombre_patron1", "")).strip(),
            str(datos.get("nombre_patron2", "")).strip(),
        )
        return jsonify(
            {
                "pasos": [
                    {
                        "clave": clave_desde_tipo_patron(tipo),
                        "nombre": ETIQUETAS_PASO_DIRIGIDO[tipo],
                    }
                    for tipo in pasos
                ]
            }
        )
    except ValueError as error:
        return jsonify({"error": str(error)}), 400


@app.route("/api/carton-muestra")
def carton_muestra():
    """Devuelve un cartón de muestra para la vista previa (misma estructura que el PDF)."""
    return jsonify({"numeros": generar_numeros_bingo(), "numero_carton": 1})


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
        puede_regenerar=bool(datos.get("regenerar")),
    )


@app.route("/regenerar/<token>", methods=["POST"])
def regenerar(token):
    """Regenera cartones al azar en modo detectar manteniendo la misma secuencia."""
    token = token_seguro(token)
    datos = cargar_sesion_resultados(token)
    if not datos or not datos.get("regenerar"):
        return render_template(
            "index.html",
            error="No se puede regenerar esta sesión. Vuelve a configurar el bingo.",
        )

    config = datos["regenerar"]
    if config.get("modo") != "detectar":
        return render_template(
            "index.html",
            error="La regeneración rápida solo está disponible en modo detectar ganadores.",
        )

    try:
        pdf_path, nombre_base, resumen = _ejecutar_modo_detectar(config)
        nuevo_token = publicar_pdf_temporal(
            pdf_path, nombre_base, resumen, regenerar=config
        )
        return redirect(url_for("resultados", token=nuevo_token))
    except ValueError as error:
        return render_template(
            "index.html",
            error=str(error),
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
