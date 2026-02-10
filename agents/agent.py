"""
Agente principal do JurisFlow - Sistema de Cálculo Jurídico Trabalhista.

Este módulo orquestra a extração de dados via IA (GPT-4o-mini) e o cálculo
determinístico de verbas rescisórias, separando responsabilidades entre
inteligência artificial e lógica pura.
"""

import os
import sys
import json
from pathlib import Path

# Adiciona a raiz do projeto ao PYTHONPATH
raiz_projeto = Path(__file__).parent.parent
sys.path.insert(0, str(raiz_projeto))

from agno.agent import Agent
from agno.models.openai import OpenAIChat
from dotenv import load_dotenv

from tools.pdf_reader import LegalPDFReader
from models.schemas import DadosTrabalhistasExtraidos
from core.calculo_trabalhista import calcular_rescisao


def carregar_prompt_sistema() -> str:
    """
    Carrega as instruções de sistema do arquivo Markdown.

    Returns:
        String contendo o prompt completo do auditor jurídico.
    """
    # Caminho relativo à raiz do projeto
    prompt_path = raiz_projeto / "prompts" / "extrator_trabalhista.md"
    
    if not prompt_path.exists():
        raise FileNotFoundError(
            f"Arquivo de prompt não encontrado: {prompt_path}\n"
            "Certifique-se de que prompts/extrator_trabalhista.md existe."
        )
    
    return prompt_path.read_text(encoding="utf-8")


def gerar_exemplo_schema() -> str:
    """
    Gera um exemplo do schema esperado para guiar a IA.
    
    Returns:
        String JSON com exemplo do formato esperado.
    """
    exemplo = {
        "nome_reclamante": "João da Silva Santos",
        "data_admissao": "2021-09-01",
        "data_dispensa": "2021-10-22",
        "salario_base": 3158.96,
        "adicionais": {
            "insalubridade": 440.0,
            "periculosidade": None,
            "noturno": 297.32
        },
        "verbas_requeridas": [
            "saldo_salario",
            "fgts",
            "multa_40",
            "aviso_previo",
            "decimo_terceiro",
            "ferias_proporcionais"
        ],
        "justificativa_demissao": "sem justa causa",
        "observacoes": [
            "Reclamante alega trabalho sem carteira assinada",
            "Empresa não efetuou pagamento das verbas rescisórias"
        ],
        "multa_467_requerida": False,
        "multa_477_requerida": False
    }
    return json.dumps(exemplo, indent=2, ensure_ascii=False)


