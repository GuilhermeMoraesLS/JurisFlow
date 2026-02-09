"""
Schemas Pydantic para extração estruturada de dados de Reclamações Trabalhistas.

Estes schemas servem como "prompt invisível" para a IA, guiando a extração
de dados através das descrições detalhadas em cada Field.
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class Adicionais(BaseModel):
    """Adicionais salariais recebidos pelo trabalhador."""

    insalubridade: Optional[float] = Field(
        default=None,
        description="Valor financeiro ou percentual do adicional de insalubridade"
    )
    periculosidade: Optional[float] = Field(
        default=None,
        description="Valor financeiro ou percentual do adicional de periculosidade"
    )
    noturno: Optional[float] = Field(
        default=None,
        description="Valor financeiro do adicional noturno"
    )


class DadosTrabalhistasExtraidos(BaseModel):
    """
    Dados estruturados extraídos de uma Reclamação Trabalhista.
    
    Este schema força o modelo de IA a retornar informações padronizadas
    e validadas sobre o vínculo empregatício e verbas rescisórias.
    """

    data_admissao: Optional[date] = Field(
        default=None,
        description="Data exata em que o vínculo empregatício iniciou"
    )
    data_dispensa: Optional[date] = Field(
        default=None,
        description="Data exata em que o funcionário foi demitido ou saiu"
    )
    salario_base: Optional[float] = Field(
        default=None,
        description="Último salário base recebido pelo funcionário, em formato numérico (ex: 1500.50)"
    )
    adicionais: Optional[Adicionais] = Field(
        default=None,
        description="Adicionais salariais recebidos (insalubridade, periculosidade, noturno)"
    )
    verbas_requeridas: List[str] = Field(
        default_factory=list,
        description=(
            "Lista padronizada das verbas rescisórias solicitadas. "
            "Use apenas termos como: 'aviso_previo', 'fgts', 'multa_40', "
            "'ferias_proporcionais', 'decimo_terceiro'. Não invente chaves."
        )
    )
    justificativa_demissao: Optional[str] = Field(
        default=None,
        description="Motivo da saída: 'sem justa causa', 'justa causa', 'pedido de demissão', etc."
    )
    observacoes: List[str] = Field(
        default_factory=list,
        description="Fatos relevantes como 'CTPS não assinada', 'escala 12x36', etc."
    )
    multa_467_requerida: bool = Field(
        default=False,
        description="True se houver pedido explícito da multa do Art. 467 (verbas incontroversas). False caso contrário."
    )
    multa_477_requerida: bool = Field(
        default=False,
        description="True se houver pedido da multa do Art. 477 (atraso no pagamento das verbas). False caso contrário."
    )