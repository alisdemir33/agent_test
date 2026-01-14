import json
import sqlite3
from datetime import datetime
from typing import Dict, Any

# Run "uv sync" to install the below packages
from dotenv import load_dotenv
from openai import OpenAI
import oracledb 

from customer_database import create_db_and_tables

load_dotenv()

db_config = {
    "user": "yztest",
    "password": "yztest",
    "dsn": "localhost:1521/DBAI"  # Host:Port/Servis_Adi (Örn: XE veya ORCL)
}

#client = OpenAI()
model_name="openai/gpt-oss-20b"
base_url_param="http://192.168.1.182:1234/v1"

client = OpenAI(
    # base_url="http://172.24.80.1:1234/v1",
    base_url=base_url_param,
    api_key="something-doesnt-matter",
)

#DB_FILE = "dummy_database.db"
#create_db_and_tables()


class Tool:
    """
    The base class for a tool that can be used by an agent.
    """

    def __init__(
        self,
        name: str,
        description: str,
        parameters: Dict[str, Any],
    ):
        self.name = name
        self.description = description
        self.parameters = parameters


    def get_schema(self) -> Dict[str, Any]:
        """
        Returns the schema for the tool in the correct OpenAI format.
        """
        return {
            "type": "function",
            "function": { # Tüm detaylar bu anahtarın altında olmalı
                "name": self.name,
                "description": self.description,
                "parameters": {
                    "type": "object",
                    "properties": self.parameters,
                    "additionalProperties": False,
                    "required": list(self.parameters.keys()),
                },
            },
        }

    def execute(self, arguments: str) -> str:
        """
        Executes the tool's logic. This method must be implemented by subclasses.
        """
        raise NotImplementedError("Each tool must implement its own execute method.")


class VerifyCustomerTool(Tool):
    def __init__(self):
        super().__init__(
            name="verify_customer",
            description="Verifies a customer's identity using their full name and PIN and returns customer ID if verified, otherwise returns -1.",
            parameters={
                "name": {
                    "type": "string",
                    "description": "The customer's full name, e.g., 'John Doe'.",
                },
                "pin": {"type": "string", "description": "The customer's PIN."},
            },
        )

    def execute(self, arguments: str) -> str:
        try:
            args = json.loads(arguments)
            conn = oracledb.connect(
            user=db_config["user"],
            password=db_config["password"],
            dsn=db_config["dsn"]
        )
            cursor = conn.cursor()
            parts = args["name"].lower().split()
            first_name = parts[0]
            last_name = parts[1] if len(parts) > 1 else ""

            # SQL SORGUSU DEĞİŞİKLİĞİ: '?' yerine ':1, :2, :3' kullanıyoruz
            sql = """
            SELECT id 
            FROM customers 
            WHERE LOWER(first_name) = :1 
            AND LOWER(last_name) = :2 
            AND pin = :3
            """
    
            cursor.execute(sql, (first_name, last_name, args["pin"]))
            result = cursor.fetchone()
            conn.close()
            if result:
                return str(result[0])
            return str(-1)
        except Exception as e:
            return f"Error in {self.name}: {e}"


class GetOrdersTool(Tool):
    def __init__(self):
        super().__init__(
            name="get_orders",
            description="Retrieves the order history for a verified customer.",
            parameters={
                "customer_id": {
                    "type": "integer",
                    "description": "The customer's unique ID.",
                }
            },
        )

    def execute(self, arguments: str) -> str:
        conn = None
        try:
            args = json.loads(arguments)
            conn = oracledb.connect(
                user=db_config["user"],
                password=db_config["password"],
                dsn=db_config["dsn"]
            )
            cursor = conn.cursor()
            
            cursor.execute(
                "SELECT id, customer_id, order_date, product_name, amount FROM orders WHERE customer_id = :1", 
                (args["customer_id"],)
            )
            
            columns = [col[0] for col in cursor.description]
            orders = [dict(zip(columns, row)) for row in cursor.fetchall()]
            
            # default=str ekleyerek datetime hatasını çözüyoruz
            return json.dumps(orders, default=str)
            
        except Exception as e:
            return f"Error in {self.name}: {e}"
        finally:
            if conn:
                conn.close() # Java'daki try-with-resources mantığı


