"""
Agente principal do JurisFlow - Sistema de Cálculo Jurídico Trabalhista.

Este módulo orquestra a extração de dados via IA (GPT-4o-mini) e o cálculo
determinístico de verbas rescisórias, separando responsabilidades entre
inteligência artificial e lógica pura.
"""

import os
import json
from pathlib import Path

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
    prompt_path = Path("prompts/extrator_trabalhista.md")
    
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
            f"❌ Arquivo não encontrado: {caminho_pdf}\n"
            f"Crie uma pasta 'documentos/' e adicione um PDF de teste."
        )
    
    print(f"📄 Processando: {pdf_path.name}")
    print("=" * 80)
    
    # 1. EXTRAÇÃO VIA IA
    print("\n🤖 FASE 1: Extração de Dados (GPT-4o-mini)")
    print("-" * 80)
    
    agent = inicializar_agente()
    
    response = agent.run(
        f"Extraia os dados trabalhistas do arquivo: {caminho_pdf}\n\n"
        f"Retorne APENAS o JSON no formato especificado, sem texto adicional.",
        stream=False
    )
    
    resposta_texto = response.content
    print(f"\n🔍 Resposta bruta da IA:")
    print(resposta_texto[:500] + "..." if len(resposta_texto) > 500 else resposta_texto)
    print()
    
    # Parse da resposta
    try:
        json_limpo = limpar_json_da_resposta(resposta_texto)
        dados_dict = json.loads(json_limpo)
        dados_extraidos = DadosTrabalhistasExtraidos(**dados_dict)
        
        print("✅ JSON validado com sucesso!")
        
    except json.JSONDecodeError as e:
        print(f"❌ Erro ao parsear JSON: {e}")
        print(f"\nJSON extraído:\n{json_limpo[:300]}...")
        print("\nCriando objeto vazio para demonstração...")
        dados_extraidos = DadosTrabalhistasExtraidos()
        
    except Exception as e:
        print(f"❌ Erro na validação Pydantic: {e}")
        print("\nCriando objeto vazio para demonstração...")
        dados_extraidos = DadosTrabalhistasExtraidos()
    
    print("\n--- DADOS EXTRAÍDOS (IA) ---")
    print(dados_extraidos.model_dump_json(indent=2, exclude_none=True))
    
    # 2. CÁLCULO DETERMINÍSTICO
    print("\n" + "=" * 80)
    print("🧮 FASE 2: Cálculo de Verbas Rescisórias (Core)")
    print("-" * 80)
    
    resultado_calculo = calcular_rescisao(dados_extraidos)
    
    print("\n--- CÁLCULO JURÍDICO (CORE) ---")
    
    if resultado_calculo["status"] == "erro":
        print(f"❌ ERRO: {resultado_calculo['erro']}")
    else:
        print(f"✅ Status: {resultado_calculo['status'].upper()}")
        print(f"\n📊 Tempo de Serviço:")
        ts = resultado_calculo['tempo_servico']
        print(f"   • {ts['anos']} anos, {ts['meses']} meses, {ts['dias']} dias")
        print(f"   • Total: {ts['meses_totais']} meses")
        
        print(f"\n💰 Remuneração Base: R$ {resultado_calculo['salario_base']:.2f}")
        
        if resultado_calculo.get('remuneracao_base_calculo', 0) > resultado_calculo['salario_base']:
            print(f"💰 Remuneração Total (com adicionais): R$ {resultado_calculo['remuneracao_base_calculo']:.2f}")
        
        print(f"\n📋 Memória de Cálculo - Verbas Rescisórias:")
        for verba, detalhes in resultado_calculo['memoria_calculo'].items():
            # Pula multas CLT nesta seção (serão mostradas depois)
            if verba.startswith("multa_") and verba.endswith("_clt"):
                continue
                
            print(f"\n   {verba.upper()}:")
            print(f"   • Descrição: {detalhes['descricao']}")
            print(f"   • Fórmula: {detalhes['formula']}")
            print(f"   • Valor: R$ {detalhes['valor']:.2f}")
        
        print(f"\n💵 SUBTOTAL (Verbas Rescisórias): R$ {resultado_calculo['total_estimado']:.2f}")
        
        # Seção dedicada às Multas CLT
        tem_multas = (resultado_calculo.get('multa_477_valor', 0) > 0 or 
                      resultado_calculo.get('multa_467_valor', 0) > 0)
        
        if tem_multas:
            print(f"\n" + "─" * 80)
            print("⚖️  MULTAS CLT APLICADAS:")
            
            if resultado_calculo.get('multa_477_valor', 0) > 0:
                multa_477 = resultado_calculo['memoria_calculo'].get('multa_477_clt', {})
                print(f"\n   🔴 MULTA ART. 477 CLT (Atraso no Pagamento):")
                print(f"   • Descrição: {multa_477.get('descricao', 'N/A')}")
                print(f"   • Fórmula: {multa_477.get('formula', 'N/A')}")
                print(f"   • Valor: R$ {resultado_calculo['multa_477_valor']:.2f}")
            
            if resultado_calculo.get('multa_467_valor', 0) > 0:
                multa_467 = resultado_calculo['memoria_calculo'].get('multa_467_clt', {})
                print(f"\n   🔴 MULTA ART. 467 CLT (Verbas Incontroversas - 50%):")
                print(f"   • Descrição: {multa_467.get('descricao', 'N/A')}")
                print(f"   • Fórmula: {multa_467.get('formula', 'N/A')}")
                print(f"   • Valor: R$ {resultado_calculo['multa_467_valor']:.2f}")
            
            print(f"\n💰 SUBTOTAL DAS MULTAS: R$ {resultado_calculo['multa_477_valor'] + resultado_calculo['multa_467_valor']:.2f}")
        
        # Total Geral
        print(f"\n" + "=" * 80)
        print(f"💰💰 TOTAL GERAL (Verbas + Multas): R$ {resultado_calculo['total_geral']:.2f}")
        print("=" * 80)
        
        if resultado_calculo['observacoes']:
            print(f"\n⚠️  Observações:")
            for obs in resultado_calculo['observacoes']:
                print(f"   • {obs}")
    
    print("\n" + "=" * 80)
    
    return {
        "dados_extraidos": dados_extraidos.model_dump(),
        "calculo": resultado_calculo
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