from disco.sector import Sector


class DISCO:
    def __init__(self, platos=2, pistas=20, sectores_por_pista=20, tamano_sector=16):
        self.platos = platos
        self.pistas_por_superficie = pistas
        self.sectores_por_pista = sectores_por_pista
        self.superficies_por_plato = 2
        self.tamano_sector = tamano_sector

        self.total_sectores = platos * self.superficies_por_plato * pistas * sectores_por_pista
        self.sectores = [None] * self.total_sectores
        self.mapa_ubicacion_fisica = {}
        self.ultimo_lba_asignado = 0  # Puntero para asignación continua

    def _chs_a_lba(self, plato, superficie, pista, sector):
        spp = self.sectores_por_pista
        pps = self.pistas_por_superficie
        spf = self.superficies_por_plato
        sectores_por_plato = spf * pps * spp
        sectores_por_superficie = pps * spp
        return (plato * sectores_por_plato) + (superficie * sectores_por_superficie) + (pista * spp) + sector

    def _lba_a_chs(self, lba):
        if lba >= self.total_sectores:
            raise ValueError("fuera de rango")
        spp = self.sectores_por_pista
        pps = self.pistas_por_superficie
        spf = self.superficies_por_plato
        sectores_por_plato = spf * pps * spp
        sectores_por_superficie = pps * spp
        plato = lba // sectores_por_plato
        resto_plato = lba % sectores_por_plato
        superficie = resto_plato // sectores_por_superficie
        resto_sup = resto_plato % sectores_por_superficie
        pista = resto_sup // spp
        sector = resto_sup % spp
        return (plato, superficie, pista, sector)

    # ──────────────────────────────────────────────────────────────────
    #  FRAGMENTACIÓN LÓGICA POR ATRIBUTOS
    #  Guarda atributo por atributo. Si el atributo no cabe en el
    #  espacio restante del sector, salta al siguiente sector.
    # ──────────────────────────────────────────────────────────────────
    def guardar_dato(self, lista_atributos_bytes, id_registro):
        ubicaciones = []
        lba_inicial = self.ultimo_lba_asignado
        lba_actual = self.ultimo_lba_asignado
        
        # Historial de cambios para posible ROLLBACK
        fragmentos_agregados = []
        sectores_creados = []

        try:
            for attr_bytes in lista_atributos_bytes:
                tam_attr = len(attr_bytes)

                # Validación vital: si el atributo en sí es más grande que el sector, es físicamente imposible no decapitarlo
                if tam_attr > self.tamano_sector:
                    raise ValueError(
                        f"El atributo pesa {tam_attr} bytes y el sector solo {self.tamano_sector} bytes. "
                        "Para no decapitar, el sector debe ser al menos del tamaño del atributo más grande."
                    )

                guardado = False
                while lba_actual < self.total_sectores:
                    sector = self.sectores[lba_actual]
                    if sector is None:
                        sector = Sector(self.tamano_sector)
                        self.sectores[lba_actual] = sector
                        sectores_creados.append(lba_actual)

                    # Si el atributo cabe COMPLETO en el espacio restante del sector
                    if sector.espacio_disponible() >= tam_attr:
                        sector.agregar_fragmento(id_registro, attr_bytes)
                        frag = sector.fragmentos[-1]
                        ubicaciones.append((lba_actual, frag['inicio'], frag['fin']))
                        
                        # Guardamos en el historial
                        fragmentos_agregados.append((sector, frag))
                        guardado = True
                        break  
                    else:
                        # No cabe. Pasamos al siguiente sector dejando un "hueco" (espacio desperdiciado)
                        lba_actual += 1

                if not guardado:
                    raise MemoryError("¡Disco lleno! No se pudo guardar el registro.")

            # Si terminamos el FOR sin errores, confirmamos la transacción (COMMIT)
            self.ultimo_lba_asignado = lba_actual
            self.mapa_ubicacion_fisica[id_registro] = ubicaciones

        except MemoryError as e:
            # === ROLLBACK (Garbage Collector) ===
            # 1. Revertimos los fragmentos que ya se habían guardado a medias
            for sector, frag in fragmentos_agregados:
                if frag in sector.fragmentos:
                    sector.fragmentos.remove(frag)
                    sector.tamano_ocupado -= (frag['fin'] - frag['inicio'] + 1)
            
            # 2. Eliminamos los sectores que creamos en este intento fallido
            for lba in sectores_creados:
                self.sectores[lba] = None

            # 3. Retornamos el puntero a donde estaba originalmente
            self.ultimo_lba_asignado = lba_inicial
            
            # 4. Volvemos a lanzar el error para que la UI lo notifique
            raise e

    def recuperar_dato(self, id_registro):
        if id_registro not in self.mapa_ubicacion_fisica:
            return None

        # Obtenemos los LBAs únicos preservando el orden
        lbas_unicos = []
        for lba, _, _ in self.mapa_ubicacion_fisica[id_registro]:
            if lba not in lbas_unicos:
                lbas_unicos.append(lba)

        fragmentos = []
        for lba in lbas_unicos:
            sector = self.sectores[lba]
            if sector:
                fragmentos.extend(sector.obtener_fragmentos(id_registro))

        return b''.join(fragmentos)

    def obtener_ubicacion(self, id_registro):
        return self.mapa_ubicacion_fisica.get(id_registro, None)