class CheckRefundEligibilityTool(Tool):
    def __init__(self):
        super().__init__(
            name="check_refund_eligibility",
            description="Checks if an order is eligible for a refund based on the order date.",
            parameters={
                "customer_id": {
                    "type": "integer",
                    "description": "The customer's unique ID.",
                },
                "order_id": {
                    "type": "integer",
                    "description": "The unique ID of the order.",
                },
            },
        )

    def execute(self, arguments: str) -> str:
        try:
            args = json.loads(arguments)
            conn = oracledb.connect(
                user=db_config["user"],
                password=db_config["password"],
                dsn=db_config["dsn"]
            )
            cursor = conn.cursor()
            
            # Oracle'dan tarihi çekiyoruz
            cursor.execute(
                "SELECT order_date FROM orders WHERE id = :1 AND customer_id = :2",
                (args["order_id"], args["customer_id"]),
            )
            result = cursor.fetchone()
            conn.close()

            if not result:
                return "False" # Sipariş bulunamadı

            # result[0] zaten <class 'datetime.datetime'> tipindedir.
            # (2025, 11, 11, 12, 20, 5) formatında gelmesi onun hazır olduğunu gösterir.
            order_date = result[0] 
            
            # Şimdiki zamanı alıyoruz
            current_date = datetime.now()
            
            # İki tarih arasındaki farkı hesaplıyoruz
            # Java'daki Duration veya Period gibi düşünebilirsiniz.
            difference = current_date - order_date
            
            # 30 günden küçük veya eşit mi?
            is_eligible = difference.days <= 30
            
            return str(is_eligible)
            
        except Exception as e:
            return f"Error in {self.name}: {e}"


class IssueRefundTool(Tool):
    def __init__(self):
        super().__init__(
            name="issue_refund",
            description="Issues a refund for an order.",
            parameters={
                "customer_id": {
                    "type": "integer",
                    "description": "The customer's unique ID.",
                },
                "order_id": {
                    "type": "integer",
                    "description": "The unique ID of the order.",
                },
            },
        )

    def execute(self, arguments: str) -> str:
        try:
            args = json.loads(arguments)
            # in reality, this would be stored in some database
            print(
                f"Refund issued for order {args['order_id']} for customer {args['customer_id']}"
            )
            return str(True)
        except Exception as e:
            return f"Error in {self.name}: {e}"


class ShareFeedbackTool(Tool):
    def __init__(self):
        super().__init__(
            name="share_feedback",
            description="Allows a customer to provide feedback about their experience.",
            parameters={
                "customer_id": {
                    "type": "integer",
                    "description": "The customer's unique ID.",
                },
                "feedback": {
                    "type": "string",
                    "description": "The feedback text from the customer.",
                },
            },
        )

    def execute(self, arguments: str) -> str:
        try:
            args = json.loads(arguments)
            # in reality, this would be stored in some database
            print(
                f"Feedback received from customer {args['customer_id']}: {args['feedback']}"
            )
            return "Thank you for your feedback!"
        except Exception as e:
            return f"Error in {self.name}: {e}"


class Agent:
    """
    The base class for an agent that can interact with the OpenAI API.
    """

    def __init__(self, model: str = "openai/gpt-oss-20b"):
        # Yapılandırmayı doğrudan burada yapıyoruz
        self.model = model
        
        # OpenAI istemcisini Agent başlatıldığı an oluşturuyoruz
        self.client = OpenAI(
            base_url=base_url_param,
            api_key="something-doesnt-matter",
        )
        
        self.messages: list[Dict[str, Any]] = []
        self.tools: Dict[str, Tool] = {}

    def register_tool(self, tool: Tool):
        """
        Registers a tool with the agent.
        """
        self.tools[tool.name] = tool

    def _get_tool_schemas(self) -> list[Dict[str, Any]]:
        """
        Returns the list of tool schemas.
        """
        return [tool.get_schema() for tool in self.tools.values()]

    def execute_tool_call(self, tool_call: Any) -> str:
        """
        Executes a tool call and returns the output.
        """
        fn_name = tool_call.name
        fn_args = json.loads(tool_call.arguments)

        if fn_name in self.tools:
            tool_to_call = self.tools[fn_name]
            try:
                print(f"Calling {fn_name} with arguments: {fn_args}")
                # The return value of the function is converted to a string to be compatible with the API.
                return str(tool_to_call.execute(tool_call))
            except Exception as e:
                return f"Error calling {fn_name}: {e}"

        return f"Unknown tool: {fn_name}"

    def run(self):
        """
        Runs the agent. This method should be implemented by subclasses.
        """
        raise NotImplementedError("The run method must be implemented by a subclass.")


