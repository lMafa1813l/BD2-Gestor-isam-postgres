class Sector:
    def __init__(self, tamano):
        self.tamano_total = tamano
        self.fragmentos = []  
        self.tamano_ocupado = 0

    def espacio_disponible(self):
        return self.tamano_total - self.tamano_ocupado

    def agregar_fragmento(self, id_registro, fragmento_bytes):
        disponible = self.espacio_disponible()
        if disponible == 0:
            return 0  

        longitud_a_guardar = min(len(fragmento_bytes), disponible)
        inicio = self.tamano_ocupado
        fin = inicio + longitud_a_guardar - 1

        self.fragmentos.append({
            'id_registro': id_registro,
            'datos': fragmento_bytes[:longitud_a_guardar],
            'inicio': inicio,
            'fin': fin
        })
        self.tamano_ocupado += longitud_a_guardar
        return longitud_a_guardar 


    def obtener_fragmentos(self, id_registro):
        return [frag['datos'] for frag in self.fragmentos if frag['id_registro'] == id_registro]
