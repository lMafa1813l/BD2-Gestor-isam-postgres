# Preparación de la rama etapa-ii para publicación

Los CSV, metadatos de las mediciones, operaciones, planes y escenarios de fallo
se conservan byte por byte. Sus hashes se pueden volver a comprobar con
`make dist-report`.

Antes de publicar se externalizó la autenticación del nuevo laboratorio. La
clave se genera localmente con `secrets`, se guarda en `.secrets/` con permisos
600 y se suministra a Docker mediante un archivo de secreto. Las conexiones
Python y los user mappings FDW leen ese mismo archivo. No se versiona su valor.

Los ZIP de evidencia contenían además copias redundantes de las fuentes presentes
al medir, con una contraseña fija de demostración. Se retiraron esas entradas
`sources/`; los planes y archivos `trial.json` se conservaron con sus hashes
originales. Los mapas de hashes de fuentes en los metadatos describen la versión
experimental previa a esta externalización de autenticación, y no se han
reemplazado por hashes que aparenten corresponder a la ejecución anterior.

El esquema, las reglas de asignación, las operaciones, las semillas y el método
de medición permanecen iguales. La rama contiene el código vigente y una
validación adicional de conexiones/FDW con las credenciales externalizadas.
Los 70 ensayos oficiales no se presentan como reejecutados tras este cambio.

La evidencia de la Etapa I se conserva en sus archivos históricos originales;
no se ha reescrito `main` ni su historial.
