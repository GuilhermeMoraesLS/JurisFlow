"""
Agente especialista em cálculo de atrasados previdenciários do INSS.

Este módulo orquestra a extração de dados via IA (GPT-4o-mini) e o cálculo
de atrasados com correção monetária por índices oficiais do Banco Central.
"""

import os
import sys
import json
from pathlib import Path

# Adiciona a raiz do projeto ao PYTHONPATH
raiz_projeto = Path(__file__).parent.parent
sys.path.insert(0, str(raiz_projeto))

from datetime import date

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

from tools.pdf_reader import LegalPDFReader
from models.schemas_prev import DadosPrevidenciarios
from core.financeiro_bcb import GerenteFinanceiroBCB
from core.lookup_data import obter_salario_minimo, validar_rmi


def carregar_prompt_sistema() -> str:
    """
    Carrega as instruções de sistema do arquivo Markdown.

    Returns:
        String contendo o prompt completo do contador previdenciário.
        
    Raises:
        FileNotFoundError: Se o arquivo de prompt não existir.
    """
    # Caminho relativo à raiz do projeto
    prompt_path = raiz_projeto / "prompts" / "extrator_previdenciario.md"
    
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Arquivo de prompt não encontrado: {prompt_path}\n"
            "Certifique-se de que prompts/extrator_previdenciario.md existe."
        )
    
    return prompt_path.read_text(encoding="utf-8")


def gerar_exemplo_schema() -> str:
    """
    Gera um exemplo do schema esperado para guiar a IA.
    
    Returns:
        String JSON com exemplo do formato esperado.
    """
    exemplo = {
        "nome_segurado": "Maria da Silva Oliveira",
        "tipo_beneficio": "Aposentadoria por Invalidez",
        "dib": "2021-06-15",
        "dip": None,
        "rmi": 1500.0,
        "tem_adicional_25": False,
        "indice_correcao": "SELIC",
        "observacoes": [
            "Benefício concedido judicialmente sob protocolo NB 187.654.321-0",
            "Sentença transitada em julgado em 10/12/2023"
        ]
    }
    return json.dumps(exemplo, indent=2, ensure_ascii=False)


def inicializar_agente() -> Agent:
    """
    Configura e retorna o agente de extração previdenciária.

    Returns:
        Agente configurado com GPT-4o-mini, ferramentas e schema estruturado.
    """
    system_prompt = carregar_prompt_sistema()
    exemplo_json = gerar_exemplo_schema()
    
    # Adiciona o exemplo ao prompt
    prompt_completo = f"""{system_prompt}

# EXEMPLO DE RESPOSTA ESPERADA

Para um processo com:
- Segurado: Maria da Silva Oliveira
- Benefício: Aposentadoria por Invalidez
- DIB: 15/06/2021
- RMI (do contexto adicional): R$ 1.500,00

Você deve retornar EXATAMENTE este formato:

```json
{exemplo_json}
```

IMPORTANTE: Retorne APENAS o JSON, sem texto adicional."""

    agent = Agent(
        model=OpenAIChat(id="gpt-4o-mini", temperature=0.1),  # Temperatura baixa para precisão
        description="Contador Previdenciário Especialista em extração de dados do INSS",
        tools=[LegalPDFReader()],
        markdown=False,  # Desativa markdown para evitar code blocks
        instructions=prompt_completo,
    )
    
    return agent


def limpar_json_da_resposta(resposta: str) -> str:
    """
    Remove markdown code blocks e texto extra da resposta da IA.
    
    Args:
        resposta: Texto bruto retornado pela IA
        
    Returns:
        String JSON limpa
    """
    # Remove markdown code blocks
    if "```json" in resposta:
        inicio = resposta.find("```json") + 7
        fim = resposta.rfind("```")
        return resposta[inicio:fim].strip()
    elif "```" in resposta:
        inicio = resposta.find("```") + 3
        fim = resposta.rfind("```")
        return resposta[inicio:fim].strip()
    
    # Procura por { } no texto
    inicio_json = resposta.find("{")
    fim_json = resposta.rfind("}") + 1
    
    if inicio_json != -1 and fim_json > inicio_json:
        return resposta[inicio_json:fim_json]
    
    return resposta.strip()


