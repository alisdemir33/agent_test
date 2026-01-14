from openai import OpenAI
from mcp import ClientSession, StdioServerParameters
from mcp.client.stdio import stdio_client
import asyncio
import json
from aioconsole import ainput

class MCPCustomerAgent:
    def __init__(self):
        self.client = OpenAI(base_url="http://192.168.1.182:1234/v1", api_key="no-key")
        self.messages = [
            {"role": "developer", "content": "You are a friendly customer service agent. Always verify identity before giving info."}
        ]

    async def run(self):
        # 1. MCP Server'a bağlan (mcp_server.py'ın çalıştığını varsayıyoruz)
        #server_params = {"command": "python", "args": ["mcp_server.py"]}
        server_params = StdioServerParameters(
        command="uv", # uv kullandığın için komutu uv yapman daha sağlıklı
        args=["run", "python", "mcp_server.py"], # uv run ile çalıştırıyoruz
        env=None
    )
        
        async with stdio_client(server_params) as (read, write):
            async with ClientSession(read, write) as session:
                await session.initialize()
                
                # 2. Yetenekleri OTOMATİK KEŞFET (list_tools)
                # Not: Gerçek SDK'da bu session.list_tools() olarak çağrılır
                available_mcp_tools = await session.list_tools()
                
                # OpenAI formatına dönüştür
                openai_tools = [
                    {
                        "type": "function",
                        "function": {
                            "name": t.name,
                            "description": t.description,
                            "parameters": t.inputSchema
                        }
                    } for t in available_mcp_tools.tools
                ]

                print("Welcome! MCP Server connected. How can I help?")
                
                while True:
                    user_input = await ainput("\nYour input: ")
                    if user_input.lower() == "exit": break
                    
                    self.messages.append({"role": "user", "content": user_input})

                    # Model Döngüsü
                    for _ in range(5):
                        response = self.client.chat.completions.create(
                            model="llama-3.1-70b",
                            messages=self.messages,
                            tools=openai_tools
                        )

                        assistant_msg = response.choices[0].message
                        self.messages.append(assistant_msg.model_dump(exclude_none=True))

                        if assistant_msg.content:
                            print(f"Assistant: {assistant_msg.content}")

                        if assistant_msg.tool_calls:
                            for tool_call in assistant_msg.tool_calls:
                                # 3. MCP Server Üzerinden TOOL'u Çalıştır
                                result = await session.call_tool(
                                    tool_call.function.name, 
                                    arguments=json.loads(tool_call.function.arguments)
                                )
                                
                                # Sonucu geçmişe ekle
                                self.messages.append({
                                    "role": "tool",
                                    "tool_call_id": tool_call.id,
                                    "name": tool_call.function.name,
                                    "content": str(result.content)
                                })
                            continue
                        break

if __name__ == "__main__":
    agent = MCPCustomerAgent()
    asyncio.run(agent.run())