#DISCO DE FABIANES - SIMULACIÓN DE ALMACENAMIENTO FÍSICO DE BASE DE DATOS
# - BUSTAMANTE TORRES, FABIAN
# - MEDINA GRADOS, FABIAN 
# - SALAS RAMOS, RODRIGO
import sys
import os
import csv
from PyQt6.QtWidgets import QApplication, QMessageBox
from basededatos.basededatos import BaseDeDatos
from util.estructura import leer_sql, parse_create_table, convertir_fila
from disco.disco import DISCO
from interfaz.interfaz import ConfigDialog, ArchivosDialog, VentanaPrincipal


def main():
    app = QApplication(sys.argv)

    # 1. Configuración del disco
    config = ConfigDialog()
    if not config.exec():
        return
    valores = config.get_valores()
    disco = DISCO(
        platos=valores["platos"],
        pistas=valores["pistas"],
        sectores_por_pista=valores["sectores"],
        tamano_sector=valores["tamano"]
    )

    # 2. Selección de archivos
    archivos = ArchivosDialog()
    if not archivos.exec():
        QMessageBox.warning(None, "Cancelado", "No se seleccionaron archivos.")
        return

    # 3. Cargar estructura y datos
    bd = BaseDeDatos(disco)
    try:
        sql = leer_sql(archivos.ruta_txt)
        nombre_tabla, estructura = parse_create_table(sql)
    except Exception as e:
        QMessageBox.critical(None, "Error", f"Error al procesar .txt:\n{e}")
        return

    try:
        filas = []
        with open(archivos.ruta_csv, encoding='utf-8') as archivo:
            if archivos.chk_headers.isChecked():
                lector = csv.DictReader(archivo, delimiter=',', quotechar='"')
                for row in lector:
                    fila = convertir_fila(estructura, row)
                    filas.append(fila)
            else:
                lector = csv.reader(archivo, delimiter=',', quotechar='"')
                for row in lector:
                    if not row or not any(row):
                        continue
                    # Mapear los valores de la fila a los nombres de la estructura
                    row_dict = {}
                    for i, (col, _) in enumerate(estructura):
                        if i < len(row):
                            row_dict[col] = row[i]
                    fila = convertir_fila(estructura, row_dict)
                    filas.append(fila)

        bd.definir_tabla(nombre_tabla, estructura)

        # ── Carga atómica: cada registro debe caber completo en un sector ──
        resumen = bd.cargar_datos(nombre_tabla, filas)

        # Construir mensaje de resultado para el usuario
        total = len(filas)
        msg = f"Se almacenaron {resumen['insertados']} de {total} registros.\n"

        if resumen["descartados"]:
            n_desc = len(resumen["descartados"])
            msg += f"\n⚠ {n_desc} registro(s) NO se almacenaron por no caber " \
                   f"completos en un sector (no se fragmentan).\n"
            # Mostrar el motivo del primer descartado como ejemplo
            ejemplo = resumen["descartados"][0][1]
            msg += f"Ejemplo: {ejemplo}"

        if resumen["disco_lleno"]:
            msg += "\n\n⚠ El disco se llenó durante la carga. " \
                   "La carga se detuvo, los registros ya guardados quedaron intactos."

        if resumen["insertados"] == 0:
            QMessageBox.critical(
                None, "No se pudo almacenar ningún registro",
                "Ningún registro cupo en un sector.\n\n"
                f"Aumente el tamaño del sector (actual: {valores['tamano']} bytes) "
                "para que pueda contener al menos un registro completo."
            )
            return
        elif resumen["descartados"] or resumen["disco_lleno"]:
            QMessageBox.warning(None, "Carga parcial", msg)
        else:
            QMessageBox.information(None, "Carga completa", msg)

    except Exception as e:
        QMessageBox.critical(None, "Error", f"Error al cargar CSV:\n{e}")
        return

    # 4. Mostrar ventana principal
    ventana = VentanaPrincipal(disco, bd, nombre_tabla)
    ventana.show()
    sys.exit(app.exec())


if __name__ == "__main__":
    main()