def detectar_salario_minimo_dinamico(dados: DadosPrevidenciarios) -> bool:
    """
    Detecta se o benefício deve usar salário mínimo dinâmico.
    
    Esta função analisa os dados extraídos pela IA e determina se o benefício
    acompanha os reajustes do salário mínimo ou tem valor fixo.
    
    Args:
        dados: Dados previdenciários extraídos pela IA.
        
    Returns:
        True se deve usar salário mínimo dinâmico, False caso contrário.
        
    Lógica de Detecção:
        1. Se a RMI está ausente ou é zero → usa salário mínimo dinâmico
        2. Se a RMI é aproximadamente igual ao salário mínimo vigente na DIB → usa dinâmico
        3. Se nas observações houver menção a "salário mínimo" → usa dinâmico
        4. Caso contrário → usa valor fixo
    """
    # 1. Se não tem RMI informada, assume salário mínimo
    if not dados.rmi or dados.rmi <= 0:
        return True
    
    # 2. Verifica se a RMI é aproximadamente igual ao salário mínimo na DIB
    if dados.dib:
        try:
            salario_minimo_dib = obter_salario_minimo(dados.dib)
            
            # Tolerância de R$ 5,00 para considerar como salário mínimo
            # (para casos de arredondamento ou valores próximos)
            diferenca = abs(dados.rmi - salario_minimo_dib)
            
            if diferenca <= 5.0:
                return True
            
            # Também verifica com o adicional de 25% aplicado
            if dados.tem_adicional_25:
                salario_com_adicional = salario_minimo_dib * 1.25
                diferenca_com_adicional = abs(dados.rmi - salario_com_adicional)
                
                if diferenca_com_adicional <= 5.0:
                    return True
        
        except ValueError:
            # Se não conseguir buscar salário mínimo da DIB, continua análise
            pass
    
    # 3. Verifica observações por palavras-chave
    if dados.observacoes:
        palavras_chave_sm = [
            "salário mínimo",
            "salario minimo",
            "um salário mínimo",
            "1 salário mínimo",
            "benefício de piso",
            "piso previdenciário",
            "valor mínimo",
            "sm vigente"
        ]
        
        observacoes_lower = [obs.lower() for obs in dados.observacoes]
        texto_observacoes = " ".join(observacoes_lower)
        
        for palavra_chave in palavras_chave_sm:
            if palavra_chave in texto_observacoes:
                return True
    
    # 4. Se passou por todos os testes, é um valor fixo
    return False