class CustomerServiceAgent(Agent):
    """
    A customer service agent that extends the base Agent class.
    """
    
    def __init__(self, model="gpt-4o"):
        super().__init__(model)
        self._set_initial_prompt()
        self._register_all_tools()

    def _set_initial_prompt(self):
        self.messages = [
            {
                "role": "developer",
                "content": """
                    You are a friendly and helpful customer service agent. 
                    You must ALWAYS verify the customer's identity before providing any sensitive information. 
                    You MUST NOT expose any information to unverified customers.
                    You MUST NOT provide any information that is not related to the customer's question.
                    DON'T guess any information - neither customer nor order related (or anything else).
                    If you can't perform a certain customer or order-related task, you must direct the user to a human agent.
                    Ask for confirmation before performing any key actions.
                    If you can't help a customer or if a customer is asking for something that is not related to the customer service, you MUST say "I'm sorry, I can't help with that."
                """
            }
        ]

    def _register_all_tools(self):
        tools_to_register = [
            VerifyCustomerTool(),
            GetOrdersTool(),
            CheckRefundEligibilityTool(),
            IssueRefundTool(),
            ShareFeedbackTool(),
        ]

        for tool in tools_to_register:
            self.register_tool(tool)

    def run(self):
        print("Welcome! How can we help you? (Type 'exit' to end)")
        
        while True:
            user_input = input("Your input: ")
            if user_input.lower() == "exit":
                break

            self.messages.append({"role": "user", "content": user_input})

            for _ in range(5):
                # 'responses.create' ve 'input=' yerine standart olanı kullanıyoruz
                response = self.client.chat.completions.create(
                    model=self.model,
                    messages=self.messages, # 'input' DEĞİL 'messages'
                    tools=self._get_tool_schemas(),
                    
                )

                # Standart OpenAI yanıt yapısını alıyoruz
                assistant_msg = response.choices[0].message
                
                # Mesajı geçmişe ekle (Pydantic nesnesini dict'e çevirerek)
                self.messages.append(assistant_msg.model_dump(exclude_none=True))

                # 1. Eğer model bir metin cevabı verdiyse yazdır
                if assistant_msg.content:
                    print(f"Assistant: {assistant_msg.content}")

                # 2. Eğer Tool Call (Function Call) varsa işle
                if assistant_msg.tool_calls:
                    for tool_call in assistant_msg.tool_calls:
                        fn_name = tool_call.function.name
                        fn_args = tool_call.function.arguments
                        
                        print(f"Sistem: {fn_name} aracı çağrılıyor...")
                        
                        if fn_name in self.tools:
                            tool_output = self.tools[fn_name].execute(fn_args)
                        else:
                            tool_output = f"Error: Tool {fn_name} not found."

                        # Tool sonucunu listeye ekle (Bu format kritiktir!)
                        self.messages.append({
                            "role": "tool",
                            "tool_call_id": tool_call.id,
                            "name": fn_name,
                            "content": str(tool_output),
                        })
                    # Tool call'dan sonra döngü devam eder, model sonucu değerlendirir
                    continue 
                else:
                    # Tool call yoksa bu tur biter, yeni kullanıcı girişi beklenir
                    break

def main():
    agent = CustomerServiceAgent()
    agent.run()

if __name__ == "__main__":
    main()