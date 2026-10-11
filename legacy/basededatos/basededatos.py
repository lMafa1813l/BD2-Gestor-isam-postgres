from disco.disco import DISCO
from memoria.Avl import AVLIndex
from util.estructura import empaquetar_atributos, desempaquetar

class BaseDeDatos:
    def __init__(self, disco=None):
        self.disco = disco if disco else DISCO()
        self.tablas = {}

    def definir_tabla(self, nombre_tabla, estructura):
        columnas = [col for col, _ in estructura]
        
        def bool_parser(v):
            if isinstance(v, str):
                return v.strip().lower() in ('1', 'true', 't', 'yes', 'y')
            return bool(v)

        tipos = {
            col: (
                int   if tipo == 'i' else
                float if tipo == 'd' else
                bool_parser if tipo == '?' else
                str
            )
            for col, tipo in estructura
        }
        self.tablas[nombre_tabla] = {
            'estructura': estructura,
            'columnas':   columnas,
            'tipos':      tipos,
            # ── CORRECCIÓN: se crea un AVL por TODAS las columnas ──────────
            'indices':    {col: AVLIndex() for col in columnas},
            'registros':  {}
        }

    def cargar_datos(self, nombre_tabla, filas):
        """
        Carga los registros usando FRAGMENTACIÓN LÓGICA POR ATRIBUTOS.
        Cada atributo se guarda íntegramente. Si un atributo no cabe en el 
        sector actual, se coloca en el siguiente sector, dejando el espacio 
        sobrante vacío para no decapitar el dato.
        """
        tabla      = self.tablas[nombre_tabla]
        estructura = tabla['estructura']

        resumen = {"insertados": 0, "descartados": [], "disco_lleno": False}

        for fila in filas:
            id_reg  = f"{nombre_tabla}_{len(tabla['registros']) + 1}"
            
            # Convierte la fila a una lista de bloques binarios (uno por atributo)
            lista_atributos_bytes = empaquetar_atributos(estructura, fila)

            try:
                self.disco.guardar_dato(lista_atributos_bytes, id_reg)
            except ValueError as e:
                # El atributo en sí es más grande que todo el sector (imposible de guardar sin decapitar)
                resumen["descartados"].append((fila, str(e)))
                continue
            except MemoryError:
                # No hay más sectores libres: se detiene la carga
                resumen["disco_lleno"] = True
                break

            ubicacion = self.disco.obtener_ubicacion(id_reg)
            for (col, _), val in zip(estructura, fila):
                tabla['indices'][col].insertar(val, id_reg, ubicacion)

            tabla['registros'][id_reg] = ubicacion
            resumen["insertados"] += 1

        return resumen

    def buscar_por_campo(self, nombre_tabla, columna, valor):
        tabla = self.tablas.get(nombre_tabla)
        if not tabla:
            return []

        estructura = tabla['estructura']
        tipo       = tabla['tipos'].get(columna, str)

        if not valor.strip():
            return self._recuperar_todos(tabla)

        try:
            valor_convertido = tipo(valor)
        except (ValueError, TypeError):
            return []

        avl = tabla['indices'].get(columna)
        if not avl:
            return []

        coincidencias = avl.buscar(valor_convertido)
        resultados = []
        for id_reg, _ in coincidencias:
            data = self.disco.recuperar_dato(id_reg)
            if data:
                fila = desempaquetar(estructura, data)
                resultados.append({
                    "id":        id_reg,
                    "registro":  {col: val for (col, _), val in zip(estructura, fila)},
                    "ubicacion": self.disco.obtener_ubicacion(id_reg)
                })
        return resultados

    def buscar_por_rango(self, nombre_tabla, columna, valor_min, valor_max):
        tabla = self.tablas.get(nombre_tabla)
        if not tabla:
            return []

        estructura = tabla['estructura']
        tipo       = tabla['tipos'].get(columna, str)

        try:
            min_c = tipo(valor_min)
            max_c = tipo(valor_max)
        except (ValueError, TypeError):
            return []

        if min_c > max_c:
            min_c, max_c = max_c, min_c

        # ── CORRECCIÓN: solo para columnas de texto 
        # Una comparación de strings es letra por letra: "L" < "Leo" es
        # falso porque "Leo" sigue agregando caracteres después de "L".
        # Para que el usuario pueda escribir "L" y que incluya cualquier
        # palabra que empiece con esa letra (Leo, Luis, etc.), se le
        # agrega un sufijo que la hace "mayor" que cualquier palabra que
        # comience igual.
        if tipo is str:
            max_c = max_c + "\uffff"

        avl = tabla['indices'].get(columna)
        if not avl:
            return []

        coincidencias = avl.buscar_rango(min_c, max_c)
        resultados = []
        for id_reg, _ in coincidencias:
            data = self.disco.recuperar_dato(id_reg)
            if data:
                fila = desempaquetar(estructura, data)
                resultados.append({
                    "id":        id_reg,
                    "registro":  {col: val for (col, _), val in zip(estructura, fila)},
                    "ubicacion": self.disco.obtener_ubicacion(id_reg)
                })
        return resultados

    def _recuperar_todos(self, tabla):
        estructura = tabla['estructura']
        resultados = []
        for id_reg, ubicacion in tabla['registros'].items():
            data = self.disco.recuperar_dato(id_reg)
            if data:
                fila = desempaquetar(estructura, data)
                resultados.append({
                    "id":        id_reg,
                    "registro":  {col: val for (col, _), val in zip(estructura, fila)},
                    "ubicacion": ubicacion
                })
        return resultados

    def listar_registros(self, nombre_tabla):
        tabla = self.tablas.get(nombre_tabla)
        if not tabla:
            return []
        return self._recuperar_todos(tabla)