def inicializar_agente() -> Agent:
    """
    Configura e retorna o agente de extração jurídica.

    Returns:
        Agente configurado com GPT-4o-mini, ferramentas e schema estruturado.
    """
    system_prompt = carregar_prompt_sistema()
    exemplo_json = gerar_exemplo_schema()
    
    # Adiciona o exemplo ao prompt
    prompt_completo = f"""{system_prompt}

# EXEMPLO DE RESPOSTA ESPERADA

Para um processo com:
- Admissão: 01/09/2021
- Demissão: 22/10/2021  
- Salário: R$ 3.158,96
- Adicional insalubridade: R$ 440,00
- Adicional noturno: R$ 297,32

Você deve retornar EXATAMENTE este formato:

```json
{exemplo_json}
```

IMPORTANTE: Retorne APENAS o JSON, sem texto adicional."""

    agent = Agent(
        model=OpenAIChat(id="gpt-4o-mini", temperature=0.1),  # Temperatura baixa para mais precisão
        description="Você é um extrator de dados jurídicos que retorna APENAS JSON estruturado.",
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


def formatar_para_word(dados_extraidos: DadosTrabalhistasExtraidos, resultado_calculo: dict) -> str:
    """
    Formata os resultados em texto limpo, pronto para copiar no Word.
    
    Args:
        dados_extraidos: Dados estruturados extraídos pela IA
        resultado_calculo: Resultado do cálculo das verbas
        
    Returns:
        String formatada sem emojis, pronta para documento oficial
    """
    linhas = []
    
    # Cabeçalho
    linhas.append("=" * 80)
    linhas.append("RELATORIO DE CALCULO TRABALHISTA")
    linhas.append("JurisFlow - Sistema de Calculo Juridico")
    linhas.append("=" * 80)
    linhas.append("")
    
    # Identificação do Reclamante
    if dados_extraidos.nome_reclamante:
        linhas.append("RECLAMANTE: " + dados_extraidos.nome_reclamante.upper())
        linhas.append("")
    
    # Dados do Vínculo
    linhas.append("-" * 80)
    linhas.append("1. DADOS DO VINCULO EMPREGATICIO")
    linhas.append("-" * 80)
    linhas.append("")
    
    if dados_extraidos.data_admissao:
        linhas.append(f"Data de Admissao: {dados_extraidos.data_admissao.strftime('%d/%m/%Y')}")
    
    if dados_extraidos.data_dispensa:
        linhas.append(f"Data de Dispensa: {dados_extraidos.data_dispensa.strftime('%d/%m/%Y')}")
    
    if dados_extraidos.salario_base:
        linhas.append(f"Salario Base: R$ {dados_extraidos.salario_base:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.'))
    
    # Adicionais
    if dados_extraidos.adicionais:
        tem_adicionais = False
        adicionais_texto = []
        
        if dados_extraidos.adicionais.insalubridade:
            tem_adicionais = True
            valor = f"R$ {dados_extraidos.adicionais.insalubridade:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            adicionais_texto.append(f"  - Insalubridade: {valor}")
        
        if dados_extraidos.adicionais.periculosidade:
            tem_adicionais = True
            valor = f"R$ {dados_extraidos.adicionais.periculosidade:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            adicionais_texto.append(f"  - Periculosidade: {valor}")
        
        if dados_extraidos.adicionais.noturno:
            tem_adicionais = True
            valor = f"R$ {dados_extraidos.adicionais.noturno:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            adicionais_texto.append(f"  - Adicional Noturno: {valor}")
        
        if tem_adicionais:
            linhas.append("")
            linhas.append("Adicionais Salariais:")
            linhas.extend(adicionais_texto)
    
    if dados_extraidos.justificativa_demissao:
        linhas.append("")
        linhas.append(f"Tipo de Demissao: {dados_extraidos.justificativa_demissao.title()}")
    
    # Tempo de Serviço
    if resultado_calculo["status"] == "sucesso":
        linhas.append("")
        ts = resultado_calculo['tempo_servico']
        linhas.append(f"Tempo de Servico: {ts['anos']} anos, {ts['meses']} meses e {ts['dias']} dias")
        linhas.append(f"Total em Meses: {ts['meses_totais']:.2f} meses")
    
    linhas.append("")
    
    # Cálculos
    if resultado_calculo["status"] == "sucesso":
        linhas.append("-" * 80)
        linhas.append("2. MEMORIA DE CALCULO - VERBAS RESCISSORIAS")
        linhas.append("-" * 80)
        linhas.append("")
        
        if resultado_calculo.get('remuneracao_base_calculo'):
            valor = f"R$ {resultado_calculo['remuneracao_base_calculo']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            linhas.append(f"Remuneracao Base para Calculo: {valor}")
            linhas.append("")
        
        # Verbas Rescisórias
        for verba, detalhes in resultado_calculo['memoria_calculo'].items():
            if verba.startswith("multa_") and verba.endswith("_clt"):
                continue
            
            linhas.append(verba.upper().replace("_", " "))
            linhas.append(f"  Descricao: {detalhes['descricao']}")
            linhas.append(f"  Formula: {detalhes['formula']}")
            valor = f"R$ {detalhes['valor']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            linhas.append(f"  Valor: {valor}")
            linhas.append("")
        
        # Subtotal
        valor = f"R$ {resultado_calculo['total_estimado']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        linhas.append(f"SUBTOTAL (Verbas Rescissorias): {valor}")
        linhas.append("")
        
        # Multas CLT
        tem_multas = (resultado_calculo.get('multa_477_valor', 0) > 0 or 
                      resultado_calculo.get('multa_467_valor', 0) > 0)
        
        if tem_multas:
            linhas.append("-" * 80)
            linhas.append("3. MULTAS CLT APLICADAS")
            linhas.append("-" * 80)
            linhas.append("")
            
            if resultado_calculo.get('multa_477_valor', 0) > 0:
                multa_477 = resultado_calculo['memoria_calculo'].get('multa_477_clt', {})
                linhas.append("MULTA ART. 477 CLT (Atraso no Pagamento)")
                linhas.append(f"  Descricao: {multa_477.get('descricao', 'N/A')}")
                linhas.append(f"  Formula: {multa_477.get('formula', 'N/A')}")
                valor = f"R$ {resultado_calculo['multa_477_valor']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                linhas.append(f"  Valor: {valor}")
                linhas.append("")
            
            if resultado_calculo.get('multa_467_valor', 0) > 0:
                multa_467 = resultado_calculo['memoria_calculo'].get('multa_467_clt', {})
                linhas.append("MULTA ART. 467 CLT (Verbas Incontroversas - 50%)")
                linhas.append(f"  Descricao: {multa_467.get('descricao', 'N/A')}")
                linhas.append(f"  Formula: {multa_467.get('formula', 'N/A')}")
                valor = f"R$ {resultado_calculo['multa_467_valor']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
                linhas.append(f"  Valor: {valor}")
                linhas.append("")
            
            subtotal_multas = resultado_calculo['multa_477_valor'] + resultado_calculo['multa_467_valor']
            valor = f"R$ {subtotal_multas:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
            linhas.append(f"SUBTOTAL DAS MULTAS: {valor}")
            linhas.append("")
        
        # Total Geral
        linhas.append("=" * 80)
        valor = f"R$ {resultado_calculo['total_geral']:,.2f}".replace(',', '_').replace('.', ',').replace('_', '.')
        linhas.append(f"TOTAL GERAL (Verbas + Multas): {valor}")
        linhas.append("=" * 80)
        linhas.append("")
        
        # Observações
        if resultado_calculo['observacoes']:
            linhas.append("-" * 80)
            linhas.append("4. OBSERVACOES")
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
        linhas.append(f"Motivo: {resultado_calculo['erro']}")
        linhas.append("")
    
    # Rodapé
    linhas.append("-" * 80)
    if resultado_calculo.get('data_calculo'):
        linhas.append(f"Data do Calculo: {resultado_calculo['data_calculo']}")
    linhas.append("Documento gerado pelo sistema JurisFlow")
    linhas.append("=" * 80)
    
    return "\n".join(linhas)


def processar_reclamacao(caminho_pdf: str) -> dict:
    """
    Pipeline completo: Extração (IA) → Cálculo (Lógica Pura).

    Args:
        caminho_pdf: Caminho para o arquivo PDF da reclamação trabalhista.

    Returns:
        Dicionário com resultados da extração e do cálculo.

    Raises:
        FileNotFoundError: Se o PDF não existir.
    """
    # Validação do arquivo
    pdf_path = Path(caminho_pdf)
    if not pdf_path.exists():
        raise FileNotFoundError(
            f"Arquivo nao encontrado: {caminho_pdf}\n"
            f"Crie uma pasta 'documentos/' e adicione um PDF de teste."
        )
    
    print(f"Processando: {pdf_path.name}")
    print("=" * 80)
    
    # 1. EXTRAÇÃO VIA IA
    print("\nFASE 1: Extracao de Dados (GPT-4o-mini)")
    print("-" * 80)
    
    agent = inicializar_agente()
    
    response = agent.run(
        f"Extraia os dados trabalhistas do arquivo: {caminho_pdf}\n\n"
        f"Retorne APENAS o JSON no formato especificado, sem texto adicional.",
        stream=False
    )
    
    resposta_texto = response.content
    
    # Parse da resposta
    try:
        json_limpo = limpar_json_da_resposta(resposta_texto)
        dados_dict = json.loads(json_limpo)
        dados_extraidos = DadosTrabalhistasExtraidos(**dados_dict)
        
        print("JSON validado com sucesso!")
        
    except json.JSONDecodeError as e:
        print(f"Erro ao parsear JSON: {e}")
        print(f"\nJSON extraido:\n{json_limpo[:300]}...")
        print("\nCriando objeto vazio para demonstracao...")
        dados_extraidos = DadosTrabalhistasExtraidos()
        
    except Exception as e:
        print(f"Erro na validacao Pydantic: {e}")
        print("\nCriando objeto vazio para demonstracao...")
        dados_extraidos = DadosTrabalhistasExtraidos()
    
    # 2. CÁLCULO DETERMINÍSTICO
    print("\n" + "=" * 80)
    print("FASE 2: Calculo de Verbas Rescissorias (Core)")
    print("-" * 80)
    
    resultado_calculo = calcular_rescisao(dados_extraidos)
    
    # 3. FORMATAÇÃO PARA WORD
    print("\n" + "=" * 80)
    print("RELATORIO FORMATADO PARA WORD")
    print("=" * 80)
    print("\n")
    
    texto_formatado = formatar_para_word(dados_extraidos, resultado_calculo)
    print(texto_formatado)
    
    print("\n" + "=" * 80)
    print("FIM DO RELATORIO")
    print("=" * 80)
    
    return {
        "dados_extraidos": dados_extraidos.model_dump(),
        "calculo": resultado_calculo,
        "relatorio_word": texto_formatado
    }


def main():
    """Ponto de entrada principal do sistema."""
    load_dotenv()
    
    if not os.getenv("OPENAI_API_KEY"):
        print("❌ ERRO: OPENAI_API_KEY não encontrada!")
        print("Configure o arquivo .env com sua chave da OpenAI.")
        return
    
    print("🏛️  JurisFlow - Sistema de Cálculo Jurídico Trabalhista")
    print("=" * 80)
    
    caminho_pdf = "documentos/processo_exemplo.pdf"
    
    try:
        resultado = processar_reclamacao(caminho_pdf)
        print("\n✅ Processamento concluído com sucesso!")
        
    except FileNotFoundError as e:
        print(f"\n{e}")
        print("\n💡 Dica: Adicione um PDF de teste em 'documentos/processo_exemplo.pdf'")
        
    except Exception as e:
        print(f"\n❌ Erro inesperado: {type(e).__name__}")
        print(f"   Detalhes: {str(e)}")
        import traceback
        traceback.print_exc()


if __name__ == "__main__":
    main()