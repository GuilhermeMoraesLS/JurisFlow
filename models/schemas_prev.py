"""
Schemas Pydantic para extração estruturada de dados de Ações Previdenciárias.

Estes schemas servem como "prompt invisível" para a IA, guiando a extração
de dados de processos contra o INSS através das descrições detalhadas em cada Field.
"""

from datetime import date
from typing import List, Optional

from pydantic import BaseModel, Field


class DadosPrevidenciarios(BaseModel):
    """
    Dados estruturados extraídos de uma Ação Previdenciária contra o INSS.
    
    Este schema força o modelo de IA a retornar informações padronizadas
    e validadas sobre benefícios previdenciários, datas e valores.
    """

    nome_segurado: Optional[str] = Field(
        default=None,
        description="Nome completo do segurado/autor da ação previdenciária"
    )
    
    tipo_beneficio: Optional[str] = Field(
        default=None,
        description=(
            "Tipo de benefício previdenciário requerido ou concedido. "
            "Exemplos: 'Aposentadoria por Invalidez', 'Auxílio-Doença', "
            "'Aposentadoria por Tempo de Contribuição', 'Pensão por Morte', "
            "'Auxílio-Acidente', 'Aposentadoria Especial', 'BPC-LOAS'"
        )
    )
    
    dib: Optional[date] = Field(
        default=None,
        description=(
            "DIB - Data de Início do Benefício (também chamada de Data do Fato Gerador). "
            "É a data a partir da qual o benefício deveria ter sido concedido. "
            "Use o formato ISO: YYYY-MM-DD (exemplo: 2021-03-15). "
            "Se não encontrar explicitamente no documento, procure por termos como: "
            "'data do requerimento administrativo', 'DER', 'data da incapacidade', "
            "'data do óbito' (em caso de pensão). Se não houver, retorne null."
        )
    )
    
    dip: Optional[date] = Field(
        default=None,
        description=(
            "DIP - Data de Início do Pagamento. É a data em que o INSS voltou a pagar "
            "ou foi determinado a começar o pagamento do benefício. "
            "Use o formato ISO: YYYY-MM-DD (exemplo: 2023-07-01). "
            "Em muitos casos, a DIP não está explícita no documento - se não encontrar, "
            "retorne null. Não confunda com a DIB."
        )
    )
    
    rmi: Optional[float] = Field(
        default=None,
        description=(
            "RMI - Renda Mensal Inicial do benefício, em Reais. "
            "É o valor mensal que o segurado tem direito a receber. "
            "Procure por termos como: 'valor do benefício', 'RMI', 'renda mensal', "
            "'salário de benefício'. "
            "Se o valor NÃO estiver explícito no PDF, procure no 'Contexto Adicional' "
            "fornecido pelo usuário (pode estar em uma consulta ao CNIS ou cálculo à parte). "
            "Se não houver informação em lugar nenhum, retorne null. "
            "NÃO invente valores - apenas extraia."
        )
    )
    
    tem_adicional_25: bool = Field(
        default=False,
        description=(
            "Indica se há direito ao acréscimo de 25% sobre o valor do benefício "
            "(adicional de grande invalidez, previsto no Art. 45 da Lei 8.213/91). "
            "Marque como true apenas se o documento mencionar explicitamente: "
            "'grande invalidez', 'adicional de 25%', 'necessidade de assistência permanente'. "
            "Se não houver menção, marque como false."
        )
    )
    
    indice_correcao: str = Field(
        default="SELIC",
        description=(
            "Índice de correção monetária a ser aplicado nos atrasados. "
            "Valores aceitos: 'SELIC', 'INPC', 'IPCA-E', 'TR'. "
            "Se não estiver especificado no documento, use 'SELIC' como padrão "
            "(conforme jurisprudência recente do STF - Tema 810). "
            "Procure na seção de pedidos ou no dispositivo da sentença."
        )
    )
    
    observacoes: List[str] = Field(
        default_factory=list,
        description=(
            "Lista de fatos relevantes extraídos do processo. Exemplos: "
            "'Benefício indeferido administrativamente sob protocolo NB 123.456.789-0', "
            "'Laudo médico pericial anexado aos autos', "
            "'Autor requereu tutela de urgência para implantação imediata', "
            "'Sentença concedeu o benefício com base em prova testemunhal', "
            "'Processo em grau de recurso (TRF-3)'. "
            "Use linguagem objetiva e evite interpretações."
        )
    )