def formatar_relatorio_previdenciario(
    dados: DadosPrevidenciarios,
    resultado_calculo: dict
) -> str:
    """
    Formata os resultados em texto limpo, pronto para copiar no Word.
    
    Args:
        dados: Dados estruturados extraídos pela IA.
        resultado_calculo: Resultado do cálculo de atrasados com correção.
        
    Returns:
        String formatada sem emojis, pronta para documento oficial.
    """
    linhas = []
    
    # Cabeçalho
    linhas.append("=" * 80)
    linhas.append("RELATORIO DE CALCULO DE ATRASADOS PREVIDENCIARIOS")
    linhas.append("JurisFlow - Sistema de Calculo Juridico")
    linhas.append("=" * 80)
    linhas.append("")
    
    # Identificação do Segurado
    if dados.nome_segurado:
        linhas.append("SEGURADO: " + dados.nome_segurado.upper())
        linhas.append("")
    
    # Dados do Benefício
    linhas.append("-" * 80)
    linhas.append("1. DADOS DO BENEFICIO PREVIDENCIARIO")
    linhas.append("-" * 80)
    linhas.append("")
    
    if dados.tipo_beneficio:
        linhas.append(f"Tipo de Beneficio: {dados.tipo_beneficio}")
    
    if dados.dib:
        linhas.append(f"DIB (Data de Inicio do Beneficio): {dados.dib.strftime('%d/%m/%Y')}")
    
    if dados.dip:
        linhas.append(f"DIP (Data de Inicio do Pagamento): {dados.dip.strftime('%d/%m/%Y')}")
    
    # RMI (com campo especial para salário mínimo dinâmico)
    if resultado_calculo.get('usar_salario_minimo_dinamico'):
        linhas.append("RMI (Renda Mensal Inicial): SALARIO MINIMO NACIONAL (atualizado mensalmente)")
        
        if dados.tem_adicional_25:
            linhas.append("  + Adicional de 25% (Grande Invalidez) aplicado sobre cada competencia")
    elif dados.rmi:
        valor_rmi = f"R$ {dados.rmi:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        linhas.append(f"RMI (Renda Mensal Inicial): {valor_rmi} (Valor Fixo)")
        
        if dados.tem_adicional_25:
            rmi_com_adicional = dados.rmi * 1.25
            valor_total = f"R$ {rmi_com_adicional:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            linhas.append(f"RMI com Adicional de 25% (Grande Invalidez): {valor_total}")
    
    linhas.append(f"Indice de Correcao: {dados.indice_correcao}")
    linhas.append("")
    
    # Observações do Processo
    if dados.observacoes:
        linhas.append("-" * 80)
        linhas.append("2. OBSERVACOES DO PROCESSO")
        linhas.append("-" * 80)
        linhas.append("")
        for i, obs in enumerate(dados.observacoes, 1):
            linhas.append(f"{i}. {obs}")
        linhas.append("")
    
    # Cálculo de Atrasados
    if resultado_calculo["status"] == "sucesso":
        linhas.append("-" * 80)
        linhas.append("3. CALCULO DE ATRASADOS COM CORRECAO MONETARIA")
        linhas.append("-" * 80)
        linhas.append("")
        
        linhas.append(f"Periodo de Atraso:")
        linhas.append(f"  Data Inicial (DIB): {resultado_calculo['data_inicio']}")
        linhas.append(f"  Data Final: {resultado_calculo['data_fim']}")
        linhas.append(f"  Total de Meses em Atraso: {resultado_calculo['total_meses']}")
        linhas.append("")
        
        # Base de cálculo
        if resultado_calculo.get('usar_salario_minimo_dinamico'):
            linhas.append("BASE DE CALCULO: Salario Minimo Nacional (atualizado mensalmente)")
            linhas.append("  O valor foi ajustado conforme os reajustes oficiais em cada competencia.")
        else:
            valor_base = f"R$ {resultado_calculo['rmi_base']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            linhas.append(f"RMI Base (Valor Fixo): {valor_base}")
        
        if resultado_calculo['tem_adicional_25']:
            if resultado_calculo.get('usar_salario_minimo_dinamico'):
                linhas.append("  + Adicional de 25% (Grande Invalidez) sobre cada competencia")
            else:
                valor_adicional = f"R$ {resultado_calculo['rmi_com_adicional']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                linhas.append(f"RMI com Adicional de 25%: {valor_adicional}")
        
        linhas.append("")
        
        valor_sem_correcao = f"R$ {resultado_calculo['total_devido_sem_correcao']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        linhas.append(f"Total Devido (sem correcao): {valor_sem_correcao}")
        linhas.append("")
        
        linhas.append(f"Indice Aplicado: {resultado_calculo['indice_aplicado']}")
        
        # Calcula taxa acumulada percentual: (total_corrigido / total_sem_correcao - 1) * 100
        if resultado_calculo['total_devido_sem_correcao'] > 0:
            taxa_acumulada_percentual = ((resultado_calculo['total_corrigido'] / resultado_calculo['total_devido_sem_correcao']) - 1) * 100
            linhas.append(f"Taxa de Correcao Acumulada: {taxa_acumulada_percentual:.4f}%")
        
        linhas.append("")
        
        valor_corrigido = f"R$ {resultado_calculo['total_corrigido']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        valor_diferenca = f"R$ {resultado_calculo['diferenca_correcao']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        
        linhas.append("=" * 80)
        linhas.append(f"TOTAL CORRIGIDO: {valor_corrigido}")
        linhas.append(f"Diferenca pela Correcao: {valor_diferenca}")
        linhas.append("=" * 80)
        linhas.append("")
        
        # Memória de Cálculo Mensal (Amostra dos primeiros e últimos 3 meses)
        memoria = resultado_calculo.get('memoria_mensal', [])
        
        if len(memoria) > 6:
            linhas.append("-" * 80)
            linhas.append("4. MEMORIA DE CALCULO MENSAL (Amostra)")
            linhas.append("-" * 80)
            linhas.append("")
            linhas.append("Primeiros 3 Meses:")
            for mes_info in memoria[:3]:
                competencia = mes_info['competencia']
                tipo = mes_info.get('tipo', 'RMI Mensal')
                valor_original = f"R$ {mes_info['valor_original']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                valor_corrigido = f"R$ {mes_info['valor_corrigido']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                fator = mes_info.get('fator_correcao', 1.0)
                linhas.append(f"  {competencia} ({tipo}):")
                linhas.append(f"    Original: {valor_original} x Fator: {fator:.6f} = Corrigido: {valor_corrigido}")
            
            linhas.append("")
            linhas.append(f"[... {len(memoria) - 6} competencias intermediarias ...]")
            linhas.append("")
            
            linhas.append("Ultimos 3 Meses:")
            for mes_info in memoria[-3:]:
                competencia = mes_info['competencia']
                tipo = mes_info.get('tipo', 'RMI Mensal')
                valor_original = f"R$ {mes_info['valor_original']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                valor_corrigido = f"R$ {mes_info['valor_corrigido']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                fator = mes_info.get('fator_correcao', 1.0)
                linhas.append(f"  {competencia} ({tipo}):")
                linhas.append(f"    Original: {valor_original} x Fator: {fator:.6f} = Corrigido: {valor_corrigido}")
            
            linhas.append("")
        elif len(memoria) > 0:
            # Se tiver menos de 6 meses, mostra todos
            linhas.append("-" * 80)
            linhas.append("4. MEMORIA DE CALCULO MENSAL (Completa)")
            linhas.append("-" * 80)
            linhas.append("")
            for mes_info in memoria:
                competencia = mes_info['competencia']
                tipo = mes_info.get('tipo', 'RMI Mensal')
                valor_original = f"R$ {mes_info['valor_original']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                valor_corrigido = f"R$ {mes_info['valor_corrigido']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                fator = mes_info.get('fator_correcao', 1.0)
                linhas.append(f"  {competencia} ({tipo}):")
                linhas.append(f"    Original: {valor_original} x Fator: {fator:.6f} = Corrigido: {valor_corrigido}")
            linhas.append("")
        
        # Observações Técnicas
        if resultado_calculo.get('observacoes'):
            linhas.append("-" * 80)
            linhas.append("5. OBSERVACOES TECNICAS")
            linhas.append("-" * 80)
            linhas.append("")
            for i, obs in enumerate(resultado_calculo['observacoes'], 1):
                linhas.append(f"{i}. {obs}")
            linhas.append("")
    
    else:
        linhas.append("-" * 80)
        linhas.append("ERRO NO CALCULO")
        linhas.append("-" * 80)
        linhas.append("")
        linhas.append(f"Motivo: {resultado_calculo.get('erro', 'Erro desconhecido')}")
        linhas.append("")
    
    # Rodapé
    linhas.append("-" * 80)
    if resultado_calculo.get('data_calculo'):
        linhas.append(f"Data do Calculo: {resultado_calculo['data_calculo']}")
    linhas.append("Documento gerado pelo sistema JurisFlow")
    linhas.append("Modulo: Calculos Previdenciarios")
    linhas.append("=" * 80)
    
    return "\n".join(linhas)


def processar_acao_previdenciaria(
    caminho_pdf: str,
    contexto_adicional: str = ""
) -> dict:
    """
    Pipeline completo: Extração (IA) → Cálculo (BCB + Lógica).

    Args:
        caminho_pdf: Caminho para o arquivo PDF da ação previdenciária.
        contexto_adicional: Notas do advogado (RMI, datas, etc).

    Returns:
        Dicionário com resultados da extração e do cálculo.

    Raises:
        FileNotFoundError: Se o PDF não existir.
    """
    # Validação do arquivo
    pdf_path = Path(caminho_pdf)
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Arquivo não encontrado: {caminho_pdf}\n"
            f"Adicione um PDF de ação previdenciária na pasta 'documentos/'."
        )
    
    print(f"Processando: {pdf_path.name}")
    print("=" * 80)
    
    # 1. EXTRAÇÃO VIA IA
    print("\nFASE 1: Extração de Dados Previdenciários (GPT-4o-mini)")
    print("-" * 80)
    
    agent = inicializar_agente()
    
    # Monta a query com contexto adicional se fornecido
    query = f"Analise este PDF: {caminho_pdf}"
    
    if contexto_adicional:
        query += f"\n\nCONTEXTO ADICIONAL DO USUARIO:\n{contexto_adicional}"
    
    query += "\n\nRetorne os dados estruturados conforme o schema."
    
    response = agent.run(query, stream=False)
    
    resposta_texto = response.content
    
    # Parse da resposta
    try:
        json_limpo = limpar_json_da_resposta(resposta_texto)
        dados_dict = json.loads(json_limpo)
        dados_extraidos = DadosPrevidenciarios(**dados_dict)
        
        print("✓ Dados extraídos e validados com sucesso!")
        print(f"  - Segurado: {dados_extraidos.nome_segurado or 'N/A'}")
        print(f"  - Tipo de Benefício: {dados_extraidos.tipo_beneficio or 'N/A'}")
        print(f"  - RMI: R$ {dados_extraidos.rmi:.2f}" if dados_extraidos.rmi else "  - RMI: Não informada")
        print(f"  - DIB: {dados_extraidos.dib}" if dados_extraidos.dib else "  - DIB: Não informada")
        
    except json.JSONDecodeError as e:
        print(f"✗ Erro ao parsear JSON: {e}")
        print(f"\nJSON extraído:\n{json_limpo[:300]}...")
        print("\nCriando objeto vazio para demonstração...")
        dados_extraidos = DadosPrevidenciarios()
        
    except Exception as e:
        print(f"✗ Erro na validação Pydantic: {e}")
        print("\nCriando objeto vazio para demonstração...")
        dados_extraidos = DadosPrevidenciarios()
    
    # ===== NOVA LÓGICA: DETECÇÃO DE SALÁRIO MÍNIMO DINÂMICO =====
    usar_sm_dinamico = False
    
    if dados_extraidos.dib:  # Só detecta se tiver DIB
        usar_sm_dinamico = detectar_salario_minimo_dinamico(dados_extraidos)
        
        if usar_sm_dinamico:
            print("\n🔍 DETECÇÃO AUTOMÁTICA:")
            print("  ✓ Benefício identificado como SALÁRIO MÍNIMO DINÂMICO")
            print("  → Os reajustes legais do salário mínimo serão aplicados automaticamente")
            print("    em cada competencia (conforme Lei vigente).")
        else:
            print("\n🔍 DETECÇÃO AUTOMÁTICA:")
            print("  ✓ Benefício identificado como VALOR FIXO")
            if dados_extraidos.rmi:
                print(f"  → Será usado o valor de R$ {dados_extraidos.rmi:.2f} para todas as competências.")
    
    # 2. CÁLCULO DE ATRASADOS
    resultado_calculo = {}
    texto_formatado = None
    
    # Valida se tem os dados mínimos para calcular
    pode_calcular = dados_extraidos.dib is not None
    
    if not usar_sm_dinamico:
        pode_calcular = pode_calcular and dados_extraidos.rmi and dados_extraidos.rmi > 0
    
    if pode_calcular:
        print("\n" + "=" * 80)
        print("FASE 2: Cálculo de Atrasados com Correção Monetária (BCB)")
        print("-" * 80)
        
        # Define data final (hoje ou DIP, se fornecida)
        data_fim = dados_extraidos.dip if dados_extraidos.dip else date.today()
        
        # Validação da RMI (se não for salário mínimo dinâmico)
        if not usar_sm_dinamico and dados_extraidos.rmi:
            valido, mensagem = validar_rmi(dados_extraidos.rmi, dados_extraidos.dib)
            if not valido:
                print(f"\n⚠ AVISO DE VALIDAÇÃO: {mensagem}")
                print("  O cálculo prosseguirá, mas revise o valor informado.")
        
        gerente_bcb = GerenteFinanceiroBCB()
        
        # ===== CHAMA O CÁLCULO COM O FLAG CORRETO =====
        resultado_calculo = gerente_bcb.calcular_atrasados(
            rmi=dados_extraidos.rmi if not usar_sm_dinamico else 0.0,  # Passa 0 se for dinâmico
            data_inicio=dados_extraidos.dib,
            data_fim=data_fim,
            indice=dados_extraidos.indice_correcao,
            tem_adicional_25=dados_extraidos.tem_adicional_25,
            usar_salario_minimo_dinamico=usar_sm_dinamico  # ← NOVO PARÂMETRO
        )
        
        if resultado_calculo["status"] == "sucesso":
            print(f"✓ Cálculo concluído!")
            print(f"  - Período: {dados_extraidos.dib} até {data_fim}")
            print(f"  - Total de meses: {resultado_calculo['total_meses']}")
            print(f"  - Índice aplicado: {resultado_calculo['indice_aplicado']}")
            
            if usar_sm_dinamico:
                print(f"  - Modo: SALÁRIO MÍNIMO DINÂMICO (atualizado mensalmente)")
            else:
                print(f"  - Modo: VALOR FIXO (R$ {dados_extraidos.rmi:.2f})")
            
            print(f"  - Total corrigido: R$ {resultado_calculo['total_corrigido']:,.2f}")
            
            # 3. FORMATAÇÃO PARA WORD (só se cálculo teve sucesso)
            print("\n" + "=" * 80)
            print("RELATÓRIO FORMATADO PARA WORD")
            print("=" * 80)
            print("\n")
            
            texto_formatado = formatar_relatorio_previdenciario(dados_extraidos, resultado_calculo)
            print(texto_formatado)
            
            print("\n" + "=" * 80)
            print("FIM DO RELATÓRIO")
            print("=" * 80)
        else:
            print(f"✗ Erro no cálculo: {resultado_calculo['erro']}")
    
    else:
        print("\n⚠ AVISO: Cálculo de atrasados não executado.")
        if not dados_extraidos.dib:
            print("  - DIB não encontrada no documento.")
        if not usar_sm_dinamico and (not dados_extraidos.rmi or dados_extraidos.rmi <= 0):
            print("  - RMI não informada ou inválida.")
            print("  - Forneça a RMI no 'Contexto Adicional' (ex: 'RMI de R$ 1.500,00')")
            print("  - Ou informe que é um benefício de salário mínimo.")
        
        resultado_calculo = {
            "status": "nao_executado",
            "erro": "Dados insuficientes para realizar o cálculo. Verifique DIB e RMI."
        }
    
    return {
        "dados_extraidos": dados_extraidos.model_dump(),
        "calculo": resultado_calculo,
        "relatorio_word": texto_formatado,
        "usar_salario_minimo_dinamico": usar_sm_dinamico
    }


def main():
    """Ponto de entrada principal do sistema previdenciário."""
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERRO: OPENAI_API_KEY não encontrada!")
        print("Configure o arquivo .env com sua chave da OpenAI.")
        return
    
    print("🏛️  JurisFlow - Sistema de Cálculo de Atrasados Previdenciários")
    print("=" * 80)
    
    # Configuração de exemplo
    caminho_pdf = str(raiz_projeto / "documentos" / "processo_previdenciario_exemplo.pdf")
    
    # Simula notas do advogado (contexto adicional)
    notas_usuario = """
    Cliente sempre recebeu um salário mínimo de forma dinâmica durante todo o período de contribuição.
    Benefício concedido com adicional de 25% por grande invalidez.
    """
    
    try:
        resultado = processar_acao_previdenciaria(
            caminho_pdf=caminho_pdf,
            contexto_adicional=notas_usuario
        )
        
        print("\n✅ Processamento concluído com sucesso!")
        
        # Resumo final
        if resultado['calculo'].get('status') == 'sucesso':
            total = resultado['calculo']['total_corrigido']
            print(f"\n💰 VALOR TOTAL DOS ATRASADOS: R$ {total:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
            
            if resultado.get('usar_salario_minimo_dinamico'):
                print("\n📊 MÉTODO APLICADO: Salário Mínimo Dinâmico")
                print("   Os valores foram atualizados conforme os reajustes legais em cada mês.")
            else:
                print("\n📊 MÉTODO APLICADO: Valor Fixo de RMI")
        
    except FileNotFoundError as e:
        print(f"\n❌ {e}")
        print("\n💡 Dica: Adicione um PDF de ação previdenciária em 'documentos/processo_previdenciario_exemplo.pdf'")
        print("         Ou use qualquer PDF de sentença/petição do INSS disponível.")
        
    except Exception as e:
        print(f"\n❌ Erro inesperado: {type(e).__name__}")
        print(f"   Detalhes: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()