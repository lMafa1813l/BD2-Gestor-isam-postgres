class NodoAVL:
    def __init__(self, clave, valores):
        self.clave = clave
        self.valores = valores  
        self.izquierda = None
        self.derecha = None
        self.altura = 1

class AVLIndex:
    def __init__(self):
        self.raiz = None

    def insertar(self, clave, id_registro, lbas):
        self.raiz = self._insertar(self.raiz, clave, id_registro, lbas)

    def _insertar(self, nodo, clave, id_registro, lbas):
        if not nodo:
            return NodoAVL(clave, [(id_registro, lbas)])
        if clave < nodo.clave:
            nodo.izquierda = self._insertar(nodo.izquierda, clave, id_registro, lbas)
        elif clave > nodo.clave:
            nodo.derecha = self._insertar(nodo.derecha, clave, id_registro, lbas)
        else:
            nodo.valores.append((id_registro, lbas))
            return nodo

        nodo.altura = 1 + max(self._altura(nodo.izquierda), self._altura(nodo.derecha))
        balance = self._balance(nodo)

        if balance > 1 and clave < nodo.izquierda.clave:
            return self._rotar_derecha(nodo)
        if balance < -1 and clave > nodo.derecha.clave:
            return self._rotar_izquierda(nodo)
        if balance > 1 and clave > nodo.izquierda.clave:
            nodo.izquierda = self._rotar_izquierda(nodo.izquierda)
            return self._rotar_derecha(nodo)
        if balance < -1 and clave < nodo.derecha.clave:
            nodo.derecha = self._rotar_derecha(nodo.derecha)
            return self._rotar_izquierda(nodo)

        return nodo

    def buscar(self, clave):
        return self._buscar(self.raiz, clave)

    def _buscar(self, nodo, clave):
        if not nodo:
            return []
        if clave == nodo.clave:
            return nodo.valores
        elif clave < nodo.clave:
            return self._buscar(nodo.izquierda, clave)
        else:
            return self._buscar(nodo.derecha, clave)

    def buscar_rango(self, minimo, maximo):
        resultados = []
        self._buscar_rango(self.raiz, minimo, maximo, resultados)
        return resultados

    def _buscar_rango(self, nodo, minimo, maximo, resultados):
        if not nodo:
            return
        if minimo < nodo.clave:
            self._buscar_rango(nodo.izquierda, minimo, maximo, resultados)
        if minimo <= nodo.clave <= maximo:
            resultados.extend(nodo.valores)
        if nodo.clave < maximo:
            self._buscar_rango(nodo.derecha, minimo, maximo, resultados)

    def inorden(self):
        resultado = []
        self._inorden(self.raiz, resultado)
        return resultado

    def _inorden(self, nodo, resultado):
        if nodo:
            self._inorden(nodo.izquierda, resultado)
            resultado.extend(nodo.valores)
            self._inorden(nodo.derecha, resultado)

    def _altura(self, nodo):
        return nodo.altura if nodo else 0

    def _balance(self, nodo):
        return self._altura(nodo.izquierda) - self._altura(nodo.derecha)

    def _rotar_derecha(self, z):
        y = z.izquierda
        T3 = y.derecha
        y.derecha = z
        z.izquierda = T3
        z.altura = 1 + max(self._altura(z.izquierda), self._altura(z.derecha))
        y.altura = 1 + max(self._altura(y.izquierda), self._altura(y.derecha))
        return y

    def _rotar_izquierda(self, z):
        y = z.derecha
        T2 = y.izquierda
        y.izquierda = z
        z.derecha = T2
        z.altura = 1 + max(self._altura(z.izquierda), self._altura(z.derecha))
        y.altura = 1 + max(self._altura(y.izquierda), self._altura(y.derecha))
        return y
