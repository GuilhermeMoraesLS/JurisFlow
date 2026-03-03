"""
Módulo de interação humana para validação e correção de dados extraídos pela IA.

Implementa o padrão "Human-in-the-Loop" para garantir que campos obrigatórios
ausentes sejam preenchidos manualmente antes de prosseguir para o cálculo.
"""

from datetime import date, datetime
from typing import Any


def _solicitar_data(nome_campo: str, exemplo: str = "2021-09-01") -> date:
    """
    Solicita ao utilizador uma data válida no formato YYYY-MM-DD.

    Args:
        nome_campo: Nome amigável do campo (ex: "admissão").
        exemplo: Exemplo de data para guiar o utilizador.

    Returns:
        Objeto date validado.
    """
    while True:
        print(f"\n[Human-in-the-Loop] A data de {nome_campo} não foi encontrada no documento.")
        print(f"Por favor, insira a data no formato YYYY-MM-DD (ex: {exemplo}):")
        
        entrada = input("  Data: ").strip()
        
        try:
            data_validada = datetime.strptime(entrada, "%Y-%m-%d").date()
            print(f"  ✓ Data de {nome_campo} aceite: {data_validada.strftime('%d/%m/%Y')}")
            return data_validada
        except ValueError:
            print(f"  ✗ Formato inválido '{entrada}'. Use o formato YYYY-MM-DD (ex: {exemplo}).")


def validar_dados_obrigatorios(dados_extraidos: dict[str, Any]) -> dict[str, Any]:
    """
    Valida os campos obrigatórios do dicionário extraído pela IA.

    Se `data_admissao` ou `data_dispensa` estiverem ausentes (None),
    pausa a execução e solicita input manual ao utilizador.

    Args:
        dados_extraidos: Dicionário com os dados extraídos pela Fase 1 (LLM).
                         Pode conter objetos `date` ou strings "YYYY-MM-DD".

    Returns:
        Dicionário atualizado com os campos obrigatórios preenchidos.

    Exemplo:
        >>> dados = {"data_admissao": None, "data_dispensa": date(2023, 10, 22)}
        >>> dados_atualizados = validar_dados_obrigatorios(dados)
        # [Human-in-the-Loop] A data de admissão não foi encontrada...
        # Data: 2021-09-01
        >>> dados_atualizados["data_admissao"]
        date(2021, 9, 1)
    """
    campos_ausentes = []

    # Verifica quais campos obrigatórios estão em falta
    if not dados_extraidos.get("data_admissao"):
        campos_ausentes.append("data_admissao")

    if not dados_extraidos.get("data_dispensa"):
        campos_ausentes.append("data_dispensa")

    # Se não há campos em falta, retorna imediatamente
    if not campos_ausentes:
        return dados_extraidos

    # Avisa o utilizador sobre os campos em falta
    print("\n" + "=" * 80)
    print("ATENÇÃO: INTERVENÇÃO HUMANA NECESSÁRIA")
    print("=" * 80)
    print(f"Os seguintes campos obrigatórios não foram encontrados no documento:")
    for campo in campos_ausentes:
        nome_legivel = campo.replace("_", " ").title()
        print(f"  - {nome_legivel}")
    print("\nO sistema irá solicitar o preenchimento manual de cada campo em falta.")

    # Solicita input para cada campo em falta
    dados_atualizados = dados_extraidos.copy()

    if "data_admissao" in campos_ausentes:
        data_admissao = _solicitar_data(
            nome_campo="admissão",
            exemplo="2021-09-01"
        )
        dados_atualizados["data_admissao"] = data_admissao

    if "data_dispensa" in campos_ausentes:
        # Usa a data de admissão como referência para o exemplo
        data_ref = dados_atualizados.get("data_admissao")
        exemplo_dispensa = "2023-10-22" if not data_ref else str(date(data_ref.year + 1, data_ref.month, data_ref.day))

        data_dispensa = _solicitar_data(
            nome_campo="dispensa",
            exemplo=exemplo_dispensa
        )
        dados_atualizados["data_dispensa"] = data_dispensa

    # Validação cruzada: admissão deve ser anterior à dispensa
    data_adm = dados_atualizados.get("data_admissao")
    data_disp = dados_atualizados.get("data_dispensa")

    if data_adm and data_disp and data_adm >= data_disp:
        print("\n  ✗ ERRO: A data de admissão não pode ser igual ou posterior à data de dispensa.")
        print("  Por favor, corrija as datas:")
        dados_atualizados["data_admissao"] = _solicitar_data("admissão", "2021-09-01")
        dados_atualizados["data_dispensa"] = _solicitar_data("dispensa", "2023-10-22")

    print("\n  ✓ Validação concluída. Prosseguindo para o cálculo...")
    print("=" * 80)

    return dados_atualizados