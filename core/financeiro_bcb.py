"""
Módulo de cálculos financeiros com integração ao Banco Central do Brasil.

Implementa busca de índices oficiais (SELIC, INPC, IPCA-E) e cálculo de
atrasados previdenciários com correção monetária e juros.
"""

from datetime import date
from typing import Dict, Any, List
from dateutil.relativedelta import relativedelta
from bcb import sgs
import warnings


class GerenteFinanceiroBCB:
    """
    Gerencia cálculos financeiros usando índices oficiais do Banco Central.
    
    Integra-se com a API do BCB (Sistema Gerenciador de Séries Temporais - SGS)
    para buscar taxas de correção monetária e juros aplicáveis a ações previdenciárias.
    """
    
    # Códigos das séries temporais do SGS/BCB
    CODIGO_SELIC_MENSAL = 4189  # Taxa SELIC acumulada mensalmente
    CODIGO_INPC_MENSAL = 188    # INPC mensal
    CODIGO_IPCA_E_MENSAL = 433  # IPCA-E mensal
    
    def __init__(self):
        """Inicializa o gerente financeiro."""
        self.cache_taxas: Dict[str, Any] = {}
    
    def get_selic_acumulada(self, data_inicio: date, data_fim: date) -> float:
        """
        Busca a taxa SELIC acumulada entre duas datas no BCB.
        
        Args:
            data_inicio: Data inicial do período.
            data_fim: Data final do período.
        
        Returns:
            Taxa SELIC acumulada no período (em decimal, ex: 0.1350 = 13,50%).
            Em caso de erro na API, retorna taxa estimada de fallback.
        
        Exemplo:
            >>> gerente = GerenteFinanceiroBCB()
            >>> taxa = gerente.get_selic_acumulada(date(2023, 1, 1), date(2023, 12, 31))
            >>> print(f"SELIC acumulada: {taxa:.4%}")
        """
        try:
            # Busca a série temporal da SELIC no BCB
            df_selic = sgs.get(
                {'selic': self.CODIGO_SELIC_MENSAL},
                start=data_inicio,
                end=data_fim
            )
            
            if df_selic.empty:
                warnings.warn(
                    f"Nenhum dado SELIC encontrado para {data_inicio} a {data_fim}. "
                    "Usando taxa de fallback."
                )
                return self._taxa_fallback_selic(data_inicio, data_fim)
            
            # Calcula a taxa acumulada usando fórmula: (1 + r1) * (1 + r2) * ... - 1
            # As taxas do BCB vêm em percentual (ex: 1.25 = 1,25%)
            taxas_mensais = df_selic['selic'] / 100  # Converte para decimal
            taxa_acumulada = (1 + taxas_mensais).prod() - 1
            
            return float(taxa_acumulada)
        
        except Exception as e:
            warnings.warn(
                f"Erro ao buscar SELIC no BCB: {type(e).__name__} - {str(e)}. "
                "Usando taxa de fallback."
            )
            return self._taxa_fallback_selic(data_inicio, data_fim)
    
    def _taxa_fallback_selic(self, data_inicio: date, data_fim: date) -> float:
        """
        Retorna taxa SELIC estimada quando a API do BCB falhar.
        
        Tabela simplificada baseada em médias históricas recentes.
        
        Args:
            data_inicio: Data inicial do período.
            data_fim: Data final do período.
        
        Returns:
            Taxa estimada (aproximação para MVP).
        """
        # Calcula número de meses entre as datas
        delta = relativedelta(data_fim, data_inicio)
        meses = (delta.years * 12) + delta.months + (1 if delta.days > 0 else 0)
        
        # Taxa mensal média aproximada (baseada em período 2023-2024: ~1,08% a.m.)
        taxa_mensal_media = 0.0108  # 1,08% ao mês
        
        # Fórmula de juros compostos: (1 + i)^n - 1
        taxa_acumulada = (1 + taxa_mensal_media) ** meses - 1
        
        return taxa_acumulada
    
    def get_inpc_acumulado(self, data_inicio: date, data_fim: date) -> float:
        """
        Busca o INPC acumulado entre duas datas no BCB.
        
        Args:
            data_inicio: Data inicial do período.
            data_fim: Data final do período.
        
        Returns:
            Índice INPC acumulado (em decimal, ex: 0.0523 = 5,23%).
        """
        try:
            df_inpc = sgs.get(
                {'inpc': self.CODIGO_INPC_MENSAL},
                start=data_inicio,
                end=data_fim
            )
            
            if df_inpc.empty:
                return self._taxa_fallback_inpc(data_inicio, data_fim)
            
            # Acumula os índices mensais
            taxas_mensais = df_inpc['inpc'] / 100
            indice_acumulado = (1 + taxas_mensais).prod() - 1
            
            return float(indice_acumulado)
        
        except Exception as e:
            warnings.warn(f"Erro ao buscar INPC: {e}. Usando fallback.")
            return self._taxa_fallback_inpc(data_inicio, data_fim)
    
    def _taxa_fallback_inpc(self, data_inicio: date, data_fim: date) -> float:
        """Fallback do INPC (média ~0,4% a.m. em 2023-2024)."""
        delta = relativedelta(data_fim, data_inicio)
        meses = (delta.years * 12) + delta.months + (1 if delta.days > 0 else 0)
        taxa_mensal_media = 0.004  # 0,4% ao mês
        return (1 + taxa_mensal_media) ** meses - 1
    
    def get_ipca_e_acumulado(self, data_inicio: date, data_fim: date) -> float:
        """
        Busca o IPCA-E acumulado entre duas datas no BCB.
        
        Args:
            data_inicio: Data inicial do período.
            data_fim: Data final do período.
        
        Returns:
            Índice IPCA-E acumulado (em decimal).
        """
        try:
            df_ipca_e = sgs.get(
                {'ipca_e': self.CODIGO_IPCA_E_MENSAL},
                start=data_inicio,
                end=data_fim
            )
            
            if df_ipca_e.empty:
                return self._taxa_fallback_ipca_e(data_inicio, data_fim)
            
            taxas_mensais = df_ipca_e['ipca_e'] / 100
            indice_acumulado = (1 + taxas_mensais).prod() - 1
            
            return float(indice_acumulado)
        
        except Exception as e:
            warnings.warn(f"Erro ao buscar IPCA-E: {e}. Usando fallback.")
            return self._taxa_fallback_ipca_e(data_inicio, data_fim)
    
    def _taxa_fallback_ipca_e(self, data_inicio: date, data_fim: date) -> float:
        """Fallback do IPCA-E (média ~0,42% a.m. em 2023-2024)."""
        delta = relativedelta(data_fim, data_inicio)
        meses = (delta.years * 12) + delta.months + (1 if delta.days > 0 else 0)
        taxa_mensal_media = 0.0042  # 0,42% ao mês
        return (1 + taxa_mensal_media) ** meses - 1
    
    def calcular_atrasados(
        self,
        rmi: float,
        data_inicio: date,
        data_fim: date,
        indice: str = "SELIC",
        tem_adicional_25: bool = False
    ) -> Dict[str, Any]:
        """
        Calcula o valor total de atrasados previdenciários com correção monetária.
        
        Args:
            rmi: Renda Mensal Inicial do benefício (valor mensal).
            data_inicio: DIB - Data de Início do Benefício.
            data_fim: Data final do cálculo (geralmente data da sentença ou data atual).
            indice: Índice de correção: "SELIC", "INPC" ou "IPCA-E".
            tem_adicional_25: Se aplica adicional de 25% (grande invalidez).
        
        Returns:
            Dicionário contendo:
            - status: "sucesso" ou "erro"
            - rmi_base: RMI original
            - rmi_com_adicional: RMI + 25% (se aplicável)
            - total_meses: Quantidade de meses de atraso
            - total_devido_sem_correcao: Soma simples (RMI × meses)
            - indice_aplicado: Nome do índice usado
            - taxa_acumulada: Taxa de correção total do período
            - total_corrigido: Valor final com correção
            - memoria_mensal: Lista de meses com valores detalhados
            - observacoes: Notas sobre o cálculo
        
        Exemplo:
            >>> gerente = GerenteFinanceiroBCB()
            >>> resultado = gerente.calcular_atrasados(
            ...     rmi=1500.0,
            ...     data_inicio=date(2023, 1, 1),
            ...     data_fim=date(2024, 1, 1),
            ...     indice="SELIC"
            ... )
            >>> print(f"Total corrigido: R$ {resultado['total_corrigido']:.2f}")
        """
        # Validações
        if rmi <= 0:
            return {
                "status": "erro",
                "erro": "RMI deve ser maior que zero.",
                "total_corrigido": 0.0
            }
        
        if data_inicio >= data_fim:
            return {
                "status": "erro",
                "erro": "Data de início deve ser anterior à data final.",
                "total_corrigido": 0.0
            }
        
        # Aplica adicional de 25% se for grande invalidez
        rmi_efetivo = rmi * 1.25 if tem_adicional_25 else rmi
        
        # Calcula número de meses de atraso
        delta = relativedelta(data_fim, data_inicio)
        total_meses = (delta.years * 12) + delta.months + (1 if delta.days > 0 else 0)
        
        # Total devido sem correção (soma simples)
        total_sem_correcao = rmi_efetivo * total_meses
        
        # Busca taxa de correção de acordo com o índice escolhido
        if indice.upper() == "SELIC":
            taxa_acumulada = self.get_selic_acumulada(data_inicio, data_fim)
        elif indice.upper() == "INPC":
            taxa_acumulada = self.get_inpc_acumulado(data_inicio, data_fim)
        elif indice.upper() == "IPCA-E":
            taxa_acumulada = self.get_ipca_e_acumulado(data_inicio, data_fim)
        else:
            return {
                "status": "erro",
                "erro": f"Índice '{indice}' não suportado. Use SELIC, INPC ou IPCA-E.",
                "total_corrigido": 0.0
            }
        
        # Aplica correção sobre o total devido
        total_corrigido = total_sem_correcao * (1 + taxa_acumulada)
        
        # Gera memória de cálculo mensal (simplificada para MVP)
        memoria_mensal: List[Dict[str, Any]] = []
        data_atual = data_inicio
        
        for mes_num in range(1, total_meses + 1):
            # Simplificação: aplica fração da taxa proporcional ao tempo decorrido
            meses_desde_inicio = mes_num
            taxa_proporcional = taxa_acumulada * (meses_desde_inicio / total_meses)
            valor_mensal_corrigido = rmi_efetivo * (1 + taxa_proporcional)
            
            memoria_mensal.append({
                "mes": mes_num,
                "competencia": data_atual.strftime("%m/%Y"),
                "valor_base": round(rmi_efetivo, 2),
                "taxa_periodo": round(taxa_proporcional * 100, 4),
                "valor_corrigido": round(valor_mensal_corrigido, 2)
            })
            
            # Avança para o próximo mês
            data_atual = data_atual + relativedelta(months=1)
        
        # Observações
        observacoes = []
        
        if tem_adicional_25:
            observacoes.append(
                f"Acréscimo de 25% aplicado (grande invalidez). "
                f"RMI original: R$ {rmi:.2f} → RMI efetivo: R$ {rmi_efetivo:.2f}"
            )
        
        observacoes.append(
            f"Índice de correção: {indice.upper()} (conforme determinação judicial)."
        )
        
        observacoes.append(
            f"Taxa acumulada no período: {taxa_acumulada:.4%}"
        )
        
        observacoes.append(
            "Cálculo simplificado para MVP. Em produção, usar cálculo mês a mês "
            "com taxas específicas de cada competência."
        )
        
        # Monta resultado
        return {
            "status": "sucesso",
            "rmi_base": round(rmi, 2),
            "rmi_com_adicional": round(rmi_efetivo, 2),
            "tem_adicional_25": tem_adicional_25,
            "total_meses": total_meses,
            "total_devido_sem_correcao": round(total_sem_correcao, 2),
            "indice_aplicado": indice.upper(),
            "taxa_acumulada": round(taxa_acumulada * 100, 4),  # Em percentual
            "total_corrigido": round(total_corrigido, 2),
            "diferenca_correcao": round(total_corrigido - total_sem_correcao, 2),
            "memoria_mensal": memoria_mensal,
            "observacoes": observacoes,
            "data_inicio": data_inicio.isoformat(),
            "data_fim": data_fim.isoformat(),
            "data_calculo": date.today().isoformat()
        }