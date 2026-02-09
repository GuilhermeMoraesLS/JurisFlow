"""
Ferramenta para leitura de arquivos PDF jurídicos usando o framework Agno.

Esta toolkit permite que agentes de IA extraiam texto de documentos PDF,
essencial para análise de reclamações trabalhistas e outros documentos legais.
"""

from pathlib import Path

from agno.tools import Toolkit
from pypdf import PdfReader


class LegalPDFReader(Toolkit):
    """
    Toolkit para extração de texto de arquivos PDF jurídicos.
    
    Permite que agentes leiam e processem documentos PDF, incluindo
    reclamações trabalhistas, petições, sentenças e outros documentos legais.
    """

    def __init__(self):
        """Inicializa a toolkit e registra o método de leitura."""
        super().__init__(name="legal_pdf_reader")
        self.register(self.read_pdf_text)

    def read_pdf_text(self, pdf_path: str) -> str:
        """
        Extrai todo o texto de um arquivo PDF.

        Args:
            pdf_path: Caminho completo ou relativo para o arquivo PDF.

        Returns:
            String contendo todo o texto extraído do PDF, com páginas concatenadas.
            Em caso de erro, retorna uma mensagem descritiva do problema.

        Exemplo:
            >>> reader = LegalPDFReader()
            >>> texto = reader.read_pdf_text("reclamacao_trabalhista.pdf")
            >>> print(texto[:100])
        """
        try:
            # Converte para Path para melhor manipulação de caminhos
            file_path = Path(pdf_path)

            # Verifica se o arquivo existe
            if not file_path.exists():
                return f"Erro: O arquivo '{pdf_path}' não foi encontrado."

            # Verifica se é um arquivo (não um diretório)
            if not file_path.is_file():
                return f"Erro: '{pdf_path}' não é um arquivo válido."

            # Abre e processa o PDF
            reader = PdfReader(file_path)
            
            # Extrai texto de todas as páginas
            texto_completo = []
            total_paginas = len(reader.pages)

            for numero_pagina, page in enumerate(reader.pages, start=1):
                texto_pagina = page.extract_text()
                if texto_pagina:  # Adiciona apenas se houver texto
                    texto_completo.append(f"--- Página {numero_pagina}/{total_paginas} ---\n")
                    texto_completo.append(texto_pagina)
                    texto_completo.append("\n\n")

            if not texto_completo:
                return f"Aviso: O PDF '{pdf_path}' foi lido, mas não contém texto extraível. Pode ser um PDF digitalizado sem OCR."

            return "".join(texto_completo)

        except PermissionError:
            return f"Erro: Sem permissão para ler o arquivo '{pdf_path}'. Verifique as permissões."

        except Exception as e:
            return f"Erro ao processar o PDF '{pdf_path}': {type(e).__name__} - {str(e)}"