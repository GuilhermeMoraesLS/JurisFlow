import asyncio
from pathlib import Path

from fastmcp import Client

caminho_server = Path(__file__).parent / "server_mcp.py"
cliente = Client(caminho_server)

async def testar_mcp(cliente, nome_usuario, id_usuario):
    async with cliente:
        argumentos = {"nome_usuario": nome_usuario, "id_usuario": id_usuario}
        resultado = await cliente.call_tool("dar_bom_dia", arguments=argumentos)
        print(resultado)


if __name__ == "__main__":
    asyncio.run(testar_mcp(cliente, "Alice", 123))
    