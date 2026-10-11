import struct
import re

def leer_sql(nombre_archivo):
    with open(nombre_archivo, 'r') as f:
        return f.read()

def parse_create_table(sql):
    estructura = []
    nombre_tabla = None

    for linea in sql.splitlines():
        linea = linea.strip().strip(',').strip(';')

        if not linea:
            continue

        if 'create table' in linea.lower():
            match = re.search(r'create table\s+([a-zA-Z_][a-zA-Z0-9_]*)', linea, re.IGNORECASE)
            if match:
                nombre_tabla = match.group(1).lower()
            continue

        if linea.startswith("(") or linea.startswith(")"):
            continue

        # Eliminar decoradores
        linea = linea.split('not null')[0].split('primary key')[0].strip().lower()

        match = re.match(r'^([a-z_][a-z0-9_]*)\s+([a-z]+)(?:\(([^)]+)\))?', linea)
        if not match:
            continue

        nombre, tipo, params = match.groups()

        if tipo in ("varchar", "char", "string") and params:
            estructura.append((nombre, f"{int(params)}s"))
        elif tipo in ("text", "string"):
            # Si no dan tamaño en el string, asignamos 255 por defecto
            estructura.append((nombre, "255s"))
        elif tipo in ("int", "integer", "entero"):
            estructura.append((nombre, "i"))
        elif tipo in ("decimal", "double", "float", "numeric", "real"):
            estructura.append((nombre, "d"))  # d = double (8 bytes) para máxima precisión
        elif tipo in ("boolean", "bool"):
            estructura.append((nombre, "?"))  # ? = boolean (1 byte)
        elif tipo in ("date",):
            estructura.append((nombre, "10s")) # Fecha YYYY-MM-DD
        elif tipo in ("datetime", "timestamp"):
            estructura.append((nombre, "19s")) # YYYY-MM-DD HH:MM:SS

    return nombre_tabla, estructura  


def empaquetar(estructura, datos):
    formato = '=' + ''.join(tipo for _, tipo in estructura)
    valores = []
    for (_, tipo), val in zip(estructura, datos):
        if tipo.endswith('s'):
            tam = int(tipo[:-1])
            valores.append(val.encode('utf-8')[:tam].ljust(tam, b'\x00'))
        else:
            valores.append(val)
    return struct.pack(formato, *valores)

def empaquetar_atributos(estructura, datos):
    """
    Convierte un registro de Python a una LISTA de fragmentos binarios,
    un fragmento por cada atributo. Útil para guardar atributo por atributo sin decapitar.
    """
    lista_bytes = []
    for (_, tipo), val in zip(estructura, datos):
        formato = '=' + tipo
        if tipo.endswith('s'):
            tam = int(tipo[:-1])
            val_bytes = val.encode('utf-8')[:tam].ljust(tam, b'\x00')
            lista_bytes.append(struct.pack(formato, val_bytes))
        else:
            lista_bytes.append(struct.pack(formato, val))
    return lista_bytes

def desempaquetar(estructura, registro_bytes):
    formato = '=' + ''.join(tipo for _, tipo in estructura)
    valores = struct.unpack(formato, registro_bytes)
    resultado = []
    for (_, tipo), val in zip(estructura, valores):
        if tipo.endswith('s'):
            resultado.append(val.decode('utf-8').rstrip('\x00'))
        else:
            resultado.append(val)
    return resultado

def convertir_fila(estructura, fila_dict):
    fila_convertida = []
    # Convertimos todas las llaves del CSV a minúsculas para un match perfecto
    fila_dict_lower = {str(k).strip().lower(): v for k, v in fila_dict.items() if k is not None}
    
    for (col, tipo) in estructura:
        col_buscada = col.lower()
        val = fila_dict_lower.get(col_buscada)
        
        if val is None:
            raise KeyError(f"Columna '{col}' no encontrada en el CSV")

        if tipo == 'i':
            # Si el valor está vacío, asignamos 0 como valor por defecto
            fila_convertida.append(int(val) if str(val).strip() else 0)
        elif tipo == 'd':
            # Si el valor está vacío, asignamos 0.0 como valor por defecto
            fila_convertida.append(float(val) if str(val).strip() else 0.0)
        elif tipo == '?':
            val_bool = str(val).strip().lower() in ('1', 'true', 't', 'yes', 'y')
            fila_convertida.append(val_bool)
        elif tipo.endswith('s'):
            fila_convertida.append(val.strip())
        else:
            fila_convertida.append(val)
    return fila_convertida
