from fastmcp import FastMCP

mcp_server = FastMCP("test-mcp-server")

@mcp_server.tool() 
async def dar_bom_dia(nome_usuario : str, id_usuario : int) -> str:         #Quanto mais informações é melhor para a IA. Infos de tipo
    return f"Bom dia, {nome_usuario}! Seu ID de usuário é {id_usuario}."

if __name__ == "__main__":
    mcp_server.run(transport="stdio")