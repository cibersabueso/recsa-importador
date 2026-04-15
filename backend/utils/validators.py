from __future__ import annotations

CAMPOS_ESTANDAR: list[str] = [
    "root_cliente",
    "nombre_completo",
    "direccion",
    "telefono_principal",
    "telefono_secundario",
    "email",
    "monto_deuda_original",
    "monto_deuda_actual",
    "fecha_vencimiento",
    "numero_documento",
    "producto",
    "sucursal_origen",
    "dias_mora",
    "tramo_mora",
]

CAMPOS_OBLIGATORIOS_POR_DEFECTO: set[str] = {
    "root_cliente",
    "nombre_completo",
    "monto_deuda_original",
    "fecha_vencimiento",
}


def validar_fila(
    fila: dict[str, str | None], obligatorios: list[str]
) -> tuple[bool, list[str]]:
    errores: list[str] = []
    for campo in obligatorios:
        valor = fila.get(campo)
        if valor is None or str(valor).strip() == "":
            errores.append(f"Campo obligatorio vacío: {campo}")
    return len(errores) == 0, errores


def normalizar_decimal(valor: str | None, separador_decimal: str) -> str | None:
    if valor is None:
        return None
    texto = str(valor).strip()
    if not texto:
        return None
    if separador_decimal == ",":
        texto = texto.replace(".", "").replace(",", ".")
    return texto
